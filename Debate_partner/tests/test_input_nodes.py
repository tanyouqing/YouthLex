import unittest
from unittest.mock import patch

from app.graph.nodes import debate_nodes


class _OkLLMClient:
    def chat_json(self, **_: object) -> dict:
        return {
            "summary": "用户主张退还押金。",
            "claims": ["退还押金"],
            "evidence": ["转账记录"],
            "legal_basis": ["民法典第577条"],
            "request": "返还押金",
        }


class _FailLLMClient:
    def chat_json(self, **_: object) -> dict:
        raise RuntimeError("mock llm failure")


class _StaticLLMClient:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def chat_json(self, **_: object) -> dict:
        return dict(self.payload)


class InputNodeTests(unittest.TestCase):
    def tearDown(self) -> None:
        debate_nodes._LLM_CLIENT = None

    def test_init_session_normalizes_and_clears_temp_fields(self) -> None:
        history = [{"round_no": 1}]
        previous = ["第一次输入"]
        state = {
            "max_rounds": 0,
            "round_index": -3,
            "ui_action": "unknown",
            "should_end": True,
            "debate_history": history,
            "previous_user_inputs": previous,
            "parsed_claim": {"summary": "stale"},
            "attack_target": "stale",
            "retrieved_knowledge": [{"record_id": "k1"}],
            "counterargument_draft": "stale",
            "followup_question": "stale",
        }

        result = debate_nodes.init_session(state)
        history.append({"round_no": 2})
        previous.append("第二次输入")

        self.assertEqual(result.get("max_rounds"), 1)
        self.assertEqual(result.get("round_index"), 0)
        self.assertEqual(result.get("ui_action"), "send")
        self.assertEqual(result.get("should_end"), False)
        self.assertEqual(result.get("parsed_claim"), {})
        self.assertEqual(result.get("attack_target"), "")
        self.assertEqual(result.get("retrieved_knowledge"), [])
        self.assertEqual(result.get("counterargument_structured"), {})
        self.assertEqual(result.get("counterargument_citations"), {})
        self.assertEqual(result.get("counterargument_quality_flags"), [])
        self.assertEqual(result.get("counterargument_draft"), "")
        self.assertEqual(result.get("followup_question"), "")
        self.assertEqual(len(result.get("debate_history", [])), 1)
        self.assertEqual(len(result.get("previous_user_inputs", [])), 1)
        self.assertTrue(bool(result.get("debug", {}).get("input_warnings")))

    def test_fetch_user_input_marks_empty_send_invalid(self) -> None:
        result = debate_nodes.fetch_user_input(
            {
                "current_user_input": " \n\t ",
                "ui_action": "send",
            }
        )

        self.assertEqual(result.get("input_valid"), False)
        self.assertEqual(result.get("input_error_code"), "INVALID_ARGUMENT")
        self.assertEqual(result.get("normalized_user_input"), "")

    def test_fetch_user_input_normalizes_action_and_text(self) -> None:
        result = debate_nodes.fetch_user_input(
            {
                "current_user_input": "  我   要   维权 \n ",
                "ui_action": "not-valid",
            }
        )

        self.assertEqual(result.get("ui_action"), "send")
        self.assertEqual(result.get("current_user_input"), "我   要   维权")
        self.assertEqual(result.get("normalized_user_input"), "我 要 维权")
        self.assertEqual(result.get("input_valid"), True)
        self.assertTrue(bool(result.get("debug", {}).get("input_warnings")))

    def test_parse_user_claim_skips_when_input_invalid(self) -> None:
        result = debate_nodes.parse_user_claim(
            {
                "current_user_input": "",
                "normalized_user_input": "",
                "previous_user_inputs": [],
                "input_valid": False,
            }
        )

        parsed = result.get("parsed_claim", {})
        self.assertEqual(parsed.get("parse_source"), "skipped")
        self.assertEqual(parsed.get("claims"), [])
        self.assertEqual(parsed.get("has_new_argument"), False)

    def test_parse_user_claim_uses_normalized_dedup(self) -> None:
        debate_nodes._LLM_CLIENT = _OkLLMClient()
        result = debate_nodes.parse_user_claim(
            {
                "current_user_input": " 我主张   退还押金 ",
                "normalized_user_input": "我主张 退还押金",
                "previous_user_inputs": ["我主张 退还押金"],
                "input_valid": True,
                "case_background": "租房押金纠纷",
                "debate_history": [],
            }
        )

        parsed = result.get("parsed_claim", {})
        self.assertEqual(parsed.get("parse_source"), "llm")
        self.assertEqual(parsed.get("has_new_argument"), False)
        self.assertEqual(parsed.get("claims"), ["退还押金"])

    def test_parse_user_claim_fallback_and_debug_on_llm_failure(self) -> None:
        debate_nodes._LLM_CLIENT = _FailLLMClient()
        result = debate_nodes.parse_user_claim(
            {
                "current_user_input": "我主张退还押金",
                "normalized_user_input": "我主张退还押金",
                "previous_user_inputs": [],
                "input_valid": True,
                "case_background": "租房押金纠纷",
                "debate_history": [],
            }
        )

        parsed = result.get("parsed_claim", {})
        self.assertEqual(parsed.get("parse_source"), "fallback")
        self.assertEqual(parsed.get("has_new_argument"), True)
        self.assertEqual(result.get("debug", {}).get("parse", {}).get("error_code"), "PARSE_CLAIM_LLM_FAILED")

    def test_identify_attack_target_returns_structured_meta(self) -> None:
        debate_nodes._LLM_CLIENT = _StaticLLMClient(
            {
                "attack_target_category": "证据链薄弱",
                "attack_target": "缺少关键证据链闭环",
                "secondary_attack_target_category": "法律依据不足",
                "reason": "关键事实未形成可核验证据闭环。",
            }
        )
        result = debate_nodes.identify_attack_target(
            {
                "current_user_input": "我要求退押金",
                "parsed_claim": {
                    "claims": ["要求退押金"],
                    "evidence": ["聊天记录"],
                    "legal_basis": ["民法典第577条"],
                },
                "debate_history": [],
            }
        )

        self.assertEqual(result.get("attack_target_category"), "证据链薄弱")
        self.assertEqual(result.get("attack_target_source"), "llm")
        self.assertEqual(result.get("attack_target"), "缺少关键证据链闭环")
        self.assertTrue(bool(result.get("attack_target_reason")))

    def test_identify_attack_target_fallback_on_invalid_llm_output(self) -> None:
        debate_nodes._LLM_CLIENT = _StaticLLMClient(
            {
                "attack_target_category": "未知类型",
                "attack_target": "",
                "reason": "",
            }
        )
        result = debate_nodes.identify_attack_target(
            {
                "current_user_input": "我要求退押金",
                "parsed_claim": {
                    "claims": ["要求退押金"],
                    "evidence": ["聊天记录"],
                    "legal_basis": [],
                },
                "debate_history": [],
            }
        )

        self.assertEqual(result.get("attack_target_category"), "法律依据不足")
        self.assertEqual(result.get("attack_target_source"), "fallback")
        self.assertEqual(result.get("debug", {}).get("attack", {}).get("error_code"), "ATTACK_TARGET_INVALID_OUTPUT")

    def test_identify_attack_target_reranks_when_same_as_recent(self) -> None:
        debate_nodes._LLM_CLIENT = _StaticLLMClient(
            {
                "attack_target_category": "证据链薄弱",
                "attack_target": "证据还不完整",
                "secondary_attack_target_category": "法律依据不足",
                "reason": "先攻证据。",
            }
        )
        result = debate_nodes.identify_attack_target(
            {
                "current_user_input": "我要求退押金",
                "parsed_claim": {
                    "claims": ["要求退押金"],
                    "evidence": ["聊天记录"],
                    "legal_basis": ["民法典第577条"],
                },
                "debate_history": [{"attack_target_category": "证据链薄弱"}],
            }
        )

        self.assertEqual(result.get("attack_target_category"), "法律依据不足")
        self.assertEqual(result.get("attack_target_source"), "reranked")
        self.assertEqual(result.get("debug", {}).get("attack", {}).get("rerank_applied"), True)

    def test_identify_attack_target_marks_info_insufficient_on_failure(self) -> None:
        debate_nodes._LLM_CLIENT = _FailLLMClient()
        result = debate_nodes.identify_attack_target(
            {
                "current_user_input": " ",
                "parsed_claim": {
                    "claims": [],
                    "evidence": [],
                    "legal_basis": [],
                },
                "debate_history": [],
            }
        )

        self.assertEqual(result.get("attack_target_category"), "论点信息不足")
        self.assertEqual(result.get("attack_target_source"), "fallback")
        self.assertEqual(result.get("debug", {}).get("attack", {}).get("error_code"), "ATTACK_TARGET_LLM_FAILED")

    @patch("app.graph.nodes.debate_nodes.search_knowledge")
    def test_retrieve_knowledge_records_retrieval_mode(self, mock_search) -> None:
        mock_search.return_value = (
            [
                {
                    "record_id": "STATUTE_CN_0001",
                    "record_type": "statute",
                    "score": 90,
                    "citation": "民法典第465条",
                    "snippet": "合同依法成立...",
                }
            ],
            {"mode": "vector", "error_code": ""},
        )
        result = debate_nodes.retrieve_knowledge(
            {
                "current_user_input": "房东拒退押金",
                "attack_target": "证据链薄弱",
                "parsed_claim": {"claims": ["返还押金"]},
                "scenario_hint": "rental_dispute",
                "debate_history": [],
            }
        )

        self.assertEqual(result.get("retrieval_mode"), "vector")
        self.assertEqual(len(result.get("retrieved_knowledge", [])), 1)
        self.assertEqual(result.get("debug", {}).get("retrieval", {}).get("mode"), "vector")

    def test_assess_knowledge_support_adds_synthetic_hits(self) -> None:
        debate_nodes._LLM_CLIENT = _StaticLLMClient(
            {
                "is_sufficient": False,
                "missing_aspects": ["缺少损失金额证明路径"],
                "synthetic_support": [
                    {
                        "title": "损失证明结构",
                        "support_text": "先证明损失项目，再证明金额与违约行为关联。",
                        "citation": "LLM补强建议",
                        "confidence": 0.82,
                    }
                ],
            }
        )
        result = debate_nodes.assess_knowledge_support(
            {
                "case_background": "租房押金争议",
                "parsed_claim": {"claims": ["返还押金"]},
                "attack_target": "损失计算不充分",
                "retrieved_knowledge": [],
                "debug": {},
            }
        )

        self.assertEqual(result.get("knowledge_sufficiency"), False)
        self.assertEqual(len(result.get("retrieved_knowledge", [])), 1)
        self.assertEqual(result.get("retrieved_knowledge", [])[0].get("record_type"), "synthetic_support")
        self.assertEqual(result.get("debug", {}).get("knowledge_audit", {}).get("synthetic_count"), 1)

    def test_assess_knowledge_support_fallback_when_llm_error(self) -> None:
        debate_nodes._LLM_CLIENT = _FailLLMClient()
        result = debate_nodes.assess_knowledge_support(
            {
                "case_background": "租房押金争议",
                "parsed_claim": {"claims": ["返还押金"]},
                "attack_target": "证据链薄弱",
                "retrieved_knowledge": [
                    {
                        "record_id": "CASE_CN_0001",
                        "record_type": "case",
                        "score": 88,
                        "citation": "示例案件",
                        "snippet": "若房东扣押金应承担举证责任。",
                    }
                ],
                "debug": {},
            }
        )

        self.assertEqual(result.get("knowledge_sufficiency"), True)
        self.assertEqual(len(result.get("retrieved_knowledge", [])), 1)
        self.assertEqual(result.get("debug", {}).get("knowledge_audit", {}).get("error_code"), "KNOWLEDGE_AUDIT_FAILED")

    def test_judge_continue_or_end_ignores_keyword_in_send(self) -> None:
        result = debate_nodes.judge_continue_or_end(
            {
                "current_user_input": "我不想结束，我还要继续。",
                "round_index": 1,
                "max_rounds": 5,
                "no_new_argument_streak": 1,
                "ui_action": "send",
                "parsed_claim": {"has_new_argument": False},
                "debug": {},
            }
        )

        self.assertEqual(result.get("should_end"), False)
        self.assertEqual(result.get("end_reason_code"), "IN_PROGRESS")
        self.assertEqual(result.get("no_new_argument_streak"), 2)

    def test_judge_continue_or_end_on_explicit_end(self) -> None:
        result = debate_nodes.judge_continue_or_end(
            {
                "current_user_input": "",
                "round_index": 1,
                "max_rounds": 5,
                "no_new_argument_streak": 0,
                "ui_action": "end",
                "parsed_claim": {"has_new_argument": True},
                "debug": {},
            }
        )

        self.assertEqual(result.get("should_end"), True)
        self.assertEqual(result.get("end_reason_code"), "USER_ENDED")
        self.assertIn("用户点击结束辩论", result.get("end_reason", ""))

    def test_judge_continue_or_end_on_max_rounds(self) -> None:
        result = debate_nodes.judge_continue_or_end(
            {
                "current_user_input": "继续",
                "round_index": 4,
                "max_rounds": 5,
                "no_new_argument_streak": 0,
                "ui_action": "send",
                "parsed_claim": {"has_new_argument": True},
                "debug": {},
            }
        )

        self.assertEqual(result.get("should_end"), True)
        self.assertEqual(result.get("end_reason_code"), "MAX_ROUNDS_REACHED")

    def test_ask_next_challenge_persists_snapshot_with_defensive_copy(self) -> None:
        state = {
            "round_index": 0,
            "current_user_input": "我主张退还押金",
            "parsed_claim": {"summary": "主张退还押金"},
            "attack_target": "证据链薄弱",
            "attack_target_category": "证据链薄弱",
            "attack_target_reason": "证据不足",
            "counterargument_draft": "【反方核心反驳】证据链不完整。",
            "followup_question": "请补充交接清单。",
            "counterargument_structured": {"support_gap_notes": ["缺少交接证据"]},
            "counterargument_citations": {"core_rebuttal": ["CASE_CN_0001"]},
            "counterargument_quality_flags": ["missing_citation:legal_basis"],
            "debate_history": [],
            "previous_user_inputs": [],
        }
        result = debate_nodes.ask_next_challenge(state)
        state["counterargument_structured"]["support_gap_notes"].append("后续污染")
        state["counterargument_citations"]["core_rebuttal"].append("污染ID")

        turn = result.get("debate_history", [])[0]
        self.assertEqual(turn.get("counterargument_structured_snapshot", {}).get("support_gap_notes"), ["缺少交接证据"])
        self.assertEqual(turn.get("counterargument_citations_snapshot", {}).get("core_rebuttal"), ["CASE_CN_0001"])
        self.assertEqual(turn.get("counterargument_quality_flags"), ["missing_citation:legal_basis"])

    def test_generate_debate_report_repairs_payload(self) -> None:
        debate_nodes._LLM_CLIENT = _StaticLLMClient(
            {
                "debate_background": "",
                "user_claim_summary": [],
                "defendant_rebuttal_points": [],
                "user_strengths": ["表达清晰"],
                "user_weaknesses": ["证据不足"],
                "evidence_improvement_suggestions": ["补充交接清单"],
                "legal_argument_suggestions": ["补充法条要件映射"],
                "overall_score": 999,
            }
        )
        result = debate_nodes.generate_debate_report(
            {
                "case_background": "租房押金争议",
                "debate_history": [
                    {"parsed_summary": "要求退押金", "attack_target": "证据链薄弱"},
                ],
                "ui_action": "end",
                "end_reason": "",
                "end_reason_code": "USER_ENDED",
                "debug": {},
            }
        )

        self.assertEqual(result.get("report_source"), "llm")
        self.assertEqual(result.get("report", {}).get("overall_score"), 100)
        self.assertTrue(result.get("report_quality_flags"))
        self.assertTrue(result.get("debug", {}).get("report", {}).get("repair_applied"))

    def test_generate_debate_report_fallback_on_error(self) -> None:
        debate_nodes._LLM_CLIENT = _FailLLMClient()
        result = debate_nodes.generate_debate_report(
            {
                "case_background": "租房押金争议",
                "debate_history": [],
                "ui_action": "end",
                "end_reason": "",
                "debug": {},
            }
        )

        self.assertEqual(result.get("report_source"), "fallback")
        self.assertIn("fallback_used", result.get("report_quality_flags", []))
        self.assertEqual(result.get("debug", {}).get("report", {}).get("error_code"), "REPORT_LLM_FAILED")


if __name__ == "__main__":
    unittest.main()
