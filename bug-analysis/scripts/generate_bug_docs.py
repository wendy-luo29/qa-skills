#!/usr/bin/env python
"""从缺陷 YAML 记录同时生成 Markdown 缺陷单与 Excel 缺陷表。

用法：
    python generate_bug_docs.py reports/bugs/BUG-REQ001-001.yaml
    python generate_bug_docs.py bugs.yaml -o reports/bugs
    python generate_bug_docs.py testcases/REQ-002-quote_price/bugs -o reports/bugs --merge
    python generate_bug_docs.py a.yaml b.yaml --merge

输出：
    单份模式：{outdir}/{bug_id}.md、{outdir}/{bug_id}.xlsx
    合并模式：同一需求的缺陷合并为一份 {outdir}/{需求号}-defects.md 与 {需求号}-defects.xlsx
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import yaml
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

REQUIRED = [
    "bug_id",
    "title",
    "severity",
    "priority",
    "requirement",
    "environment.base_url",
    "api.method",
    "api.path",
    "request.body",
    "response.status",
    "response.body",
    "expected.ac",
    "expected.rule",
    "related_cases",
    "analysis.root_cause",
    "suggestion.fix",
]

EXCEL_COLUMNS = [
    ("缺陷编号", "bug_id"),
    ("缺陷标题", "title"),
    ("严重程度", "severity"),
    ("优先级", "priority"),
    ("接口地址", "_full_url"),
    ("请求方法", "api.method"),
    ("路径", "api.path"),
    ("请求传参", "request.body"),
    ("响应结果", "response.status"),
    ("返回结果", "response.body"),
    ("预期结果", "_expected"),
    ("原因分析", "analysis.root_cause"),
    ("影响范围", "impact.scope"),
    ("修复建议", "suggestion.fix"),
    ("发现版本", "discovered_version"),
    ("关联用例", "_cases"),
    ("关联需求", "requirement"),
    ("提交人", "reporter"),
    ("提交时间", "reported_at"),
]

FONT_NAME = "微软雅黑"
FONT_SIZE = 11
HEADER_FILL = PatternFill("solid", fgColor="D9E1F2")
CJK = re.compile(r"[\u4e00-\u9fff]")


def cell_value(data: dict, key: str) -> str:
    if key == "_full_url":
        return dig(data, "environment.base_url").rstrip("/") + dig(data, "api.path")
    if key == "_expected":
        ac = dig(data, "expected.ac")
        rule = dig(data, "expected.rule")
        return f"[{ac}] {rule}" if ac else rule
    if key == "_cases":
        return "\n".join(
            f"{case.get('case_id', '')}（{case.get('title', '')}）"
            for case in data.get("related_cases") or []
        )
    return as_text(dig(data, key, ""))


def dig(data, path, default=""):
    node = data
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return default if node is None else node


def as_text(value) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value)


def validate(data: dict) -> None:
    missing = [path for path in REQUIRED if dig(data, path, None) in (None, "", [], {})]
    if missing:
        raise SystemExit("以下必填字段缺失，请补全后再生成：" + "、".join(missing))
    if not isinstance(data["related_cases"], list) or not data["related_cases"]:
        raise SystemExit("related_cases 必须是非空列表")


def load_record(path: Path) -> dict:
    """读取并校验单份缺陷记录（YAML/JSON），错误信息带上文件名。"""
    text = path.read_text(encoding="utf-8")
    data = (
        yaml.safe_load(text)
        if path.suffix.lower() in (".yaml", ".yml")
        else json.loads(text)
    )
    if not isinstance(data, dict):
        raise SystemExit(f"{path.name}: 缺陷记录根节点必须是映射（键值结构）")
    try:
        validate(data)
    except SystemExit as exc:
        raise SystemExit(f"{path.name}: {exc}") from exc
    return data


def requirement_id(data: dict) -> str:
    """从 requirement 字段提取需求号（如 REQ-002），无匹配时回退 BUGS。"""
    match = re.search(r"[A-Za-z]{2,}-\d+", str(dig(data, "requirement", "")))
    return match.group(0).upper() if match else "BUGS"


def render_markdown(data: dict) -> str:
    cases = "\n".join(
        f"| {c.get('case_id', '')} | {c.get('title', '')} | {c.get('ac', '')} "
        f"| {c.get('priority', '')} | {c.get('source', '')} |"
        for c in data["related_cases"]
    )
    attachments = data.get("attachments") or []
    attachment_lines = "\n".join(f"- {item}" for item in attachments) or "- 无"
    request_headers = dig(data, "request.headers", {})
    header_line = (
        "、".join(f"{key}: {value}" for key, value in request_headers.items())
        if isinstance(request_headers, dict)
        else str(request_headers)
    )
    return f"""# [{data['bug_id']}] {data['title']}

| 字段 | 内容 |
|---|---|
| 缺陷编号 | {data['bug_id']} |
| 状态 | {data.get('status', '新建')} |
| 严重度 / 优先级 | {data['severity']} / {data['priority']} |
| 发现版本 | {data.get('discovered_version', '未填写')} |
| 提交人 / 时间 | {data.get('reporter', '未填写')} / {data.get('reported_at', '未填写')} |
| 关联需求 | {data['requirement']} |

## 1. 环境
- 环境：{dig(data, 'environment.name', '未填写')}
- Base URL：{dig(data, 'environment.base_url')}
- 部署版本：{dig(data, 'environment.deploy_version', '未填写')}

## 2. 地址
- 方法：{dig(data, 'api.method')}
- 路径：{dig(data, 'api.path')}
- 完整 URL：{dig(data, 'environment.base_url').rstrip('/')}{dig(data, 'api.path')}

## 3. 请求传参
```json
{as_text(dig(data, 'request.body'))}
```
- Headers：{header_line or '未填写'}
- 复现命令：`{data.get('reproduce_command', '未填写')}`

## 4. 返回结果
- HTTP 状态：{dig(data, 'response.status')}
- 耗时：{dig(data, 'response.elapsed', '未记录')}
- 响应体：
```json
{as_text(dig(data, 'response.body'))}
```
- request-id：{dig(data, 'response.request_id', '无')}
- 日志：{dig(data, 'response.log', '无')}

## 5. 预期结果
- 引用 AC：{dig(data, 'expected.ac')}
- 需求原文：{dig(data, 'expected.rule')}
- 实际 vs 预期：{dig(data, 'expected.actual_vs_expected', '未填写')}

## 6. 关联用例
| case_id | 用例标题 | AC | 优先级 | 来源 |
|---|---|---|---|---|
{cases}

## 7. 附件
{attachment_lines}

## 8. 原因分析
- 现象：{dig(data, 'analysis.phenomenon', '未填写')}
- 直接原因：{dig(data, 'analysis.direct_cause', '未填写')}
- 根本原因：{dig(data, 'analysis.root_cause')}
- 证据：{dig(data, 'analysis.evidence', '未填写')}
- 待确认：{dig(data, 'analysis.pending', '无')}

## 9. 影响范围
- 受影响范围：{dig(data, 'impact.scope', '未评估')}
- 是否偶现：{dig(data, 'impact.frequency', '未验证')}
- 关联功能：{dig(data, 'impact.related', '无')}

## 10. 修复建议 / 验证建议
- 建议：{dig(data, 'suggestion.fix')}
- 回归范围：{dig(data, 'suggestion.regression', '未指定')}
"""


def render_excel(bugs: list[dict], path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "缺陷明细"

    sheet.append([label for label, _ in EXCEL_COLUMNS])
    for data in bugs:
        sheet.append([cell_value(data, key) for _, key in EXCEL_COLUMNS])

    for cell in sheet[1]:
        cell.font = Font(name=FONT_NAME, size=FONT_SIZE, bold=True)
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center")

    wrap = Alignment(vertical="top", wrap_text=True)
    for row in sheet.iter_rows(min_row=2):
        for cell in row:
            cell.font = Font(name=FONT_NAME, size=FONT_SIZE)
            cell.alignment = wrap

    for index, (label, key) in enumerate(EXCEL_COLUMNS, start=1):
        longest = max(
            [len(label)]
            + [len(line) for data in bugs for line in cell_value(data, key).splitlines()]
        )
        width = max(sum(2 if CJK.match(ch) else 1 for ch in label) + 2, min(longest + 2, 60))
        sheet.column_dimensions[get_column_letter(index)].width = width
    sheet.row_dimensions[1].height = 24
    for row_number in range(2, sheet.max_row + 1):
        sheet.row_dimensions[row_number].height = 120
    sheet.freeze_panes = "A2"

    case_sheet = workbook.create_sheet("关联用例")
    merged = len(bugs) > 1
    case_sheet.append(
        (["缺陷编号"] if merged else []) + ["case_id", "用例标题", "AC", "优先级", "来源"]
    )
    for data in bugs:
        prefix = [data["bug_id"]] if merged else []
        for case in data["related_cases"]:
            case_sheet.append(
                prefix
                + [
                    case.get("case_id", ""),
                    case.get("title", ""),
                    case.get("ac", ""),
                    case.get("priority", ""),
                    case.get("source", ""),
                ]
            )
    for cell in case_sheet[1]:
        cell.font = Font(name=FONT_NAME, size=FONT_SIZE, bold=True)
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center")
    for row in case_sheet.iter_rows(min_row=2):
        for cell in row:
            cell.font = Font(name=FONT_NAME, size=FONT_SIZE)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    widths = ([14] if merged else []) + [18, 40, 12, 10, 45]
    for index, width in enumerate(widths, start=1):
        case_sheet.column_dimensions[get_column_letter(index)].width = width
    case_sheet.freeze_panes = "A2"

    try:
        workbook.save(path)
    except PermissionError:
        raise SystemExit(f"无法写入 {path}：文件正被 Excel 打开，请关闭后重试")


def render_merged_markdown(req_id: str, bugs: list[dict]) -> str:
    """同一需求的缺陷合并成一份 Markdown：一览表 + 逐条完整缺陷单。"""

    def case_ids(data: dict) -> str:
        seen: list[str] = []
        for case in data["related_cases"]:
            cid = case.get("case_id", "")
            if cid and cid not in seen:
                seen.append(cid)
        return "、".join(seen)

    rows = "\n".join(
        f"| {data['bug_id']} | {data['title']} | {data['severity']} / {data['priority']} "
        f"| {data.get('status', '新建')} | {dig(data, 'expected.ac')} | {case_ids(data)} |"
        for data in bugs
    )
    sections = "\n---\n\n".join(render_markdown(data) for data in bugs)
    return f"""# {req_id} 缺陷汇总（共 {len(bugs)} 条）

> 生成时间：{datetime.now():%Y-%m-%d %H:%M}｜同一需求的确认缺陷合并记录于本文件。

## 缺陷一览

| 缺陷编号 | 标题 | 严重度 / 优先级 | 状态 | 关联 AC | 关联用例 |
|---|---|---|---|---|---|
{rows}

---

{sections}
"""


def expand_sources(raw: list[str]) -> list[Path]:
    """把输入参数展开为缺陷文件列表（支持目录与多文件，按文件名排序）。"""
    suffixes = (".yaml", ".yml", ".json")
    files: list[Path] = []
    for item in raw:
        path = Path(item).expanduser().resolve()
        if path.is_dir():
            found = sorted(
                child
                for child in path.iterdir()
                if child.is_file() and child.suffix.lower() in suffixes
            )
            if not found:
                raise SystemExit(f"目录中没有缺陷 YAML/JSON：{path}")
            files.extend(found)
        elif path.is_file():
            files.append(path)
        else:
            raise SystemExit(f"找不到缺陷记录：{path}")
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description="生成缺陷单 Markdown 与 Excel")
    parser.add_argument(
        "source", nargs="+", help="缺陷 YAML/JSON 文件（可传目录或多个文件）"
    )
    parser.add_argument("-o", "--outdir", help="输出目录，默认与输入同目录")
    parser.add_argument(
        "--merge",
        action="store_true",
        help="合并模式：同一需求的缺陷合并输出为一份 {需求号}-defects.md/.xlsx",
    )
    args = parser.parse_args()

    files = expand_sources(args.source)
    outdir = Path(args.outdir).resolve() if args.outdir else files[0].parent
    outdir.mkdir(parents=True, exist_ok=True)

    if args.merge:
        groups: dict[str, list[dict]] = {}
        for path in files:
            data = load_record(path)
            groups.setdefault(requirement_id(data), []).append(data)
        for req_id, group in groups.items():
            md_path = outdir / f"{req_id}-defects.md"
            xlsx_path = outdir / f"{req_id}-defects.xlsx"
            md_path.write_text(render_merged_markdown(req_id, group), encoding="utf-8")
            render_excel(group, xlsx_path)
            print(f"已生成缺陷汇总（{len(group)} 条）：{md_path}")
            print(f"已生成缺陷汇总表（{len(group)} 条）：{xlsx_path}")
        return 0

    if len(files) > 1:
        raise SystemExit("一次只能生成一份缺陷单；多份缺陷请加 --merge 合并输出")
    data = load_record(files[0])
    md_path = outdir / f"{data['bug_id']}.md"
    xlsx_path = outdir / f"{data['bug_id']}.xlsx"
    md_path.write_text(render_markdown(data), encoding="utf-8")
    render_excel([data], xlsx_path)

    print(f"已生成缺陷单：{md_path}")
    print(f"已生成缺陷表：{xlsx_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
