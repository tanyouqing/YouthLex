from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.services.delilegal_client import (
    DeliLegalClient,
    build_case_search_payload,
    build_law_search_payload,
    extract_first_law_id,
)


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_summary_markdown(
    *,
    case_payload: dict[str, Any],
    case_response: dict[str, Any],
    law_payload: dict[str, Any],
    law_response: dict[str, Any],
    law_detail_response: dict[str, Any] | None,
    law_id: str | None,
) -> str:
    case_records = case_response.get("items", [])
    law_records = law_response.get("items", [])

    lines = [
        "# 得理开放平台 API 测试摘要",
        "",
        "## 测试结论",
        f"- 类案检索命中数量: `{len(case_records)}`",
        f"- 法规检索命中数量: `{len(law_records)}`",
        f"- 法规详情已拉取: `{law_detail_response is not None}`，lawId: `{law_id}`",
        f"- 类案检索 totalCount: `{case_response.get('total_count')}`",
        f"- 法规检索 totalCount: `{law_response.get('total_count')}`",
        "",
        "## 类案检索请求体",
        "```json",
        json.dumps(case_payload, ensure_ascii=False, indent=2),
        "```",
        "",
        "## 类案检索规范化响应",
        "```json",
        json.dumps(case_response, ensure_ascii=False, indent=2),
        "```",
        "",
        "## 法规检索请求体",
        "```json",
        json.dumps(law_payload, ensure_ascii=False, indent=2),
        "```",
        "",
        "## 法规检索规范化响应",
        "```json",
        json.dumps(law_response, ensure_ascii=False, indent=2),
        "```",
    ]

    if law_detail_response:
        lines.extend(
            [
                "",
                "## 法规详情关键信息",
                f"- 标题: {law_detail_response.get('title')}",
                f"- 发布机关: {law_detail_response.get('publisher')}",
                f"- 发布日期: {law_detail_response.get('publish_date')}",
                f"- 时效性: {law_detail_response.get('timeliness')}",
            ]
        )

    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="测试得理开放平台 API 并落盘请求/响应样例。")
    parser.add_argument(
        "--guide-docx",
        default=None,
        help="官方说明文档路径。未设置环境变量时，可从该 docx 中提取测试凭据。",
    )
    parser.add_argument(
        "--case-query",
        default="上下班途中车祸引起的工伤保险案例",
        help="类案检索测试问题。",
    )
    parser.add_argument(
        "--law-query",
        default="深圳市房地产相关的法律规定有哪些？",
        help="法规检索测试问题。",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=3,
        help="每个检索接口的测试返回条数。",
    )
    parser.add_argument(
        "--output-dir",
        default="docs/delilegal_api_samples",
        help="请求/响应样例输出目录。",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    case_payload = build_case_search_payload(
        keyword_arr=[args.case_query],
        page_size=args.page_size,
    )
    law_payload = build_law_search_payload(
        keywords=[args.law_query],
        field_name="semantic",
        page_size=args.page_size,
    )

    with DeliLegalClient.from_env(guide_docx=args.guide_docx) as client:
        case_response = client.search_cases(keyword_arr=[args.case_query], page_size=args.page_size)
        law_response = client.search_laws(
            keywords=[args.law_query],
            field_name="semantic",
            page_size=args.page_size,
        )
        law_id = extract_first_law_id(law_response)
        law_detail_response = client.get_law_detail(law_id) if law_id else None

    dump_json(output_dir / "case_search.request.json", case_payload)
    dump_json(output_dir / "case_search.response.json", case_response)
    dump_json(output_dir / "law_search.request.json", law_payload)
    dump_json(output_dir / "law_search.response.json", law_response)
    if law_detail_response is not None:
        dump_json(output_dir / "law_detail.response.json", law_detail_response)

    summary_markdown = build_summary_markdown(
        case_payload=case_payload,
        case_response=case_response,
        law_payload=law_payload,
        law_response=law_response,
        law_detail_response=law_detail_response,
        law_id=law_id,
    )
    (output_dir / "README.md").write_text(summary_markdown, encoding="utf-8")

    print(f"样例文件已写入: {output_dir.resolve()}")
    print(f"类案检索 total_count={case_response.get('total_count')} items={len(case_response.get('items', []))}")
    print(f"法规检索 total_count={law_response.get('total_count')} items={len(law_response.get('items', []))}")
    if law_detail_response is not None:
        print(f"法规详情已获取 lawId={law_id} title={law_detail_response.get('title')}")
    else:
        print("法规详情未执行：法规检索结果中未找到可用 lawId。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
