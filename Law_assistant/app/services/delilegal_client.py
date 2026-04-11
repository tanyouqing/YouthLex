from __future__ import annotations

import os
from dotenv import load_dotenv
load_dotenv()

import re
from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import httpx

from app.services.retrieval_types import (
    CaseSearchItem,
    CaseSearchResult,
    LawDetailItem,
    LawSearchItem,
    LawSearchResult,
)


DEFAULT_DELILEGAL_BASE_URL = "https://openapi.delilegal.com"
DEFAULT_DELILEGAL_TIMEOUT = 20.0
DOCX_NAMESPACE = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
APP_ID_PATTERN = re.compile(r"appid:\s*([A-Za-z0-9]+)")
SECRET_PATTERN = re.compile(r"secret:\s*([A-Za-z0-9]+)")
logger = logging.getLogger(__name__)


class DeliLegalError(Exception):
    """Base exception for DeliLegal client errors."""


class DeliLegalConfigError(DeliLegalError):
    """Raised when credentials or endpoint config are missing."""


class DeliLegalTransportError(DeliLegalError):
    """Raised when the HTTP request cannot reach the remote server."""


class DeliLegalHTTPError(DeliLegalError):
    """Raised when the remote server returns a non-2xx response."""


class DeliLegalAPIError(DeliLegalError):
    """Raised when the remote API returns a business error payload."""


class DeliLegalResponseError(DeliLegalError):
    """Raised when the remote payload shape is not what the app expects."""


@dataclass(frozen=True)
class DeliLegalCredentials:
    app_id: str
    secret: str


def _text_from_node(node: ET.Element) -> str:
    parts: list[str] = []
    for text_node in node.findall(".//w:t", DOCX_NAMESPACE):
        if text_node.text:
            parts.append(text_node.text)
    return "".join(parts).strip()


def extract_credentials_from_guide_docx(guide_docx: str | Path) -> DeliLegalCredentials:
    """Read the official guide docx and extract the demo appid/secret."""

    path = Path(guide_docx)
    with ZipFile(path) as archive:
        xml_bytes = archive.read("word/document.xml")

    root = ET.fromstring(xml_bytes)
    body = root.find("w:body", DOCX_NAMESPACE)
    if body is None:
        raise DeliLegalConfigError(f"未在文档中找到正文: {path}")

    text = "\n".join(
        text
        for child in body
        if child.tag.endswith("}p")
        for text in [_text_from_node(child)]
        if text
    )

    app_id_match = APP_ID_PATTERN.search(text)
    secret_match = SECRET_PATTERN.search(text)
    if app_id_match is None or secret_match is None:
        raise DeliLegalConfigError(f"未能从文档中解析 appid/secret: {path}")

    return DeliLegalCredentials(
        app_id=app_id_match.group(1),
        secret=secret_match.group(1),
    )


def load_delilegal_credentials(
    *,
    app_id: str | None = None,
    secret: str | None = None,
    guide_docx: str | Path | None = None,
) -> DeliLegalCredentials:
    """Load credentials from args, env, or the official guide docx."""

    resolved_app_id = app_id or os.getenv("DELILEGAL_APP_ID")
    resolved_secret = secret or os.getenv("DELILEGAL_SECRET")

    if resolved_app_id and resolved_secret:
        return DeliLegalCredentials(app_id=resolved_app_id, secret=resolved_secret)

    if guide_docx is not None:
        return extract_credentials_from_guide_docx(guide_docx)

    raise DeliLegalConfigError(
        "缺少得理开放平台凭据。请设置 DELILEGAL_APP_ID / DELILEGAL_SECRET，"
        "或在脚本中通过 --guide-docx 指向官方说明文档。"
    )


def build_case_search_payload(
    *,
    keyword_arr: list[str] | None = None,
    long_text: str | None = None,
    page_no: int = 1,
    page_size: int = 5,
    sort_field: str = "correlation",
    sort_order: str = "desc",
    case_year_start: int | None = None,
    case_year_end: int | None = None,
    court_level_arr: list[str] | None = None,
    judgement_type_arr: list[str] | None = None,
) -> dict[str, Any]:
    """Build the official case-search request payload."""

    if not keyword_arr and not long_text:
        raise ValueError("类案检索至少需要 keyword_arr 或 long_text 其中之一。")

    condition: dict[str, Any] = {}
    if keyword_arr:
        condition["keywordArr"] = keyword_arr
    if long_text:
        condition["longText"] = long_text
    if case_year_start is not None:
        condition["caseYearStart"] = case_year_start
    if case_year_end is not None:
        condition["caseYearEnd"] = case_year_end
    if court_level_arr:
        condition["courtLevelArr"] = court_level_arr
    if judgement_type_arr:
        condition["judgementTypeArr"] = judgement_type_arr

    return {
        "pageNo": page_no,
        "pageSize": page_size,
        "sortField": sort_field,
        "sortOrder": sort_order,
        "condition": condition,
    }


def build_law_search_payload(
    *,
    keywords: list[str],
    field_name: str = "semantic",
    page_no: int = 1,
    page_size: int = 5,
    sort_field: str = "correlation",
    sort_order: str = "desc",
) -> dict[str, Any]:
    """Build the official law-search request payload."""

    if not keywords:
        raise ValueError("法规检索至少需要一个 keywords 条目。")

    return {
        "pageNo": page_no,
        "pageSize": page_size,
        "sortField": sort_field,
        "sortOrder": sort_order,
        "condition": {
            "keywords": keywords,
            "fieldName": field_name,
        },
    }


def extract_first_law_id(response_payload: dict[str, Any]) -> str | None:
    """Return the first law id from either normalized or raw law-search payloads."""

    candidate_lists: list[Any] = [response_payload.get("items")]

    body = response_payload.get("body")
    if isinstance(body, dict):
        candidate_lists.append(body.get("data"))
        candidate_lists.append(body.get("records"))

    for items in candidate_lists:
        if not isinstance(items, list) or not items:
            continue

        first_item = items[0]
        if not isinstance(first_item, dict):
            continue

        law_id = first_item.get("id")
        if isinstance(law_id, str) and law_id:
            return law_id

    return None


def _ensure_mapping(value: Any, *, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DeliLegalResponseError(f"{context} 不是对象结构。")
    return value


def _ensure_list(value: Any, *, context: str) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise DeliLegalResponseError(f"{context} 不是数组结构。")
    return value


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _int_or_zero(value: Any) -> int:
    return value if isinstance(value, int) else 0


def _normalize_law_search_item(item: dict[str, Any]) -> LawSearchItem:
    law_id = _string_or_none(item.get("id"))
    title = _string_or_none(item.get("title"))
    if law_id is None or title is None:
        raise DeliLegalResponseError("法规检索结果缺少 id 或 title 字段。")

    highlights = item.get("highlights")
    normalized_highlights = (
        [entry for entry in highlights if isinstance(entry, str)]
        if isinstance(highlights, list)
        else []
    )
    return {
        "id": law_id,
        "title": title,
        "publisher": _string_or_none(item.get("publisherName")),
        "publish_date": _string_or_none(item.get("publishDate")),
        "active_date": _string_or_none(item.get("activeDate")),
        "timeliness": _string_or_none(item.get("timelinessName")),
        "level": _string_or_none(item.get("levelName")),
        "issued_no": _string_or_none(item.get("issuedNo")),
        "highlights": normalized_highlights,
    }


def _normalize_case_search_item(item: dict[str, Any]) -> CaseSearchItem:
    case_id = _string_or_none(item.get("id"))
    title = _string_or_none(item.get("title"))
    content = _string_or_none(item.get("content"))
    if case_id is None or title is None or content is None:
        raise DeliLegalResponseError("类案检索结果缺少 id、title 或 content 字段。")

    return {
        "id": case_id,
        "title": title,
        "court": _string_or_none(item.get("court")),
        "case_number": _string_or_none(item.get("caseNumber")),
        "judgement_date": _string_or_none(item.get("judgementDate")),
        "judgement_type": _string_or_none(item.get("judgementType")),
        "case_type": _string_or_none(item.get("caseType")),
        "cause": _string_or_none(item.get("cause")),
        "level_of_trial": _string_or_none(item.get("levelOfTrial")),
        "publish_type_name": _string_or_none(item.get("publishTypeName")),
        "content": content,
    }


def _normalize_law_detail_item(body: dict[str, Any]) -> LawDetailItem:
    law_id = (
        _string_or_none(body.get("lawsId"))
        or _string_or_none(body.get("lawId"))
        or _string_or_none(body.get("id"))
    )
    title = _string_or_none(body.get("title"))
    content = _string_or_none(body.get("lawDetailContent"))
    if law_id is None or title is None or content is None:
        raise DeliLegalResponseError("法规详情结果缺少 lawsId/title/lawDetailContent 字段。")

    return {
        "id": law_id,
        "title": title,
        "publisher": _string_or_none(body.get("publisherName")),
        "publish_date": _string_or_none(body.get("publishDate")),
        "active_date": _string_or_none(body.get("activeDate")),
        "timeliness": _string_or_none(body.get("timelinessName")),
        "level": _string_or_none(body.get("levelName")),
        "issued_no": _string_or_none(body.get("issuedNo")),
        "content": content,
    }


class DeliLegalClient:
    """Thin client around the official DeliLegal retrieval APIs."""

    def __init__(
        self,
        credentials: DeliLegalCredentials,
        *,
        base_url: str = DEFAULT_DELILEGAL_BASE_URL,
        timeout: float = DEFAULT_DELILEGAL_TIMEOUT,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._credentials = credentials
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            transport=transport,
        )

    @classmethod
    def from_env(
        cls,
        *,
        guide_docx: str | Path | None = None,
        timeout: float = DEFAULT_DELILEGAL_TIMEOUT,
        transport: httpx.BaseTransport | None = None,
    ) -> "DeliLegalClient":
        """Create a client from environment variables or the official guide docx."""

        credentials = load_delilegal_credentials(guide_docx=guide_docx)
        base_url = os.getenv("DELILEGAL_BASE_URL", DEFAULT_DELILEGAL_BASE_URL)
        return cls(
            credentials,
            base_url=base_url,
            timeout=timeout,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "DeliLegalClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "appid": self._credentials.app_id,
            "secret": self._credentials.secret,
        }

    def _request(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        """Send a request and convert remote failures into explicit domain errors."""

        logger.info("DeliLegal request start method=%s url=%s", method, url)
        try:
            response = self._client.request(method, url, headers=self.headers, **kwargs)
        except httpx.RequestError as exc:
            logger.warning("DeliLegal transport failure method=%s url=%s error=%s", method, url, exc)
            raise DeliLegalTransportError(f"请求得理开放平台失败: {exc}") from exc

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "DeliLegal HTTP failure method=%s url=%s status=%s",
                method,
                url,
                exc.response.status_code,
            )
            raise DeliLegalHTTPError(
                f"得理开放平台返回 HTTP {exc.response.status_code}: {exc.response.text}"
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise DeliLegalResponseError("得理开放平台返回的不是合法 JSON。") from exc

        if not isinstance(payload, dict):
            raise DeliLegalResponseError(f"接口返回不是 JSON 对象: {payload!r}")

        success = payload.get("success")
        code = payload.get("code")
        if success is False or (isinstance(code, int) and code != 0 and success is not True):
            message = payload.get("msg") or "得理开放平台返回业务错误。"
            logger.warning(
                "DeliLegal API failure method=%s url=%s code=%s message=%s",
                method,
                url,
                code,
                message,
            )
            raise DeliLegalAPIError(f"得理开放平台业务失败 code={code}: {message}")

        logger.info("DeliLegal request success method=%s url=%s", method, url)
        return payload

    def search_cases(
        self,
        *,
        keyword_arr: list[str] | None = None,
        long_text: str | None = None,
        page_no: int = 1,
        page_size: int = 5,
        sort_field: str = "correlation",
        sort_order: str = "desc",
        case_year_start: int | None = None,
        case_year_end: int | None = None,
        court_level_arr: list[str] | None = None,
        judgement_type_arr: list[str] | None = None,
    ) -> CaseSearchResult:
        """Search similar cases and return a normalized result shape."""

        payload = build_case_search_payload(
            keyword_arr=keyword_arr,
            long_text=long_text,
            page_no=page_no,
            page_size=page_size,
            sort_field=sort_field,
            sort_order=sort_order,
            case_year_start=case_year_start,
            case_year_end=case_year_end,
            court_level_arr=court_level_arr,
            judgement_type_arr=judgement_type_arr,
        )
        raw_payload = self._request("POST", "/api/qa/v3/search/queryListCase", json=payload)
        body = _ensure_mapping(raw_payload.get("body"), context="类案检索 body")
        items = [
            _normalize_case_search_item(_ensure_mapping(item, context="类案检索列表项"))
            for item in _ensure_list(body.get("data"), context="类案检索 body.data")
        ]
        return {
            "query_id": _string_or_none(body.get("queryId")),
            "total_count": _int_or_zero(body.get("totalCount")),
            "total_page": _int_or_zero(body.get("totalPage")),
            "items": items,
        }

    def search_laws(
        self,
        *,
        keywords: list[str],
        field_name: str = "semantic",
        page_no: int = 1,
        page_size: int = 5,
        sort_field: str = "correlation",
        sort_order: str = "desc",
    ) -> LawSearchResult:
        """Search laws and return a normalized result shape."""

        payload = build_law_search_payload(
            keywords=keywords,
            field_name=field_name,
            page_no=page_no,
            page_size=page_size,
            sort_field=sort_field,
            sort_order=sort_order,
        )
        raw_payload = self._request("POST", "/api/qa/v3/search/queryListLaw", json=payload)
        body = _ensure_mapping(raw_payload.get("body"), context="法规检索 body")
        items = [
            _normalize_law_search_item(_ensure_mapping(item, context="法规检索列表项"))
            for item in _ensure_list(body.get("data"), context="法规检索 body.data")
        ]
        return {
            "query_id": _string_or_none(body.get("queryId")),
            "total_count": _int_or_zero(body.get("totalCount")),
            "total_page": _int_or_zero(body.get("totalPage")),
            "items": items,
        }

    def get_law_detail(self, law_id: str, *, merge: bool = True) -> LawDetailItem:
        """Load a law detail by law id and normalize the official response."""

        raw_payload = self._request(
            "GET",
            "/api/qa/v3/search/lawInfo",
            params={"lawId": law_id, "merge": str(merge).lower()},
        )
        body = _ensure_mapping(raw_payload.get("body"), context="法规详情 body")
        return _normalize_law_detail_item(body)
