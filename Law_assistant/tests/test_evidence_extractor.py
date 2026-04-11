from app.graphs.legal_triage.state import empty_evidence_slots
from app.services.evidence_extractor import (
    build_case_context,
    compute_missing_slots,
    merge_evidence_slots,
    merge_evidence_state,
)


class FakeEvidenceNormalizer:
    def normalize_evidence_slots(
        self,
        user_input: str,
        scenario: str,
        current_slots: dict,
        rule_extracted_slots: dict,
        requested_slot: str | None = None,
    ):
        class Output:
            counterparty = "阿慧面馆"
            time_place = None
            amount = None
            agreement = None
            breach_fact = None
            existing_evidence = []

        return Output()


def test_merge_evidence_slots_extracts_amount_and_evidence() -> None:
    slots = merge_evidence_slots(
        empty_evidence_slots(),
        "老板拖欠我兼职工资，说好一天150元，我有微信聊天截图和转账记录。",
    )

    assert slots["counterparty"] == "老板"
    assert slots["amount"] == "150元"
    assert slots["agreement"] is not None
    assert "聊天记录" in slots["existing_evidence"]
    assert "转账记录" in slots["existing_evidence"]


def test_merge_evidence_state_accepts_shop_name_as_counterparty() -> None:
    result = merge_evidence_state(
        empty_evidence_slots(),
        "阿慧面馆",
        requested_slot="counterparty",
        llm=object(),
    )

    assert result["evidence_slots"]["counterparty"] == "阿慧面馆"
    assert result["slot_statuses"]["counterparty"] == "complete"


def test_merge_evidence_state_upgrades_generic_counterparty_to_specific_name() -> None:
    first_turn = merge_evidence_state(
        empty_evidence_slots(),
        "对方是商家",
        requested_slot="counterparty",
        llm=object(),
    )

    second_turn = merge_evidence_state(
        first_turn["evidence_slots"],
        "店名叫阿慧面馆",
        requested_slot="counterparty",
        llm=object(),
    )

    assert first_turn["evidence_slots"]["counterparty"] == "商家"
    assert first_turn["slot_statuses"]["counterparty"] == "usable"
    assert second_turn["evidence_slots"]["counterparty"] == "阿慧面馆"
    assert second_turn["slot_statuses"]["counterparty"] == "complete"


def test_merge_evidence_state_accepts_approximate_amount() -> None:
    result = merge_evidence_state(
        empty_evidence_slots(),
        "三十多块钱",
        requested_slot="amount",
        llm=object(),
    )

    assert result["evidence_slots"]["amount"] == "约30余元"
    assert result["slot_statuses"]["amount"] == "usable"
    assert result["slot_notes"]["amount"]


def test_merge_evidence_state_accepts_multi_part_amount() -> None:
    result = merge_evidence_state(
        empty_evidence_slots(),
        "餐费16元，去医院花了300多",
        requested_slot="amount",
        llm=object(),
    )

    assert result["evidence_slots"]["amount"] == "餐费16元；约300余元；总额待进一步核算"
    assert result["slot_statuses"]["amount"] == "usable"


def test_merge_evidence_state_accepts_partial_time_place() -> None:
    result = merge_evidence_state(
        empty_evidence_slots(),
        "昨天晚上",
        requested_slot="time_place",
        llm=object(),
    )

    assert result["evidence_slots"]["time_place"] == "时间：昨天晚上"
    assert result["slot_statuses"]["time_place"] == "usable"
    assert result["slot_notes"]["time_place"]


def test_merge_evidence_state_formats_full_time_place_without_misidentifying_counterparty() -> None:
    result = merge_evidence_state(
        empty_evidence_slots(),
        "昨天晚上在学校北门阿慧面馆吃面时发现虫子",
        requested_slot="time_place",
        llm=object(),
    )

    assert result["evidence_slots"]["counterparty"] is None
    assert result["evidence_slots"]["time_place"] == "时间：昨天晚上；地点：学校北门阿慧面馆"
    assert result["slot_statuses"]["time_place"] == "complete"


def test_merge_evidence_state_normalizes_evidence_synonyms() -> None:
    result = merge_evidence_state(
        empty_evidence_slots(),
        "我有付款小票、消费记录和现场拍的视频",
        requested_slot="existing_evidence",
        llm=object(),
    )

    assert "消费小票" in result["evidence_slots"]["existing_evidence"]
    assert "消费记录" in result["evidence_slots"]["existing_evidence"]
    assert "现场视频" in result["evidence_slots"]["existing_evidence"]
    assert result["slot_statuses"]["existing_evidence"] == "complete"


def test_merge_evidence_state_uses_llm_fallback_when_rules_miss_requested_slot() -> None:
    result = merge_evidence_state(
        empty_evidence_slots(),
        "阿慧",
        requested_slot="counterparty",
        llm=FakeEvidenceNormalizer(),
    )

    assert result["evidence_slots"]["counterparty"] == "阿慧面馆"
    assert result["slot_statuses"]["counterparty"] == "complete"


def test_compute_missing_slots_returns_only_unfilled_slots() -> None:
    merge_result = merge_evidence_state(
        empty_evidence_slots(),
        "房东不退押金，我有微信聊天截图。",
        llm=object(),
    )

    missing_slots = compute_missing_slots(
        merge_result["evidence_slots"],
        merge_result["slot_statuses"],
    )

    assert "existing_evidence" not in missing_slots
    assert "breach_fact" not in missing_slots


def test_build_case_context_contains_slot_summary() -> None:
    merge_result = merge_evidence_state(
        empty_evidence_slots(),
        "同学借钱不还，说好上周还我500元，我有转账记录。",
        llm=object(),
    )
    conversation_history = [{"role": "user", "content": "同学借钱不还，说好上周还我500元，我有转账记录。"}]

    context = build_case_context(conversation_history, merge_result["evidence_slots"])

    assert "相对方信息" in context
    assert "标的金额：500元" in context
    assert "现有证据：转账记录" in context
