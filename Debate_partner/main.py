from __future__ import annotations

from app.graph.builder import build_debate_graph


END_COMMANDS = {"/end", "/quit", "结束", "停止", "到这里"}


def _print_last_round(state: dict) -> None:
    history = state.get("debate_history", [])
    if not history:
        return

    turn = history[-1]
    print(f"\n[Round {turn.get('round_no')}] User: {turn.get('user_input', '')}")
    print("Assistant (Brief):")
    print(turn.get("assistant_brief") or turn.get("assistant_reply", ""))
    print("\nAssistant (Detail):")
    print(turn.get("assistant_detail") or turn.get("assistant_reply", ""))


def _print_report(state: dict) -> None:
    report = state.get("report", {})
    if not report:
        return

    print("\n=== End Reason ===")
    print(report.get("end_reason", state.get("end_reason", "流程结束")))

    print("\n=== Structured Report ===")
    for key, value in report.items():
        print(f"- {key}: {value}")


def run_demo() -> None:
    graph = build_debate_graph()

    state: dict = {
        "session_id": "demo-session-cli",
        "case_background": "学生租房退租后，房东拒绝返还押金并主张维修费用。",
        "scenario_hint": "rental_dispute",
        "max_rounds": 5,
        "round_index": 0,
        "debate_history": [],
        "previous_user_inputs": [],
        "current_user_input": "",
        "ui_action": "send",
    }

    print("法律辩论 CLI 模式已启动。输入 /end 或 结束 可生成报告并退出。")

    while True:
        user_input = input("\nYou: ").strip()
        if not user_input:
            print("请输入有效内容，或输入 /end 结束。")
            continue

        action = "end" if user_input in END_COMMANDS else "send"
        invoke_state = dict(state)
        invoke_state["ui_action"] = action
        invoke_state["current_user_input"] = "" if action == "end" else user_input

        state = graph.invoke(invoke_state, config={"recursion_limit": 100})

        if action == "send":
            _print_last_round(state)
        else:
            print("\n你已结束辩论，正在展示报告。")

        if state.get("report"):
            _print_report(state)
            break


if __name__ == "__main__":
    run_demo()
