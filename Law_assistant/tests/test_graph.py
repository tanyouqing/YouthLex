from app.graphs.legal_triage import nodes
from app.graphs.legal_triage.graph import (
    WELCOME_MESSAGE,
    build_graph,
    create_initial_state,
    create_next_turn_state,
    finalize_triage_state,
    iterate_legal_triage,
    run_legal_triage,
)
from app.schemas.triage import TriageRequest, TriageScenario
from app.services.llm_client import (
    ActionPlanOutput,
    DeliverablesOutput,
    EmpathyOutput,
    LegalGroundingOutput,
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


class FakeKnowledgeBaseFailure:
    def __enter__(self):
        raise RuntimeError("kb unavailable")

    def __exit__(self, *_args):
        return None


class FakeLegalTriageLLM:
    def generate_empathy(self, user_input: str, scenario: str) -> EmpathyOutput:
        return EmpathyOutput(assistant_message="安抚阶段")

    def generate_legal_grounding(
        self,
        user_input: str,
        scenario: str,
        legal_basis_items: list[dict],
        retrieval_status: str,
    ) -> LegalGroundingOutput:
        assert retrieval_status in {"success", "empty", "unavailable"}
        return LegalGroundingOutput(
            assistant_message=f"定性阶段-{retrieval_status}",
            legal_basis_notes=["依据一", "依据二"] if legal_basis_items else ["暂无检索依据"],
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
            assistant_message="SOP 阶段",
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
        assert retrieval_status in {"success", "empty", "unavailable"}
        return DeliverablesOutput(
            assistant_message=f"交付物阶段-{retrieval_status}",
            demand_letter=draft_demand_letter,
            similar_cases=(
                []
                if similar_case_items
                else [
                    {
                        "title": "模型回退案例",
                        "summary": "摘要",
                        "judgment": "结果",
                        "takeaway": "启示",
                    }
                ]
            ),
        )


def test_graph_compiles() -> None:
    graph = build_graph()

    assert graph is not None


def test_graph_first_turn_stops_at_slot_filling(monkeypatch) -> None:
    nodes.get_legal_triage_llm.cache_clear()
    monkeypatch.setattr(nodes, "get_legal_triage_llm", lambda: FakeLegalTriageLLM())
    monkeypatch.setattr(nodes, "LegalKnowledgeBase", FakeKnowledgeBaseSuccess)

    request = TriageRequest(
        user_input="房东不退押金",
        scenario=TriageScenario.HOUSING,
        session_id="graph-test",
    )
    initial_state = create_initial_state(request)

    final_state = run_legal_triage(initial_state)

    assert final_state["session_id"] == "graph-test"
    assert final_state["scenario"] == "housing"
    assert final_state["current_stage"] == "slot_filling"
    assert "安抚阶段" in final_state["assistant_message"]
    assert "定性阶段-success" in final_state["assistant_message"]
    assert final_state["requested_slot"] == "time_place"
    assert final_state["action_steps"] == []
    assert final_state["demand_letter"] == ""


def test_graph_uses_scenario_hint_and_persists_welcome_message(monkeypatch) -> None:
    nodes.get_legal_triage_llm.cache_clear()
    monkeypatch.setattr(nodes, "get_legal_triage_llm", lambda: FakeLegalTriageLLM())
    monkeypatch.setattr(nodes, "LegalKnowledgeBase", FakeKnowledgeBaseSuccess)

    request = TriageRequest(
        user_input="老板拖欠我兼职工资，还把我拉黑了",
        scenario_hint=TriageScenario.CONSUMER,
        session_id="graph-hint",
    )
    initial_state = create_initial_state(request)
    final_state = run_legal_triage(initial_state)
    persisted_state = finalize_triage_state(final_state)

    assert initial_state["scenario"] == "labor"
    assert initial_state["conversation_history"][0] == {
        "role": "assistant",
        "content": WELCOME_MESSAGE,
    }
    assert persisted_state["conversation_history"][1] == {
        "role": "user",
        "content": "老板拖欠我兼职工资，还把我拉黑了",
    }


def test_graph_finalizes_after_explicit_request(monkeypatch) -> None:
    nodes.get_legal_triage_llm.cache_clear()
    monkeypatch.setattr(nodes, "get_legal_triage_llm", lambda: FakeLegalTriageLLM())
    monkeypatch.setattr(nodes, "LegalKnowledgeBase", FakeKnowledgeBaseSuccess)

    first_turn_state = run_legal_triage(
        create_initial_state(
            TriageRequest(
                user_input="老板拖欠兼职工资",
                scenario=TriageScenario.LABOR,
                session_id="graph-finalize",
            )
        )
    )
    next_turn_state = create_next_turn_state(
        first_turn_state,
        TriageRequest(
            user_input="开始整理",
            session_id="graph-finalize",
        ),
    )

    final_state = run_legal_triage(next_turn_state)

    assert final_state["current_stage"] == "deliverables"
    assert final_state["finalized_once"] is True
    assert final_state["legal_basis"][0]["id"] == "law-1"
    assert final_state["similar_cases"][0]["title"] == "学生兼职工资纠纷案"
    assert final_state["action_steps"]
    assert final_state["demand_letter"]
    assert "交付物阶段-success" in final_state["assistant_message"]


def test_graph_finalizes_when_retrieval_fails(monkeypatch) -> None:
    nodes.get_legal_triage_llm.cache_clear()
    monkeypatch.setattr(nodes, "get_legal_triage_llm", lambda: FakeLegalTriageLLM())
    monkeypatch.setattr(nodes, "LegalKnowledgeBase", FakeKnowledgeBaseFailure)

    first_turn_state = run_legal_triage(
        create_initial_state(
            TriageRequest(
                user_input="老板拖欠工资",
                scenario=TriageScenario.LABOR,
                session_id="graph-failure",
            )
        )
    )
    next_turn_state = create_next_turn_state(
        first_turn_state,
        TriageRequest(user_input="开始整理", session_id="graph-failure"),
    )

    final_state = run_legal_triage(next_turn_state)

    assert final_state["session_id"] == "graph-failure"
    assert final_state["current_stage"] == "deliverables"
    assert final_state["legal_basis"] == []
    assert final_state["legal_basis_notes"] == ["暂无检索依据"]
    assert "交付物阶段-unavailable" in final_state["assistant_message"]
    assert final_state["similar_cases"]


def test_graph_iterates_stage_events_for_intro_turn(monkeypatch) -> None:
    nodes.get_legal_triage_llm.cache_clear()
    monkeypatch.setattr(nodes, "get_legal_triage_llm", lambda: FakeLegalTriageLLM())
    monkeypatch.setattr(nodes, "LegalKnowledgeBase", FakeKnowledgeBaseSuccess)

    request = TriageRequest(
        user_input="老板拖欠工资",
        scenario=TriageScenario.LABOR,
        session_id="graph-stream",
    )
    initial_state = create_initial_state(request)

    events = list(iterate_legal_triage(initial_state))

    assert events[0]["event"] == "stage_started"
    assert events[0]["stage"] == "empathy"
    assert events[1]["event"] == "stage_completed"
    assert events[1]["stage"] == "empathy"
    assert events[-1]["event"] == "stage_completed"
    assert events[-1]["stage"] == "slot_filling"
    assert "安抚阶段" in events[-1]["state"]["assistant_message"]


def test_finalize_triage_state_appends_assistant_message() -> None:
    state = {
        "session_id": "finalize-test",
        "scenario": "labor",
        "user_input": "老板拖欠工资",
        "case_context": "context",
        "conversation_history": [{"role": "user", "content": "老板拖欠工资"}],
        "evidence_slots": {
            "counterparty": None,
            "time_place": None,
            "amount": None,
            "agreement": None,
            "breach_fact": "老板拖欠工资",
            "existing_evidence": [],
        },
        "missing_slots": ["counterparty", "time_place", "amount", "agreement", "existing_evidence"],
        "legal_basis": [],
        "legal_basis_notes": [],
        "action_steps": [],
        "demand_letter": "",
        "similar_cases": [],
        "current_stage": "slot_filling",
        "assistant_message": "最终建议",
        "empathy_message": "",
        "legal_grounding_message": "",
        "intro_completed": True,
        "requested_slot": "counterparty",
        "unavailable_slots": [],
        "awaiting_confirmation": False,
        "finalized_once": False,
    }

    finalized = finalize_triage_state(state)

    assert finalized["conversation_history"][-1] == {
        "role": "assistant",
        "content": "最终建议",
    }
