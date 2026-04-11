from pathlib import Path
from zipfile import ZipFile

import httpx
import pytest

from app.services.delilegal_client import (
    DeliLegalAPIError,
    DeliLegalClient,
    DeliLegalConfigError,
    DeliLegalCredentials,
    DeliLegalHTTPError,
    DeliLegalResponseError,
    build_case_search_payload,
    build_law_search_payload,
    extract_credentials_from_guide_docx,
    extract_first_law_id,
    load_delilegal_credentials,
)
from app.services.knowledge_base import LegalKnowledgeBase


def make_client_with_payloads(payloads: list[dict]) -> DeliLegalClient:
    responses = iter(payloads)

    def handler(request: httpx.Request) -> httpx.Response:
        payload = next(responses)
        status_code = payload.pop("_status_code", 200)
        return httpx.Response(status_code, json=payload, request=request)

    return DeliLegalClient(
        DeliLegalCredentials(app_id="test-app-id", secret="test-secret"),
        transport=httpx.MockTransport(handler),
    )


def test_build_case_search_payload_contains_string_array() -> None:
    payload = build_case_search_payload(
        keyword_arr=["工伤保险", "上下班途中车祸"],
        page_size=3,
        court_level_arr=["1", "2"],
    )

    assert payload["pageNo"] == 1
    assert payload["pageSize"] == 3
    assert payload["condition"]["keywordArr"] == ["工伤保险", "上下班途中车祸"]
    assert payload["condition"]["courtLevelArr"] == ["1", "2"]


def test_build_case_search_payload_requires_query() -> None:
    with pytest.raises(ValueError):
        build_case_search_payload()


def test_build_law_search_payload_with_semantic_mode() -> None:
    payload = build_law_search_payload(
        keywords=["深圳市房地产相关的法律规定有哪些？"],
        field_name="semantic",
        page_size=2,
    )

    assert payload["pageSize"] == 2
    assert payload["condition"]["fieldName"] == "semantic"
    assert payload["condition"]["keywords"] == ["深圳市房地产相关的法律规定有哪些？"]


def test_extract_first_law_id_from_normalized_items() -> None:
    payload = {
        "items": [
            {"id": "law-id-001", "title": "测试法规"},
        ],
    }

    assert extract_first_law_id(payload) == "law-id-001"


def test_extract_credentials_from_guide_docx(tmp_path: Path) -> None:
    docx_path = tmp_path / "guide.docx"
    document_xml = """
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body>
        <w:p>
          <w:r><w:t>curl -X POST 'https://openapi.delilegal.com/api/qa/v3/search/queryListCase'</w:t></w:r>
        </w:p>
        <w:p>
          <w:r><w:t>-H "appid: demoAppId123"</w:t></w:r>
        </w:p>
        <w:p>
          <w:r><w:t>-H "secret: demoSecret456"</w:t></w:r>
        </w:p>
      </w:body>
    </w:document>
    """.strip()

    with ZipFile(docx_path, "w") as archive:
        archive.writestr("word/document.xml", document_xml)

    credentials = extract_credentials_from_guide_docx(docx_path)

    assert credentials.app_id == "demoAppId123"
    assert credentials.secret == "demoSecret456"


def test_load_delilegal_credentials_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DELILEGAL_APP_ID", "env-appid")
    monkeypatch.setenv("DELILEGAL_SECRET", "env-secret")

    credentials = load_delilegal_credentials()

    assert credentials.app_id == "env-appid"
    assert credentials.secret == "env-secret"


def test_load_delilegal_credentials_requires_input(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DELILEGAL_APP_ID", raising=False)
    monkeypatch.delenv("DELILEGAL_SECRET", raising=False)

    with pytest.raises(DeliLegalConfigError):
        load_delilegal_credentials()


def test_client_search_laws_normalizes_response() -> None:
    client = make_client_with_payloads(
        [
            {
                "success": True,
                "code": 0,
                "msg": "",
                "body": {
                    "queryId": "query-1",
                    "totalCount": 1,
                    "totalPage": 1,
                    "data": [
                        {
                            "id": "law-1",
                            "title": "测试法规",
                            "publisherName": "测试机关",
                            "publishDate": "2024-01-01",
                            "activeDate": "2024-01-02",
                            "timelinessName": "有效",
                            "levelName": "地方政府规章",
                            "issuedNo": "测试令第1号",
                            "highlights": ["亮点1"],
                        }
                    ],
                },
            }
        ]
    )

    result = client.search_laws(keywords=["租房押金"], field_name="semantic")

    assert result["query_id"] == "query-1"
    assert result["total_count"] == 1
    assert result["items"][0]["publisher"] == "测试机关"
    assert result["items"][0]["highlights"] == ["亮点1"]
    client.close()


def test_client_search_cases_normalizes_response() -> None:
    client = make_client_with_payloads(
        [
            {
                "success": True,
                "code": 0,
                "msg": "",
                "body": {
                    "queryId": "query-case",
                    "totalCount": 1,
                    "totalPage": 1,
                    "data": [
                        {
                            "id": "case-1",
                            "title": "测试案例",
                            "content": "这是一个测试案例的完整内容。",
                            "court": "测试法院",
                            "caseNumber": "（2024）测01号",
                            "judgementDate": "2024-02-01",
                            "judgementType": "判决书",
                            "caseType": "民事案件",
                            "cause": "租赁合同纠纷",
                            "levelOfTrial": "民事一审",
                            "publishTypeName": "普通案例",
                        }
                    ],
                },
            }
        ]
    )

    result = client.search_cases(long_text="押金不退怎么办")

    assert result["query_id"] == "query-case"
    assert result["items"][0]["court"] == "测试法院"
    assert result["items"][0]["content"] == "这是一个测试案例的完整内容。"
    client.close()


def test_client_get_law_detail_normalizes_response() -> None:
    client = make_client_with_payloads(
        [
            {
                "success": True,
                "code": 0,
                "msg": "",
                "body": {
                    "lawsId": "law-1",
                    "title": "测试法规",
                    "publisherName": "测试机关",
                    "publishDate": "2024-01-01",
                    "activeDate": "2024-01-02",
                    "timelinessName": "有效",
                    "levelName": "地方政府规章",
                    "issuedNo": "测试令第1号",
                    "lawDetailContent": "法规正文内容",
                },
            }
        ]
    )

    result = client.get_law_detail("law-1")

    assert result["id"] == "law-1"
    assert result["content"] == "法规正文内容"
    client.close()


def test_knowledge_base_retrieve_legal_basis_uses_detail_linking() -> None:
    client = make_client_with_payloads(
        [
            {
                "success": True,
                "code": 0,
                "msg": "",
                "body": {
                    "queryId": "law-query",
                    "totalCount": 1,
                    "totalPage": 1,
                    "data": [
                        {
                            "id": "law-1",
                            "title": "测试法规",
                            "publisherName": "测试机关",
                            "publishDate": "2024-01-01",
                            "activeDate": "2024-01-02",
                            "timelinessName": "有效",
                            "levelName": "地方政府规章",
                            "issuedNo": "测试令第1号",
                            "highlights": [],
                        }
                    ],
                },
            },
            {
                "success": True,
                "code": 0,
                "msg": "",
                "body": {
                    "lawsId": "law-1",
                    "title": "测试法规",
                    "publisherName": "测试机关",
                    "publishDate": "2024-01-01",
                    "activeDate": "2024-01-02",
                    "timelinessName": "有效",
                    "levelName": "地方政府规章",
                    "issuedNo": "测试令第1号",
                    "lawDetailContent": "这是法规正文内容，用于生成 snippet。",
                },
            },
        ]
    )

    knowledge_base = LegalKnowledgeBase(client=client)

    items = knowledge_base.retrieve_legal_basis("兼职工资拖欠")

    assert items[0]["id"] == "law-1"
    assert "法规正文内容" in (items[0]["content"] or "")
    assert items[0]["snippet"]
    knowledge_base.close()


def test_knowledge_base_retrieve_similar_cases_returns_structured_items() -> None:
    client = make_client_with_payloads(
        [
            {
                "success": True,
                "code": 0,
                "msg": "",
                "body": {
                    "queryId": "case-query",
                    "totalCount": 1,
                    "totalPage": 1,
                    "data": [
                        {
                            "id": "case-1",
                            "title": "测试案例",
                            "content": "这是一个测试案例的完整内容，用于生成摘要。",
                            "court": "测试法院",
                            "caseNumber": "（2024）测01号",
                            "judgementDate": "2024-02-01",
                            "judgementType": "判决书",
                            "caseType": "民事案件",
                            "cause": "租赁合同纠纷",
                            "levelOfTrial": "民事一审",
                            "publishTypeName": "普通案例",
                        }
                    ],
                },
            }
        ]
    )

    knowledge_base = LegalKnowledgeBase(client=client)

    items = knowledge_base.retrieve_similar_cases("房东不退押金")

    assert items[0]["title"] == "测试案例"
    assert items[0]["full_content"].startswith("这是一个测试案例")
    assert items[0]["judgment"] == "判决书"
    knowledge_base.close()


def test_knowledge_base_returns_empty_list_on_empty_result() -> None:
    client = make_client_with_payloads(
        [
            {
                "success": True,
                "code": 0,
                "msg": "",
                "body": {
                    "queryId": "empty-query",
                    "totalCount": 0,
                    "totalPage": 0,
                    "data": [],
                },
            }
        ]
    )

    knowledge_base = LegalKnowledgeBase(client=client)

    assert knowledge_base.retrieve_similar_cases("没有案例") == []
    knowledge_base.close()


def test_client_raises_api_error_when_success_false() -> None:
    client = make_client_with_payloads(
        [
            {
                "success": False,
                "code": 401,
                "msg": "鉴权失败",
                "body": {},
            }
        ]
    )

    with pytest.raises(DeliLegalAPIError):
        client.search_laws(keywords=["测试"])
    client.close()


def test_client_raises_http_error_on_non_2xx() -> None:
    client = make_client_with_payloads(
        [
            {
                "_status_code": 500,
                "error": "server error",
            }
        ]
    )

    with pytest.raises(DeliLegalHTTPError):
        client.search_laws(keywords=["测试"])
    client.close()


def test_client_raises_response_error_on_missing_fields() -> None:
    client = make_client_with_payloads(
        [
            {
                "success": True,
                "code": 0,
                "msg": "",
                "body": {
                    "queryId": "bad-shape",
                    "totalCount": 1,
                    "totalPage": 1,
                    "data": [
                        {
                            "title": "缺 id 的法规",
                        }
                    ],
                },
            }
        ]
    )

    with pytest.raises(DeliLegalResponseError):
        client.search_laws(keywords=["测试"])
    client.close()
