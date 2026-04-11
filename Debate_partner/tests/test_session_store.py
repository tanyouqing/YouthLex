import unittest
from datetime import datetime, timedelta, timezone

from app.api.errors import SessionNotFoundError
from app.api.store import SessionStore


class SessionStoreTests(unittest.TestCase):
    def test_create_get_update_and_ttl_expire(self) -> None:
        now_ref = {"value": datetime(2026, 4, 9, 10, 0, 0, tzinfo=timezone.utc)}
        store = SessionStore(ttl_seconds=10, now_fn=lambda: now_ref["value"])

        _, state, _ = store.create(
            {
                "session_id": "session_store_test_01",
                "case_background": "租房押金争议",
                "scenario_hint": "rental_dispute",
                "max_rounds": 5,
                "round_index": 0,
            }
        )
        self.assertEqual(state.get("round_index"), 0)

        read_state, _ = store.get("session_store_test_01")
        self.assertEqual(read_state.get("scenario_hint"), "rental_dispute")

        now_ref["value"] = now_ref["value"] + timedelta(seconds=5)
        updated_state, _ = store.run_turn(
            "session_store_test_01",
            lambda current: {**current, "round_index": 1},
        )
        self.assertEqual(updated_state.get("round_index"), 1)

        now_ref["value"] = now_ref["value"] + timedelta(seconds=11)
        with self.assertRaises(SessionNotFoundError):
            store.get("session_store_test_01")

    def test_run_turn_on_missing_session_raises(self) -> None:
        store = SessionStore(ttl_seconds=10)
        with self.assertRaises(SessionNotFoundError):
            store.run_turn("missing_session", lambda current: current)


if __name__ == "__main__":
    unittest.main()

