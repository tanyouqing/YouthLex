import unittest

from app.graph.builder import build_debate_graph
from app.graph.nodes import debate_nodes


class _FakeLLMClient:
    def chat_json(self, **_: object) -> dict:
        return {
            "summary": "用户主张房东应退还押金。",
            "claims": ["房东应退还押金"],
            "evidence": ["转账记录"],
            "legal_basis": ["民法典第577条"],
            "request": "返还押金",
            "attack_target_category": "证据链薄弱",
            "attack_target": "证据链薄弱",
            "reason": "关键证据缺失",
            "secondary_attack_target_category": "法律依据不足",
            "counterargument_draft": (
                "【主张概括】用户主张房东应退还押金。\n"
                "【反方核心反驳】现有证据不足以支持全额退还。\n"
                "【法律依据】民法典第577条。\n"
                "【证据质疑】缺少入住退租对比证据。"
            ),
            "followup_question": "请补充入住与退租时的对比证据。",
            "debate_background": "租房押金争议",
            "user_claim_summary": ["主张退还押金"],
            "defendant_rebuttal_points": ["证据不足"],
            "user_strengths": ["主张明确"],
            "user_weaknesses": ["证据薄弱"],
            "evidence_improvement_suggestions": ["补充交接记录"],
            "legal_argument_suggestions": ["补充法条适配论证"],
            "overall_score": 72,
        }


class _RoleDriftRetryGraphLLMClient:
    def __init__(self) -> None:
        self.counter_calls = 0

    def chat_json(self, **kwargs: object) -> dict:
        system_prompt = str(kwargs.get("system_prompt", ""))
        if "法律论证解析器" in system_prompt:
            return {
                "summary": "用户主张房东应退还押金。",
                "claims": ["房东应退还押金"],
                "evidence": ["转账记录", "退租视频"],
                "legal_basis": ["民法典第577条"],
                "request": "返还押金",
            }
        if "争点选择器" in system_prompt:
            return {
                "attack_target_category": "证据链薄弱",
                "attack_target": "你方关键证据链条尚不完整。",
                "reason": "关键证据缺失",
                "secondary_attack_target_category": "法律依据不足",
            }
        if "检索结果审查员" in system_prompt:
            return {
                "is_sufficient": True,
                "missing_aspects": [],
                "synthetic_support": [],
            }
        if "结构化反驳" in system_prompt:
            self.counter_calls += 1
            if self.counter_calls == 1:
                return {
                    "claim_summary": "你方主张应予支持。",
                    "core_rebuttal": "你方主张应予支持，房东应返还全部押金。",
                    "legal_basis": "依据现有证据应支持你方请求。",
                    "case_strategy": "建议法院支持你方诉请。",
                    "evidence_challenge": "证据已经充分，足以支持你方结论。",
                    "logic_challenge": "你方逻辑完整，应支持你方主张。",
                    "followup_question": "请继续补充有利证据。",
                    "support_gap_notes": [],
                    "citations": {
                        "core_rebuttal": ["CASE_CN_0001"],
                        "legal_basis": ["STATUTE_CN_0001"],
                        "case_strategy": ["CASE_CN_0001"],
                        "evidence_challenge": ["CASE_CN_0001"],
                        "logic_challenge": ["ISSUE_RULE_0001"],
                    },
                }
            return {
                "claim_summary": "你方主张返还押金。",
                "core_rebuttal": "你方尚未证明押金全额返还的事实与规则对应。",
                "legal_basis": "你方法律依据与请求结论之间仍存在要件映射不足。",
                "case_strategy": "应先核验交接事实，再审查扣减范围。",
                "evidence_challenge": "你方证据链缺少入住退租同角度比对与维修凭证。",
                "logic_challenge": "你方推理在因果衔接上仍不充分。",
                "followup_question": "请补充交接清单与维修费用对应凭证。",
                "support_gap_notes": [],
                "citations": {
                    "core_rebuttal": ["CASE_CN_0001"],
                    "legal_basis": ["STATUTE_CN_0001"],
                    "case_strategy": ["CASE_CN_0001"],
                    "evidence_challenge": ["CASE_CN_0001"],
                    "logic_challenge": ["ISSUE_RULE_0001"],
                },
            }
        if "法律辩论教练总结器" in system_prompt:
            return {
                "debate_background": "租房押金争议",
                "user_claim_summary": ["主张退还押金"],
                "defendant_rebuttal_points": ["证据不足"],
                "user_strengths": ["主张明确"],
                "user_weaknesses": ["证据薄弱"],
                "evidence_improvement_suggestions": ["补充交接记录"],
                "legal_argument_suggestions": ["补充法条适配论证"],
                "overall_score": 72,
            }
        return {}


class GraphRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        debate_nodes._LLM_CLIENT = _FakeLLMClient()
        self.graph = build_debate_graph()

    def test_send_action_runs_one_round_and_returns_brief(self) -> None:
        initial_state = {
            "session_id": "test-send-001",
            "case_background": "学生租房退租后，房东拒绝返还押金。",
            "scenario_hint": "rental_dispute",
            "max_rounds": 5,
            "round_index": 0,
            "debate_history": [],
            "previous_user_inputs": [],
            "current_user_input": "我主张房东应全额退还押金。",
            "ui_action": "send",
        }

        result = self.graph.invoke(initial_state, config={"recursion_limit": 100})

        self.assertEqual(result.get("round_index"), 1)
        self.assertEqual(len(result.get("debate_history", [])), 1)
        self.assertTrue(result.get("assistant_brief", "").startswith("【核心反驳】"))
        self.assertIn("【进一步追问】", result.get("assistant_brief", ""))
        self.assertEqual(result.get("attack_target_category"), "证据链薄弱")
        self.assertEqual(result.get("attack_target_source"), "llm")
        self.assertTrue(isinstance(result.get("counterargument_structured", {}), dict))
        self.assertTrue(isinstance(result.get("counterargument_citations", {}), dict))
        self.assertEqual(result.get("end_reason_code"), "IN_PROGRESS")
        self.assertFalse(bool(result.get("report")))

    def test_end_action_directly_generates_report(self) -> None:
        initial_state = {
            "session_id": "test-end-001",
            "case_background": "学生租房退租后，房东拒绝返还押金。",
            "scenario_hint": "rental_dispute",
            "max_rounds": 5,
            "round_index": 0,
            "debate_history": [],
            "previous_user_inputs": [],
            "current_user_input": "",
            "ui_action": "end",
        }

        result = self.graph.invoke(initial_state, config={"recursion_limit": 100})

        self.assertEqual(result.get("round_index"), 0)
        self.assertEqual(len(result.get("debate_history", [])), 0)
        self.assertTrue(bool(result.get("report")))
        self.assertIn("用户点击结束辩论", result.get("report", {}).get("end_reason", ""))
        self.assertEqual(result.get("end_reason_code"), "USER_ENDED")
        self.assertTrue(result.get("assistant_brief", "").startswith("【核心反驳】"))

    def test_send_with_empty_input_short_circuits_to_input_error(self) -> None:
        initial_state = {
            "session_id": "test-empty-send-001",
            "case_background": "学生租房退租后，房东拒绝返还押金。",
            "scenario_hint": "rental_dispute",
            "max_rounds": 5,
            "round_index": 0,
            "debate_history": [],
            "previous_user_inputs": [],
            "current_user_input": "   ",
            "ui_action": "send",
        }

        result = self.graph.invoke(initial_state, config={"recursion_limit": 100})

        self.assertEqual(result.get("round_index"), 0)
        self.assertEqual(len(result.get("debate_history", [])), 0)
        self.assertEqual(result.get("input_valid"), False)
        self.assertEqual(result.get("input_error_code"), "INVALID_ARGUMENT")
        self.assertIn("输入校验", result.get("assistant_brief", ""))
        self.assertFalse(bool(result.get("report")))

    def test_send_with_end_keyword_does_not_end_early(self) -> None:
        initial_state = {
            "session_id": "test-keyword-send-001",
            "case_background": "学生租房退租后，房东拒绝返还押金。",
            "scenario_hint": "rental_dispute",
            "max_rounds": 5,
            "round_index": 0,
            "debate_history": [],
            "previous_user_inputs": [],
            "current_user_input": "我不是要结束，我是说对方说结束不合理。",
            "ui_action": "send",
        }

        result = self.graph.invoke(initial_state, config={"recursion_limit": 100})

        self.assertEqual(result.get("should_end"), False)
        self.assertEqual(result.get("end_reason_code"), "IN_PROGRESS")
        self.assertFalse(bool(result.get("report")))

    def test_send_role_drift_is_repaired_before_final_response(self) -> None:
        debate_nodes._LLM_CLIENT = _RoleDriftRetryGraphLLMClient()
        graph = build_debate_graph()
        initial_state = {
            "session_id": "test-role-drift-send-001",
            "case_background": "学生租房退租后，房东拒绝返还押金。",
            "scenario_hint": "rental_dispute",
            "max_rounds": 5,
            "round_index": 0,
            "debate_history": [],
            "previous_user_inputs": [],
            "current_user_input": "我主张房东应全额退还押金。",
            "ui_action": "send",
        }

        result = graph.invoke(initial_state, config={"recursion_limit": 100})

        counter_debug = result.get("debug", {}).get("counterargument", {})
        self.assertEqual(counter_debug.get("source_mode"), "llm")
        self.assertTrue(counter_debug.get("retry_applied"))
        self.assertTrue(counter_debug.get("role_drift_detected"))
        self.assertIn("role_drift_repaired", result.get("counterargument_quality_flags", []))
        self.assertNotIn(
            "应返还全部押金",
            f"{result.get('assistant_brief', '')}\n{result.get('assistant_detail', '')}",
        )


if __name__ == "__main__":
    unittest.main()
