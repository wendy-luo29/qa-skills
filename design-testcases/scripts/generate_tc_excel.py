#!/usr/bin/env python
"""把用例清单（YAML/JSON）导出为 Excel，供 design-testcases 技能使用。

用法：
    python generate_tc_excel.py testcases/REQ-001-TC-list.yaml
    python generate_tc_excel.py testcases/REQ-001-TC-list.yaml -o testcases/REQ-001-TC-list.xlsx

输入格式：
    requirement: REQ-001          # 可选，缺省从文件名推断
    ac_list: [AC-01, AC-02]       # 可选，用于补全未覆盖的原子能力
    cases:
      - case_id: TC-ADDR-001
        ac: AC-01
        module: 地址校验
        title: 有效地址校验通过
        priority: P0
        precondition: 服务可用
        data: {"address": "123 Collins St"}
        steps: 1. 调用接口 2. 校验响应
        expected: 校验通过
        assertions: data.success=true
        automatable: 是
        assertion_method: 接口返回
        risk: 无
"""

import argparse
import json
import re
import sys
from pathlib import Path

import yaml
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

CASES_SHEET = "用例明细"
MATRIX_SHEET = "覆盖矩阵"

CASE_COLUMNS = [
    ("case_id", "用例编号"),
    ("ac", "关联原子能力"),
    ("module", "模块"),
    ("title", "用例标题"),
    ("priority", "优先级"),
    ("precondition", "前置条件"),
    ("data", "测试数据"),
    ("steps", "执行步骤"),
    ("expected", "预期结果"),
    ("assertions", "断言点"),
    ("automatable", "是否自动化"),
    ("assertion_method", "自动化断言方式"),
    ("risk", "风险与待确认"),
]

MATRIX_COLUMNS = ["原子能力", "用例数", "用例编号", "状态", "说明"]

HEADER_FONT = Font(bold=True)
HEADER_FILL = PatternFill("solid", fgColor="D9E1F2")
P0_FILL = PatternFill("solid", fgColor="FFC7CE")

CJK = re.compile(r"[\u4e00-\u9fff]")


def display_width(text: str) -> int:
    return sum(2 if CJK.match(ch) else 1 for ch in str(text))


def load_cases(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text) if path.suffix.lower() in (".yaml", ".yml") else json.loads(text)

    if isinstance(data, list):
        data = {"cases": data}
    if not isinstance(data, dict) or not isinstance(data.get("cases"), list):
        raise SystemExit(f"{path} 缺少 cases 列表，无法导出。")

    missing = [
        f"{index + 1}.{key}"
        for index, case in enumerate(data["cases"])
        for key, _ in CASE_COLUMNS
        if not isinstance(case, dict) or case.get(key) in (None, "")
    ]
    if missing:
        raise SystemExit("以下字段缺失，请先补全后再导出：" + "、".join(missing))
    return data


def write_cases_sheet(sheet, cases: list) -> None:
    headers = [label for _, label in CASE_COLUMNS]
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for case in cases:
        sheet.append([str(case[key]) for key, _ in CASE_COLUMNS])
        row = sheet.max_row
        if case["priority"] == "P0":
            for cell in sheet[row]:
                cell.fill = P0_FILL

    wrap = Alignment(vertical="top", wrap_text=True)
    for row in sheet.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = wrap

    for index, (key, label) in enumerate(CASE_COLUMNS, start=1):
        longest = max([display_width(label)] + [display_width(c[key]) for c in cases])
        sheet.column_dimensions[get_column_letter(index)].width = min(max(longest + 2, 10), 60)

    sheet.freeze_panes = "A2"


def write_matrix_sheet(sheet, cases: list, ac_list: list) -> None:
    sheet.append(MATRIX_COLUMNS)
    for cell in sheet[1]:
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center")

    grouped: dict[str, list[str]] = {}
    for case in cases:
        grouped.setdefault(str(case["ac"]), []).append(str(case["case_id"]))

    for ac in dict.fromkeys([*ac_list, *grouped]):
        ids = grouped.get(ac, [])
        sheet.append(
            [ac, len(ids), ", ".join(ids), "已覆盖" if ids else "未覆盖", "" if ids else "缺少对应用例"]
        )

    for index, label in enumerate(MATRIX_COLUMNS, start=1):
        width = max(display_width(label), 16)
        sheet.column_dimensions[get_column_letter(index)].width = width + 4
    sheet.column_dimensions["C"].width = 40
    sheet.freeze_panes = "A2"


def main() -> int:
    parser = argparse.ArgumentParser(description="导出测试用例清单为 Excel")
    parser.add_argument("source", help="用例清单 .yaml/.yml/.json")
    parser.add_argument("-o", "--output", help="输出 .xlsx 路径，默认与输入同名")
    args = parser.parse_args()

    source = Path(args.source).resolve()
    if not source.is_file():
        raise SystemExit(f"找不到用例清单：{source}")

    data = load_cases(source)
    cases = data["cases"]
    ac_list = [str(ac) for ac in data.get("ac_list") or []]

    workbook = Workbook()
    write_cases_sheet(workbook.active, cases)
    workbook.active.title = CASES_SHEET
    write_matrix_sheet(workbook.create_sheet(MATRIX_SHEET), cases, ac_list)

    output = Path(args.output).resolve() if args.output else source.with_suffix(".xlsx")
    output.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output)
    print(f"已导出 {len(cases)} 条用例 -> {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
