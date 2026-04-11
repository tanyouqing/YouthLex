import unittest
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
    from app.api import app as api_app
except ModuleNotFoundError:
    TestClient = None
    api_app = None
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
            "is_sufficient": True,
            "missing_aspects": [],
            "synthetic_support": [],
            "claim_summary": "用户主张房东应退还押金。",
            "core_rebuttal": "现有证据不足以支持全额退还。",
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
            "debate_background": "租房押金争议",
            "user_claim_summary": ["主张退还押金"],
            "defendant_rebuttal_points": ["证据不足"],
            "user_strengths": ["主张明确"],
            "user_weaknesses": ["证据薄弱"],
            "evidence_improvement_suggestions": ["补充交接记录"],
            "legal_argument_suggestions": ["补充法条适配论证"],
            "overall_score": 72,
        }


@unittest.skipIf(TestClient is None or api_app is None, "fastapi is not installed in current environment")
class APITests(unittest.TestCase):
    def setUp(self) -> None:
        debate_nodes._LLM_CLIENT = _FakeLLMClient()
        api_app._reset_runtime_for_tests()
        self.search_patch = patch(
            "app.graph.nodes.debate_nodes.search_knowledge",
            return_value=(
                [
                    {
                        "record_id": "STATUTE_CN_0001",
                        "record_type": "statute",
                        "score": 90,
                        "citation": "民法典第577条",
                        "snippet": "依法履行义务，违约承担责任。",
                    }
                ],
                {"mode": "vector", "error_code": ""},
            ),
        )
        self.search_patch.start()
        self.client = TestClient(api_app.app)

    def tearDown(self) -> None:
        self.search_patch.stop()
        debate_nodes._LLM_CLIENT = None

    def test_health(self) -> None:
        resp = self.client.get("/api/v1/health")
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(payload.get("status"), "ok")
        self.assertEqual(payload.get("service"), "debate-agent")

    def test_create_send_get_end_flow(self) -> None:
        create_resp = self.client.post(
            "/api/v1/sessions",
            json={
                "case_background": "学生租房押金争议",
                "scenario_hint": "rental_dispute",
                "max_rounds": 5,
            },
        )
        self.assertEqual(create_resp.status_code, 201)
        create_session = create_resp.json()["session"]
        session_id = create_session["session_id"]
        self.assertEqual(create_session["end_reason_code"], "IN_PROGRESS")

        send_resp = self.client.post(
            f"/api/v1/sessions/{session_id}/turn",
            json={"action": "send", "user_text": "我主张房东应全额退还押金。"},
        )
        self.assertEqual(send_resp.status_code, 200)
        send_session = send_resp.json()["session"]
        self.assertEqual(send_session["round_index"], 1)
        self.assertFalse(send_session["should_end"])
        self.assertEqual(send_session["end_reason_code"], "IN_PROGRESS")

        get_resp = self.client.get(f"/api/v1/sessions/{session_id}")
        self.assertEqual(get_resp.status_code, 200)
        get_session = get_resp.json()["session"]
        self.assertEqual(get_session["session_id"], session_id)
        self.assertEqual(get_session["history_count"], 1)

        end_resp = self.client.post(
            f"/api/v1/sessions/{session_id}/turn",
            json={"action": "end", "user_text": ""},
        )
        self.assertEqual(end_resp.status_code, 200)
        end_session = end_resp.json()["session"]
        self.assertTrue(end_session["should_end"])
        self.assertEqual(end_session["end_reason_code"], "USER_ENDED")
        self.assertTrue(end_session["report"])

    def test_end_then_send_returns_409(self) -> None:
        create_resp = self.client.post("/api/v1/sessions", json={})
        session_id = create_resp.json()["session"]["session_id"]
        self.client.post(
            f"/api/v1/sessions/{session_id}/turn",
            json={"action": "end", "user_text": ""},
        )

        send_resp = self.client.post(
            f"/api/v1/sessions/{session_id}/turn",
            json={"action": "send", "user_text": "继续辩论"},
        )
        self.assertEqual(send_resp.status_code, 409)
        payload = send_resp.json()
        self.assertEqual(payload["error"]["code"], "SESSION_ALREADY_ENDED")
        self.assertTrue(payload.get("trace_id"))

    def test_send_empty_text_returns_400_with_trace(self) -> None:
        create_resp = self.client.post("/api/v1/sessions", json={})
        session_id = create_resp.json()["session"]["session_id"]
        send_resp = self.client.post(
            f"/api/v1/sessions/{session_id}/turn",
            json={"action": "send", "user_text": "   "},
        )
        self.assertEqual(send_resp.status_code, 400)
        payload = send_resp.json()
        self.assertEqual(payload["error"]["code"], "INVALID_ARGUMENT")
        self.assertTrue(payload.get("trace_id"))

    def test_session_not_found_returns_404(self) -> None:
        resp = self.client.get("/api/v1/sessions/not_exists")
        self.assertEqual(resp.status_code, 404)
        payload = resp.json()
        self.assertEqual(payload["error"]["code"], "SESSION_NOT_FOUND")
        self.assertTrue(payload.get("trace_id"))

    def test_invalid_action_returns_400(self) -> None:
        create_resp = self.client.post("/api/v1/sessions", json={})
        session_id = create_resp.json()["session"]["session_id"]
        resp = self.client.post(
            f"/api/v1/sessions/{session_id}/turn",
            json={"action": "invalid_action", "user_text": "abc"},
        )
        self.assertEqual(resp.status_code, 400)
        payload = resp.json()
        self.assertEqual(payload["error"]["code"], "INVALID_ARGUMENT")
        self.assertTrue(payload.get("trace_id"))


if __name__ == "__main__":
    unittest.main()
