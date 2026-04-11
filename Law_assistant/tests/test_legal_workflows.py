from app.graphs.legal_triage.state import empty_evidence_slots
from app.services.evidence_extractor import merge_evidence_slots
from app.services.legal_workflows import (
    build_action_plan,
    build_demand_letter,
    build_legal_basis_notes,
    format_similar_cases_for_sidebar,
)


def test_build_legal_basis_notes_formats_retrieved_laws() -> None:
    notes = build_legal_basis_notes(
        legal_basis_items=[
            {
                "id": "law-1",
                "title": "劳动合同法",
                "publisher": "全国人大常委会",
                "publish_date": "2012-12-28",
                "active_date": "2013-07-01",
                "timeliness": "现行有效",
                "level": "法律",
                "snippet": "用人单位应按时支付劳动报酬。",
                "content": "正文",
            }
        ],
        scenario="labor",
        retrieval_status="success",
    )

    assert "《劳动合同法》" in notes[0]
    assert "全国人大常委会" in notes[0]


def test_build_action_plan_returns_scenario_specific_steps() -> None:
    evidence_slots = merge_evidence_slots(
        empty_evidence_slots(),
        "老板拖欠兼职工资，说好一天150元，我有微信聊天截图和转账记录。",
    )

    steps = build_action_plan(
        scenario="labor",
        evidence_slots=evidence_slots,
        missing_slots=["counterparty"],
        legal_basis_notes=["劳动报酬支付义务相关依据"],
    )

    assert any("12333" in step or "劳动保障监察部门" in step for step in steps)
    assert any("催告函" in step for step in steps)


def test_build_demand_letter_uses_template_fields() -> None:
    evidence_slots = merge_evidence_slots(
        empty_evidence_slots(),
        "房东不退押金，说好七天内退回，我有聊天记录和转账记录。",
    )

    letter = build_demand_letter(
        scenario="housing",
        evidence_slots=evidence_slots,
        legal_basis_notes=["《民法典》相关租赁规则可作为参考依据。"],
        action_steps=["先发送催告函", "再投诉平台"],
    )

    assert "租赁纠纷" in letter
    assert "房东" in letter
    assert "聊天记录" in letter
    assert "《民法典》相关租赁规则可作为参考依据。" in letter


def test_format_similar_cases_for_sidebar_formats_sections() -> None:
    cases = format_similar_cases_for_sidebar(
        similar_case_items=[
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
        ],
        scenario="labor",
    )

    assert cases[0]["title"] == "学生兼职工资纠纷案"
    assert "案情摘要" in cases[0]["summary"]
    assert "结果" in cases[0]["judgment"]
    assert "维权启示" in cases[0]["takeaway"]
