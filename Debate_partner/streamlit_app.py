from __future__ import annotations

import uuid
from typing import Any, Dict, List

import streamlit as st

from app.graph.builder import build_debate_graph


SCENARIO_OPTIONS = [
    "rental_dispute",
    "part_time_wage",
    "campus_loan",
    "training_refund",
    "student_rights",
]


def _init_ui_defaults() -> None:
    if "ui_case_background" not in st.session_state:
        st.session_state["ui_case_background"] = "学生租房退租后，房东拒绝返还押金并主张维修费用。"
    if "ui_scenario_hint" not in st.session_state:
        st.session_state["ui_scenario_hint"] = "rental_dispute"
    if "ui_max_rounds" not in st.session_state:
        st.session_state["ui_max_rounds"] = 5


@st.cache_resource
def _get_graph():
    return build_debate_graph()


def _build_initial_state() -> Dict[str, Any]:
    return {
        "session_id": f"streamlit-{uuid.uuid4().hex[:8]}",
        "case_background": st.session_state["ui_case_background"],
        "scenario_hint": st.session_state["ui_scenario_hint"],
        "max_rounds": int(st.session_state["ui_max_rounds"]),
        "round_index": 0,
        "debate_history": [],
        "previous_user_inputs": [],
        "current_user_input": "",
        "ui_action": "send",
    }


def _reset_session() -> None:
    st.session_state["debate_state"] = _build_initial_state()
    st.session_state["chat_messages"] = []
    for key in list(st.session_state.keys()):
        if key.startswith("detail_open_"):
            del st.session_state[key]


def _append_assistant_message(state: Dict[str, Any]) -> None:
    brief = str(state.get("assistant_brief", "")).strip()
    if not brief:
        return

    detail = str(state.get("assistant_detail", "")).strip() or brief
    st.session_state["chat_messages"].append(
        {
            "role": "assistant",
            "content": brief,
            "detail": detail,
        }
    )


def _sync_presets_into_state(state: Dict[str, Any]) -> Dict[str, Any]:
    state["case_background"] = st.session_state.get("ui_case_background", state.get("case_background", ""))
    state["scenario_hint"] = st.session_state.get("ui_scenario_hint", state.get("scenario_hint", ""))
    state["max_rounds"] = int(st.session_state.get("ui_max_rounds", state.get("max_rounds", 5)))
    return state


def _invoke_turn(user_text: str, action: str) -> None:
    graph = _get_graph()
    state = dict(st.session_state["debate_state"])

    is_fresh_session = (
        not state.get("debate_history")
        and not state.get("previous_user_inputs")
        and int(state.get("round_index", 0) or 0) == 0
    )
    if is_fresh_session:
        state = _sync_presets_into_state(state)

    state["current_user_input"] = user_text.strip()
    state["ui_action"] = action

    result = graph.invoke(state, config={"recursion_limit": 100})
    st.session_state["debate_state"] = result

    if user_text.strip():
        st.session_state["chat_messages"].append(
            {
                "role": "user",
                "content": user_text.strip(),
            }
        )

    _append_assistant_message(result)


def _render_report(report: Dict[str, Any]) -> None:
    st.markdown("## 辩论总结报告")
    st.markdown(f"**背景**：{report.get('debate_background', '')}")
    st.markdown(f"**结束原因**：{report.get('end_reason', '')}")
    st.markdown(f"**综合评分**：{report.get('overall_score', '')}")

    sections: List[tuple[str, List[str]]] = [
        ("用户主张摘要", list(report.get("user_claim_summary", []) or [])),
        ("反方核心反驳点", list(report.get("defendant_rebuttal_points", []) or [])),
        ("用户优势", list(report.get("user_strengths", []) or [])),
        ("用户漏洞", list(report.get("user_weaknesses", []) or [])),
        ("证据改进建议", list(report.get("evidence_improvement_suggestions", []) or [])),
        ("法律论证建议", list(report.get("legal_argument_suggestions", []) or [])),
    ]

    for title, items in sections:
        st.markdown(f"### {title}")
        if not items:
            st.markdown("- 暂无")
            continue
        st.markdown("\n".join(f"- {item}" for item in items))


def _build_node_trace(state: Dict[str, Any]) -> List[Dict[str, str]]:
    parsed_claim = state.get("parsed_claim", {}) or {}
    debug = state.get("debug", {}) or {}
    report = state.get("report", {}) or {}
    retrieval_hits = state.get("retrieved_knowledge", []) or []

    def mark(ok: bool) -> str:
        return "OK" if ok else "WAIT"

    return [
        {"node": "init_session", "status": mark(True), "hint": "状态初始化已完成"},
        {
            "node": "fetch_user_input",
            "status": mark("ui_action" in state),
            "hint": f"ui_action={state.get('ui_action', '')}, input_valid={state.get('input_valid', True)}",
        },
        {
            "node": "parse_user_claim",
            "status": mark(bool(parsed_claim.get("parse_source"))),
            "hint": f"parse_source={parsed_claim.get('parse_source', '')}",
        },
        {
            "node": "identify_attack_target",
            "status": mark(bool(state.get("attack_target_category"))),
            "hint": f"category={state.get('attack_target_category', '')}, source={state.get('attack_target_source', '')}",
        },
        {
            "node": "retrieve_knowledge",
            "status": mark(bool(state.get("retrieval_mode"))),
            "hint": f"mode={state.get('retrieval_mode', '')}, hits={len(retrieval_hits)}",
        },
        {
            "node": "assess_knowledge_support",
            "status": mark("knowledge_audit" in debug),
            "hint": f"sufficient={state.get('knowledge_sufficiency', True)}",
        },
        {
            "node": "build_counterargument",
            "status": mark(bool(state.get("counterargument_draft"))),
            "hint": f"quality_flags={len(state.get('counterargument_quality_flags', []) or [])}",
        },
        {
            "node": "judge_continue_or_end",
            "status": mark(bool(state.get("end_reason_code"))),
            "hint": f"should_end={state.get('should_end', False)}, code={state.get('end_reason_code', '')}",
        },
        {
            "node": "ask_next_challenge",
            "status": mark(bool(state.get("assistant_brief")) and not bool(report)),
            "hint": f"history_count={len(state.get('debate_history', []) or [])}",
        },
        {
            "node": "generate_debate_report",
            "status": mark(bool(report)),
            "hint": f"report_source={state.get('report_source', '')}",
        },
    ]


def _render_debug_panel(state: Dict[str, Any]) -> None:
    st.markdown("### 节点观测（测试用）")
    left, right = st.columns(2)

    with left:
        st.markdown("#### 节点链路状态")
        st.dataframe(_build_node_trace(state), use_container_width=True, hide_index=True)

        st.markdown("#### 当前轮关键字段")
        st.json(
            {
                "session_id": state.get("session_id", ""),
                "round_index": state.get("round_index", 0),
                "ui_action": state.get("ui_action", "send"),
                "input_valid": state.get("input_valid", True),
                "end_reason": state.get("end_reason", ""),
                "end_reason_code": state.get("end_reason_code", ""),
                "should_end": state.get("should_end", False),
                "attack_target": state.get("attack_target", ""),
                "attack_target_category": state.get("attack_target_category", ""),
                "attack_target_source": state.get("attack_target_source", ""),
                "retrieval_mode": state.get("retrieval_mode", ""),
                "knowledge_sufficiency": state.get("knowledge_sufficiency", True),
                "knowledge_missing_aspects": state.get("knowledge_missing_aspects", []),
                "report_source": state.get("report_source", None),
                "report_quality_flags": state.get("report_quality_flags", []),
            },
            expanded=False,
        )

    with right:
        st.markdown("#### 结构化反驳与引用")
        st.json(
            {
                "counterargument_structured": state.get("counterargument_structured", {}),
                "counterargument_citations": state.get("counterargument_citations", {}),
                "counterargument_quality_flags": state.get("counterargument_quality_flags", []),
            },
            expanded=False,
        )

        st.markdown("#### 调试信息")
        st.json(state.get("debug", {}), expanded=False)

    history = state.get("debate_history", []) or []
    if history:
        st.markdown("#### 历史快照")
        latest = history[-1]
        st.json(
            {
                "round_no": latest.get("round_no", 0),
                "parsed_summary": latest.get("parsed_summary", ""),
                "attack_target_category": latest.get("attack_target_category", ""),
                "assistant_brief": latest.get("assistant_brief", ""),
                "counterargument_structured_snapshot": latest.get("counterargument_structured_snapshot", {}),
                "counterargument_citations_snapshot": latest.get("counterargument_citations_snapshot", {}),
                "counterargument_quality_flags": latest.get("counterargument_quality_flags", []),
            },
            expanded=False,
        )


def main() -> None:
    st.set_page_config(page_title="Debate Partner Demo", layout="wide")
    st.title("法律辩论 Agent ")

    _init_ui_defaults()

    st.markdown("### 辩论预设")
    st.text_area("案件背景", key="ui_case_background", height=100)
    c1, c2, c3 = st.columns([2, 1, 1])
    c1.selectbox("维权场景", options=SCENARIO_OPTIONS, key="ui_scenario_hint")
    c2.number_input("最大轮次", min_value=1, max_value=20, step=1, key="ui_max_rounds")
    if c3.button("应用预设并新建会话", type="primary"):
        _reset_session()

    if "debate_state" not in st.session_state or "chat_messages" not in st.session_state:
        _reset_session()

    st.markdown("### 对话")
    for idx, message in enumerate(st.session_state["chat_messages"]):
        role = message.get("role", "assistant")
        if role == "user":
            with st.chat_message("user"):
                st.markdown(str(message.get("content", "")))
            continue

        with st.chat_message("assistant"):
            left, right = st.columns([0.84, 0.16])
            left.markdown(str(message.get("content", "")))
            if right.button("详情", key=f"detail_btn_{idx}"):
                state_key = f"detail_open_{idx}"
                st.session_state[state_key] = not st.session_state.get(state_key, False)

            if st.session_state.get(f"detail_open_{idx}", False):
                st.markdown("---")
                st.markdown(str(message.get("detail", "（无详情）")))

    with st.form("chat_form", clear_on_submit=True):
        user_text = st.text_input("输入你的发言")
        b1, b2 = st.columns(2)
        send_clicked = b1.form_submit_button("发送", type="primary")
        end_clicked = b2.form_submit_button("结束辩论")

    if send_clicked:
        if not user_text.strip():
            st.warning("发送前请先输入发言内容。")
        else:
            try:
                _invoke_turn(user_text=user_text, action="send")
                st.rerun()
            except Exception as exc:
                st.error(f"调用失败：{exc}")

    if end_clicked:
        try:
            _invoke_turn(user_text=user_text, action="end")
            st.rerun()
        except Exception as exc:
            st.error(f"调用失败：{exc}")

    report = st.session_state.get("debate_state", {}).get("report", {})
    if report:
        st.markdown("---")
        _render_report(report)

    st.markdown("---")
    _render_debug_panel(st.session_state.get("debate_state", {}))


if __name__ == "__main__":
    main()
