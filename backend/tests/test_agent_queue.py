from __future__ import annotations

import json

from dailyfx_agent import queue as agent_queue


def test_same_target_is_queued_without_second_owner(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_queue, "AGENT_QUEUE_DIR", tmp_path / "queues")

    first_id, first_owner, _, first_pid = agent_queue.enqueue_or_claim(
        "agy", ["--schedule-id", "1", "--target", "agy"]
    )
    second_id, second_owner, position, owner_pid = agent_queue.enqueue_or_claim(
        "agy", ["--schedule-id", "2", "--target", "agy"]
    )

    assert first_owner is True
    assert second_owner is False
    assert first_pid == owner_pid
    assert position == 2
    assert (tmp_path / "queues" / "agy" / "pending").exists()

    assert agent_queue.claim_job("agy", first_id) is True
    payload, running = agent_queue.next_job("agy")
    assert payload["job_id"] == second_id
    agent_queue.finish_job(running)
    agent_queue.release_owner("agy")


def test_stale_owner_is_replaced(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_queue, "AGENT_QUEUE_DIR", tmp_path / "queues")
    root = tmp_path / "queues" / "codex"
    root.mkdir(parents=True)
    (root / "owner.json").write_text(
        json.dumps({"pid": 999999, "target": "codex"}), encoding="utf-8"
    )

    _, owner, _, _ = agent_queue.enqueue_or_claim("codex", ["--target", "codex"])
    assert owner is True
