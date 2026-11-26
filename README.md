# qa-skills

AI 测试流程技能库，供各项目通过 git submodule 复用的公共资产。

## 技能清单

| 技能 | 职责 |
| --- | --- |
| `test-workflow` | 全流程编排与门禁 |
| `requirement-enrichment` | 需求补全，输出纯净接口文档 + 补充清单 |
| `review-requirements` | 需求评审，唯一可写知识库规则的环节 |
| `split-requirements` | 需求拆解为 AC 清单 + 影响索引 |
| `design-testcases` | 用例设计（含模板、Excel 导出、边界矩阵） |
| `review-testcases` | 用例评审 |
| `test-script` | pytest 脚本生成 |
| `code-review` | 脚本评审门禁 |
| `run-tests` | 执行与失败归因 |
| `test-report` | 报告生成、Excel 导出、飞书推送 |
| `bug-analysis` | 缺陷单生成（Markdown + Excel） |
| `manual-order-quote-flow` | 手工单创建 / 审核 / 拦截 / 出库报价校验（项目专属，需业务配置） |

## 接入方式

在项目仓中作为 submodule 挂载到技能目录：

```powershell
git submodule add <本仓地址> .claude/skills
git submodule update --init --recursive
```

更新到指定版本：

```powershell
git -C .claude/skills fetch --tags
git -C .claude/skills checkout v1.0.0
git add .claude/skills
```

## 约定

1. 技能不写死宿主项目的绝对路径，统一以「项目根目录 + 相对路径」表达。
2. 技能产物写到项目侧目录，不写回技能目录。
3. `manual-order-quote-flow` 含业务参数，接入前需替换为项目自己的配置。
4. 业务常量集中在 `design-testcases/references/case-template.md` 与 `manual-order-quote-flow/SKILL.md` 的示例段，接入新项目时按项目实际值替换，禁止把新业务常量写进技能正文。
5. 版本遵循语义化版本，变更记录见 `CHANGELOG.md`。

## 目录结构

```text
<skill>/
├── SKILL.md            # 技能定义与执行流程
├── references/         # 参考规范、模板
└── scripts/            # 可执行脚本
```
