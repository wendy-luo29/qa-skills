---
name: design-testcases
description: 测试用例设计（合并版）。当需求已拆成原子能力（AC 编号）或有 OpenAPI 接口文档时，设计可追溯、可自动化、带明确断言点和验证 SQL 的测试用例，并输出用例清单与 Excel 文件。支持 AC 追溯、覆盖矩阵、自动化可行性标注、基于数据库约束的规则引擎。不做需求评审、不写自动化脚本。
---

# 测试用例设计专家（design-testcases）

## 何时使用
- 用户要求"设计测试用例 / 写用例 / 根据 AC 生成用例 / 输出用例 Excel / 生成 API 测试用例 / 根据接口文档生成用例"。
- 功能拆分已完成（有 AC 编号），或已提供 OpenAPI/Swagger 文档。

## 上下游
- 上游：`split-requirements`（功能拆分，提供 AC 编号与验收口径）；或直接提供 OpenAPI 文档。来自拆分的输入必须带 `review_record` / `review_gate`，缺失则退回 `split-requirements` 补齐需求评审。
- 下游：`review-testcases`（多视角用例评审）。

## 输入

| 参数 | 必填 | 说明 |
|------|------|------|
| 原子能力清单（AC） | 二选一 | `AC-{编号}` 列表 + 验收口径（来自 split-requirements） |
| OpenAPI 文档 | 二选一 | OpenAPI/Swagger JSON 文件路径 |
| 知识库路径 | 推荐 | 默认 `<项目根>/knowledge/`，用于读取规则、踩坑、影响索引、已有用例 |
| 已有测试用例 | 可选 | Excel 格式（`testcases/*.yaml/.xlsx`），用于对比覆盖缺口和复用 |
| 项目资料 | 可选 | 需求文档、业务逻辑文档 |
| 数据库连接 | 可选 | db_config.json，默认从技能目录读取 |

## 角色
你是一名资深测试工程师兼自动化测试架构师。任务不是堆用例数量，而是设计"少而准、可执行、可自动化"的测试用例。

## 设计原则
1. **可追溯**：每条用例必须关联 `AC-{编号}`，无 AC 时填"未关联"。
2. **可断言**：断言必须具体到字段和值，禁止"验证是否正常"。
3. **可验证**：涉及数据写入的用例必须带验证 SQL；只读接口填 `N/A（只读接口）`。
4. **可自动化**：每条用例标注"是否自动化"和"自动化断言方式"。
5. **不臆造**：拿不准的业务规则标【待确认】，写入 risk 字段。
6. **控规模**：每个 API 用例数建议 ≤ 30，P0 ≤ 5，执行去重裁剪。
7. **尊重历史**：**必须先读知识库**——历史踩坑不能重蹈覆辙、已有用例优先复用、变更影响索引必须对照。

---

## 执行流程

### Step 0：环境准备（uv）

```powershell
# Windows PowerShell
$SkillDir = "d:\ai-test-framework\.claude\skills\design-testcases"
if (!(Get-Command uv -ErrorAction SilentlyContinue)) {
    powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
}
uv sync --project $SkillDir
```

后续脚本统一用 `uv run --project $SkillDir python "$SkillDir\scripts\<脚本>.py"`。

### Step 1：确认输入并创建工作区

```powershell
uv run --project $SkillDir python "$SkillDir\scripts\setup_workspace.py" `
  --api_doc "<API文档路径>" `
  [--testcase "<已有用例Excel>"] `
  [--project_info "<项目资料目录>"] `
  [--business_doc "<业务逻辑文档>"] `
  [--db_info "<db_config.json路径>"]
```

输出工作区路径。若未提供 API 文档（仅有 AC 清单），跳过此步，直接从 Step 4 开始。

### Step 2：确定目标 API

用户指定了目标 API 则直接使用；否则运行 `find_uncovered_apis.py` 对比已有用例找缺口：

```powershell
uv run --project $SkillDir python "$SkillDir\scripts\find_uncovered_apis.py" `
  --api_doc "<工作区>\api_docs\<文件名>" `
  [--testcase "<工作区>\testcase\<文件名>"]
```

输出 `api_list_to_design.json`。

### Step 3：深度解析（OpenAPI + 数据库）

对每个目标 API：

1. **解析 OpenAPI**：提取 `summary`、`description`、`requestBody schema`，递归构建字段树（字段路径、类型、必填、枚举、maxLength/minLength）。
2. **查询数据库表结构**：从 API description/字段注释识别涉及的表，运行 `query_db_schema.py`：

```powershell
uv run --project $SkillDir python "$SkillDir\scripts\query_db_schema.py" `
  --db_config "<工作区>\db_info\db_config.json" `
  --table_keywords "address,suburb"
```

3. **分析 DB 约束**：主键、唯一键、联合唯一、外键、默认值、非空、字段注释中的业务规则。
4. **实测数据事实（涉计费/费率/价卡时强制）**：查询费率表并输出「费率事实表」——分段起点/终点、每段 fee、per_kilogram_fee 归属段、fuel_rate、单位、是否按 zone/承运商/仓库区分。**禁止只依据文档或推测确定分段与费率。**
   - 找不到费率表或字段含义不明 → 登记 M/Q 项，不得静默假设
   - 文档与 DB 冲突 → 以文档为准设计断言，同时把 DB 事实写入边界矩阵备查
5. **映射 API 字段 → DB 字段**：驼峰↔下划线转换、显式声明、注释推断；无法确定标注"映射关系待确认"。
6. **识别隐式模式**：审计字段、乐观锁(version)、软删除(deleted_at/is_deleted)、状态机(status)、多租户、树形结构。

### Step 4：读取知识库（★ 设计前必做，跳过即视为违规）

**在写任何一条用例之前**，先按顺序执行以下读取。找不到知识库时（新项目/无历史），跳过并记录"知识库未建立"。

#### 4.1 读业务规则 — `knowledge/rules/<module>/<feature>.md`
- 从项目根 `knowledge/INDEX.md` 导航到当前模块的规则文档
- 规则文档第一行必须有版本号和 confirmed 日期（如 `v2.1 confirmed by 业务方 2026-11-15`）
- **将规则文档里的 confirmed 规则当作设计用例的"第一依据"**，OpenAPI 文档有歧义时以规则文档为准
- 规则文档里的【待确认】项 → 生成的用例里也必须标【待确认】（risk 字段）

#### 4.2 读历史踩坑 — `knowledge/gotchas/`
- 浏览所有 gotcha 条目，筛选与当前模块/功能相关的（标题或正文含模块关键词）
- **每一条踩坑必须在设计用例时有体现**——要么已有对应用例（复用），要么新增用例覆盖
- 输出时用 `risk` 字段关联踩坑编号：`risk: "踩坑 gotcha_001 已覆盖"`

#### 4.3 读影响索引 — `knowledge/impact-index.yaml`
- 找到当前变更对应的 change 条目（按 `module` + `feature` 匹配）
- 查看 `regression_targets` 列出的 case_id 清单
- **这些 case_id 对应的已有用例是必跑回归的**，标记 `is_regression: "是"`，不重新设计（除非规则已变）
- 查看 `gotchas` 和 `knowledge_docs` 引用的相关文档

#### 4.4 读变更历史 — `knowledge/changelog/`
- 读取当前模块最近 3 条变更记录
- 识别"规则变了"的部分 → 已有用例需要更新；识别"新增功能"的部分 → 需要新增用例

#### 4.5 读已有用例 — `testcases/*.yaml/.xlsx`
- 对比已有用例清单（testcases 目录下的 YAML/Excel）
- 按以下优先级判断每条已有用例的处置：

| 情况 | 处置 | 字段标注 |
|------|------|---------|
| 规则没变、用例仍适用 | **直接复用**，不重新设计 | `is_regression: "是"`，`case_id` 沿用原编号 |
| 规则变了（如 v1.2 → v2.0） | **更新用例**，改 test_data / expected_result / validation_sql | `case_version: "2"`（递增） |
| 接口签名变了（字段增删改） | **废弃旧用例 + 重新设计** | 旧用例在 impact-index 标 `status: superseded` |
| 新功能、历史无覆盖 | **新增用例** | `case_id` 新编号，`case_version: "1"` |

#### 4.6 输出知识库读取摘要（写入工作区）
读取完成后，在工作区生成 `knowledge_context_summary.md`，包含：
```markdown
## 本次设计的知识库上下文

### 已读规则
- knowledge/rules/lsp_backend/address_validation.md (v2.1 confirmed 2026-11-15)

### 相关踩坑（必须覆盖）
- gotcha_001: PO Box 正则大小写不敏感 → 已有 TC-ADDR-024 覆盖（xfail 待解）
- gotcha_002: DB 字段 NOT NULL 但 API 返回空串 → 本次新增用例覆盖

### 影响索引条目（必回归）
- CHG-001: 地址校验 v2.1 全面确认 → 回归 TC-ADDR-003/008/009/022/023/024/029/030/050
- CHG-001d: PO Box 正则 → 回归 TC-ADDR-022/023/024

### 已有用例处置
- 复用：TC-ADDR-001/002/003/004/...（共 28 条）
- 更新：TC-ADDR-008（reason 文案从 "not found" 更新为 "address not found"）
- 废弃：无
- 新增：3 条（覆盖 gotcha_002）
```

**如果跳过了 Step 4（知识库不存在）**，摘要必须写明 `知识库未建立，所有用例为全新设计`。

### Step 5：应用 8 条规则生成用例（内核）

基于 Step 4 读取的知识库上下文，对每个 API 字段树依次应用以下规则。详细方法见 `references/design-methods.md`。

> **规则应用优先级**：知识库 confirmed 规则 > OpenAPI schema > DB 约束 > 通用规则。
> 即：如果 rules/lsp_backend/address_validation.md 里已写死 "state 接受全名和缩写"，
> 不要等 OpenAPI schema 有没有 enum 才决定，直接设计全名+缩写两个用例。

| 规则 | 目标 | 生成方法 |
|------|------|---------|
| 1 顶层必填校验 | `schema.required` 顶层字段 | 每个必填字段移除，期望 400/业务错误 |
| 2 嵌套必填校验 | 嵌套对象/`array.items` 必填字段 | 递归查找，缺失嵌套必填字段 |
| 3 字符串长度校验 | 所有 `type:string` 字段 | 基于实际 maxLength（OpenAPI > DB），测 N-1/N/N+1 |
| 4 枚举值校验 | 带 `enum` 或描述含枚举的字段 | 每个合法值一条正向 + 一条非法值负向 |
| 5 字段类型校验 | 所有字段 | 类型不匹配（整型传字符串等） |
| 6 数值边界校验 | `type:integer/number` 的 schema 约束 + **description / 需求文档中的数值型业务阈值** + **DB 实测分段** | 0/-1/1 + `下界-精度 / 下界 / 上界 / 上界+精度`；业务阈值不得只出一条「超限」用例；费率/价卡分段按「段起点-精度 / 段起点 / 段起点+精度」逐点覆盖（见 Step 5.5） |
| 7 业务规则校验 | **知识库 confirmed 规则 + API description + DB 约束 + 计费公式** | 唯一性、外键、默认值、规则文档业务规则、应用层约束；**计费公式必须拆成「分段 / 取整 / 累加单位 / 取数维度」四类边界**并全部进入 Step 5.5 |
| 8 隐式规则推断 | DB 模式 + RESTful 常识 + 知识库踩坑 | 审计字段、乐观锁、软删除、状态机、批量事务、关联完整性 |

**规则7 是核心**：需结合知识库 confirmed 规则 + 数据库唯一索引、外键、默认值、字段注释生成用例，并区分"数据库层约束"与"应用层约束"。

**规则8 必须读 gotchas**：如果知识库有 gotcha 提到某类隐式模式容易漏（如 PO Box 正则、DB null 问题），这些场景必须作为高优先级用例生成。

### Step 5.5：约束抽取与边界矩阵（强制）

**约束抽取**：设计前先机械列出全部数值约束，写入 `<工作区>/output/constraints.json`：

| 约束来源 | 抽取内容 | category |
|---|---|---|
| OpenAPI schema | `minimum` / `maximum` / `minLength` / `maxLength` / `enum` / `required` | `schema` |
| description 与需求文档 | 正则抽取「>X」「≥X」「≤X」「<X」「超过 X」「最大 N」「最少 N」，记录比较符、阈值、单位 | `threshold` |
| DB 实测费率数据 | 费率/价卡表的分段起点终点、每段 fee、per_kg 归属段、fuel、最小/最大重量 | `segment` / `perkg` |
| 计费公式 | 首重阈值、取整方向/单位/时机、累加单位、按维度取数差异 | `formula` |
| DB 字段约束 | 字段长度、数值精度（如 `decimal(12,3)`）、非空、默认值 | `dbfield` |

每条约束记录：`约束ID / category / 维度 / 比较符 / 阈值 / 精度 / 判定粒度（字段 / 单个包裹 / 合计）/ 来源`。

**公式边界四件套（涉计费接口必做，逐项至少 2 个数据点）**：

| 维度 | 抽取内容 | 缺少时 |
|---|---|---|
| 分段 | 每段起点/终点，出「恰好」与「±一个精度」 | 查 DB 费率表，不猜 |
| 取整 | 取整方向（向上 / 四舍五入 / 截断）、单位（kg）、时机（匹配前 / 后）；出「跨档 0.01」点 | 登记 Q 项并标「待定」 |
| 累加单位 | 每 1kg / 每 0.5kg；出「1 个单位」与「2 个单位」两个点，断言增量恒定 | 登记 Q 项 |
| 取数维度 | 同重量在不同 zone / 承运商 / 仓库下金额是否不同 | 查 DB 对比，至少两维度各一点 |

**边界矩阵**：写入 `<工作区>/output/boundary_matrix.md`，必须包含三节：

1）约束矩阵（每个约束至少 4 个数据点）：

| 约束ID | 约束 | 数据点 | 用例ID | 状态 |
|---|---|---|---|---|
| BC-001 | 三边和 ≤120cm | 119.99 / 120.00 / 120.01 | TC-QTS-036 / 031 / 012 | 已覆盖 |

2）费率事实表（涉计费必填）：承运商 × zone × 段起点 × fee × per_kg × fuel × 实测日期。

3）维度覆盖表（逐类打勾，缺失必须写原因）：

| 类别 | 是否覆盖 | 约束ID / 用例 | 缺失原因 |
|---|---|---|---|
| schema 约束 | | | |
| 文档业务阈值 | | | |
| 价卡/费率分段 | | | |
| 续重/累加单位 | | | |
| 取整/舍入 | | | |
| 取数维度（zone/承运商/仓库） | | | |
| 长度/数量 | | | |

规则：
- 「>120 不可发」等价于「≤120 可发」，属闭区间，必须出 `上界-精度`、`上界`、`上界+精度` 三个点。
- 精度取该字段的写入精度（尺寸/重量 `0.01`，金额 `0.001`），**不得用「上限+10」这类非边界值**。
- 两个阈值存在包含关系（如最长边 120 与三边和 120）时，用一个远小于另一维度的值隔离；隔离不了就在矩阵标「不可独立验证」并登记 Q 项。
- 取整时机、舍入模式、判定粒度未定义时不得自行假设：登记 Q 项，边界点标「待定」。
- 价卡/费率分段点（如 `1.001~3.0`）属于数值约束，段上下界各取「恰好」与「超 0.001」两个点。
- **不得只覆盖文档写出的阈值**：凡需求提到「按重量 / 体积 / 区域计价」，必须同时完成四件套与费率事实表。

**约束覆盖率必须 100%**（每个约束至少 2 个有效数据点），且维度覆盖表无未说明缺失，才能进入 Step 7。

**跳过已有用例（不重新设计）**：如果 Step 4.5 判定某场景已有有效用例，**规则 1-8 应用到该字段时跳过重复生成**，直接引用已有 case_id 并标记 `is_regression: "是"`。

### Step 6：八层覆盖审查 + 去重裁剪

生成后逐条对照八层覆盖检查（见 `references/design-methods.md` 第8节），不适用层写明原因。

然后执行去重裁剪（见 `references/design-methods.md` 第9节）：
- 相同 (api_url, test_item, test_data 摘要) 合并
- 同字段多边界用例合并（仅限 N-1/N/N+1，且 `test_data` 必须列出全部数据点；**业务阈值的边界点不得合并**——箱规、重量、金额分段、费率分段等）
- **一条用例只能有一个期望方向**（通过 / 拒绝）；同一字段的「越界拒绝」与「边界通过」必须拆成两条，不得合并（如尺寸 0 拒绝 vs 0.01 通过）
- 比例只作提示：补用例只能来自约束缺口或维度缺口，**不得为凑正向/负向比例新增用例**
- P0 ≤ 5 条/API，总数 ≤ 30 条/API

### Step 7：输出 JSON 并校验

每条用例写入工作区 `output/cases_batch_<N>.json`，JSON 数组格式。字段定义见下节。

校验：
```powershell
uv run --project $SkillDir python "$SkillDir\scripts\validate_json.py" "<工作区>\output\cases_batch_<N>.json"
```

### Step 8：导出 Excel

```powershell
uv run --project $SkillDir python "$SkillDir\scripts\export_excel.py" `
  --workspace "<工作区路径>" `
  [--ac_list "AC-01,AC-02,AC-03"]
```

输出 `<工作区>/output/api_testcases_<时间戳>.xlsx`，包含 4 个 Sheet：
- **用例明细**（30 列，P0 标红、按 test_type 行染色）
- **覆盖矩阵**（AC → 用例编号 → 状态）
- **待确认清单**（risk 非"无"的用例，按优先级排序）
- **覆盖率统计**（类型分布、优先级分布、AC 覆盖、API 分布）

---

## 用例字段定义（30 列）

完整列定义见 `references/testcase-headers.md`。每条用例必须包含以下核心字段：

```json
{
  "case_id": "TC-ADDR-001",
  "ac": "AC-01",
  "project": "",
  "module": "地址管理",
  "feature": "地址搜索",
  "test_item": "有效关键字模糊搜索",
  "title": "有效关键字搜索返回匹配结果",
  "preconditions": "服务可用，存在测试数据",
  "db_tables": "lsp_dev.lsp_address_suburb",
  "test_data": "{\"keyword\": \"上海\", \"limit\": 20}",
  "steps": "1. 调用 POST /address/search 2. 校验响应",
  "expected_result": "HTTP 200，data.list 非空，包含含'上海'的记录",
  "validation_sql": "SELECT COUNT(*) FROM lsp_address_suburb WHERE suburb_name LIKE '%上海%'",
  "actual_result": "",
  "is_passed": "",
  "estimated_hours": "0.5",
  "execute_date": "",
  "test_progress": "",
  "case_type": "API测试",
  "priority": "P0",
  "is_regression": "是",
  "is_blocker": "否",
  "requirement_id": "REQ-001",
  "api_url": "POST /address/search",
  "bug_count": "0",
  "bug_unresolved": "0",
  "case_version": "1",
  "automatable": "是",
  "assertion_method": "接口返回+数据库字段",
  "risk": "无"
}
```

> `test_type`（正向/负向/边界/安全/权限）为内部字段，控制行颜色，**不导出为列**。`case_type` 固定填 `API测试`。

## 用例编号规则
- 格式：`TC-{模块缩写}-{三位序号}`，模块缩写 3~6 位大写字母，如 `TC-ADDR-001`。
- 编号一旦分配不复用，删除的用例编号置空不回收。
- 与脚本对应关系：脚本首行注释 `# case_id: TC-ADDR-001`。

## 断言设计规范
断言必须具体到字段和值：
- 响应 `status=200`、`data.success=true`、`data.orderId` 非空且格式符合约定
- 数据库 `order.status` 更新为 `CREATED`（用验证 SQL）
- 下游事件表产生一条 `ADDRESS_VALIDATED` 事件

禁止："验证返回成功"、"验证功能是否正常"。

## 优先级与自动化标注
- 优先级判定见 `references/testcase-headers.md`（P0 冒烟/P1 核心/P2 增强/P3 边缘）。
- 自动化可行性：是/否/部分，断言方式：接口返回/数据库字段/日志/事件/页面元素。

## 门禁
- **评审溯源门禁**：AC 清单缺少 `review_record` / `review_gate`，或门禁值为 `reject` → 不得设计或导出用例，退回 `split-requirements` / `review-requirements`。
- **知识库门禁**：如果 `knowledge/INDEX.md` 存在，Step 4 必须执行且输出摘要；直接跳到 Step 5-8 视为违规。
- **复用门禁**：已有用例未做 Step 4.5 处置（复用/更新/废弃/新增）就直接输出 → 退回补做。
- **影响索引门禁**：`impact-index.yaml` 里标记的 `regression_targets` 必须出现在最终清单里（复用或更新都行，不能消失）。
- **边界矩阵门禁**：`output/boundary_matrix.md` 未生成，或任一约束的有效数据点 < 2，或存在「上限+10」类占位值 → 不得导出。约束覆盖率 100% 是硬要求（因文档缺失登记了 Q/M 的约束可标「待定」，但必须在矩阵中显式列出，不得静默跳过），用例类型百分比（正向/负向/边界/安全）只作提示，不作门禁。
- **费率事实门禁**：需求涉及计费 / 费率 / 价卡，但矩阵中未输出「费率事实表」→ 不得导出。
- **维度覆盖门禁**：维度覆盖表缺少「分段 / 续重或累加单位 / 取整 / 取数维度」任一类且未写明缺失原因 → 不得导出。
- **类型纯度门禁**：单条用例同时包含正向与负向断言（如「0 拒绝、0.01 通过」写在一条）→ 退回拆分。
- 高优先级待确认项未闭环 → 不进入 `review-testcases`。
- 每个 AC 至少有一条用例，且覆盖矩阵无未说明的空缺 → 进入 `review-testcases`。
- P0/P1 用例必须 `automatable=是`。

## 输出禁忌
- 禁止未读知识库就开始设计（知识库存在时）。
- 禁止输出"验证功能是否正常"这类无效用例。
- 禁止一条用例覆盖多个无关原子能力。
- 禁止不写断言点、不标优先级、不标自动化可行性、不写验证 SQL（只读接口除外）。
- 禁止把异常场景笼统合并成一条"测试异常情况"。
- 禁止使用未关联 AC 的用例编号。
- 禁止已有用例可复用时重新设计（导致 testcases/ 目录膨胀）。
- 禁止 Step 4 生成的 `knowledge_context_summary.md` 被忽略——必须写入工作区。

---

## 参考文档

### 本 Skill 参考
- `references/design-methods.md` — 等价类、边界值、结对、场景法、八层覆盖、去重裁剪
- `references/testcase-headers.md` — 30 列标准表头、优先级标准、自动化判定、验证 SQL 规范
- `scripts/query_db_schema.py` — 数据库表结构查询

### 知识库参考（★ Step 4 必读）
- `<项目根>/knowledge/INDEX.md` — 知识库入口，按模块→承运商→版本导航
- `<项目根>/knowledge/impact-index.yaml` — 测试影响索引（机读），变更单元 → 回归目标用例
- `<项目根>/knowledge/rules/<module>/<feature>.md` — 业务规则 confirmed 文档
- `<项目根>/knowledge/gotchas/gotcha_NNN_<主题>.md` — 历史踩坑，标题里的 NNN 是编号
- `<项目根>/knowledge/changelog/YYYY-MM-DD_<变更描述>.md` — 变更历史
- `<项目根>/testcases/*.yaml/.xlsx` — 已有用例，Step 4.5 对比处置
