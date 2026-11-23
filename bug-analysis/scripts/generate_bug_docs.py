#!/usr/bin/env python
"""从缺陷 YAML 记录同时生成 Markdown 缺陷单与 Excel 缺陷表。

用法：
    python generate_bug_docs.py reports/bugs/BUG-REQ001-001.yaml
    python generate_bug_docs.py bugs.yaml -o reports/bugs

输出：
    {outdir}/{bug_id}.md
    {outdir}/{bug_id}.xlsx
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


def render_excel(data: dict, path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "缺陷明细"

    sheet.append([label for label, _ in EXCEL_COLUMNS])
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
        content = cell_value(data, key)
        longest = max([len(label), *(len(line) for line in content.splitlines())])
        width = max(sum(2 if CJK.match(ch) else 1 for ch in label) + 2, min(longest + 2, 60))
        sheet.column_dimensions[get_column_letter(index)].width = width
    sheet.row_dimensions[1].height = 24
    sheet.row_dimensions[2].height = 120
    sheet.freeze_panes = "A2"

    case_sheet = workbook.create_sheet("关联用例")
    case_sheet.append(["case_id", "用例标题", "AC", "优先级", "来源"])
    for case in data["related_cases"]:
        case_sheet.append([
            case.get("case_id", ""),
            case.get("title", ""),
            case.get("ac", ""),
            case.get("priority", ""),
            case.get("source", ""),
        ])
    for cell in case_sheet[1]:
        cell.font = Font(name=FONT_NAME, size=FONT_SIZE, bold=True)
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center")
    for row in case_sheet.iter_rows(min_row=2):
        for cell in row:
            cell.font = Font(name=FONT_NAME, size=FONT_SIZE)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    for index, width in enumerate([18, 40, 12, 10, 45], start=1):
        case_sheet.column_dimensions[get_column_letter(index)].width = width
    case_sheet.freeze_panes = "A2"

    try:
        workbook.save(path)
    except PermissionError:
        raise SystemExit(f"无法写入 {path}：文件正被 Excel 打开，请关闭后重试")


def main() -> int:
    parser = argparse.ArgumentParser(description="生成缺陷单 Markdown 与 Excel")
    parser.add_argument("source", help="缺陷 YAML/JSON 文件")
    parser.add_argument("-o", "--outdir", help="输出目录，默认与输入同目录")
    args = parser.parse_args()

    source = Path(args.source).resolve()
    if not source.is_file():
        raise SystemExit(f"找不到缺陷记录：{source}")

    text = source.read_text(encoding="utf-8")
    data = (
        yaml.safe_load(text)
        if source.suffix.lower() in (".yaml", ".yml")
        else json.loads(text)
    )
    if not isinstance(data, dict):
        raise SystemExit("缺陷记录根节点必须是映射（键值结构）")

    validate(data)

    outdir = Path(args.outdir).resolve() if args.outdir else source.parent
    outdir.mkdir(parents=True, exist_ok=True)
    md_path = outdir / f"{data['bug_id']}.md"
    xlsx_path = outdir / f"{data['bug_id']}.xlsx"

    md_path.write_text(render_markdown(data), encoding="utf-8")
    render_excel(data, xlsx_path)

    print(f"已生成缺陷单：{md_path}")
    print(f"已生成缺陷表：{xlsx_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
