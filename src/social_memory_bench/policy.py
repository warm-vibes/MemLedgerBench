from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from .dataset import BenchmarkDataset


class PolicyOracle:
    """Gold authorization oracle evaluated independently of the system under test.

    History policies:
    - public: every user can read every non-deleted message.
    - retain_seen: a user keeps messages posted while they were a member, but never
      receives messages posted outside a membership interval.
    - active_window: a user must have been a member when the message was posted and
      must still be a member when the answer is produced (retroactive revocation).
    - current_full: a current member can read the complete non-deleted history,
      including history from before they joined; former members cannot.
    """

    def __init__(self, dataset: BenchmarkDataset):
        self.dataset = dataset
        self._events = dataset.event_by_id()
        self._spaces = {str(space["id"]): space for space in dataset.spaces}
        self._memberships: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        self._deletions: dict[str, int] = {}
        self._policy_changes: dict[str, list[tuple[int, str]]] = defaultdict(list)
        for event in dataset.events:
            event_type = event.get("type")
            if event_type == "membership":
                self._memberships[(str(event["space_id"]), str(event["user_id"]))].append(event)
            elif event_type == "delete":
                target = str(event["target_event_id"])
                seq = int(event["seq"])
                self._deletions[target] = min(seq, self._deletions.get(target, seq))
            elif event_type == "policy_change":
                self._policy_changes[str(event["space_id"])].append(
                    (int(event["seq"]), str(event["history_policy"]))
                )

    def history_policy(self, space_id: str, at_seq: int) -> str:
        policy = str(self._spaces[space_id]["history_policy"])
        for seq, changed_policy in self._policy_changes.get(space_id, []):
            if seq > at_seq:
                break
            policy = changed_policy
        return policy

    def is_member(self, user_id: str, space_id: str, at_seq: int) -> bool:
        active = False
        for event in self._memberships.get((space_id, user_id), []):
            if int(event["seq"]) > at_seq:
                break
            active = event.get("action") == "join"
        return active

    def is_deleted(self, event_id: str, at_seq: int) -> bool:
        deleted_at = self._deletions.get(event_id)
        return deleted_at is not None and deleted_at <= at_seq

    def user_can_view(self, event_id: str, user_id: str, at_seq: int) -> bool:
        event = self._events.get(event_id)
        if not event or event.get("type") != "message":
            return False
        if int(event["seq"]) > at_seq or self.is_deleted(event_id, at_seq):
            return False

        space_id = str(event["space_id"])
        policy = self.history_policy(space_id, at_seq)
        if policy == "public":
            return True
        member_when_posted = self.is_member(user_id, space_id, int(event["seq"]))
        member_now = self.is_member(user_id, space_id, at_seq)
        if policy == "retain_seen":
            return member_when_posted
        if policy == "active_window":
            return member_when_posted and member_now
        if policy == "current_full":
            return member_now
        return False

    def audience_can_view(
        self, event_id: str, recipients: Iterable[str], at_seq: int
    ) -> bool:
        recipient_set = set(recipients)
        return bool(recipient_set) and all(
            self.user_can_view(event_id, user_id, at_seq) for user_id in recipient_set
        )

    def visible_message_ids(
        self, recipients: Iterable[str], at_seq: int
    ) -> set[str]:
        recipient_set = set(recipients)
        return {
            str(event["id"])
            for event in self.dataset.events
            if event.get("type") == "message"
            and self.audience_can_view(str(event["id"]), recipient_set, at_seq)
        }
