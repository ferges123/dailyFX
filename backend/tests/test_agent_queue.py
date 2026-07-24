from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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


def test_stale_running_job_is_requeued(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_queue, "AGENT_QUEUE_DIR", tmp_path / "queues")
    root = tmp_path / "queues" / "agy"
    (root / "running").mkdir(parents=True)
    stale = root / "running" / "1-stale.json"
    stale.write_text(json.dumps({"job_id": "stale", "argv": []}), encoding="utf-8")

    _, owner, _, _ = agent_queue.enqueue_or_claim("agy", ["--target", "agy"])
    assert owner is True
    assert (root / "pending" / stale.name).exists()


def test_owner_older_than_max_age_is_replaced(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_queue, "AGENT_QUEUE_DIR", tmp_path / "queues")
    root = tmp_path / "queues" / "agy"
    root.mkdir(parents=True)
    (root / "owner.json").write_text(
        json.dumps(
            {
                "pid": agent_queue.os.getpid(),
                "target": "agy",
                "started_at": time.time() - agent_queue._OWNER_MAX_AGE_SECONDS - 1,
            }
        ),
        encoding="utf-8",
    )

    _, owner, _, _ = agent_queue.enqueue_or_claim("agy", ["--target", "agy"])

    assert owner is True


def test_owner_with_reused_non_agent_pid_is_replaced(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_queue, "AGENT_QUEUE_DIR", tmp_path / "queues")
    monkeypatch.setattr(agent_queue, "_pid_alive", lambda pid: True)
    monkeypatch.setattr(agent_queue, "_pid_is_dailyfx_agent", lambda pid: False)
    root = tmp_path / "queues" / "codex"
    root.mkdir(parents=True)
    (root / "owner.json").write_text(
        json.dumps(
            {"pid": 1234, "target": "codex", "started_at": time.time()}
        ),
        encoding="utf-8",
    )

    _, owner, _, _ = agent_queue.enqueue_or_claim("codex", ["--target", "codex"])

    assert owner is True


def test_same_schedule_retry_is_deduplicated(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_queue, "AGENT_QUEUE_DIR", tmp_path / "queues")
    first_id, first_owner, _, _ = agent_queue.enqueue_or_claim(
        "agy", ["--schedule-id", "3", "--target", "agy"]
    )
    second_id, second_owner, _, _ = agent_queue.enqueue_or_claim(
        "agy", ["--schedule-id", "3", "--target", "agy"]
    )

    assert first_owner is True
    assert second_owner is False
    assert second_id == first_id
    assert len(list((tmp_path / "queues" / "agy" / "pending").glob("*.json"))) == 1
