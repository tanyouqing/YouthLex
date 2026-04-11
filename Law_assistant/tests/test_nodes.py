import pytest

from app.services.delilegal_client import (
    DeliLegalAPIError,
    DeliLegalConfigError,
    DeliLegalHTTPError,
    DeliLegalResponseError,
    DeliLegalTransportError,
)
from app.graphs.legal_triage.graph import create_initial_state, create_next_turn_state
from app.graphs.legal_triage.nodes import deliverables_node, legal_grounding_node, slot_filling_node
from app.schemas.triage import TriageRequest, TriageScenario


def build_state():
    request = TriageRequest(
        user_input="老板拖欠兼职工资",
        scenario=TriageScenario.LABOR,
        session_id="node-test",
    )
    state = create_initial_state(request)
    state["action_steps"] = ["先发催告函"]
    return state


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
                "title": "学生兼职工资纠纷案",
                "court": "示例法院",
                "case_number": "（2024）示01号",
                "judgement_date": "2024-03-01",
                "judgement_type": "判决书",
                "case_type": "劳动争议",
                "summary": "法院支持劳动者追索工资。",
                "excerpt": "法院支持劳动者追索工资。",
                "full_content": "完整案例内容",
                "judgment": "法院判令支付拖欠工资。",
                "takeaway": "保留聊天记录和考勤证据。",
            }
        ]


class FakeKnowledgeBaseEmpty(FakeKnowledgeBaseSuccess):
    def retrieve_legal_basis(self, query: str, scenario: str | None = None):
        return []

    def retrieve_similar_cases(self, query: str, scenario: str | None = None):
        return []


class FakeKnowledgeBaseFailure:
    def __enter__(self):
        raise RuntimeError("kb unavailable")

    def __exit__(self, *_args):
        return None


def make_retrieval_failure_class(error: Exception):
    class _Failure:
        def __enter__(self):
            raise error

        def __exit__(self, *_args):
            return None

    return _Failure


class FakeLegalTriageLLM:
    def generate_legal_grounding(
        self,
        user_input: str,
        scenario: str,
        legal_basis_items: list[dict],
        retrieval_status: str,
    ):
        assert retrieval_status in {"success", "empty", "unavailable"}
        return type(
            "Output",
            (),
            {
                "assistant_message": f"grounding-{retrieval_status}",
                "legal_basis_notes": ["note"] if legal_basis_items else ["fallback-note"],
            },
        )()

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
    ):
        assert retrieval_status in {"success", "empty", "unavailable"}
        return type(
            "Output",
            (),
            {
                "assistant_message": f"deliverables-{retrieval_status}",
                "demand_letter": draft_demand_letter,
                "similar_cases": [],
            },
        )()


def test_legal_grounding_uses_retrieved_laws(monkeypatch) -> None:
    from app.graphs.legal_triage import nodes

    monkeypatch.setattr(nodes, "LegalKnowledgeBase", FakeKnowledgeBaseSuccess)
    monkeypatch.setattr(nodes, "get_legal_triage_llm", lambda: FakeLegalTriageLLM())

    result = legal_grounding_node(build_state())

    assert result["legal_basis"][0]["id"] == "law-1"
    assert result["legal_basis_notes"] == ["note"]
    assert result["assistant_message"] == "grounding-success"


def test_legal_grounding_degrades_on_retrieval_failure(monkeypatch) -> None:
    from app.graphs.legal_triage import nodes

    monkeypatch.setattr(nodes, "LegalKnowledgeBase", FakeKnowledgeBaseFailure)
    monkeypatch.setattr(nodes, "get_legal_triage_llm", lambda: FakeLegalTriageLLM())

    result = legal_grounding_node(build_state())

    assert result["legal_basis"] == []
    assert result["legal_basis_notes"] == ["fallback-note"]
    assert result["assistant_message"] == "grounding-unavailable"


@pytest.mark.parametrize(
    "error",
    [
        DeliLegalConfigError("missing credentials"),
        DeliLegalTransportError("transport"),
        DeliLegalHTTPError("http"),
        DeliLegalAPIError("api"),
        DeliLegalResponseError("response"),
    ],
)
def test_legal_grounding_degrades_on_classified_retrieval_errors(monkeypatch, error) -> None:
    from app.graphs.legal_triage import nodes

    monkeypatch.setattr(nodes, "LegalKnowledgeBase", make_retrieval_failure_class(error))
    monkeypatch.setattr(nodes, "get_legal_triage_llm", lambda: FakeLegalTriageLLM())

    result = legal_grounding_node(build_state())

    assert result["legal_basis"] == []
    assert result["assistant_message"] == "grounding-unavailable"


def test_deliverables_prefers_retrieved_cases(monkeypatch) -> None:
    from app.graphs.legal_triage import nodes

    monkeypatch.setattr(nodes, "LegalKnowledgeBase", FakeKnowledgeBaseSuccess)
    monkeypatch.setattr(nodes, "get_legal_triage_llm", lambda: FakeLegalTriageLLM())
    state = build_state()
    state["legal_basis"] = [
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
    state["legal_basis_notes"] = ["note"]

    result = deliverables_node(state)

    assert "deliverables-success" in result["assistant_message"]
    assert "催告函" in result["demand_letter"]
    assert result["similar_cases"][0]["title"] == "学生兼职工资纠纷案"
    assert "案情摘要" in result["similar_cases"][0]["summary"]


def test_deliverables_returns_placeholder_when_cases_empty(monkeypatch) -> None:
    from app.graphs.legal_triage import nodes

    monkeypatch.setattr(nodes, "LegalKnowledgeBase", FakeKnowledgeBaseEmpty)
    monkeypatch.setattr(nodes, "get_legal_triage_llm", lambda: FakeLegalTriageLLM())
    state = build_state()
    state["legal_basis"] = []
    state["legal_basis_notes"] = ["fallback-note"]

    result = deliverables_node(state)

    assert "deliverables-empty" in result["assistant_message"]
    assert result["similar_cases"][0]["title"] == "示例案例占位"


@pytest.mark.parametrize(
    "error",
    [
        DeliLegalConfigError("missing credentials"),
        DeliLegalTransportError("transport"),
        DeliLegalHTTPError("http"),
        DeliLegalAPIError("api"),
        DeliLegalResponseError("response"),
    ],
)
def test_deliverables_degrades_on_classified_retrieval_errors(monkeypatch, error) -> None:
    from app.graphs.legal_triage import nodes

    monkeypatch.setattr(nodes, "LegalKnowledgeBase", make_retrieval_failure_class(error))
    monkeypatch.setattr(nodes, "get_legal_triage_llm", lambda: FakeLegalTriageLLM())
    state = build_state()
    state["legal_basis"] = []
    state["legal_basis_notes"] = ["fallback-note"]

    result = deliverables_node(state)

    assert "deliverables-unavailable" in result["assistant_message"]
    assert result["similar_cases"]


def test_slot_filling_sets_single_requested_slot_for_intro_turn() -> None:
    state = build_state()
    state["empathy_message"] = "安抚阶段"
    state["legal_grounding_message"] = "定性阶段"
    state["legal_basis_notes"] = ["note"]

    result = slot_filling_node(state)

    assert result["requested_slot"] == "time_place"
    assert result["awaiting_confirmation"] is False
    assert "安抚阶段" in result["assistant_message"]
    assert "接下来我只确认一项" in result["assistant_message"]


def test_slot_filling_marks_requested_slot_unavailable_and_moves_on() -> None:
    intro_state = slot_filling_node(
        {
            **build_state(),
            "empathy_message": "安抚阶段",
            "legal_grounding_message": "定性阶段",
            "legal_basis_notes": ["note"],
        }
    )
    next_turn_state = create_next_turn_state(
        {**build_state(), **intro_state, "intro_completed": True},
        TriageRequest(
            user_input="具体时间我记不清了",
            session_id="node-test",
        ),
    )

    result = slot_filling_node(next_turn_state)

    assert "time_place" in result["unavailable_slots"]
    assert result["requested_slot"] == "amount"
    assert "暂时无法补充" in result["assistant_message"]


def test_slot_filling_moves_on_after_generic_counterparty_is_collected() -> None:
    base_state = create_initial_state(
        TriageRequest(
            user_input="面里吃出虫子，拒绝赔偿",
            scenario=TriageScenario.CONSUMER,
            session_id="node-counterparty",
        )
    )
    intro_state = slot_filling_node(
        {
            **base_state,
            "empathy_message": "安抚阶段",
            "legal_grounding_message": "定性阶段",
            "legal_basis_notes": ["note"],
        }
    )
    assert intro_state["requested_slot"] == "counterparty"

    next_turn_state = create_next_turn_state(
        {**base_state, **intro_state, "intro_completed": True},
        TriageRequest(
            user_input="商家",
            session_id="node-counterparty",
        ),
    )

    result = slot_filling_node(next_turn_state)

    assert next_turn_state["slot_statuses"]["counterparty"] == "usable"
    assert result["requested_slot"] == "time_place"
    assert "后续如果有更精确材料还可以继续补" in result["assistant_message"]


def test_slot_filling_moves_on_after_approximate_amount_is_collected() -> None:
    first_turn_state = slot_filling_node(
        {
            **build_state(),
            "empathy_message": "安抚阶段",
            "legal_grounding_message": "定性阶段",
            "legal_basis_notes": ["note"],
        }
    )
    time_place_turn = create_next_turn_state(
        {**build_state(), **first_turn_state, "intro_completed": True},
        TriageRequest(
            user_input="昨天晚上在学校附近便利店上班",
            session_id="node-amount",
        ),
    )
    amount_prompt_state = slot_filling_node(time_place_turn)
    assert amount_prompt_state["requested_slot"] == "amount"

    amount_turn = create_next_turn_state(
        {**time_place_turn, **amount_prompt_state, "intro_completed": True},
        TriageRequest(
            user_input="三十多块钱",
            session_id="node-amount",
        ),
    )
    result = slot_filling_node(amount_turn)

    assert amount_turn["slot_statuses"]["amount"] == "usable"
    assert amount_turn["evidence_slots"]["amount"] == "约30余元"
    assert result["requested_slot"] == "agreement"
