from __future__ import annotations

import re
from copy import deepcopy
from typing import TypedDict

from app.graphs.legal_triage.state import (
    EvidenceSlots,
    ScenarioValue,
    SlotNotes,
    SlotStatuses,
    empty_slot_notes,
)


SLOT_ORDER = [
    "counterparty",
    "time_place",
    "amount",
    "agreement",
    "breach_fact",
    "existing_evidence",
]

GENERIC_COUNTERPARTIES = {
    "房东",
    "二房东",
    "中介",
    "合租人",
    "老板",
    "商家",
    "卖家",
    "同学",
    "平台",
    "公司",
    "学校",
    "驾校",
    "教培机构",
    "健身房",
    "店家",
    "门店",
    "商户",
}

COUNTERPARTY_SUFFIXES = (
    "有限责任公司",
    "有限公司",
    "培训机构",
    "培训班",
    "工作室",
    "商场",
    "超市",
    "商户",
    "平台",
    "门店",
    "店铺",
    "面馆",
    "饭店",
    "餐馆",
    "餐厅",
    "火锅店",
    "奶茶店",
    "酒店",
    "药店",
    "医院",
    "诊所",
    "公司",
    "机构",
    "驾校",
    "学校",
    "学院",
    "大学",
    "店",
)

COUNTERPARTY_CONTEXT_PATTERNS = (
    r"(?:对方|商家|店家|店名|门店|商户|平台|公司|老板|房东|中介|卖家|机构)(?:叫|名叫|是|为)?([A-Za-z0-9\u4e00-\u9fa5·]{2,32}(?:"
    + "|".join(COUNTERPARTY_SUFFIXES)
    + r"))",
    r"(?:店名叫|门店叫|商家叫|平台叫)([A-Za-z0-9\u4e00-\u9fa5·]{2,32}(?:"
    + "|".join(COUNTERPARTY_SUFFIXES)
    + r"))",
)

GENERIC_COUNTERPARTY_PATTERNS = (
    r"(房东|二房东|中介|合租人|老板|商家|卖家|同学|平台|公司|学校|驾校|教培机构|健身房|店家|门店|商户)",
)

TIME_KEYWORDS = (
    "今天",
    "昨天",
    "前天",
    "前几天",
    "前阵子",
    "当天",
    "当时",
    "上周",
    "本周",
    "上个月",
    "这个月",
    "去年",
    "今年",
    "周一",
    "周二",
    "周三",
    "周四",
    "周五",
    "周六",
    "周日",
    "星期一",
    "星期二",
    "星期三",
    "星期四",
    "星期五",
    "星期六",
    "星期日",
    "凌晨",
    "早上",
    "上午",
    "中午",
    "下午",
    "傍晚",
    "晚上",
)

PLACE_HINTS = (
    "学校",
    "校门",
    "北门",
    "南门",
    "宿舍",
    "出租屋",
    "小区",
    "公司",
    "店里",
    "门店",
    "平台",
    "商场",
    "超市",
    "面馆",
    "饭店",
    "餐馆",
    "餐厅",
    "医院",
    "诊所",
    "工作室",
    "办公室",
    "地铁站",
    "公交站",
)

AGREEMENT_HINTS = (
    "约定",
    "说好",
    "答应",
    "合同",
    "协议",
    "承诺",
    "每月",
    "一天",
    "每节课",
    "包退",
    "返还",
    "菜单",
    "页面",
    "写着",
    "宣传",
    "保证",
    "保障",
    "应当",
    "现做现卖",
    "食品安全",
)

BREACH_HINTS = (
    "拖欠",
    "不发",
    "不给",
    "不退",
    "跑路",
    "拉黑",
    "失联",
    "造谣",
    "辱骂",
    "违约",
    "骗",
    "扣押",
    "拒绝",
    "辞退",
    "取消",
    "吃出",
    "异物",
    "虫子",
    "变质",
    "过期",
    "拒赔",
    "拒绝赔偿",
    "拒绝退款",
)

EVIDENCE_SYNONYMS = {
    "微信聊天截图": "聊天记录",
    "微信聊天": "聊天记录",
    "聊天截图": "聊天记录",
    "聊天记录": "聊天记录",
    "截图": "截图",
    "录音": "录音",
    "录像": "现场视频",
    "现场视频": "现场视频",
    "视频": "现场视频",
    "录屏": "录屏",
    "照片": "现场照片",
    "图片": "现场照片",
    "现场照片": "现场照片",
    "合同": "合同",
    "协议": "协议",
    "转账记录": "转账记录",
    "转账截图": "转账记录",
    "付款记录": "付款记录",
    "支付记录": "付款记录",
    "消费记录": "消费记录",
    "订单详情": "订单详情",
    "订单截图": "订单详情",
    "收据": "消费小票",
    "小票": "消费小票",
    "发票": "发票",
    "工牌": "工牌",
    "打卡": "考勤记录",
    "考勤": "考勤记录",
    "排班表": "排班表",
    "工作照": "工作现场照片",
    "快递单": "快递单",
    "病历": "病历资料",
    "诊断证明": "诊断证明",
    "检验报告": "检测报告",
    "检测报告": "检测报告",
    "网页链接": "网页链接",
    "链接": "网页链接",
}

EXPLICIT_FINALIZE_HINTS = (
    "开始整理",
    "开始总结",
    "帮我整理",
    "请整理",
    "直接整理",
    "开始生成",
    "生成交付物",
    "生成催告函",
    "出结果",
)

EXPLICIT_FINALIZE_RESPONSES = (
    "没有更多了",
    "没有更多",
    "没有了",
    "就这些",
    "就这样",
    "先这样",
    "差不多了",
    "补不了了",
    "没法补充了",
    "无法补充了",
)

UNAVAILABLE_RESPONSE_HINTS = (
    "补不了",
    "补不出",
    "没法补充",
    "无法补充",
    "记不清",
    "记不得",
    "不记得",
    "想不起来",
    "找不到",
    "丢了",
    "没留",
    "没有",
)

AMOUNT_LABELS = {
    "押金": "押金",
    "工资": "工资",
    "薪资": "工资",
    "薪水": "工资",
    "退款": "退款金额",
    "退费": "退款金额",
    "赔偿": "赔偿金额",
    "学费": "学费",
    "课时费": "课时费",
    "餐费": "餐费",
    "面": "餐费",
    "饭": "餐费",
    "检查费": "检查费",
    "医药费": "医药费",
    "医疗费": "医药费",
    "治疗费": "治疗费",
    "挂号费": "挂号费",
    "损失": "损失金额",
}

TOTAL_AMOUNT_HINTS = ("一共", "总共", "合计", "总额", "共计", "总计", "一共花了", "总损失")
AMOUNT_APPROXIMATE_HINTS = ("约", "大概", "差不多", "左右", "余", "多")

TIME_ONLY_NOTE = "时间地点目前只确认到了时间信息，后续如能补地点会更利于维权整理。"
PLACE_ONLY_NOTE = "时间地点目前只确认到了地点信息，后续如能补时间会更利于维权整理。"
GENERIC_COUNTERPARTY_NOTE = "相对方目前仅确认到身份称呼，后续如拿到具体店名、公司名或平台主体，可再补充。"
APPROXIMATE_AMOUNT_NOTE = "金额目前按口述约数整理，后续可结合票据或账单继续精确核算。"
MULTI_PART_AMOUNT_NOTE = "金额目前已按费用项先整理，若后续能核出总额，可再补充。"


class EvidenceMergeResult(TypedDict):
    evidence_slots: EvidenceSlots
    slot_statuses: SlotStatuses
    slot_notes: SlotNotes


def merge_evidence_slots(existing_slots: EvidenceSlots, user_input: str) -> EvidenceSlots:
    return merge_evidence_state(existing_slots, user_input)["evidence_slots"]


def merge_evidence_state(
    existing_slots: EvidenceSlots,
    user_input: str,
    *,
    scenario: ScenarioValue | None = None,
    requested_slot: str | None = None,
    llm: object | None = None,
) -> EvidenceMergeResult:
    merged = deepcopy(existing_slots)
    extracted = extract_evidence_slots(user_input)
    merged = _merge_slot_candidates(merged, extracted)

    if _should_attempt_llm_normalization(
        user_input=user_input,
        extracted=extracted,
        merged=merged,
        requested_slot=requested_slot,
    ):
        llm_candidate = _normalize_with_llm(
            user_input=user_input,
            scenario=scenario,
            requested_slot=requested_slot,
            current_slots=merged,
            rule_extracted=extracted,
            llm=llm,
        )
        if llm_candidate is not None:
            merged = _merge_slot_candidates(merged, llm_candidate)

    if not merged["breach_fact"]:
        merged["breach_fact"] = _compact_text(user_input, max_length=120)

    slot_statuses, slot_notes = derive_slot_metadata(merged)
    return {
        "evidence_slots": merged,
        "slot_statuses": slot_statuses,
        "slot_notes": slot_notes,
    }


def extract_evidence_slots(user_input: str) -> EvidenceSlots:
    normalized = _normalize_text(user_input)
    sentences = _split_sentences(user_input)
    return {
        "counterparty": _extract_counterparty(user_input, normalized),
        "time_place": _extract_time_place(user_input, sentences),
        "amount": _extract_amount(user_input),
        "agreement": _extract_agreement(sentences),
        "breach_fact": _extract_breach_fact(sentences),
        "existing_evidence": _extract_existing_evidence(normalized),
    }


def derive_slot_metadata(evidence_slots: EvidenceSlots) -> tuple[SlotStatuses, SlotNotes]:
    slot_statuses: SlotStatuses = {
        "counterparty": "missing",
        "time_place": "missing",
        "amount": "missing",
        "agreement": "missing",
        "breach_fact": "missing",
        "existing_evidence": "missing",
    }
    slot_notes = empty_slot_notes()

    counterparty = evidence_slots["counterparty"]
    if counterparty:
        if _is_generic_counterparty(counterparty):
            slot_statuses["counterparty"] = "usable"
            slot_notes["counterparty"] = [GENERIC_COUNTERPARTY_NOTE]
        else:
            slot_statuses["counterparty"] = "complete"

    time_value = evidence_slots["time_place"]
    if time_value:
        time_part, place_part = _split_time_place_value(time_value)
        if time_part and place_part:
            slot_statuses["time_place"] = "complete"
        else:
            slot_statuses["time_place"] = "usable"
            slot_notes["time_place"] = [TIME_ONLY_NOTE if time_part else PLACE_ONLY_NOTE]

    amount_value = evidence_slots["amount"]
    if amount_value:
        if "待进一步核算" in amount_value:
            slot_statuses["amount"] = "usable"
            slot_notes["amount"] = [MULTI_PART_AMOUNT_NOTE]
        elif any(hint in amount_value for hint in AMOUNT_APPROXIMATE_HINTS):
            slot_statuses["amount"] = "usable"
            slot_notes["amount"] = [APPROXIMATE_AMOUNT_NOTE]
        else:
            slot_statuses["amount"] = "complete"

    if evidence_slots["agreement"]:
        slot_statuses["agreement"] = "complete"
    if evidence_slots["breach_fact"]:
        slot_statuses["breach_fact"] = "complete"
    if evidence_slots["existing_evidence"]:
        slot_statuses["existing_evidence"] = "complete"
    return slot_statuses, slot_notes


def compute_missing_slots(
    evidence_slots: EvidenceSlots,
    slot_statuses: SlotStatuses | None = None,
) -> list[str]:
    if slot_statuses is not None:
        return [field for field in SLOT_ORDER if slot_statuses[field] == "missing"]

    missing_slots: list[str] = []
    for field in SLOT_ORDER:
        value = evidence_slots[field]
        if field == "existing_evidence":
            if not value:
                missing_slots.append(field)
        elif not value:
            missing_slots.append(field)
    return missing_slots


def choose_next_slot(
    missing_slots: list[str],
    unavailable_slots: list[str],
) -> str | None:
    for slot in SLOT_ORDER:
        if slot in missing_slots and slot not in unavailable_slots:
            return slot
    return None


def slot_has_value(
    evidence_slots: EvidenceSlots,
    slot_name: str,
    slot_statuses: SlotStatuses | None = None,
) -> bool:
    if slot_statuses is not None:
        return slot_statuses[slot_name] != "missing"

    value = evidence_slots[slot_name]
    if slot_name == "existing_evidence":
        return bool(value)
    return bool(value)


def remove_resolved_unavailable_slots(
    unavailable_slots: list[str],
    evidence_slots: EvidenceSlots,
    slot_statuses: SlotStatuses | None = None,
) -> list[str]:
    return [
        slot
        for slot in unavailable_slots
        if not slot_has_value(evidence_slots, slot, slot_statuses)
    ]


def is_explicit_finalize_request(user_input: str) -> bool:
    normalized = _normalize_text(user_input)
    if not normalized:
        return False
    if normalized in EXPLICIT_FINALIZE_RESPONSES:
        return True
    return any(hint in normalized for hint in EXPLICIT_FINALIZE_HINTS)


def is_requested_slot_unavailable(
    user_input: str,
    requested_slot: str | None,
    evidence_slots: EvidenceSlots,
    slot_statuses: SlotStatuses | None = None,
) -> bool:
    if not requested_slot:
        return False
    if slot_has_value(evidence_slots, requested_slot, slot_statuses):
        return False

    normalized = _normalize_text(user_input)
    if not normalized:
        return False
    return any(hint in normalized for hint in UNAVAILABLE_RESPONSE_HINTS)


def build_case_context(conversation_history: list[dict], evidence_slots: EvidenceSlots) -> str:
    user_messages = [
        message.get("content", "")
        for message in conversation_history
        if message.get("role") == "user" and message.get("content")
    ]
    evidence_summary = [
        f"相对方信息：{evidence_slots['counterparty'] or '待补充'}",
        f"时间地点：{evidence_slots['time_place'] or '待补充'}",
        f"标的金额：{evidence_slots['amount'] or '待补充'}",
        f"合同约定：{evidence_slots['agreement'] or '待补充'}",
        f"违约事实：{evidence_slots['breach_fact'] or '待补充'}",
        "现有证据："
        + ("、".join(evidence_slots["existing_evidence"]) if evidence_slots["existing_evidence"] else "待补充"),
    ]
    message_summary = " ".join(user_messages[-6:])
    return f"用户陈述：{message_summary}\n证据链概况：{'；'.join(evidence_summary)}"


# Helpers below.


def _merge_slot_candidates(existing_slots: EvidenceSlots, candidate_slots: EvidenceSlots) -> EvidenceSlots:
    merged = deepcopy(existing_slots)
    merged["counterparty"] = _merge_counterparty_value(
        merged["counterparty"],
        candidate_slots["counterparty"],
    )
    merged["time_place"] = _merge_time_place_value(
        merged["time_place"],
        candidate_slots["time_place"],
    )
    merged["amount"] = _merge_amount_value(
        merged["amount"],
        candidate_slots["amount"],
    )
    merged["agreement"] = _merge_text_slot_value(
        merged["agreement"],
        candidate_slots["agreement"],
    )
    merged["breach_fact"] = _merge_breach_fact(
        merged["breach_fact"],
        candidate_slots["breach_fact"],
    )
    merged["existing_evidence"] = _merge_evidence_lists(
        merged["existing_evidence"],
        candidate_slots["existing_evidence"],
    )
    return merged


def _merge_counterparty_value(existing: str | None, new_value: str | None) -> str | None:
    candidate = _normalize_counterparty_value(new_value)
    current = _normalize_counterparty_value(existing)
    if not candidate:
        return current
    if not current:
        return candidate
    return candidate if _counterparty_score(candidate) > _counterparty_score(current) else current


def _merge_time_place_value(existing: str | None, new_value: str | None) -> str | None:
    current_time, current_place = _split_time_place_value(existing)
    next_time, next_place = _split_time_place_value(new_value)
    merged_time = _prefer_more_specific_fragment(current_time, next_time)
    merged_place = _prefer_more_specific_fragment(current_place, next_place)
    return _format_time_place_value(merged_time, merged_place)


def _merge_amount_value(existing: str | None, new_value: str | None) -> str | None:
    current_items = _split_amount_items(existing)
    next_items = _split_amount_items(new_value)
    if not current_items:
        return "；".join(next_items) if next_items else None
    if not next_items:
        return "；".join(current_items)

    merged_items: list[str] = []
    indexed: dict[str, int] = {}
    for item in current_items + next_items:
        key = _amount_item_key(item)
        if key not in indexed:
            indexed[key] = len(merged_items)
            merged_items.append(item)
            continue
        existing_item = merged_items[indexed[key]]
        if _amount_item_score(item) > _amount_item_score(existing_item):
            merged_items[indexed[key]] = item

    concrete_items = [item for item in merged_items if item != "总额待进一步核算"]
    has_total = any(item.startswith("总额") for item in concrete_items)
    if len(concrete_items) > 1 and not has_total and "总额待进一步核算" not in merged_items:
        merged_items.append("总额待进一步核算")
    return "；".join(merged_items)


def _merge_text_slot_value(existing: str | None, new_value: str | None) -> str | None:
    current = _normalize_text_value(existing)
    candidate = _normalize_text_value(new_value)
    if not candidate:
        return current
    if not current:
        return candidate
    return candidate if _text_specificity_score(candidate) > _text_specificity_score(current) else current


def _merge_breach_fact(existing: str | None, new_value: str | None) -> str | None:
    current = _normalize_text_value(existing)
    candidate = _normalize_text_value(new_value)
    if not candidate:
        return current
    if not current:
        return candidate
    return candidate if _breach_fact_score(candidate) > _breach_fact_score(current) else current


def _should_attempt_llm_normalization(
    *,
    user_input: str,
    extracted: EvidenceSlots,
    merged: EvidenceSlots,
    requested_slot: str | None,
) -> bool:
    normalized = _normalize_text(user_input)
    if len(normalized) < 2:
        return False

    if requested_slot == "counterparty":
        return not merged["counterparty"] or _is_generic_counterparty(merged["counterparty"] or "")
    if requested_slot == "time_place":
        return not merged["time_place"] and _looks_like_time_or_place_reply(user_input)
    if requested_slot == "amount":
        return not merged["amount"] and _looks_like_amount_reply(user_input)
    if requested_slot == "agreement":
        return not merged["agreement"]
    if requested_slot == "breach_fact":
        return not merged["breach_fact"]
    if requested_slot == "existing_evidence":
        return not merged["existing_evidence"] and _looks_like_evidence_reply(user_input)

    if not any(extracted[field] for field in SLOT_ORDER if field != "existing_evidence"):
        return _looks_like_amount_reply(user_input) or _looks_like_time_or_place_reply(user_input)
    return False


def _normalize_with_llm(
    *,
    user_input: str,
    scenario: ScenarioValue | None,
    requested_slot: str | None,
    current_slots: EvidenceSlots,
    rule_extracted: EvidenceSlots,
    llm: object | None,
) -> EvidenceSlots | None:
    active_llm = llm or _resolve_llm_from_graph()
    if active_llm is None:
        return None

    normalizer = getattr(active_llm, "normalize_evidence_slots", None)
    if normalizer is None:
        return None

    try:
        result = normalizer(
            user_input=user_input,
            scenario=scenario or "other",
            current_slots=current_slots,
            rule_extracted_slots=rule_extracted,
            requested_slot=requested_slot,
        )
    except Exception:
        return None

    return {
        "counterparty": _normalize_counterparty_value(getattr(result, "counterparty", None)),
        "time_place": _normalize_time_place_value(getattr(result, "time_place", None)),
        "amount": _normalize_amount_value(getattr(result, "amount", None)),
        "agreement": _normalize_text_value(getattr(result, "agreement", None)),
        "breach_fact": _normalize_text_value(getattr(result, "breach_fact", None)),
        "existing_evidence": _normalize_evidence_list(getattr(result, "existing_evidence", [])),
    }


def _resolve_llm_from_graph() -> object | None:
    try:
        from app.graphs.legal_triage import nodes
    except Exception:
        return None
    try:
        return nodes.get_legal_triage_llm()
    except Exception:
        return None


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text).strip()


def _normalize_text_value(value: str | None) -> str | None:
    if not value:
        return None
    compact = re.sub(r"\s+", " ", value).strip(" ，,；;。")
    return compact or None


def _compact_text(text: str, *, max_length: int) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_length:
        return compact
    return compact[: max_length - 3] + "..."


def _split_sentences(text: str) -> list[str]:
    chunks = re.split(r"[。！？；;\n]", text)
    return [chunk.strip(" ，,") for chunk in chunks if chunk.strip(" ，,")]


def _extract_counterparty(text: str, normalized: str) -> str | None:
    explicit_time_place = _has_explicit_time_place_context(text)
    stripped = _normalize_text_value(text)
    if stripped and len(_normalize_text(stripped)) <= 20 and not explicit_time_place:
        short_candidate = _match_specific_counterparty(stripped)
        if short_candidate:
            return short_candidate

    for pattern in COUNTERPARTY_CONTEXT_PATTERNS:
        match = re.search(pattern, text)
        if match:
            candidate = _normalize_counterparty_value(match.group(1))
            if candidate:
                return candidate

    generic_context_match = re.search(
        r"(?:对方|商家|老板|卖家|平台|房东|中介)(?:是|为|叫|名叫)?("
        + "|".join(GENERIC_COUNTERPARTIES)
        + r")",
        normalized,
    )
    if generic_context_match:
        return generic_context_match.group(1)

    if not explicit_time_place:
        for pattern in GENERIC_COUNTERPARTY_PATTERNS:
            match = re.search(pattern, normalized)
            if match:
                return match.group(1)
    return None


def _match_specific_counterparty(text: str) -> str | None:
    for suffix in COUNTERPARTY_SUFFIXES:
        pattern = rf"([A-Za-z0-9\u4e00-\u9fa5·]{{2,32}}{re.escape(suffix)})"
        matches = re.findall(pattern, text)
        if matches:
            cleaned = [_normalize_counterparty_value(match) for match in matches]
            candidates = [candidate for candidate in cleaned if candidate]
            if candidates:
                return max(candidates, key=_counterparty_score)
    return None


def _normalize_counterparty_value(value: str | None) -> str | None:
    compact = _normalize_text_value(value)
    if not compact:
        return None
    contextual_match = re.match(
        r"^(?:对方|店名|门店|商家|老板|平台|公司|店家|商户)(?:是|叫|名叫|为)(.+)$",
        compact,
    )
    if contextual_match:
        compact = contextual_match.group(1)
    compact = compact.strip(" ：:，,；;。")
    return compact or None


def _counterparty_score(value: str) -> int:
    score = len(value)
    if _is_generic_counterparty(value):
        return 10
    if any(value.endswith(suffix) for suffix in COUNTERPARTY_SUFFIXES):
        score += 20
    if "市" in value or "区" in value:
        score += 5
    return score


def _is_generic_counterparty(value: str) -> bool:
    return value in GENERIC_COUNTERPARTIES


def _extract_time_place(text: str, sentences: list[str]) -> str | None:
    stripped = _normalize_text_value(text)
    if (
        stripped
        and len(_normalize_text(stripped)) <= 20
        and _match_specific_counterparty(stripped)
        and not _has_explicit_time_place_context(stripped)
    ):
        return None

    time_part = _extract_time_fragment(text)
    place_part = _extract_place_fragment(text)

    if not time_part and not place_part:
        for sentence in sentences:
            if not time_part:
                time_part = _extract_time_fragment(sentence)
            if not place_part:
                place_part = _extract_place_fragment(sentence)
            if time_part or place_part:
                break

    return _format_time_place_value(time_part, place_part)


def _extract_time_fragment(text: str) -> str | None:
    normalized = _normalize_text(text)
    explicit_patterns = (
        r"\d{4}年\d{1,2}月\d{1,2}日(?:\d{1,2}[点时]\d{0,2}分?)?",
        r"\d{1,2}月\d{1,2}日(?:\d{1,2}[点时]\d{0,2}分?)?",
        r"\d{1,2}[点时]\d{0,2}分?",
        r"(?:今天|昨天|前天|前几天|上周|本周|上个月|这个月|去年|今年|当天|当时)(?:凌晨|早上|上午|中午|下午|傍晚|晚上)?",
        r"(?:周一|周二|周三|周四|周五|周六|周日|星期一|星期二|星期三|星期四|星期五|星期六|星期日)(?:凌晨|早上|上午|中午|下午|傍晚|晚上)?",
    )
    for pattern in explicit_patterns:
        match = re.search(pattern, normalized)
        if match:
            return match.group(0)
    for keyword in TIME_KEYWORDS:
        if keyword in text:
            return keyword
    return None


def _extract_place_fragment(text: str) -> str | None:
    for match in re.finditer(r"(?:在|于)([^，。；\n]{2,40})", text):
        candidate = _trim_place_fragment(match.group(1))
        if candidate:
            return candidate

    stripped = _normalize_text_value(text)
    if (
        stripped
        and len(_normalize_text(stripped)) <= 24
        and any(hint in stripped for hint in PLACE_HINTS)
        and not _looks_like_amount_reply(stripped)
        and not _match_specific_counterparty(stripped)
    ):
        return stripped
    return None


def _trim_place_fragment(value: str) -> str | None:
    trimmed = value.strip(" ：:，,；;。")
    stop_markers = ("吃", "买", "上班", "消费", "签约", "付款", "发现", "遇到", "工作", "就餐", "点餐")
    for marker in stop_markers:
        marker_index = trimmed.find(marker)
        if marker_index > 1:
            trimmed = trimmed[:marker_index]
            break
    trimmed = trimmed.strip(" ：:，,；;。")
    return trimmed or None


def _split_time_place_value(value: str | None) -> tuple[str | None, str | None]:
    compact = _normalize_text_value(value)
    if not compact:
        return None, None

    time_match = re.search(r"时间：([^；]+)", compact)
    place_match = re.search(r"地点：(.+)$", compact)
    if time_match or place_match:
        return (
            _normalize_text_value(time_match.group(1) if time_match else None),
            _normalize_text_value(place_match.group(1) if place_match else None),
        )

    time_part = _extract_time_fragment(compact)
    place_part = _extract_place_fragment(compact)
    return time_part, place_part


def _format_time_place_value(time_part: str | None, place_part: str | None) -> str | None:
    formatted: list[str] = []
    if time_part:
        formatted.append(f"时间：{time_part}")
    if place_part:
        formatted.append(f"地点：{place_part}")
    if not formatted:
        return None
    return "；".join(formatted)


def _normalize_time_place_value(value: str | None) -> str | None:
    time_part, place_part = _split_time_place_value(value)
    return _format_time_place_value(time_part, place_part)


def _prefer_more_specific_fragment(existing: str | None, new_value: str | None) -> str | None:
    current = _normalize_text_value(existing)
    candidate = _normalize_text_value(new_value)
    if not candidate:
        return current
    if not current:
        return candidate
    return candidate if len(candidate) > len(current) else current


def _extract_amount(text: str) -> str | None:
    clauses = [
        clause.strip(" ，,；;。")
        for clause in re.split(r"[，,。；;\n]", text)
        if clause.strip(" ，,；;。")
    ]
    amount_items: list[str] = []

    for clause in clauses:
        expressions = _extract_amount_expressions(clause)
        if not expressions:
            continue

        label = _extract_amount_label(clause)
        total_clause = any(hint in clause for hint in TOTAL_AMOUNT_HINTS)
        for expression in expressions:
            normalized_expression = _normalize_amount_expression(expression)
            if not normalized_expression:
                continue
            item = normalized_expression
            if total_clause:
                item = f"总额{normalized_expression}" if not normalized_expression.startswith("总额") else normalized_expression
            elif label:
                item = f"{label}{normalized_expression}"
            if item not in amount_items:
                amount_items.append(item)

    if len(amount_items) > 1 and not any(item.startswith("总额") for item in amount_items):
        amount_items.append("总额待进一步核算")
    return "；".join(amount_items) if amount_items else None


def _extract_amount_expressions(clause: str) -> list[str]:
    expressions: list[str] = []
    patterns = (
        r"(?:¥|￥)?\d+(?:\.\d+)?(?:多|余|左右)?(?:元|块钱|块|w|W|万)?",
        r"[零〇一二两三四五六七八九十百千万]+(?:多|余|左右)?(?:元|块钱|块)",
        r"[零〇一二两三四五六七八九十百千万]{2,}(?:多|余|左右)",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, clause):
            expression = match.group(0)
            if not expression:
                continue
            if not any(token in clause for token in ("元", "块", "钱", "w", "W", "万", "金额", "花", "赔", "退", "押金", "工资", "损失")):
                continue
            if expression not in expressions:
                expressions.append(expression)
    return expressions


def _normalize_amount_value(value: str | None) -> str | None:
    compact = _normalize_text_value(value)
    if not compact:
        return None
    if "；" in compact:
        items = [_normalize_text_value(item) for item in compact.split("；")]
        normalized_items = [item for item in items if item]
        return "；".join(normalized_items) if normalized_items else None
    if compact == "总额待进一步核算":
        return compact
    if compact.startswith("总额") and compact != "总额待进一步核算":
        suffix = _normalize_amount_expression(compact.removeprefix("总额"))
        return f"总额{suffix}" if suffix else None

    label = _extract_amount_label(compact)
    expression = compact.removeprefix(label) if label and compact.startswith(label) else compact
    normalized_expression = _normalize_amount_expression(expression)
    if not normalized_expression:
        return compact
    return f"{label}{normalized_expression}" if label and not compact.startswith("总额") else normalized_expression


def _normalize_amount_expression(expression: str) -> str | None:
    compact = _normalize_text(expression)
    if not compact:
        return None
    if compact == "总额待进一步核算":
        return compact

    if re.fullmatch(r"(?:¥|￥)?\d+(?:\.\d+)?(?:元|块钱|块)?", compact):
        number = re.sub(r"^(?:¥|￥)", "", compact)
        if number.endswith("块钱"):
            number = number.removesuffix("块钱") + "元"
        elif number.endswith("块"):
            number = number.removesuffix("块") + "元"
        elif not number.endswith("元"):
            number += "元"
        return number

    digit_approx = re.fullmatch(r"(?:¥|￥)?(\d+(?:\.\d+)?)(多|余|左右)(?:元|块钱|块)?", compact)
    if digit_approx:
        return f"约{digit_approx.group(1)}余元"

    digit_w = re.fullmatch(r"(\d+(?:\.\d+)?)(w|W|万)", compact)
    if digit_w:
        return f"{digit_w.group(1)}万"

    chinese_match = re.fullmatch(r"([零〇一二两三四五六七八九十百千万]+)(多|余|左右)?(?:元|块钱|块)?", compact)
    if chinese_match:
        amount_num = _parse_chinese_number(chinese_match.group(1))
        if amount_num is None:
            return None
        if chinese_match.group(2):
            return f"约{amount_num}余元"
        return f"{amount_num}元"

    return compact


def _extract_amount_label(text: str) -> str:
    for keyword, label in AMOUNT_LABELS.items():
        if keyword in text:
            return label
    return ""


def _parse_chinese_number(text: str) -> int | None:
    numerals = {
        "零": 0,
        "〇": 0,
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
    }
    units = {"十": 10, "百": 100, "千": 1000, "万": 10000}
    total = 0
    section = 0
    number = 0
    for char in text:
        if char in numerals:
            number = numerals[char]
            continue
        if char in units:
            unit = units[char]
            if unit == 10000:
                section = (section + number) * unit
                total += section
                section = 0
                number = 0
                continue
            section += (number or 1) * unit
            number = 0
            continue
        return None
    return total + section + number


def _split_amount_items(value: str | None) -> list[str]:
    compact = _normalize_text_value(value)
    if not compact:
        return []
    return [
        item
        for item in (_normalize_text_value(part) for part in compact.split("；"))
        if item
    ]


def _amount_item_key(item: str) -> str:
    if item == "总额待进一步核算":
        return item
    if item.startswith("总额"):
        return "总额"
    label = _extract_amount_label(item)
    return label or item


def _amount_item_score(item: str) -> int:
    score = len(item)
    if item == "总额待进一步核算":
        return 1
    if item.startswith("总额"):
        score += 10
    if any(hint in item for hint in AMOUNT_APPROXIMATE_HINTS):
        score -= 3
    if "待进一步核算" in item:
        score -= 2
    if any(char.isdigit() for char in item):
        score += 5
    return score


def _extract_agreement(sentences: list[str]) -> str | None:
    for sentence in sentences:
        if any(hint in sentence for hint in AGREEMENT_HINTS):
            return _compact_text(sentence, max_length=100)
    return None


def _extract_breach_fact(sentences: list[str]) -> str | None:
    for sentence in sentences:
        if any(hint in sentence for hint in BREACH_HINTS):
            return _compact_text(sentence, max_length=100)
    return None


def _extract_existing_evidence(normalized: str) -> list[str]:
    evidence_items: list[str] = []
    sorted_items = sorted(EVIDENCE_SYNONYMS.items(), key=lambda item: len(item[0]), reverse=True)
    for keyword, normalized_label in sorted_items:
        if normalized_label == "截图" and any(
            existing in evidence_items for existing in ("聊天记录", "转账记录", "订单详情")
        ):
            continue
        if keyword in normalized and normalized_label not in evidence_items:
            evidence_items.append(normalized_label)
    return evidence_items


def _normalize_evidence_list(values: list[str]) -> list[str]:
    normalized_items: list[str] = []
    for value in values:
        compact = _normalize_text_value(value)
        if not compact:
            continue
        normalized_label = EVIDENCE_SYNONYMS.get(compact, compact)
        if normalized_label not in normalized_items:
            normalized_items.append(normalized_label)
    return normalized_items


def _merge_evidence_lists(existing: list[str], new_items: list[str]) -> list[str]:
    merged = list(_normalize_evidence_list(existing))
    for item in _normalize_evidence_list(new_items):
        if item not in merged:
            merged.append(item)
    return merged


def _text_specificity_score(value: str) -> int:
    score = len(value)
    if any(hint in value for hint in AGREEMENT_HINTS):
        score += 10
    return score


def _breach_fact_score(value: str) -> int:
    score = len(value)
    if any(hint in value for hint in BREACH_HINTS):
        score += 10
    if len(value) > 60:
        score -= 5
    return score


def _looks_like_amount_reply(text: str) -> bool:
    normalized = _normalize_text(text)
    return bool(
        re.search(r"\d", normalized)
        or any(char in normalized for char in "一二两三四五六七八九十百千万")
        or any(token in normalized for token in ("元", "块", "钱", "损失", "赔偿", "退款", "押金", "工资", "学费", "花了"))
    )


def _looks_like_time_or_place_reply(text: str) -> bool:
    normalized = _normalize_text(text)
    return (
        any(keyword in normalized for keyword in TIME_KEYWORDS)
        or any(hint in normalized for hint in PLACE_HINTS)
        or "在" in normalized
        or "于" in normalized
    )


def _looks_like_evidence_reply(text: str) -> bool:
    normalized = _normalize_text(text)
    return any(keyword in normalized for keyword in EVIDENCE_SYNONYMS)


def _has_explicit_time_place_context(text: str) -> bool:
    normalized = _normalize_text(text)
    return any(keyword in normalized for keyword in TIME_KEYWORDS) or "在" in normalized or "于" in normalized
