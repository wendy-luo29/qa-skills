---
name: manual-order-quote-flow
description: Create a 0102 manual order, audit it, check 0109 interception, then verify 0801 outbound status and lsp_quote tables. Use when asked to create a manual order and validate quote calculation.
---

# 手工订单创建 + 计费校验流程

在 LSP/SCP 测试环境跑通一条完整链路：**0102 手工订单 → 审核 → 0109 拦截检查 → 0801 出库申请单 → 5 张计费表校验**。

本流程已实现为可执行用例，优先复用，不要重写：

- 用例：`tests/ui/test_manual_order_quote_calc.py`
- Page Object：`pages/manual_order_page.py`、`pages/intercept_order_page.py`、`pages/outbound_apply_page.py`
- 通用工具：`pages/base_page.py`（`search_keywords` / `grid_rows` / `click_confirm`）
- DB 只读封装：`utils/db.py`，或 `tests/conftest.py` 里的 `db` fixture

## 前置条件

1. `config/env.yaml` 配好 `ui_base_url` 与 `credentials.ui`（禁止在代码里硬编码地址/账号）。
2. DB 断言需要环境变量 `TEST_DB_PASSWORD`（密码不落盘）：
   ```powershell
   $env:TEST_DB_PASSWORD = "<密码>"
   ```
   未设置时 `db` fixture 会自动 skip 整条用例。
3. 依赖已安装：`playwright`、`pytest-playwright`、`pymysql`。

## 执行方式

```powershell
# 完整链路（约 3-4 分钟，含 30s/60s 等待和计费轮询）
python -m pytest tests/ui/test_manual_order_quote_calc.py -v

# 只回归创建+审核（不查计费）
python -m pytest tests/ui/test_create_manual_order.py -v
```

时间参数在 `config/env.yaml` 的 `manual_order_quote` 段：`intercept_check_delay`(30)、`outbound_check_delay`(60)、`calc_timeout`(240)、`poll_interval`(10)，单位秒。

## 流程细节

### 1. 0102 创建手工订单

使用 `ManualOrderPage`：

```python
order.open_0102()
before = order.first_order_info().get(order.COL_NO)
order.click_new()
order.fill_form(order_type="零售", platform_search="Lasoo", ship=ShipInfo())
order.add_first_sku()                       # 必须先加产品明细，否则保存报 skus can't be empty
order.set_first_line(quantity=1, unit_price=10)
order.save()                                # 弹确认框点「是」
order.wait_first_order_changed(before)      # 列表第一行 = 新订单，审核状态「审核中」
order.submit_audit()                        # 选中该行 → 审核 → 「是」→ 状态「通过」
```

关键点：
- 表单字段一律用 `input[name='main.xxx']`，不要用 ExtJS 生成的 id。
- 工具栏按钮用 `a.x-btn:visible:has-text('...')`（页面有隐藏重名按钮）。
- 明细数量/售价通过 ExtJS store 写入（`set_first_line`），不要硬点内联编辑单元格。
- 列表读取用 `first_order_info()`：按可见列头与可见 td 顺序对齐，隐藏列不渲染 td。

### 2. 取 ERP订单ID

- 0102 列表可见列「**ERP订单ID**」= store 字段 `orderId`（形如 `O2123674...`）。
- 「手工单号」是 `manualOrderNo`（形如 `MNO...`），**不是** ERP 订单ID，后续查询用错会查不到。
- 0109 的「渠道订单ID」是 `rd3OrderId`（形如 `MLOD...`），也不是 ERP订单ID。

### 3. 0109 拦截检查

```python
ic = InterceptOrderPage(page)
ic.open_0109()
hit = ic.find_by_erp_order_id(erp_order_id)   # 返回行或 None
```

- grid 组件 id：`OrderInterceptionGridPanelID`。
- 用顶部「关键字」框查询（`input[name='keywords']:visible`）；多 tab 共存时隐藏页也有同名字段，**必须 `:visible`**。
- 命中行按 store 字段 `orderId` 精确匹配。
- 命中即已拦截，打印 `拦截类型`（如「运费预算失败」）与 `拦截时间` 判断原因。

### 4. 0801 出库申请单状态

```python
ob = OutboundApplyPage(page)
ob.open_0801()
row = ob.wait_for_status(erp_order_id, expected="转执行单",
                         timeout_ms=240_000, poll_ms=10_000)
```

- grid 组件 id：`SoApplyGridPanelID`；来源单号 `fromOrderNo` = ERP订单ID。
- 「单据状态」是字典渲染文本，常见值：`转执行单`(28)、`物流计费失败`(24)、`取消订单`(25)、`导出失败/导入失败`。
- 计费是异步调度，通常创建后 2-3 分钟才完成；固定 60s 后仍需轮询到 `转执行单`。
- 遇到明确失败状态立即断言失败，不要一直等到超时。

### 5. 计费表校验（lsp_scp）

| 表 | 关联键 | 断言 |
|---|---|---|
| `lsp_quote_task` | `order_code` = ERP订单ID | 1 条；`status=200`（300=计费失败）；`predict_price > 0`；`predict_carrier_code` 非空 |
| `lsp_quote_task_address` | `quote_task_id` | 2 条：发件 `type=100` + 收件 `type=200`；收件 state/postcode/address1 与下单一致 |
| `lsp_quote_task_package` | `quote_task_id` | ≥1 条，`status=100`，长宽高/重量 > 0 |
| `lsp_quote_task_package_sku` | 经 package.id 关联 | ≥1 条；`sum(qty)` = 下单件数；sku 非空 |
| `lsp_quote_task_job_log` | `quote_task_id` | ≥1 条；包含 `calc` 与 `choice` 动作（另有 `merge`） |

注意：实际库中**没有** `lsp_quote`、`lsp_quote_task_log` 两张表，分别对应 `lsp_quote_task`、`lsp_quote_task_job_log`。若用户指定了别的日志表，先 `SHOW COLUMNS` 确认再改断言。

查询示例（pymysql 参数用 `%s`）：

```sql
SELECT * FROM lsp_quote_task WHERE order_code = %s ORDER BY created_at DESC LIMIT 1;
SELECT * FROM lsp_quote_task_package WHERE quote_task_id = %s AND status = 100;
```

## 扩展与排错

- 想换地址/SKU/平台：改 `ShipInfo` 参数或 `add_first_sku` 的选择逻辑，其余流程不变。
- 用例失败先看 0801 的「单据状态」：`物流计费失败` 说明价卡/地址/SKU 组合无可用承运商，再查 `lsp_quote_task_job_log.failed_reason`。
- 0109 查到记录时，检查 `拦截类型`；「运费预算失败」通常是上游计费失败导致，不是脚本问题。
- 不要修改 `tests/ui/test_create_manual_order.py`；新增场景另建用例文件。
- 数据库只读：断言只做 SELECT，不改生产/测试数据。
