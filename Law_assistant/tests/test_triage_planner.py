from app.graphs.legal_triage.graph import create_initial_state
from app.schemas.triage import TriageRequest
from app.services.knowledge_base import LegalKnowledgeBase
from app.services.triage_planner import (
    build_case_query_plan,
    build_legal_query_plan,
    resolve_scenario,
    route_scenario,
)


class RecordingClient:
    def __init__(self) -> None:
        self.last_search_laws_args: dict | None = None
        self.last_search_cases_args: dict | None = None

    def search_laws(self, **kwargs):
        self.last_search_laws_args = kwargs
        return {
            "query_id": "law-query",
            "total_count": 0,
            "total_page": 0,
            "items": [],
        }

    def get_law_detail(self, law_id: str, *, merge: bool = True):
        raise AssertionError("empty law search should not request detail")

    def search_cases(self, **kwargs):
        self.last_search_cases_args = kwargs
        return {
            "query_id": "case-query",
            "total_count": 0,
            "total_page": 0,
            "items": [],
        }

    def close(self) -> None:
        return None


def test_route_scenario_detects_labor_dispute() -> None:
    assert route_scenario("老板拖欠我兼职工资，还把我拉黑了") == "labor"


def test_route_scenario_detects_housing_dispute() -> None:
    assert route_scenario("房东不退押金，还说家电坏了要我赔") == "housing"


def test_create_initial_state_auto_routes_when_scenario_missing() -> None:
    request = TriageRequest(user_input="同学借钱不还，还一直拖着", session_id="route-state")

    state = create_initial_state(request)

    assert state["scenario"] == "debt"


def test_resolve_scenario_prefers_stronger_auto_match_over_hint() -> None:
    assert resolve_scenario("老板拖欠我兼职工资，还把我拉黑了", scenario_hint="consumer") == "labor"


def test_resolve_scenario_keeps_hint_when_text_is_ambiguous() -> None:
    assert resolve_scenario("对方一直拖着不处理", scenario_hint="labor") == "labor"


def test_resolve_scenario_uses_auto_match_when_hint_is_other() -> None:
    assert resolve_scenario("房东不退押金，还让我赔家电", scenario_hint="other") == "housing"


def test_build_legal_query_plan_generates_semantic_question() -> None:
    plan = build_legal_query_plan("房东不退押金", scenario="housing")

    assert plan.field_name == "semantic"
    assert "房屋与租赁纠纷" in plan.rewritten_query
    assert "房东不退押金" in plan.rewritten_query


def test_build_case_query_plan_prefers_keyword_mode_for_short_input() -> None:
    plan = build_case_query_plan("房东不退押金", scenario="housing")

    assert plan.preferred_mode == "keyword_arr"
    assert "押金" in plan.keyword_arr


def test_build_case_query_plan_prefers_long_text_for_long_input() -> None:
    plan = build_case_query_plan(
        "房东一直拖着不退押金，我已经搬走了，他还说墙面和家电有问题，要扣我很多钱。",
        scenario="housing",
    )

    assert plan.preferred_mode == "long_text"
    assert plan.long_text is not None
    assert "用户案情" in plan.long_text


def test_knowledge_base_uses_rewritten_legal_query() -> None:
    client = RecordingClient()
    knowledge_base = LegalKnowledgeBase(client=client)

    result = knowledge_base.retrieve_legal_basis("老板拖欠我兼职工资", scenario="labor")

    assert result == []
    assert client.last_search_laws_args is not None
    assert client.last_search_laws_args["field_name"] == "semantic"
    assert "劳动与兼职纠纷" in client.last_search_laws_args["keywords"][0]
    assert knowledge_base.last_legal_query is not None


def test_knowledge_base_uses_keyword_case_query_for_short_input() -> None:
    client = RecordingClient()
    knowledge_base = LegalKnowledgeBase(client=client)

    result = knowledge_base.retrieve_similar_cases("房东不退押金", scenario="housing")

    assert result == []
    assert client.last_search_cases_args is not None
    assert client.last_search_cases_args["keyword_arr"]
    assert "押金" in client.last_search_cases_args["keyword_arr"]
    assert "long_text" not in client.last_search_cases_args


def test_knowledge_base_uses_long_text_case_query_for_long_input() -> None:
    client = RecordingClient()
    knowledge_base = LegalKnowledgeBase(client=client)

    result = knowledge_base.retrieve_similar_cases(
        "房东一直拖着不退押金，我已经搬走了，他还说墙面和家电有问题，要扣我很多钱。",
        scenario="housing",
    )

    assert result == []
    assert client.last_search_cases_args is not None
    assert client.last_search_cases_args["long_text"] is not None
    assert "用户案情" in client.last_search_cases_args["long_text"]
