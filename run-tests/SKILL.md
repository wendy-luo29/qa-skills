---
name: run-tests
description: 执行测试脚本并分析结果。当用户说"跑一下测试 / 执行用例 / 跑 smoke / 回归测试 / 为什么失败了 / 生成测试报告"时使用。负责确定执行范围、运行 pytest、失败归因和出具报告；不负责生成或修改脚本（走 test-script），也不负责代码评审（走 code-review）。
---

# 测试执行与结果分析（run-tests）

## 何时使用
- 脚本已生成或修改，需要实际运行验证。
- 需要按范围执行：smoke、某模块、单文件、单用例、全量回归。
- 用例执行失败，需要定位是环境、数据、脚本还是真实缺陷。
- 需要输出一份可交付的执行报告。

不适用：写脚本 → `test-script`；评审脚本 → `code-review`；设计用例 → `design-testcases`。

## 上下游
- 上游：`test-script`（脚本就绪）、`code-review`（评审通过）。
- 下游：缺陷单、测试报告、发布门禁结论。

## 输入
- 执行范围：`smoke` / 模块 / 文件 / 单用例 / 全量。
- 运行环境：由 `config/env.yaml` 决定（`api_base_url`、`ui_base_url`）。
- 是否允许修改脚本：默认不允许，只报告；需要修时转 `test-script`。
- 是否需要落盘报告：默认输出到 `reports/`。

## 执行流程

### 1. 预检（不通过就不要盲目开跑）
- `python -m pytest --version` 可执行，依赖已安装。
- `config/env.yaml` 中目标环境的 `api_base_url` / `ui_base_url` 非空；为空会跑本地 demo server，地址校验等接口用例会被 skip。
- 目标地址可连通（超时、DNS、端口不通属于环境问题，不是用例失败）。
- 记录环境标识（URL、分支、commit），写进报告，否则结果无法复现。

### 2. 确认执行范围

| 场景 | 命令 |
|---|---|
| 冒烟 | `python -m pytest -m smoke -q` |
| API 全量 | `python -m pytest tests/api -q` |
| UI 全量 | `python -m pytest tests/ui -q` |
| 单文件 | `python -m pytest tests/api/test_address_validate.py -q` |
| 单用例 | `python -m pytest "tests/api/test_address_validate.py::test_validate_valid_address" -q` |
| 按关键字 | `python -m pytest -k "address and valid" -q` |
| 只跑上次失败 | `python -m pytest --lf -q` |
| 全量回归 | `python -m pytest tests -q -ra --junitxml=reports/junit.xml` |

约定：统一用 `python -m pytest`，避免多环境 PATH 差异；不加 `-x` 除非用户明确要求"失败即停"，否则一次跑完才能看到全貌。

### 3. 执行注意事项
- **skip 不等于通过**：`api_base_url` 为空或 `CI` 变量存在时，接口用例会整体 skip，报告里必须单列跳过数量和原因。
- 失败不要立刻重跑。先读 traceback 和请求/响应证据，再决定是否复跑单条验证稳定性。
- 连续两次结果不一致 → 标记为 flaky，归类到"稳定性问题"，不能靠重跑掩盖。
- 执行过程中不改用例、不改断言、不调超时来"跑绿"；需要改脚本时停下，转 `test-script` 并说明原因。

### 4. 失败归因（必须落到一类）

| 类型 | 判定依据 | 处理 |
|---|---|---|
| A 环境问题 | 连接超时 / DNS / 服务未启动 / 证书 | 修环境，不计为缺陷 |
| B 数据问题 | 前置数据缺失、脏数据、账号失效 | 修 fixture 或数据，转 `test-script` |
| C 脚本缺陷 | 定位失效、等待不足、断言写错、参数拼错 | 转 `test-script` 修复，不判为产品 bug |
| D 需求/预期不一致 | 实现与文档冲突，但行为可能合理 | 记录证据，交需求方确认 |
| E 真实缺陷 | 可稳定复现，实现违反已确认的 AC | 出缺陷单，附请求/响应/日志 |

证据最少包含：`case_id`、实际请求、实际响应（或截图）、断言差异、日志路径。

### 5. 报告发送（飞书群机器人）
执行完成后先生成 junit，再推送摘要：

```bash
python -m pytest tests -q --junitxml=reports/junit.xml \
  --html=reports/report.html --self-contained-html
python scripts/send_report.py
```

- 本步骤只负责群摘要；需要用例明细、失败证据、AC 覆盖率时转 `test-report` 生成完整报告。
- webhook 只从环境变量 `FEISHU_WEBHOOK` 读取，禁止写入仓库或报告。
- 有在线报告时用 `REPORT_URL` 或 `--report-url` 附带链接（CI artifact / Pages）。
- 无 webhook 时先 `--dry-run` 预览文案，不得声称"已发送"。

## 输出结构

```
## 执行概要
- 环境：{env}｜分支：{branch}｜commit：{sha}｜时间：{yyyy-MM-dd HH:mm}
- 范围：{marker / 路径}
- 结果：通过 {n}｜失败 {n}｜跳过 {n}｜错误 {n}｜耗时 {t}s
- 有效执行率：(passed + failed) / total，skip 不计入通过

## 失败明细
| case_id | 用例 | 断言/报错摘要 | 归因类型 | 证据 | 建议动作 |

## 跳过明细
| case_id | 跳过原因 |

## 结论
- 通过 / 有条件通过（仅环境类失败）/ 阻断
- 下一步：{转 test-script / 提缺陷 / 修环境 / 可发布}
```

## 门禁
- 通过：无 failed / error，且不存在"全部 skip"的假通过。
- 有条件通过：仅 A 类环境失败，且已在报告中标注。
- 阻断：存在 C/D/E 类失败，或有效执行率为 0。
- 报告必须能回答三件事：跑了什么、失败属于谁、下一步做什么。

## 输出禁忌
- 禁止把 "全部 skip" 汇报成 "全部通过"。
- 禁止为跑绿而删用例、改断言、放宽超时或 mock 掉失败点。
- 禁止只贴 traceback 不给归因和证据。
- 禁止在未确认的情况下直接把失败定性为"产品 bug"。
- 禁止跳过预检直接执行并污染报告的环境信息。
