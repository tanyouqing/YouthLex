from __future__ import annotations

import re
from dataclasses import dataclass


ScenarioValue = str


SCENARIO_KEYWORDS: dict[ScenarioValue, tuple[str, ...]] = {
    "housing": (
        "租房",
        "租赁",
        "房东",
        "押金",
        "租金",
        "二房东",
        "中介",
        "转租",
        "合租",
        "退租",
        "房源",
        "维修",
    ),
    "labor": (
        "工资",
        "薪资",
        "薪水",
        "老板",
        "兼职",
        "实习",
        "拖欠",
        "劳动",
        "离职",
        "辞退",
        "加班",
        "工时",
        "中介费",
        "培训费",
        "服装费",
        "劳务",
    ),
    "consumer": (
        "退款",
        "退费",
        "假货",
        "网购",
        "卖家",
        "商家",
        "二手",
        "平台",
        "教培",
        "驾校",
        "健身房",
        "课程",
        "考研班",
        "虚假宣传",
        "医美",
        "消费",
    ),
    "debt": (
        "借钱",
        "借款",
        "还钱",
        "欠钱",
        "欠款",
        "校园贷",
        "套路贷",
        "贷款",
        "转账",
        "借条",
        "催还",
    ),
    "ip_reputation": (
        "论文",
        "作品",
        "署名",
        "盗用",
        "抄袭",
        "侵权",
        "名誉",
        "诽谤",
        "造谣",
        "网暴",
        "网络暴力",
        "表白墙",
        "论坛",
        "帖子",
        "辱骂",
    ),
}

SCENARIO_LABELS: dict[ScenarioValue, str] = {
    "housing": "房屋与租赁纠纷",
    "labor": "劳动与兼职纠纷",
    "consumer": "消费与教培维权",
    "debt": "借贷与财产纠纷",
    "ip_reputation": "知识产权与名誉权纠纷",
    "other": "综合维权纠纷",
}

SCENARIO_CASE_HINTS: dict[ScenarioValue, tuple[str, ...]] = {
    "housing": ("租房", "押金", "房东违约"),
    "labor": ("工资拖欠", "兼职", "劳动关系"),
    "consumer": ("退款", "虚假宣传", "消费纠纷"),
    "debt": ("借钱不还", "借款", "催收"),
    "ip_reputation": ("名誉侵权", "造谣", "作品署名"),
    "other": ("维权", "纠纷", "责任"),
}


@dataclass(frozen=True)
class LegalQueryPlan:
    rewritten_query: str
    field_name: str = "semantic"


@dataclass(frozen=True)
class CaseQueryPlan:
    rewritten_query: str
    preferred_mode: str
    keyword_arr: list[str]
    long_text: str | None


def route_scenario(user_input: str) -> ScenarioValue:
    best_scenario, best_score, _ = get_best_scenario_match(user_input)
    if best_score <= 0:
        return "other"
    return best_scenario


def get_scenario_scores(user_input: str) -> dict[ScenarioValue, int]:
    normalized = _normalize_text(user_input)
    if not normalized:
        return {scenario: 0 for scenario in (*SCENARIO_KEYWORDS.keys(), "other")}

    scenario_scores: dict[ScenarioValue, int] = {}
    for scenario, keywords in SCENARIO_KEYWORDS.items():
        score = 0
        for keyword in keywords:
            if keyword in normalized:
                score += _keyword_weight(keyword)
        scenario_scores[scenario] = score

    scenario_scores["other"] = 0
    return scenario_scores


def get_best_scenario_match(user_input: str) -> tuple[ScenarioValue, int, dict[ScenarioValue, int]]:
    scenario_scores = get_scenario_scores(user_input)
    best_scenario = max(scenario_scores, key=scenario_scores.get, default="other")
    best_score = scenario_scores.get(best_scenario, 0)
    return best_scenario, best_score, scenario_scores


def resolve_scenario(
    user_input: str,
    scenario_hint: ScenarioValue | None = None,
) -> ScenarioValue:
    if not scenario_hint:
        return route_scenario(user_input)

    best_scenario, best_score, scenario_scores = get_best_scenario_match(user_input)
    if scenario_hint == "other":
        return best_scenario if best_score > 0 else "other"

    hinted_score = scenario_scores.get(scenario_hint, 0)
    if best_scenario != scenario_hint and best_score >= hinted_score + 2 and best_score > 0:
        return best_scenario
    return scenario_hint


def build_legal_query_plan(user_input: str, scenario: ScenarioValue | None = None) -> LegalQueryPlan:
    active_scenario = scenario or route_scenario(user_input)
    compact_text = _compact_text(user_input, max_length=120)
    scenario_label = SCENARIO_LABELS.get(active_scenario, SCENARIO_LABELS["other"])
    return LegalQueryPlan(
        rewritten_query=(
            f"大学生遇到“{compact_text}”这类{scenario_label}时，通常涉及哪些法律规定、责任规则和维权依据？"
        )
    )


def build_case_query_plan(user_input: str, scenario: ScenarioValue | None = None) -> CaseQueryPlan:
    active_scenario = scenario or route_scenario(user_input)
    compact_text = _compact_text(user_input, max_length=180)
    keyword_arr = _extract_case_keywords(compact_text, active_scenario)
    long_text = (
        f"{SCENARIO_LABELS.get(active_scenario, SCENARIO_LABELS['other'])}。"
        f"用户案情：{compact_text}。"
        "请检索争议事实接近、维权路径相似的真实案例。"
    )

    preferred_mode = "long_text" if _should_prefer_long_text(compact_text) else "keyword_arr"
    if preferred_mode == "keyword_arr" and not keyword_arr:
        preferred_mode = "long_text"

    return CaseQueryPlan(
        rewritten_query=long_text,
        preferred_mode=preferred_mode,
        keyword_arr=keyword_arr,
        long_text=long_text if preferred_mode == "long_text" else None,
    )


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text).strip()


def _compact_text(text: str, *, max_length: int) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_length:
        return compact
    return compact[: max_length - 3] + "..."


def _keyword_weight(keyword: str) -> int:
    return 2 if len(keyword) >= 3 else 1


def _extract_case_keywords(user_input: str, scenario: ScenarioValue) -> list[str]:
    keywords: list[str] = []
    normalized = _normalize_text(user_input)

    for keyword in SCENARIO_KEYWORDS.get(scenario, ()):
        if keyword in normalized and keyword not in keywords:
            keywords.append(keyword)

    for hint in SCENARIO_CASE_HINTS.get(scenario, ()):
        if hint not in keywords:
            keywords.append(hint)

    return keywords[:3]


def _should_prefer_long_text(user_input: str) -> bool:
    punctuation_count = sum(user_input.count(mark) for mark in ("，", "。", "；", ",", ";"))
    return len(user_input) >= 28 or punctuation_count >= 2
