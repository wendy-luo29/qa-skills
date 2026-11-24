# 单条测试用例卡片模板（case card）

> 用途：`design-testcases` 生成用例时，`title / preconditions / test_data / steps / expected_result / validation_sql`
> 六个字段一律按本模板书写。目标：**不读脚本、不读代码，也能看懂这条用例在测什么、怎么做、看什么**。
> 生成前必读；Step 7 自检门禁逐条校验。

---

## 一、卡片结构总览

| 字段 | 强制结构 | 硬性要求 |
|---|---|---|
| title | 三段式 | `{业务对象} {条件} {动作} → {可观测结果}` |
| preconditions | 四分区 | 【环境】【主数据】【夹具】【认证】，每项写具体值 |
| test_data | 三列表 | `字段路径 \| 取值 \| 依据`，参数化组合逐条列全 |
| steps | 编号步骤 | 每步「动作 + 观察点」，最多 6 步 |
| expected_result | 四分区 | 【HTTP】【包装层】【业务断言】【落库断言】，一条断言一行 |
| validation_sql | 可执行 SQL | 完整、带 WHERE、注释目的、参数占位 |

Excel 单元格内用换行分段（JSON 里写 `\n`），不要用分号堆成一句话。

---

## 二、标题：三段式

```
{业务对象} {条件} {动作} → {可观测结果}
```

- **业务对象**：具体到承运商 / 字段 / 能力（PRO、三边和、carrierStrategyCode），不写"接口""功能"。
- **条件**：关键入参值（重量、尺寸、编码、缺失哪个字段）。
- **动作**：做了什么（提交报价、移除必填项、重复提交）。
- **可观测结果**：具体金额、`code`、行数、落库 `status`。

| ✗ 反例 | ✓ 正例 |
|---|---|
| 验证计费功能正常 | PRO 承运商 MEL→SYD 1.15kg 单包裹 → 返回 19.96 且落库 status=200 |
| 验证必填校验 | 移除 ownerId 提交报价 → code='500' 且不落任务行 |
| 测试箱规边界 | 三边和恰 120cm 且称重恰 22kg → canShipping=true 且金额按 22kg 段现算 |

**禁止**："验证 XX 正常 / 成功 / 正确"，也不允许把多个场景塞进一个标题。

---

## 三、前置条件：四分区（必须写具体值）

```
【环境】<服务地址 / 依赖中间件 / 数据库连通性>
【主数据】<仓库、承运商、策略、价卡、zone 等实际值及定位方式>
【夹具】<本用例专用的唯一数据，如 requestId / orderCode 规则>
【认证】<鉴权方式；不鉴权写"无（接口不经网关，不校验 Authorization）">
```

| ✗ 反例 | ✓ 正例 |
|---|---|
| 服务可用，存在测试数据 | 【环境】lsp_quote 服务可用；SCP 库可写（autocommit=True）<br>【主数据】warehouse=BG03（VIC 3012，from_zone=MEL）；shipTo=2000（lsp_carrier_zone 实查→SYD）；PRO=CAR2025062611067266788（fuel=0.2861）<br>【夹具】requestId / orderCode 每次生成唯一值，orderCode 以 TESTSO 开头便于清理<br>【认证】无（接口不经网关，不校验 Authorization） |

规则：
- 不能写"存在测试数据""环境正常"这类无法复现的描述。
- 主数据必须给出**可实查的 ID 或编码**，并注明定位方式（如"lsp_carrier_rate 实查"）。
- 夹具必须能隔离本条用例（唯一 requestId / orderCode），否则无法断言落库。

---

## 四、测试数据：三列表

```
字段路径 | 取值 | 依据
--- | --- | ---
carrierStrategyCode | VIR|CAR2025062611067266788|CAR1772558358570467341 | 接口只认策略编码，VIR 后按 ID 指定
shipTo.postcode | 2000 | lsp_carrier_zone 实查 → SYD
warehouse[0].packages[0].weight | 1.15 | 向上取整 2kg，落 1.001~3 段
```

规则：
- **字段路径写全**（`warehouse[0].packages[0].weight`），不要写"重量"。
- **依据写来源**：OpenAPI 约束 / 需求条款 / DB 实查 / 上一轮实测值。
- 参数化组合（一个用例含多个实例）必须**逐条列全**，用 `实例1：` 前缀分行，不能写"等"。
- 不出现"正常值""随便传"这类找不到依据的取值。

---

## 五、测试步骤：编号 + 动作 + 观察点

```
1. 构造 payload：<改了什么>；观察 <构造结果是否唯一/合法>
2. POST /quote/price_sync；观察 HTTP 状态码与响应体
3. 断言 L1/L2：<HTTP + 包装层>；观察 code / success / data
4. 断言 L3：<业务字段>；观察金额、行数、isBest
5. 执行验证 SQL；观察 <表名与关键字段>
```

规则：
- 最多 6 步；一步只做一件事，动作开头用动词。
- 每步必须有**可观察对象**，禁止"检查结果是否正确"。
- 不要写"运行 pytest 脚本"——用例要能脱离脚本手工执行。

---

## 六、预期结果：四分区断言

```
【HTTP】status == 200
【包装层】code == "200"；success == true；data 非空（响应不含 requestId/orderCode）
【业务断言】bookingCarrierId == CAR2025062611067266788；shippingCost == 19.96（=round(fee×(1+fuel),3)，fee=15.52、fuel=0.2861）
【业务断言】isBest=1 的行恰 1 条，且金额为该承运商最低
【落库断言】lsp_quote_task：status == 200；predict_price == 19.96；order_code 前缀 == TESTSO...
【落库断言】lsp_quote_task_address 行数 == 2（type=100/200）
```

规则：
- 一条断言一行，格式固定为 `对象/字段 运算符 期望值`。
- 金额断言必须写出**计算式与取数依据**（哪个段、fee、fuel），不能只写"金额正确"。
- 失败用例写清四要素：`code='500'`、`msg` 非空、`data == null`、`success == false`。
- 落库断言必须写明表名 + 字段 + 期望值；只读接口写"无落库断言"。
- 断言与缺陷相关的，写"设计期望 → 当前实测（缺陷编号）"，两者不要混为一谈。

---

## 七、验证 SQL：可直接执行

要求：
1. 只读，仅 `SELECT`；禁止 `SELECT *` 且无 `WHERE`。
2. 必须带 `WHERE`，用唯一键（request_id / order_code 前缀）定位本条数据。
3. 每条 SQL 上方一行注释写目的：`-- 校验任务成功落库且金额一致`。
4. 参数用 `%(name)s` 占位，并在注释里列出参数来源。
5. 多段 SQL 用 `-- ----` 分隔，每段都能独立执行。
6. 只读接口或纯行为断言：填 `N/A（只读接口）` 或 `N/A（无落库，仅行为断言）`。

```sql
-- 参数：%(request_id)s 来自请求体
-- 校验任务落库且金额一致
SELECT id, status, predict_price, predict_carrier_code, predict_calc_mode
FROM lsp_quote_task
WHERE request_id = %(request_id)s;

-- ---- 校验地址快照恰 2 行（100=发件 / 200=收件）
SELECT type, country, state, postcode
FROM lsp_quote_task_address a
JOIN lsp_quote_task t ON t.id = a.quote_task_id
WHERE t.request_id = %(request_id)s
ORDER BY a.type;
```

---

## 八、完整卡片示例（JSON 字段映射）

```json
{
  "case_id": "TC-QPS-001",
  "title": "PRO+Aramex 双承运商 1.15kg 单包裹 → 返回 2 行报价，PRO 19.96 现算一致并成功落库",
  "preconditions": "【环境】lsp_quote 服务可用；SCP 库可写（autocommit=True）\n【主数据】warehouse=BG03（VIC 3012，from_zone=MEL）；shipTo=2000（lsp_carrier_zone 实查→SYD）；PRO=CAR2025062611067266788（fuel=0.2861）；Aramex=CAR1772558358570467341\n【夹具】requestId=SAC+时间戳、orderCode=TESTSO+时间戳，每次请求唯一\n【认证】无（接口不经网关，不校验 Authorization）",
  "test_data": "字段路径 | 取值 | 依据\n--- | --- | ---\ncarrierStrategyCode | VIR|CAR2025062611067266788|CAR1772558358570467341 | §5 策略编码，VIR 后按承运商 ID 指定\nshipTo.postcode | 2000 | lsp_carrier_zone 实查→SYD\nwarehouse[0].warehouseCode | BG03 | 主数据仓库\nwarehouse[0].packages[0] | 60.5×30×15cm / 1.15kg | 向上取整 2kg，落 1.001~3 段\nwarehouse[0].packages[0].items[0] | 单 SKU，qty=1 | AC-15 包裹层优先\nisPushWms | 200 | V1.6：200=不推送\npushResultTo | 0 | 合法枚举 {0,301,200,300}\nclosePoboxCheck | 200 | 合法枚举 {100,200}",
  "steps": "1. 构造 payload：carrierStrategyCode 指定 PRO+Aramex，1 包裹 1.15kg；观察 requestId/orderCode 唯一\n2. POST /quote/price_sync；观察 HTTP 状态码与响应体\n3. 断言包装层：code='200'、success=true、data 非空\n4. 断言业务：2 行报价、PRO=19.96、isBest 恰 1 行且为 Aramex\n5. 执行验证 SQL；观察任务行、地址行、包裹/SKU 行、job_log 计数",
  "expected_result": "【HTTP】status == 200\n【包装层】code == \"200\"；success == true；data 非空（响应不含 requestId/orderCode）\n【业务断言】每承运商恰 1 行；PRO 行 shippingCost == 19.96（=round(15.52×(1+0.2861),3)）\n【业务断言】Aramex 行 shippingCost == 5.724；isBest=1 恰 1 行且为最低价行\n【落库断言】lsp_quote_task：request_id == 入参；order_code 前缀 == 入参 orderCode；status == 200；predict_price == 19.96\n【落库断言】lsp_quote_task_address 行数 == 2（type=100/200）；package == 1；sku == 1；job_log >= 1",
  "validation_sql": "-- 参数：%(request_id)s / %(order_code)s 来自请求体\n-- 校验任务落库且金额一致\nSELECT id, status, predict_price, predict_carrier_code, predict_calc_mode\nFROM lsp_quote_task\nWHERE request_id = %(request_id)s AND LEFT(order_code, CHAR_LENGTH(%(order_code)s)) = %(order_code)s;\n\n-- ---- 校验地址快照恰 2 行\nSELECT type, country, state, postcode\nFROM lsp_quote_task_address a\nJOIN lsp_quote_task t ON t.id = a.quote_task_id\nWHERE t.request_id = %(request_id)s\nORDER BY a.type;"
}
```

---

## 九、自检清单（Step 7 门禁）

- [ ] 标题符合三段式，且能独立看懂测什么
- [ ] 前置条件四个分区齐全，主数据带真实 ID/编码
- [ ] 测试数据每行有字段路径、取值、依据；参数化实例逐条列全
- [ ] 步骤 ≤ 6 步，每步都有动作和观察点
- [ ] 预期结果四分区齐全，每条断言一行且含运算符与值
- [ ] 金额断言写出计算式（fee / fuel / 段）与现算依据
- [ ] 验证 SQL 可直接执行、带 WHERE、有目的注释、参数占位
- [ ] 失败用例写全 code / msg / data / success 四要素
- [ ] 缺陷相关断言写清"设计期望 → 当前实测（D-xx）"
