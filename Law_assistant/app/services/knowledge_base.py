from __future__ import annotations

import logging
import re

from app.core.config import get_settings
from app.services.delilegal_client import DeliLegalClient
from app.services.retrieval_types import LegalBasisItem, SimilarCaseItem
from app.services.triage_planner import build_case_query_plan, build_legal_query_plan


DEFAULT_LEGAL_BASIS_LIMIT = 3
DEFAULT_LEGAL_BASIS_DETAIL_LIMIT = 3
DEFAULT_SIMILAR_CASE_LIMIT = 3
logger = logging.getLogger(__name__)


def _collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _build_snippet(text: str | None, *, max_length: int = 180) -> str:
    if not text:
        return ""
    normalized = _collapse_whitespace(text)
    if len(normalized) <= max_length:
        return normalized
    return normalized[: max_length - 3] + "..."


class LegalKnowledgeBase:
    """High-level retrieval facade for future LangGraph nodes."""

    def __init__(self, client: DeliLegalClient | None = None) -> None:
        self._owns_client = client is None
        self._client = client or DeliLegalClient.from_env(
            timeout=get_settings().delilegal_timeout_seconds
        )
        self.last_legal_query: str | None = None
        self.last_case_query: str | None = None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "LegalKnowledgeBase":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def retrieve_legal_basis(
        self,
        query: str,
        scenario: str | None = None,
        *,
        limit: int = DEFAULT_LEGAL_BASIS_LIMIT,
        detail_limit: int = DEFAULT_LEGAL_BASIS_DETAIL_LIMIT,
    ) -> list[LegalBasisItem]:
        """Retrieve structured law basis items for the legal-grounding node.

        The optional ``scenario`` is reserved for later retrieval tuning. The
        current implementation performs semantic law search with the raw query.
        """

        query_plan = build_legal_query_plan(query, scenario=scenario)
        self.last_legal_query = query_plan.rewritten_query
        logger.info(
            "Legal basis retrieval query scenario=%s field=%s query=%s",
            scenario,
            query_plan.field_name,
            query_plan.rewritten_query,
        )
        search_result = self._client.search_laws(
            keywords=[query_plan.rewritten_query],
            field_name=query_plan.field_name,
            page_size=limit,
        )
        law_items = search_result["items"][:limit]
        if not law_items:
            return []

        detail_map: dict[str, str] = {}
        for law_item in law_items[: min(detail_limit, len(law_items))]:
            detail = self._client.get_law_detail(law_item["id"], merge=True)
            detail_map[law_item["id"]] = detail["content"]

        return [
            {
                "id": law_item["id"],
                "title": law_item["title"],
                "publisher": law_item["publisher"],
                "publish_date": law_item["publish_date"],
                "active_date": law_item["active_date"],
                "timeliness": law_item["timeliness"],
                "level": law_item["level"],
                "snippet": _build_snippet(detail_map.get(law_item["id"]) or law_item["title"]),
                "content": detail_map.get(law_item["id"]),
            }
            for law_item in law_items
        ]

    def retrieve_similar_cases(
        self,
        query: str,
        scenario: str | None = None,
        *,
        limit: int = DEFAULT_SIMILAR_CASE_LIMIT,
    ) -> list[SimilarCaseItem]:
        """Retrieve structured similar cases for the deliverables node.

        The optional ``scenario`` is reserved for later retrieval tuning. The
        current implementation uses the user's text directly as long-text search.
        """

        query_plan = build_case_query_plan(query, scenario=scenario)
        self.last_case_query = query_plan.rewritten_query
        logger.info(
            "Similar case retrieval query scenario=%s mode=%s query=%s keywords=%s",
            scenario,
            query_plan.preferred_mode,
            query_plan.rewritten_query,
            query_plan.keyword_arr,
        )

        if query_plan.preferred_mode == "keyword_arr":
            search_result = self._client.search_cases(
                keyword_arr=query_plan.keyword_arr,
                page_size=limit,
            )
        else:
            search_result = self._client.search_cases(
                long_text=query_plan.long_text,
                page_size=limit,
            )
        case_items = search_result["items"][:limit]
        if not case_items:
            return []

        result: list[SimilarCaseItem] = []
        for case_item in case_items:
            excerpt = _build_snippet(case_item["content"], max_length=220)
            result.append(
                {
                    "id": case_item["id"],
                    "title": case_item["title"],
                    "court": case_item["court"],
                    "case_number": case_item["case_number"],
                    "judgement_date": case_item["judgement_date"],
                    "judgement_type": case_item["judgement_type"],
                    "case_type": case_item["case_type"],
                    "summary": excerpt,
                    "excerpt": excerpt,
                    "full_content": case_item["content"],
                    "judgment": case_item["judgement_type"] or "待补充裁判结果",
                    "takeaway": excerpt or "待结合案件内容提炼维权启示。",
                }
            )
        return result
