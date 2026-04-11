import unittest

from app.graph.nodes import debate_nodes


class _StaticLLMClient:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def chat_json(self, **_: object) -> dict:
        return dict(self.payload)


class _FailLLMClient:
    def chat_json(self, **_: object) -> dict:
        raise RuntimeError("mock llm failure")


class _SequenceLLMClient:
    def __init__(self, payloads: list[dict]) -> None:
        self.payloads = list(payloads)
        self.calls = 0

    def chat_json(self, **_: object) -> dict:
        if not self.payloads:
            raise RuntimeError("no payload configured")
        index = min(self.calls, len(self.payloads) - 1)
        self.calls += 1
        return dict(self.payloads[index])


class CounterargumentNodeTests(unittest.TestCase):
    def tearDown(self) -> None:
        debate_nodes._LLM_CLIENT = None

    def test_build_counterargument_returns_structured_and_compatible_draft(self) -> None:
        debate_nodes._LLM_CLIENT = _StaticLLMClient(
            {
                "claim_summary": "你方主张房东应全额退还押金。",
                "core_rebuttal": "你方尚未证明房屋损耗责任与押金返还范围的对应关系。",
                "legal_basis": "可围绕合同义务与违约责任构成要件继续论证。",
                "case_strategy": "类案通常先审查交接证据，再判断扣减合理性。",
                "evidence_challenge": "缺少退租交接清单与维修报价单原件。",
                "logic_challenge": "结论先于证明过程，推理链条不闭合。",
                "followup_question": "请提交退租交接记录与维修费用明细。",
                "support_gap_notes": [],
                "citations": {
                    "claim_summary": ["CASE_CN_0001"],
                    "core_rebuttal": ["CASE_CN_0001"],
                    "legal_basis": ["STATUTE_CN_0001"],
                    "case_strategy": ["CASE_CN_0001"],
                    "evidence_challenge": ["CASE_CN_0001"],
                    "logic_challenge": ["ISSUE_RULE_0001"],
                },
            }
        )

        result = debate_nodes.build_counterargument(
            {
                "case_background": "租房押金争议",
                "round_index": 0,
                "parsed_claim": {
                    "summary": "主张返还押金",
                    "claims": ["返还押金"],
                    "evidence": ["聊天记录"],
                    "legal_basis": ["民法典相关条款"],
                },
                "attack_target": "证据链薄弱",
                "retrieved_knowledge": [
                    {
                        "record_id": "STATUTE_CN_0001",
                        "record_type": "statute",
                        "score": 91,
                        "citation": "民法典合同编相关条款",
                        "snippet": "合同义务履行与违约责任。",
                    },
                    {
                        "record_id": "CASE_CN_0001",
                        "record_type": "case",
                        "score": 88,
                        "citation": "押金返还类案示例",
                        "snippet": "房东扣减押金需说明依据。",
                    },
                    {
                        "record_id": "ISSUE_RULE_0001",
                        "record_type": "issue_rule",
                        "score": 85,
                        "citation": "争点规则示例",
                        "snippet": "证据链不足时先攻击举证责任。",
                    },
                ],
                "knowledge_sufficiency": True,
                "knowledge_missing_aspects": [],
                "debug": {},
            }
        )

        self.assertTrue(result.get("counterargument_structured"))
        self.assertIn("【主张概括】", result.get("counterargument_draft", ""))
        self.assertIn("【进一步追问】", result.get("counterargument_draft", ""))
        self.assertTrue(result.get("followup_question"))
        self.assertEqual(
            result.get("counterargument_citations", {}).get("core_rebuttal", []),
            ["CASE_CN_0001"],
        )
        self.assertEqual(result.get("debug", {}).get("counterargument", {}).get("source_mode"), "llm")

    def test_build_counterargument_repairs_invalid_citations(self) -> None:
        debate_nodes._LLM_CLIENT = _StaticLLMClient(
            {
                "claim_summary": "主张返还押金。",
                "core_rebuttal": "证据链断裂。",
                "legal_basis": "法律依据不足。",
                "case_strategy": "参考类案。",
                "evidence_challenge": "缺少关键凭证。",
                "logic_challenge": "推理跳跃。",
                "followup_question": "请补充证据。",
                "support_gap_notes": [],
                "citations": {
                    "core_rebuttal": ["NOT_EXIST_ID"],
                    "legal_basis": [],
                    "case_strategy": [],
                    "evidence_challenge": [],
                    "logic_challenge": [],
                },
            }
        )

        result = debate_nodes.build_counterargument(
            {
                "case_background": "租房押金争议",
                "round_index": 1,
                "parsed_claim": {"summary": "主张返还押金", "claims": ["返还押金"]},
                "attack_target": "证据链薄弱",
                "retrieved_knowledge": [
                    {
                        "record_id": "CASE_CN_0001",
                        "record_type": "case",
                        "score": 88,
                        "citation": "押金返还类案示例",
                        "snippet": "房东扣减押金需说明依据。",
                    }
                ],
                "knowledge_sufficiency": True,
                "knowledge_missing_aspects": [],
                "debug": {},
            }
        )

        self.assertTrue(result.get("debug", {}).get("counterargument", {}).get("repair_applied"))
        self.assertIn("invalid_citation_removed", result.get("counterargument_quality_flags", []))
        self.assertIn(
            "missing_citation:core_rebuttal",
            result.get("counterargument_quality_flags", []),
        )
        self.assertEqual(
            result.get("counterargument_citations", {}).get("core_rebuttal", []),
            ["CASE_CN_0001"],
        )

    def test_build_counterargument_includes_gap_notes_when_knowledge_insufficient(self) -> None:
        debate_nodes._LLM_CLIENT = _StaticLLMClient(
            {
                "claim_summary": "主张返还押金。",
                "core_rebuttal": "你方缺少关键证据。",
                "legal_basis": "现有法条适配不足。",
                "case_strategy": "先补事实再走规则。",
                "evidence_challenge": "缺少交接凭证。",
                "logic_challenge": "论证链条断裂。",
                "followup_question": "请补充交接清单。",
                "support_gap_notes": [],
                "citations": {
                    "core_rebuttal": ["SYNTHETIC_SUPPORT_0001"],
                    "legal_basis": ["SYNTHETIC_SUPPORT_0001"],
                    "evidence_challenge": ["SYNTHETIC_SUPPORT_0001"],
                    "logic_challenge": ["SYNTHETIC_SUPPORT_0001"],
                },
            }
        )

        result = debate_nodes.build_counterargument(
            {
                "case_background": "租房押金争议",
                "round_index": 1,
                "parsed_claim": {"summary": "主张返还押金", "claims": ["返还押金"]},
                "attack_target": "证据链薄弱",
                "retrieved_knowledge": [
                    {
                        "record_id": "SYNTHETIC_SUPPORT_0001",
                        "record_type": "synthetic_support",
                        "score": 80,
                        "citation": "LLM补强建议",
                        "snippet": "需补充房屋交接过程证据链。",
                    }
                ],
                "knowledge_sufficiency": False,
                "knowledge_missing_aspects": ["缺少押金扣减的金额构成证明"],
                "debug": {},
            }
        )

        notes = result.get("counterargument_structured", {}).get("support_gap_notes", [])
        self.assertTrue(notes)
        self.assertIn("缺少押金扣减的金额构成证明", "".join(notes))

    def test_build_counterargument_fallback_on_llm_error(self) -> None:
        debate_nodes._LLM_CLIENT = _FailLLMClient()
        result = debate_nodes.build_counterargument(
            {
                "case_background": "租房押金争议",
                "round_index": 0,
                "parsed_claim": {"summary": "主张返还押金", "claims": ["返还押金"]},
                "attack_target": "证据链薄弱",
                "retrieved_knowledge": [],
                "knowledge_sufficiency": False,
                "knowledge_missing_aspects": ["缺少法条适配说明"],
                "debug": {},
            }
        )

        self.assertTrue(result.get("counterargument_draft"))
        self.assertTrue(result.get("counterargument_structured"))
        self.assertIn("fallback_used", result.get("counterargument_quality_flags", []))
        self.assertEqual(result.get("debug", {}).get("counterargument", {}).get("source_mode"), "fallback")
        self.assertEqual(result.get("debug", {}).get("counterargument", {}).get("error_code"), "COUNTERARGUMENT_LLM_FAILED")

    def test_build_counterargument_role_drift_retry_success(self) -> None:
        drift_payload = {
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
        repaired_payload = {
            "claim_summary": "你方主张要求返还押金。",
            "core_rebuttal": "你方主张尚未证明押金全额返还的事实与规则要件对应。",
            "legal_basis": "你方法律依据与请求结论之间仍存在要件映射不足。",
            "case_strategy": "应先核验交接事实，再审查扣减范围与举证责任分配。",
            "evidence_challenge": "你方证据链缺少入住退租同角度比对与维修支出原始凭证。",
            "logic_challenge": "你方推理在因果衔接上仍不充分，存在结论先行风险。",
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
        client = _SequenceLLMClient([drift_payload, repaired_payload])
        debate_nodes._LLM_CLIENT = client

        result = debate_nodes.build_counterargument(
            {
                "case_background": "租房押金争议",
                "round_index": 1,
                "parsed_claim": {"summary": "主张返还押金", "claims": ["返还押金"]},
                "attack_target": "证据链薄弱",
                "retrieved_knowledge": [
                    {
                        "record_id": "STATUTE_CN_0001",
                        "record_type": "statute",
                        "score": 90,
                        "citation": "民法典合同编相关条款",
                        "snippet": "合同义务履行与违约责任。",
                    },
                    {
                        "record_id": "CASE_CN_0001",
                        "record_type": "case",
                        "score": 88,
                        "citation": "押金返还类案示例",
                        "snippet": "房东扣减押金需说明依据。",
                    },
                    {
                        "record_id": "ISSUE_RULE_0001",
                        "record_type": "issue_rule",
                        "score": 85,
                        "citation": "争点规则示例",
                        "snippet": "证据链不足时先攻击举证责任。",
                    },
                ],
                "knowledge_sufficiency": True,
                "knowledge_missing_aspects": [],
                "debug": {},
            }
        )

        self.assertEqual(client.calls, 2)
        self.assertEqual(result.get("debug", {}).get("counterargument", {}).get("source_mode"), "llm")
        self.assertTrue(result.get("debug", {}).get("counterargument", {}).get("retry_applied"))
        self.assertTrue(result.get("debug", {}).get("counterargument", {}).get("role_drift_detected"))
        self.assertIn("role_drift_repaired", result.get("counterargument_quality_flags", []))
        self.assertNotIn("应返还全部押金", result.get("counterargument_draft", ""))

    def test_build_counterargument_role_drift_retry_fallback(self) -> None:
        drift_payload = {
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
                "legal_basis": ["CASE_CN_0001"],
                "case_strategy": ["CASE_CN_0001"],
                "evidence_challenge": ["CASE_CN_0001"],
                "logic_challenge": ["CASE_CN_0001"],
            },
        }
        client = _SequenceLLMClient([drift_payload, drift_payload])
        debate_nodes._LLM_CLIENT = client

        result = debate_nodes.build_counterargument(
            {
                "case_background": "租房押金争议",
                "round_index": 1,
                "parsed_claim": {"summary": "主张返还押金", "claims": ["返还押金"]},
                "attack_target": "证据链薄弱",
                "retrieved_knowledge": [
                    {
                        "record_id": "CASE_CN_0001",
                        "record_type": "case",
                        "score": 88,
                        "citation": "押金返还类案示例",
                        "snippet": "房东扣减押金需说明依据。",
                    }
                ],
                "knowledge_sufficiency": True,
                "knowledge_missing_aspects": [],
                "debug": {},
            }
        )

        self.assertEqual(client.calls, 2)
        self.assertEqual(result.get("debug", {}).get("counterargument", {}).get("source_mode"), "fallback")
        self.assertEqual(
            result.get("debug", {}).get("counterargument", {}).get("error_code"),
            "COUNTERARGUMENT_ROLE_DRIFT_FALLBACK",
        )
        self.assertTrue(result.get("debug", {}).get("counterargument", {}).get("retry_applied"))
        self.assertTrue(result.get("debug", {}).get("counterargument", {}).get("role_drift_detected"))
        self.assertIn("role_drift_fallback_used", result.get("counterargument_quality_flags", []))
        self.assertNotIn("应返还全部押金", result.get("counterargument_draft", ""))


if __name__ == "__main__":
    unittest.main()
