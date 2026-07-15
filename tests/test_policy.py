import unittest

from social_memory_bench.generator import generate_dataset
from social_memory_bench.policy import PolicyOracle


class PolicyOracleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.dataset = generate_dataset(scale="tiny", seed=7)
        self.oracle = PolicyOracle(self.dataset)
        self.seq = {event["id"]: event["seq"] for event in self.dataset.events}

    def test_retain_seen_keeps_old_but_blocks_future_messages(self) -> None:
        after_leave = self.seq["m_launch_after_leave"]
        self.assertTrue(self.oracle.user_can_view("m_launch_codename", "u_amina", after_leave))
        self.assertFalse(self.oracle.user_can_view("m_launch_after_leave", "u_amina", after_leave))

    def test_active_window_revokes_old_history(self) -> None:
        after_leave = self.seq["leave_board_amina"]
        self.assertFalse(self.oracle.user_can_view("m_board_budget", "u_amina", after_leave))
        self.assertTrue(self.oracle.user_can_view("m_board_budget", "u_alex_kim", after_leave))

    def test_delete_is_global_and_audience_is_intersection(self) -> None:
        after_delete = self.seq["delete_temporary_code"]
        self.assertFalse(self.oracle.user_can_view("m_temporary_code", "u_omar", after_delete))
        self.assertFalse(
            self.oracle.audience_can_view(
                "m_private_venue", {"u_amina", "u_alex_kim"}, after_delete
            )
        )


if __name__ == "__main__":
    unittest.main()

