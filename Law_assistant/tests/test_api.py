import json

from fastapi.testclient import TestClient

from app.main import app
from app.services.llm_client import (
    ActionPlanOutput,
    DeliverablesOutput,
    EmpathyOutput,
    LegalGroundingOutput,
)
from app.services.session_store import get_session_store


client = TestClient(app)


class FakeLegalTriageLLM:
    def generate_empathy(self, user_input: str, scenario: str) -> EmpathyOutput:
        return EmpathyOutput(assistant_message=f"安抚回复: {scenario} / {user_input}")

    def generate_legal_grounding(
        self,
        user_input: str,
        scenario: str,
        legal_basis_items: list[dict],
        retrieval_status: str,
    ) -> LegalGroundingOutput:
        return LegalGroundingOutput(
            assistant_message=f"初步法律定性-{retrieval_status}",
            legal_basis_notes=["要点1", "要点2"],
        )

    def generate_action_plan(
        self,
        user_input: str,
        scenario: str,
        evidence_slots: dict,
        missing_slots: list[str],
        legal_basis_notes: list[str],
        suggested_steps: list[str],
    ) -> ActionPlanOutput:
        return ActionPlanOutput(
            assistant_message="行动建议",
            action_steps=suggested_steps,
        )

    def generate_deliverables(
        self,
        user_input: str,
        scenario: str,
        action_steps: list[str],
        legal_basis_items: list[dict],
        legal_basis_notes: list[str],
        similar_case_items: list[dict],
        retrieval_status: str,
        evidence_slots: dict,
        draft_demand_letter: str,
    ) -> DeliverablesOutput:
        return DeliverablesOutput(
            assistant_message="最终建议",
            demand_letter=draft_demand_letter,
            similar_cases=[],
        )


class FakeKnowledgeBaseSuccess:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def retrieve_legal_basis(self, query: str, scenario: str | None = None):
        return [
            {
                "id": "law-1",
                "title": "劳动合同法",
                "publisher": "全国人大常委会",
                "publish_date": "2012-12-28",
                "active_date": "2013-07-01",
                "timeliness": "现行有效",
                "level": "法律",
                "snippet": "用人单位应当按时足额支付劳动报酬。",
                "content": "法规正文",
            }
        ]

    def retrieve_similar_cases(self, query: str, scenario: str | None = None):
        return [
            {
                "id": "case-1",
                "title": "案例 A",
                "court": "示例法院",
                "case_number": "（2024）示01号",
                "judgement_date": "2024-03-01",
                "judgement_type": "判决书",
                "case_type": "劳动争议",
                "summary": "摘要 A",
                "excerpt": "摘要 A",
                "full_content": "完整案例内容",
                "judgment": "结果 A",
                "takeaway": "启示 A",
            }
        ]


class FakeKnowledgeBaseFailure:
    def __enter__(self):
        raise RuntimeError("kb unavailable")

    def __exit__(self, *_args):
        return None


def parse_sse_events(raw_text: str) -> list[dict]:
    events: list[dict] = []
    for block in raw_text.strip().split("\n\n"):
        if not block.strip():
            continue
        event_name = None
        data_payload = None
        for line in block.splitlines():
            if line.startswith("event: "):
                event_name = line.removeprefix("event: ").strip()
            if line.startswith("data: "):
                data_payload = json.loads(line.removeprefix("data: ").strip())
        if event_name is not None and data_payload is not None:
            events.append({"event": event_name, "data": data_payload})
    return events


def _prepare_dependencies(monkeypatch, knowledge_base_cls) -> None:
    from app.graphs.legal_triage import nodes

    get_session_store().clear()
    nodes.get_legal_triage_llm.cache_clear()
    monkeypatch.setattr(nodes, "get_legal_triage_llm", lambda: FakeLegalTriageLLM())
    monkeypatch.setattr(nodes, "LegalKnowledgeBase", knowledge_base_cls)


def test_health() -> None:
    get_session_store().clear()
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["model"] == "MiniMax-M2.5"


def test_triage_run_returns_intro_collection_shape(monkeypatch) -> None:
    _prepare_dependencies(monkeypatch, FakeKnowledgeBaseSuccess)

    response = client.post(
        "/api/v1/triage/run",
        json={"user_input": "老板拖欠我工资", "scenario": "labor", "session_id": "demo"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == "demo"
    assert payload["scenario"] == "labor"
    assert payload["scenario_label"] == "劳动与兼职纠纷"
    assert payload["current_stage"] == "slot_filling"
    assert "安抚回复" in payload["assistant_message"]
    assert "初步法律定性-success" in payload["assistant_message"]
    assert payload["assistant_turn"]["stage"] == "slot_filling"
    assert payload["conversation_history"][-1]["role"] == "assistant"
    assert payload["progress"]["deliverables_ready"] is False
    assert payload["progress"]["next_stage"] == "slot_filling"
    assert payload["frontend"]["display_mode"] == "slot_collection"
    assert len(payload["frontend"]["follow_up_questions"]) == 1
    assert payload["sidebar"]["demand_letter"] in {"", None}
    assert payload["sidebar"]["similar_cases"] == []


def test_triage_run_degrades_when_retrieval_fails(monkeypatch) -> None:
    _prepare_dependencies(monkeypatch, FakeKnowledgeBaseFailure)

    response = client.post(
        "/api/v1/triage/run",
        json={"user_input": "老板拖欠我工资", "scenario": "labor", "session_id": "demo-fail"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == "demo-fail"
    assert payload["current_stage"] == "slot_filling"
    assert "初步法律定性-unavailable" in payload["assistant_message"]
    assert payload["frontend"]["suggested_actions"]


def test_triage_run_auto_routes_scenario(monkeypatch) -> None:
    _prepare_dependencies(monkeypatch, FakeKnowledgeBaseSuccess)

    response = client.post(
        "/api/v1/triage/run",
        json={"user_input": "老板拖欠我兼职工资，还把我拉黑了", "session_id": "demo-route"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == "demo-route"
    assert payload["scenario"] == "labor"
    assert payload["scenario_label"] == "劳动与兼职纠纷"


def test_triage_run_softly_overrides_scenario_hint_and_keeps_welcome_message(monkeypatch) -> None:
    _prepare_dependencies(monkeypatch, FakeKnowledgeBaseSuccess)

    response = client.post(
        "/api/v1/triage/run",
        json={
            "user_input": "老板拖欠我兼职工资，还把我拉黑了",
            "scenario_hint": "consumer",
            "session_id": "hint-route",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["scenario"] == "labor"
    assert payload["conversation_history"][0]["role"] == "assistant"
    assert payload["conversation_history"][0]["content"] == "遇到维权困难了？跟我讲讲，我来帮你解决"
    assert payload["conversation_history"][1]["role"] == "user"


def test_triage_run_keeps_scenario_hint_when_input_is_ambiguous(monkeypatch) -> None:
    _prepare_dependencies(monkeypatch, FakeKnowledgeBaseSuccess)

    response = client.post(
        "/api/v1/triage/run",
        json={
            "user_input": "对方一直拖着不处理，我现在很着急",
            "scenario_hint": "labor",
            "session_id": "hint-keep",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["scenario"] == "labor"


def test_triage_run_uses_auto_route_when_scenario_hint_is_other(monkeypatch) -> None:
    _prepare_dependencies(monkeypatch, FakeKnowledgeBaseSuccess)

    response = client.post(
        "/api/v1/triage/run",
        json={
            "user_input": "房东不退押金，还说家电坏了要我赔",
            "scenario_hint": "other",
            "session_id": "hint-other",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["scenario"] == "housing"


def test_triage_run_persists_session_slots_across_turns(monkeypatch) -> None:
    _prepare_dependencies(monkeypatch, FakeKnowledgeBaseSuccess)

    first_response = client.post(
        "/api/v1/triage/run",
        json={"user_input": "老板拖欠我兼职工资", "session_id": "multi-turn"},
    )
    assert first_response.status_code == 200

    second_response = client.post(
        "/api/v1/triage/run",
        json={
            "user_input": "说好一天150元，我有微信聊天截图和转账记录",
            "session_id": "multi-turn",
        },
    )

    assert second_response.status_code == 200
    payload = second_response.json()
    assert payload["scenario"] == "labor"
    assert payload["current_stage"] == "slot_filling"
    assert payload["sidebar"]["evidence_slots"]["amount"] == "150元"
    assert payload["sidebar"]["evidence_slots"]["agreement"] is not None
    assert "聊天记录" in payload["sidebar"]["evidence_slots"]["existing_evidence"]
    assert "转账记录" in payload["sidebar"]["evidence_slots"]["existing_evidence"]
    assert payload["progress"]["missing_slots"]
    assert len(payload["frontend"]["follow_up_questions"]) == 1


def test_triage_run_moves_to_next_slot_after_shop_name_response(monkeypatch) -> None:
    _prepare_dependencies(monkeypatch, FakeKnowledgeBaseSuccess)

    first_response = client.post(
        "/api/v1/triage/run",
        json={
            "user_input": "昨天晚上在学校北门吃面时发现虫子，商家拒绝赔偿",
            "scenario": "consumer",
            "session_id": "food-counterparty",
        },
    )
    assert first_response.status_code == 200

    second_response = client.post(
        "/api/v1/triage/run",
        json={
            "user_input": "阿慧面馆",
            "session_id": "food-counterparty",
        },
    )

    assert second_response.status_code == 200
    payload = second_response.json()
    assert payload["sidebar"]["evidence_slots"]["counterparty"] == "阿慧面馆"
    assert payload["frontend"]["follow_up_questions"][0].startswith("这次纠纷大概涉及多少钱")
    assert payload["progress"]["missing_slots"][0] == "amount"


def test_triage_run_accepts_approximate_amount_and_moves_on(monkeypatch) -> None:
    _prepare_dependencies(monkeypatch, FakeKnowledgeBaseSuccess)

    client.post(
        "/api/v1/triage/run",
        json={
            "user_input": "昨天晚上在学校北门吃面时发现虫子，商家拒绝赔偿",
            "scenario": "consumer",
            "session_id": "food-amount",
        },
    )
    client.post(
        "/api/v1/triage/run",
        json={
            "user_input": "阿慧面馆",
            "session_id": "food-amount",
        },
    )

    amount_response = client.post(
        "/api/v1/triage/run",
        json={
            "user_input": "三十多块钱",
            "session_id": "food-amount",
        },
    )

    assert amount_response.status_code == 200
    payload = amount_response.json()
    assert payload["sidebar"]["evidence_slots"]["amount"] == "约30余元"
    assert payload["frontend"]["follow_up_questions"][0].startswith("你们当时是怎么约定的")


def test_triage_run_final_summary_mentions_soft_gap_notes(monkeypatch) -> None:
    _prepare_dependencies(monkeypatch, FakeKnowledgeBaseSuccess)

    client.post(
        "/api/v1/triage/run",
        json={
            "user_input": "昨天晚上在学校北门吃面时发现虫子，商家拒绝赔偿",
            "scenario": "consumer",
            "session_id": "food-summary",
        },
    )
    client.post(
        "/api/v1/triage/run",
        json={
            "user_input": "阿慧面馆",
            "session_id": "food-summary",
        },
    )
    client.post(
        "/api/v1/triage/run",
        json={
            "user_input": "餐费16元，去医院花了300多",
            "session_id": "food-summary",
        },
    )

    final_response = client.post(
        "/api/v1/triage/run",
        json={"user_input": "开始整理", "session_id": "food-summary"},
    )

    assert final_response.status_code == 200
    payload = final_response.json()
    assert payload["current_stage"] == "deliverables"
    assert "仍可进一步明确" in payload["assistant_message"]
    assert "金额目前已按费用项先整理" in payload["assistant_message"]


def test_triage_run_generates_deliverables_after_explicit_finalize(monkeypatch) -> None:
    _prepare_dependencies(monkeypatch, FakeKnowledgeBaseSuccess)

    first_response = client.post(
        "/api/v1/triage/run",
        json={"user_input": "老板拖欠我兼职工资", "session_id": "finalize-turn"},
    )
    assert first_response.status_code == 200

    second_response = client.post(
        "/api/v1/triage/run",
        json={
            "user_input": "说好一天150元，我有微信聊天截图和转账记录，在学校附近便利店上班",
            "session_id": "finalize-turn",
        },
    )
    assert second_response.status_code == 200

    final_response = client.post(
        "/api/v1/triage/run",
        json={"user_input": "开始整理", "session_id": "finalize-turn"},
    )

    assert final_response.status_code == 200
    payload = final_response.json()
    assert payload["current_stage"] == "deliverables"
    assert payload["progress"]["deliverables_ready"] is True
    assert payload["sidebar"]["action_steps"]
    assert "催告函" in payload["sidebar"]["demand_letter"]
    assert payload["sidebar"]["similar_cases"][0]["title"] == "案例 A"
    assert "最终建议" in payload["assistant_message"]


def test_get_triage_session_returns_snapshot(monkeypatch) -> None:
    _prepare_dependencies(monkeypatch, FakeKnowledgeBaseSuccess)

    post_response = client.post(
        "/api/v1/triage/run",
        json={"user_input": "老板拖欠我工资", "scenario": "labor", "session_id": "snapshot"},
    )
    assert post_response.status_code == 200

    get_response = client.get("/api/v1/triage/session/snapshot")

    assert get_response.status_code == 200
    payload = get_response.json()
    assert payload["session_id"] == "snapshot"
    assert payload["assistant_turn"]["content"] == payload["assistant_message"]
    assert payload["conversation_history"][0]["role"] == "user"
    assert payload["conversation_history"][-1]["role"] == "assistant"


def test_get_triage_session_returns_404_when_missing() -> None:
    get_session_store().clear()

    response = client.get("/api/v1/triage/session/missing-session")

    assert response.status_code == 404
    assert response.json()["detail"] == "Session not found"


def test_triage_stream_returns_intro_stage_events_and_complete_payload(monkeypatch) -> None:
    _prepare_dependencies(monkeypatch, FakeKnowledgeBaseSuccess)

    response = client.post(
        "/api/v1/triage/stream",
        json={"user_input": "老板拖欠我工资", "scenario": "labor", "session_id": "stream-demo"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    events = parse_sse_events(response.text)

    assert events[0]["event"] == "session"
    assert events[0]["data"]["session_id"] == "stream-demo"
    assert events[1]["event"] == "stage_started"
    assert events[1]["data"]["stage"] == "empathy"
    assert events[2]["event"] == "stage_completed"
    assert events[2]["data"]["stage"] == "empathy"
    assert events[-1]["event"] == "complete"
    assert events[-1]["data"]["response"]["session_id"] == "stream-demo"
    assert events[-1]["data"]["response"]["current_stage"] == "slot_filling"
    assert events[-1]["data"]["response"]["conversation_history"][-1]["role"] == "assistant"


def test_triage_stream_returns_error_event_when_stage_crashes(monkeypatch) -> None:
    from app.graphs.legal_triage import graph

    _prepare_dependencies(monkeypatch, FakeKnowledgeBaseSuccess)
    original_sequence = graph.TRIAGE_NODE_SEQUENCE
    monkeypatch.setattr(
        graph,
        "TRIAGE_NODE_SEQUENCE",
        [
            *original_sequence[:2],
            ("slot_filling", lambda _state: (_ for _ in ()).throw(RuntimeError("stage boom"))),
            *original_sequence[3:],
        ],
    )

    response = client.post(
        "/api/v1/triage/stream",
        json={"user_input": "老板拖欠我工资", "scenario": "labor", "session_id": "stream-fail"},
    )

    assert response.status_code == 200
    events = parse_sse_events(response.text)
    assert events[-1]["event"] == "error"
    assert events[-1]["data"]["session_id"] == "stream-fail"
