from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from app.graph.schemas.state import KnowledgeHit, RecordType


ROOT_DIR = Path(__file__).resolve().parents[2]
KNOWLEDGE_DIR = ROOT_DIR / "knowledge"

KNOWLEDGE_FILES: Dict[RecordType, Path] = {
    "statute": KNOWLEDGE_DIR / "statutes" / "statutes.demo.jsonl",
    "case": KNOWLEDGE_DIR / "cases" / "cases.demo.jsonl",
    "issue_rule": KNOWLEDGE_DIR / "issue_rules" / "issue_rules.demo.jsonl",
    "rebuttal_template": KNOWLEDGE_DIR / "rebuttal_templates" / "rebuttal_templates.demo.jsonl",
}


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def discover_knowledge_files(knowledge_dir: Path = KNOWLEDGE_DIR) -> List[Path]:
    if not knowledge_dir.exists():
        return []

    files: List[Path] = []
    for path in knowledge_dir.rglob("*.jsonl"):
        if ".vector_store" in path.parts:
            continue
        files.append(path)
    files.sort()
    return files


@lru_cache(maxsize=1)
def load_all_records() -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for file_path in discover_knowledge_files():
        records.extend(_read_jsonl(file_path))
    return records


def clear_record_cache() -> None:
    load_all_records.cache_clear()


def _normalize_terms(text: str) -> List[str]:
    tokens = [token.strip().lower() for token in text.replace("，", " ").replace("。", " ").split()]
    return [t for t in tokens if t]


def _flatten_keywords(record: Dict[str, Any]) -> Iterable[str]:
    for kw in record.get("keywords", []):
        if isinstance(kw, str):
            yield kw.lower()

    for tag in record.get("scenario_tags", []):
        if isinstance(tag, str):
            yield tag.lower()

    content = record.get("content", {})
    for key in ("issue_name", "law_name", "article_no", "case_title", "template_type"):
        value = content.get(key)
        if isinstance(value, str):
            yield value.lower()


def _build_snippet(record: Dict[str, Any]) -> str:
    content = record.get("content", {})
    record_type = record.get("record_type")
    if record_type == "statute":
        return f"{content.get('law_name', '')}{content.get('article_no', '')}：{content.get('plain_explanation', '')}"
    if record_type == "case":
        return f"{content.get('case_title', '')}：{content.get('court_reasoning', '')}"
    if record_type == "issue_rule":
        return f"{content.get('issue_name', '')}：{content.get('issue_definition', '')}"
    if record_type == "rebuttal_template":
        return f"{content.get('template_type', '')}：{content.get('template_text', '')}"
    return ""


def simple_search(
    query: str,
    scenario_hint: str = "",
    top_k: int = 6,
) -> List[KnowledgeHit]:
    tokens = _normalize_terms(query)
    scenario_hint_norm = scenario_hint.lower().strip()

    scored: List[KnowledgeHit] = []
    for record in load_all_records():
        searchable = set(_flatten_keywords(record))
        score = sum(1 for token in tokens if token in searchable)

        if scenario_hint_norm and scenario_hint_norm in [s.lower() for s in record.get("scenario_tags", [])]:
            score += 2

        if score <= 0:
            continue

        scored.append(
            {
                "record_id": record.get("record_id", ""),
                "record_type": record.get("record_type", "issue_rule"),
                "score": score,
                "citation": record.get("source", {}).get("citation", ""),
                "snippet": _build_snippet(record),
            }
        )

    scored.sort(key=lambda row: row.get("score", 0), reverse=True)
    return scored[:top_k]


def search_knowledge(
    query: str,
    scenario_hint: str = "",
    top_k: int = 6,
) -> Tuple[List[KnowledgeHit], Dict[str, Any]]:
    query = str(query or "").strip()
    if not query:
        return [], {"mode": "keyword_fallback", "error_code": "EMPTY_QUERY", "error_message": ""}

    try:
        from app.knowledge.vector_store import DEFAULT_INDEX_DIR, search_vector_store

        hits, debug = search_vector_store(
            query=query,
            scenario_hint=scenario_hint,
            top_k=top_k,
            index_dir=DEFAULT_INDEX_DIR,
        )
        return hits, debug
    except Exception as exc:
        fallback_hits = simple_search(query=query, scenario_hint=scenario_hint, top_k=top_k)
        return (
            fallback_hits,
            {
                "mode": "keyword_fallback",
                "error_code": "VECTOR_SEARCH_FAILED",
                "error_message": str(exc),
            },
        )
