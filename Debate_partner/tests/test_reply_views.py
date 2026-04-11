import unittest

from app.graph.nodes.debate_nodes import _build_reply_views


class ReplyViewTests(unittest.TestCase):
    def test_build_reply_views_with_standard_sections(self) -> None:
        draft = (
            "【主张概括】你方主张押金应全额返还。\n"
            "【反方核心反驳】你方未证明损失与违约的因果关系。\n"
            "【法律依据】民法典第577条。\n"
            "【证据质疑】缺少入住退租对比影像。"
        )
        views = _build_reply_views(draft, "请说明损失与违约之间的对应关系。")

        self.assertIn("【核心反驳】", views["assistant_brief"])
        self.assertIn("你方未证明损失与违约的因果关系", views["assistant_brief"])
        self.assertIn("【进一步追问】请说明损失与违约之间的对应关系。", views["assistant_brief"])
        self.assertIn("【法律依据】", views["assistant_detail"])
        self.assertIn("【证据质疑】", views["assistant_detail"])

    def test_build_reply_views_without_labels(self) -> None:
        draft = "你的主张目前证据不足，无法支持结论。"
        views = _build_reply_views(draft, "请补充证据来源。")

        self.assertIn("你的主张目前证据不足", views["assistant_brief"])
        self.assertIn("【进一步追问】请补充证据来源。", views["assistant_brief"])
        self.assertIn("你的主张目前证据不足", views["assistant_detail"])

    def test_build_reply_views_uses_followup_from_draft_when_missing(self) -> None:
        draft = (
            "【反方核心反驳】你方法律路径不完整。\n"
            "【进一步追问】请说明劳动关系认定证据。"
        )
        views = _build_reply_views(draft, "")

        self.assertIn("【进一步追问】请说明劳动关系认定证据。", views["assistant_brief"])
        self.assertIn("【进一步追问】请说明劳动关系认定证据。", views["assistant_detail"])


if __name__ == "__main__":
    unittest.main()
