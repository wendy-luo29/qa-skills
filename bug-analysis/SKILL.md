---
name: bug-analysis
description: 缺陷分析与缺陷单生成。当用户说"分析这个 bug / 这条用例为什么失败 / 提个缺陷单 / 写 bug 单 / 定位根因 / 这个报错是什么问题"时使用。把失败现象整理成可复现、可追溯的缺陷记录，包含描述、环境、接口地址、请求参数、返回结果、关联用例与 AC、根因分析和修复建议；不负责修改产品代码。
---

# 缺陷分析（bug-analysis）

## 何时使用
- `run-tests` / `test-report` 中出现 FAIL，需要判断是不是真缺陷。
- 需要向开发/产品提交一份结构完整、可直接复现的缺陷单。
- 需要把"接口报错了"这类模糊描述，整理成有证据链的根因分析。

不适用：执行用例 → `run-tests`；汇总报告 → `test-report`；修测试脚本 → `test-script`。

## 上下游
- 上游：`run-tests`（失败结果、日志）、`test-report`（失败明细）。
- 下游：缺陷平台、开发修复、回归验证。

## 输入
- 失败用例的 `case_id` 与 traceback。
- 实际请求与响应（headers、body、状态码、request-id）。
- 用例清单 `testcases/REQ-xxx-TC-list.yaml` 中的标题、AC、优先级。
- 需求/评审文档中的预期规则（引用原文，不用自己的理解代替）。
- 环境信息：`api_base_url`、分支、commit、部署版本。

## 分析流程

### 1. 先复现，再下结论
- 单条复跑：`python -m pytest "tests/api/test_xxx.py::test_yyy" -q`。
- 连跑 2~3 次判断是否偶现；偶现要记录频率，不能直接定性为稳定缺陷。
- 最小化输入：逐个去掉无关字段，确认触发条件。
- 无法复现时，输出"未能复现"及已尝试条件，不要编造根因。

### 2. 采集证据（缺项必须标注"未获取"）
请求方法、完整 URL、query/body、关键 headers（脱敏）、HTTP 状态码、响应体、耗时、日志行、request-id、数据库落库结果（如已配置）。

### 3. 归因分类

| 类型 | 判定依据 | 结论 |
|---|---|---|
| A 环境问题 | 超时、DNS、服务未部署、证书、网络不通 | 不是缺陷，修环境 |
| B 数据问题 | 前置数据缺失、脏数据、账号失效 | 修数据/fixture，不是产品缺陷 |
| C 脚本缺陷 | 参数拼错、断言写错、等待不足、定位失效 | 转 `test-script` 修复 |
| D 预期不一致 | 实现与文档冲突，但实现可能合理 | 先找产品确认，暂不定性 |
| E 真实缺陷 | 可稳定复现，违反已确认的 AC | 提交缺陷单 |

判 E 的前提：预期来自已确认的 AC 或需求原文，且能给出证据链。

### 4. 根因分析（不能停在"后端问题"）
按"现象 → 直接原因 → 根本原因 → 证据"四层写：

```markdown
- 现象：空 address 返回 200 且 success=true
- 直接原因：地址校验接口未对 address 做非空判断
- 根本原因：空值校验分支在 v2.1 重构时遗漏，需求 AC-02 要求拦截
- 证据：响应体 data.success=true（见附件 response.json）；
        日志无 validation 分支记录（logs/api-20261117.log:120）
- 待确认：错误码应返回 400 还是业务码 4001，需产品确认
```

证据不足时写"疑似"，并列出还需谁提供什么信息。

### 5. 影响面评估
- 同类入参是否都受影响（空串、null、缺失、超长）。
- 是否影响其他复用该规则的接口。
- 是否影响已有 AC、是否造成数据错误。
- 是否偶现、是否与数据量/并发相关。

### 6. 定级

| 严重度 | 定义 |
|---|---|
| S1 致命 | 核心流程不可用、数据错误、安全漏洞 |
| S2 严重 | 主要功能异常，有可绕过方案 |
| S3 一般 | 边界/异常场景不符合预期 |
| S4 轻微 | 文案、提示、非功能性问题 |

优先级 P0~P3 由严重度 + 影响用户量决定，P0 必须当天响应。

## 缺陷单模板（字段不可缺）

```markdown
# [BUG-{需求号}-{序号}] {一句话描述：什么场景下什么不符合预期}

| 字段 | 内容 |
|---|---|
| 缺陷编号 | BUG-REQ001-001 |
| 状态 | 新建 |
| 严重度 / 优先级 | S2 / P1 |
| 发现版本 | commit {sha} / 分支 {branch} |
| 提交人 / 时间 | {name} / {yyyy-MM-dd HH:mm} |
| 关联需求 | REQ-001 |

## 1. 环境
- 环境：{测试/预发/生产}
- Base URL：http://192.168.1.71:13109
- 部署版本：{version}
- 操作系统 / Python：{可选}

## 2. 地址
- 方法：POST
- 路径：/address/validate
- 完整 URL：http://192.168.1.71:13109/address/validate

## 3. 请求传参
```json
{
  "address": "",
  "country": "Australia",
  "order_id": "ORD-ADDR-0002",
  "postcode": "3000",
  "state": "VIC",
  "suburb": "Melbourne"
}
```
- Headers：Content-Type: application/json（其余无关 header 已省略）
- 复现命令：`python -m pytest "tests/api/test_address_validate.py::test_null_or_empty_key_fields" -q`

## 4. 返回结果
- HTTP 状态：200
- 耗时：0.42s
- 响应体：
```json
{"code": 200, "msg": "success", "data": {"success": true}}
```
- request-id：{如有}
- 日志：logs/api-20261117.log:120

## 5. 预期结果
- 引用 AC：AC-02 空地址被拦截
- 需求原文：address 为空时应拒绝请求并返回错误原因
- 实际 vs 预期：预期 400 / success=false，实际 200 / success=true

## 6. 关联用例
| case_id | 用例标题 | AC | 优先级 | 来源 |
|---|---|---|---|---|
| TC-ADDR-002 | 空地址拦截 | AC-02 | P0 | testcases/REQ-001-TC-list.yaml |

## 7. 附件
- 响应原文：reports/attachments/BUG-REQ001-001-response.json
- 失败报告：reports/report.html#TC-ADDR-002
- 截图 / 日志：{路径}

## 8. 原因分析
{按"现象 → 直接原因 → 根本原因 → 证据"填写，见第 4 步}

## 9. 影响范围
- 受影响入参：address 为空字符串
- 是否偶现：稳定复现（3/3）
- 关联功能：地址校验、下单地址保存

## 10. 修复建议 / 验证建议
- 建议：补空值校验分支，错误码按产品定义返回
- 回归范围：AC-02 相关的 TC-ADDR-002/003/005
```

## 输出要求（Markdown + Excel，缺一不可）

同一份缺陷记录必须同时产出两种文件：

- Markdown 缺陷单：`reports/bugs/BUG-{需求号}-{序号}.md`
- Excel 缺陷表：`reports/bugs/BUG-{需求号}-{序号}.xlsx`

Excel 结构：Sheet1「缺陷明细」一行一个缺陷，列固定为
`缺陷编号 | 缺陷标题 | 严重程度 | 优先级 | 接口地址 | 请求方法 | 路径 | 请求传参 | 响应结果 | 返回结果 | 预期结果 | 原因分析 | 影响范围 | 修复建议 | 发现版本 | 关联用例 | 关联需求 | 提交人 | 提交时间`；
字体统一为微软雅黑 11 号，表头加粗、淡蓝色底色（D9E1F2），首行冻结。
Sheet2「关联用例」列为 `case_id | 用例标题 | AC | 优先级 | 来源`，字体样式与 Sheet1 一致。
其中「接口地址」是 Base URL + 路径的完整地址，「响应结果」为 HTTP 状态，「返回结果」为响应体。

### 生成方式（必须用脚本，禁止手写两种文档）

先把缺陷写成 `reports/bugs/BUG-REQ001-001.yaml`，再执行：

```bash
python .claude/skills/bug-analysis/scripts/generate_bug_docs.py reports/bugs/BUG-REQ001-001.yaml
```

完成标志：终端出现两行输出

```
已生成缺陷单：.../BUG-REQ001-001.md
已生成缺陷表：.../BUG-REQ001-001.xlsx
```

只写了 YAML、只输出了 Markdown 正文、或手写了 Excel，都视为未完成。脚本会校验必填字段并同时生成同名 `.md` 与 `.xlsx`。

**同一需求的缺陷合并输出一份文档**（推送飞书「缺陷明细」时用这种形态，一个需求一个文件，避免列出多个单缺陷链接）：

```bash
python .claude/skills/bug-analysis/scripts/generate_bug_docs.py testcases/REQ-002-quote_price/bugs -o reports/bugs --merge
```

- 输入可以是目录（取其中全部 YAML/JSON，按文件名排序）或多个文件。
- 按需求号分组（从 `requirement` 字段提取，如 `REQ-002`），每个需求输出一份
  `{需求号}-defects.md`（缺陷一览表 + 逐条完整缺陷单）和 `{需求号}-defects.xlsx`
  （Sheet1「缺陷明细」一行一个缺陷；Sheet2「关联用例」前置「缺陷编号」列，跨缺陷合并）。
- 逐条缺陷的 YAML 仍是源文件，保留在 bugs 源目录；reports/bugs 只放按需求合并后的交付文件。
- 完成标志：`已生成缺陷汇总（N 条）：.../{需求号}-defects.md` 与对应 xlsx 两行输出。

YAML 结构：

```yaml
bug_id: BUG-REQ001-001
title: 空地址未拦截，返回 success=true
status: 新建
severity: S2
priority: P1
requirement: REQ-001
discovered_version: "commit f5ce1ec / master"
reporter: 张三
reported_at: "2026-11-17 15:30"
reproduce_command: 'python -m pytest "tests/api/test_address_validate.py::test_null_or_empty_key_fields" -q'
environment:
  name: 测试
  base_url: "http://192.168.1.71:13109"
  deploy_version: "v2.1.0"
api:
  method: POST
  path: /address/validate
request:
  headers: {Content-Type: application/json}
  body: {"address": "", "country": "Australia", "order_id": "ORD-ADDR-0002"}
response:
  status: 200
  elapsed: "0.42s"
  body: {"code": 200, "msg": "success", "data": {"success": true}}
  request_id: ""
  log: "logs/api-20261117.log:120"
expected:
  ac: AC-02
  rule: address 为空时应拒绝请求并返回错误原因
  actual_vs_expected: 预期 400 / success=false，实际 200 / success=true
related_cases:
  - case_id: TC-ADDR-002
    title: 空地址拦截
    ac: AC-02
    priority: P0
    source: testcases/REQ-001-TC-list.yaml
attachments:
  - reports/report.html#TC-ADDR-002
analysis:
  phenomenon: 空 address 返回 200 且 success=true
  direct_cause: 地址校验接口未对 address 做非空判断
  root_cause: 空值校验分支在 v2.1 重构时遗漏，违反 AC-02
  evidence: 响应体 data.success=true；日志无 validation 分支记录
  pending: 错误码应为 400 还是业务码 4001，需产品确认
impact:
  scope: address 为空字符串的请求
  frequency: 稳定复现 3/3
  related: 地址校验、下单地址保存
suggestion:
  fix: 补空值校验分支，错误码按产品定义返回
  regression: AC-02 相关 TC-ADDR-002/003/005
```

## 提交要求
- 群内通知只发标题、严重度、关联用例、复现命令，正文放缺陷单链接。
- 提交前逐项核对：环境、地址、请求、返回、预期引用、关联用例、根因、证据，缺一项不提交。

## 门禁
- Markdown 与 Excel 两份文件都已生成，且缺陷编号、结果、根因一致。
- 复现步骤可被他人独立执行成功。
- 预期结果有 AC 或需求原文引用，不是个人推断。
- 每个结论有证据对应；证据缺失时标注"待确认"。
- 归因已排除 A/B/C 三类，才允许提交为产品缺陷。
- 敏感信息已脱敏（密码、token、cookie、webhook、个人信息）。

## 输出禁忌
- 禁止只写"接口报错""后端问题"这类无信息量结论。
- 禁止把脚本缺陷、数据问题包装成产品 bug。
- 禁止省略请求参数或响应体，只贴 traceback。
- 禁止编造 request-id、日志行号、版本号。
- 禁止在缺陷单中暴露凭证或完整个人隐私数据。
