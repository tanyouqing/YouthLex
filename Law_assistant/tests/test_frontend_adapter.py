from app.services.frontend_adapter import build_triage_response


def _base_state() -> dict:
    return {
        "session_id": "demo",
        "scenario": "labor",
        "user_input": "老板拖欠我工资",
        "case_context": "context",
        "conversation_history": [{"role": "user", "content": "老板拖欠我工资"}],
        "evidence_slots": {
            "counterparty": "老板",
            "time_place": None,
            "amount": None,
            "agreement": None,
            "breach_fact": "拖欠工资",
            "existing_evidence": [],
        },
        "missing_slots": ["time_place", "amount", "agreement", "existing_evidence"],
        "legal_basis": [],
        "legal_basis_notes": [],
        "action_steps": ["先补证据"],
        "demand_letter": "",
        "similar_cases": [],
        "current_stage": "slot_filling",
        "assistant_message": "请补充证据",
        "empathy_message": "安抚",
        "legal_grounding_message": "定性",
        "intro_completed": True,
        "requested_slot": "time_place",
        "unavailable_slots": [],
        "awaiting_confirmation": False,
        "finalized_once": False,
    }


def test_build_triage_response_prefers_slot_collection_when_slots_missing() -> None:
    response = build_triage_response(_base_state())

    assert response.frontend.display_mode == "slot_collection"
    assert response.frontend.primary_panel == "evidence_slots"
    assert len(response.frontend.follow_up_questions) == 1
    assert response.progress.evidence_complete is False
    assert response.progress.next_stage == "slot_filling"


def test_build_triage_response_marks_deliverables_ready() -> None:
    state = {
        **_base_state(),
        "scenario": "housing",
        "user_input": "房东不退押金",
        "conversation_history": [
            {"role": "user", "content": "房东不退押金"},
            {"role": "assistant", "content": "最终建议"},
        ],
        "evidence_slots": {
            "counterparty": "房东",
            "time_place": "2026年4月 宿舍附近出租屋",
            "amount": "2000元押金",
            "agreement": "租期届满后返还押金",
            "breach_fact": "房东拒绝退还押金",
            "existing_evidence": ["聊天记录", "转账记录"],
        },
        "missing_slots": [],
        "legal_basis_notes": ["《民法典》可作为参考依据。"],
        "action_steps": ["今天先发催告函"],
        "demand_letter": "# 催告函",
        "similar_cases": [
            {
                "title": "案例 A",
                "summary": "【案情摘要】摘要",
                "judgment": "【结果】支持退押金",
                "takeaway": "【维权启示】保留合同与付款记录",
            }
        ],
        "current_stage": "deliverables",
        "assistant_message": "最终建议",
        "requested_slot": None,
        "awaiting_confirmation": False,
        "finalized_once": True,
    }

    response = build_triage_response(state)

    assert response.frontend.display_mode == "deliverables_ready"
    assert response.frontend.primary_panel == "demand_letter"
    assert response.progress.evidence_complete is True
    assert response.progress.deliverables_ready is True
    assert response.scenario_label == "房屋与租赁纠纷"
