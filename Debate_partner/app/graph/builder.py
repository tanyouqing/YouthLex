from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.graph.nodes.debate_nodes import (
    assess_knowledge_support,
    ask_next_challenge,
    build_counterargument,
    fetch_user_input,
    generate_debate_report,
    handle_invalid_input,
    identify_attack_target,
    init_session,
    judge_continue_or_end,
    parse_user_claim,
    retrieve_knowledge,
)
from app.graph.schemas.state import DebateState


def route_after_fetch(state: DebateState) -> str:
    if state.get("ui_action", "send") == "end":
        return "generate_debate_report"
    if not state.get("input_valid", True):
        return "handle_invalid_input"
    return "parse_user_claim"


def route_after_judge(state: DebateState) -> str:
    if state.get("should_end", False):
        return "generate_debate_report"
    return "ask_next_challenge"


def build_debate_graph():
    builder = StateGraph(DebateState)

    builder.add_node("init_session", init_session)
    builder.add_node("fetch_user_input", fetch_user_input)
    builder.add_node("handle_invalid_input", handle_invalid_input)
    builder.add_node("parse_user_claim", parse_user_claim)
    builder.add_node("identify_attack_target", identify_attack_target)
    builder.add_node("retrieve_knowledge", retrieve_knowledge)
    builder.add_node("assess_knowledge_support", assess_knowledge_support)
    builder.add_node("build_counterargument", build_counterargument)
    builder.add_node("judge_continue_or_end", judge_continue_or_end)
    builder.add_node("ask_next_challenge", ask_next_challenge)
    builder.add_node("generate_debate_report", generate_debate_report)

    builder.add_edge(START, "init_session")
    builder.add_edge("init_session", "fetch_user_input")

    builder.add_conditional_edges(
        "fetch_user_input",
        route_after_fetch,
        {
            "parse_user_claim": "parse_user_claim",
            "handle_invalid_input": "handle_invalid_input",
            "generate_debate_report": "generate_debate_report",
        },
    )
    builder.add_edge("handle_invalid_input", END)

    builder.add_edge("parse_user_claim", "identify_attack_target")
    builder.add_edge("identify_attack_target", "retrieve_knowledge")
    builder.add_edge("retrieve_knowledge", "assess_knowledge_support")
    builder.add_edge("assess_knowledge_support", "build_counterargument")
    builder.add_edge("build_counterargument", "judge_continue_or_end")

    builder.add_conditional_edges(
        "judge_continue_or_end",
        route_after_judge,
        {
            "ask_next_challenge": "ask_next_challenge",
            "generate_debate_report": "generate_debate_report",
        },
    )

    builder.add_edge("ask_next_challenge", END)
    builder.add_edge("generate_debate_report", END)

    return builder.compile()
