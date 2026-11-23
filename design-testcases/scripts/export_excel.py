#!/usr/bin/env python3
"""
export_excel.py
汇总所有批次的测试用例 JSON，导出为标准格式 Excel 文件。

合并自 design-testcases 与 testcase-design-api：
- 支持 AC 追溯、用例编号、自动化可行性标注（来自 design-testcases）
- 支持验证 SQL、按 test_type 行染色、覆盖率统计（来自 testcase-design-api）
- 新增：覆盖矩阵 Sheet、待确认清单 Sheet
"""

import argparse
import json
import glob
from datetime import datetime
from pathlib import Path

try:
    import openpyxl
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False


# ── 颜色定义 ─────────────────────────────────────────────────
HEADER_FILL = PatternFill("solid", fgColor="2E75B6") if HAS_OPENPYXL else None
P0_FILL = PatternFill("solid", fgColor="FFC7CE") if HAS_OPENPYXL else None
FILL_MAP = {
    "正向": "FFFFFF",
    "负向": "FFF2CC",
    "边界": "DDEEFF",
    "安全": "FFE4CC",
    "权限": "F2F2F2",
} if HAS_OPENPYXL else {}

def split_acs(value) -> list:
    """把 "AC-01,AC-02" 这类多 AC 字符串拆成去重后的 AC 列表"""
    raw = str(value or "").strip()
    if not raw:
        return ["未关联"]
    for sep in ("，", "、", ";", "；", "/", " "):
        raw = raw.replace(sep, ",")
    return [ac for ac in dict.fromkeys(x.strip() for x in raw.split(",")) if ac]


# ── 标准列顺序（合并版，共 30 列） ──────────────────────────
# 在原 25 列基础上增加：case_id、ac、automatable、assertion_method、risk
COLUMNS = [
    ("case_id",          "用例编号",         14),
    ("ac",               "关联原子能力",     12),
    ("project",          "系统/项目",        12),
    ("module",           "模块",             15),
    ("feature",          "功能",             15),
    ("test_item",        "测试项",           22),
    ("title",            "用例标题",         28),
    ("preconditions",    "前置条件",         28),
    ("db_tables",        "涉及到数据库表",   18),
    ("test_data",        "测试数据",         32),
    ("steps",            "测试步骤",         50),
    ("expected_result",  "预期结果",         50),
    ("validation_sql",   "验证SQL",          55),
    ("actual_result",    "实际结果",         18),
    ("is_passed",        "是否通过",         10),
    ("estimated_hours",  "预计工时(h)",      11),
    ("execute_date",     "执行时间(年月日)", 14),
    ("test_progress",    "测试进度(%)",      11),
    ("case_type",        "用例类型",         10),
    ("priority",         "用例优先级",        8),
    ("is_regression",    "是否回归用例",     11),
    ("is_blocker",       "是否阻塞上线",     11),
    ("requirement_id",   "关联需求ID",       14),
    ("api_url",          "API URL",          22),
    ("bug_count",        "BUG数",             8),
    ("bug_unresolved",   "BUG未解决数",      10),
    ("case_version",     "用例版本",         10),
    ("automatable",      "是否自动化",       10),
    ("assertion_method", "自动化断言方式",   16),
    ("risk",             "风险与待确认",     22),
]

# 需要自动换行的列 key
WRAP_COLS = {
    "test_item", "steps", "test_data", "expected_result",
    "validation_sql", "preconditions", "db_tables", "risk",
}

# 需要居中的列 key
CENTER_COLS = {
    "case_id", "ac", "priority", "is_passed", "is_regression",
    "is_blocker", "bug_count", "bug_unresolved", "case_version",
    "estimated_hours", "test_progress", "case_type", "automatable",
}


def load_all_batches(workspace: str) -> list:
    """加载 output/ 目录下所有 cases_batch_*.json 文件"""
    output_dir = Path(workspace) / "output"
    pattern = str(output_dir / "cases_batch_*.json")
    files = sorted(glob.glob(pattern))

    if not files:
        pattern2 = str(Path(workspace) / "cases_batch_*.json")
        files = sorted(glob.glob(pattern2))

    all_cases = []
    for f in files:
        with open(f, encoding="utf-8-sig") as fp:
            batch = json.load(fp)
            if isinstance(batch, list):
                all_cases.extend(batch)
            elif isinstance(batch, dict) and "cases" in batch:
                all_cases.extend(batch["cases"])
        n = len(batch) if isinstance(batch, list) else len(batch.get("cases", []))
        print(f"   加载 {Path(f).name}: {n} 条用例")

    print(f"共加载 {len(all_cases)} 条测试用例")
    return all_cases


def auto_case_id(cases: list) -> list:
    """为没有 case_id 的用例自动编号：TC-{模块缩写}-{三位序号}"""
    seq_by_module = {}
    for c in cases:
        if not c.get("case_id"):
            module = str(c.get("module", "API"))
            # 模块缩写：取拼音/英文首字母，3~6 位大写
            abbr = "".join(ch for ch in module.upper() if ch.isascii() and ch.isalpha())[:6] or "API"
            seq_by_module[abbr] = seq_by_module.get(abbr, 0) + 1
            c["case_id"] = f"TC-{abbr}-{seq_by_module[abbr]:03d}"
    return cases


def make_thin_border():
    side = Side(style="thin", color="CCCCCC")
    return Border(left=side, right=side, top=side, bottom=side)


def write_cases_sheet(ws, cases: list, thin_border):
    """写用例明细 Sheet"""
    header_font = Font(name="微软雅黑", bold=True, color="FFFFFF", size=11)
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    data_font = Font(name="微软雅黑", size=10)
    center_align = Alignment(horizontal="center", vertical="top")
    left_align = Alignment(horizontal="left", vertical="top", wrap_text=True)

    # 表头
    for col_idx, (key, name, width) in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=name)
        cell.fill = HEADER_FILL
        cell.font = header_font
        cell.alignment = header_align
        cell.border = thin_border
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    ws.row_dimensions[1].height = 30
    ws.freeze_panes = "A2"

    # 数据行
    for row_idx, case in enumerate(cases, start=2):
        test_type = case.get("test_type", "正向")
        fill_color = FILL_MAP.get(test_type, "FFFFFF")
        row_fill = PatternFill("solid", fgColor=fill_color)
        is_p0 = str(case.get("priority", "")).upper() == "P0"

        for col_idx, (key, name, width) in enumerate(COLUMNS, start=1):
            val = case.get(key, "")
            cell = ws.cell(row=row_idx, column=col_idx, value=str(val) if val is not None else "")
            cell.fill = P0_FILL if is_p0 else row_fill
            cell.font = data_font
            cell.border = thin_border
            if key in WRAP_COLS:
                cell.alignment = left_align
            elif key in CENTER_COLS:
                cell.alignment = center_align
            else:
                cell.alignment = Alignment(horizontal="left", vertical="top")

        ws.row_dimensions[row_idx].height = 55

    ws.auto_filter.ref = f"A1:{get_column_letter(len(COLUMNS))}{len(cases) + 1}"


def write_matrix_sheet(ws, cases: list, thin_border, ac_list: list = None):
    """写覆盖矩阵 Sheet：原子能力 → 用例编号 → 状态"""
    ac_list = ac_list or []
    grouped = {}
    for case in cases:
        for ac in split_acs(case.get("ac", "")):
            grouped.setdefault(ac, []).append(str(case.get("case_id", "")))

    # 合并 ac_list 和实际出现的 ac
    all_acs = list(dict.fromkeys([*ac_list, *grouped.keys()]))

    headers = ["原子能力", "用例数", "用例编号", "状态", "说明"]
    header_font = Font(name="微软雅黑", bold=True, color="FFFFFF", size=11)
    header_fill = HEADER_FILL
    data_font = Font(name="微软雅黑", size=10)

    for col_idx, name in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=name)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border

    widths = [14, 10, 50, 12, 30]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"

    for row_idx, ac in enumerate(all_acs, start=2):
        ids = grouped.get(ac, [])
        status = "已覆盖" if ids else "未覆盖"
        note = "" if ids else "缺少对应用例"
        ws.cell(row=row_idx, column=1, value=ac).font = data_font
        ws.cell(row=row_idx, column=2, value=len(ids)).font = data_font
        ws.cell(row=row_idx, column=3, value=", ".join(ids)).font = data_font
        ws.cell(row=row_idx, column=4, value=status).font = data_font
        ws.cell(row=row_idx, column=5, value=note).font = data_font
        for col in range(1, 6):
            ws.cell(row=row_idx, column=col).border = thin_border


def write_pending_sheet(ws, cases: list, thin_border):
    """写待确认清单 Sheet：风险与待确认非空的用例"""
    pending = [c for c in cases if str(c.get("risk", "")).strip() not in ("", "无", "N/A")]
    headers = ["用例编号", "关联原子能力", "用例标题", "风险与待确认", "优先级"]
    header_font = Font(name="微软雅黑", bold=True, color="FFFFFF", size=11)
    data_font = Font(name="微软雅黑", size=10)

    for col_idx, name in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=name)
        cell.fill = HEADER_FILL
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border

    widths = [14, 12, 35, 50, 10]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"

    # 按优先级排序
    pri_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    pending.sort(key=lambda c: pri_order.get(str(c.get("priority", "")).upper(), 9))

    for row_idx, case in enumerate(pending, start=2):
        ws.cell(row=row_idx, column=1, value=str(case.get("case_id", ""))).font = data_font
        ws.cell(row=row_idx, column=2, value=str(case.get("ac", ""))).font = data_font
        ws.cell(row=row_idx, column=3, value=str(case.get("title", ""))).font = data_font
        ws.cell(row=row_idx, column=4, value=str(case.get("risk", ""))).font = data_font
        ws.cell(row=row_idx, column=5, value=str(case.get("priority", ""))).font = data_font
        for col in range(1, 6):
            ws.cell(row=row_idx, column=col).border = thin_border
            ws.cell(row=row_idx, column=col).alignment = Alignment(
                horizontal="left", vertical="top", wrap_text=True
            )

    return len(pending)


def write_stats_sheet(ws, cases: list, thin_border):
    """写覆盖率统计 Sheet"""
    title_font = Font(name="微软雅黑", bold=True, size=12)
    bold_font = Font(name="微软雅黑", bold=True, size=11)
    data_font = Font(name="微软雅黑", size=10)

    ws.column_dimensions["A"].width = 20
    ws.column_dimensions["B"].width = 12
    ws.column_dimensions["C"].width = 12
    ws.column_dimensions["D"].width = 15

    ws.cell(1, 1, "覆盖率统计报告").font = title_font
    ws.cell(2, 1, f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    total = len(cases)
    type_counts = {}
    api_counts = {}
    priority_counts = {}
    ac_counts = {}
    for c in cases:
        ct = c.get("test_type", "未知")
        type_counts[ct] = type_counts.get(ct, 0) + 1
        ap = c.get("api_url", "未知")
        api_counts[ap] = api_counts.get(ap, 0) + 1
        pr = c.get("priority", "未知")
        priority_counts[pr] = priority_counts.get(pr, 0) + 1
        for ac in split_acs(c.get("ac", "")):
            ac_counts[ac] = ac_counts.get(ac, 0) + 1

    row = 4
    ws.cell(row, 1, "用例类型分布").font = bold_font
    row += 1
    ws.cell(row, 1, "类型"); ws.cell(row, 2, "数量"); ws.cell(row, 3, "比例"); ws.cell(row, 4, "目标")
    row += 1
    targets = {"正向": "≥40%", "负向": "≥30%", "边界": "≥20%", "安全": "≥10%", "权限": "-"}
    for ct, cnt in sorted(type_counts.items()):
        ws.cell(row, 1, ct).font = data_font
        ws.cell(row, 2, cnt).font = data_font
        ws.cell(row, 3, f"{cnt/total*100:.1f}%" if total else "0%").font = data_font
        ws.cell(row, 4, targets.get(ct, "-")).font = data_font
        row += 1
    ws.cell(row, 1, "合计").font = bold_font
    ws.cell(row, 2, total).font = bold_font
    row += 2

    ws.cell(row, 1, "优先级分布").font = bold_font
    row += 1
    ws.cell(row, 1, "优先级"); ws.cell(row, 2, "数量")
    row += 1
    for pr in ["P0", "P1", "P2", "P3"]:
        ws.cell(row, 1, pr).font = data_font
        ws.cell(row, 2, priority_counts.get(pr, 0)).font = data_font
        row += 1
    row += 1

    ws.cell(row, 1, "原子能力覆盖").font = bold_font
    row += 1
    ws.cell(row, 1, "原子能力"); ws.cell(row, 2, "用例数")
    row += 1
    for ac, cnt in sorted(ac_counts.items(), key=lambda x: -x[1]):
        ws.cell(row, 1, ac).font = data_font
        ws.cell(row, 2, cnt).font = data_font
        row += 1
    row += 1

    ws.cell(row, 1, "接口用例分布").font = bold_font
    row += 1
    ws.cell(row, 1, "接口路径"); ws.cell(row, 2, "用例数")
    row += 1
    for ap, cnt in sorted(api_counts.items(), key=lambda x: -x[1]):
        ws.cell(row, 1, ap).font = data_font
        ws.cell(row, 2, cnt).font = data_font
        row += 1


def export_excel(cases: list, output_path: str, ac_list: list = None):
    if not HAS_OPENPYXL:
        raise RuntimeError("请安装 openpyxl: pip install openpyxl")

    wb = openpyxl.Workbook()
    thin_border = make_thin_border()

    # Sheet 1: 用例明细
    ws_cases = wb.active
    ws_cases.title = "用例明细"
    write_cases_sheet(ws_cases, cases, thin_border)

    # Sheet 2: 覆盖矩阵
    ws_matrix = wb.create_sheet("覆盖矩阵")
    write_matrix_sheet(ws_matrix, cases, thin_border, ac_list)

    # Sheet 3: 待确认清单
    ws_pending = wb.create_sheet("待确认清单")
    pending_count = write_pending_sheet(ws_pending, cases, thin_border)

    # Sheet 4: 覆盖率统计
    ws_stats = wb.create_sheet("覆盖率统计")
    write_stats_sheet(ws_stats, cases, thin_border)

    wb.save(output_path)
    print(f"Excel 已生成: {output_path}")
    print(f"  - 用例明细: {len(cases)} 条")
    print(f"  - 待确认项: {pending_count} 条")


def main():
    parser = argparse.ArgumentParser(description="导出测试用例为标准 Excel（合并版）")
    parser.add_argument("--workspace", required=True, help="工作区路径")
    parser.add_argument("--template", default=None, help="表头模板（可选，保留兼容）")
    parser.add_argument("--output", default=None, help="输出 Excel 文件路径")
    parser.add_argument("--ac_list", default=None,
                        help="逗号分隔的原子能力列表，用于补全覆盖矩阵中未覆盖的 AC")
    args = parser.parse_args()

    if not HAS_OPENPYXL:
        print("请先安装 openpyxl: pip install openpyxl")
        return

    # 1. 加载所有批次用例
    cases = load_all_batches(args.workspace)
    if not cases:
        print("没有找到任何测试用例 JSON 文件（cases_batch_*.json）")
        return

    # 2. 自动补充 case_id
    cases = auto_case_id(cases)

    # 3. AC 列表
    ac_list = [a.strip() for a in args.ac_list.split(",")] if args.ac_list else None

    # 4. 输出路径
    if args.output:
        output_path = args.output
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path(args.workspace) / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / f"api_testcases_{timestamp}.xlsx")

    # 5. 导出
    export_excel(cases, output_path, ac_list)

    # 6. 覆盖率汇总
    total = len(cases)
    type_counts = {}
    for c in cases:
        ct = c.get("test_type", "未知")
        type_counts[ct] = type_counts.get(ct, 0) + 1

    print(f"\n覆盖率汇总（共 {total} 条用例）:")
    targets = {"正向": 0.4, "负向": 0.3, "边界": 0.2, "安全": 0.1}
    for ct, target in targets.items():
        cnt = type_counts.get(ct, 0)
        ratio = cnt / total if total else 0
        status = "OK" if ratio >= target else "未达标"
        print(f"   {status} {ct}: {cnt}/{total} = {ratio*100:.0f}%（目标≥{target*100:.0f}%）")

    print(f"\n输出文件: {output_path}")


if __name__ == "__main__":
    main()
