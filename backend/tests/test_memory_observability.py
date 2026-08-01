from app.observability.memory import memory_snapshot, process_rss_bytes


def test_process_rss_bytes_is_available_on_linux():
    rss = process_rss_bytes()

    assert rss is not None
    assert rss > 0


def test_memory_snapshot_includes_process_rss():
    snapshot = memory_snapshot()

    assert snapshot["process_rss_bytes"] > 0


def test_pipeline_trace_adds_memory_snapshot(monkeypatch):
    from app.services.generation.pipeline import shared

    captured: dict = {}

    monkeypatch.setattr(shared, "memory_snapshot", lambda: {"process_rss_bytes": 123})
    monkeypatch.setattr(shared, "append_history_trace", lambda *args, **kwargs: captured.update(kwargs))

    shared._trace_stage(object(), "task-1", stage="selected_assets", message="Assets selected", details={"count": 1})

    assert captured["details"] == {"count": 1, "memory": {"process_rss_bytes": 123}}


def test_vision_completion_trace_records_memory_snapshot(monkeypatch):
    from app.services.generation.pipeline import metadata

    traces: list[dict] = []

    monkeypatch.setattr(metadata, "_trace_stage", lambda *args, **kwargs: traces.append(kwargs))
    monkeypatch.setattr(metadata, "debug_log", lambda *args, **kwargs: None)
    monkeypatch.setattr(metadata.time, "time", lambda: 10.0)

    class Analysis:
        title = "Title"
        summary = "Summary"
        tags = ["tag"]
        token_count = 1
        provider = "test"
        model = "test-model"

    class Client:
        async def get_asset_thumbnail(self, asset_id, size):
            assert asset_id == "asset-1"
            assert size == "preview"
            return b"preview", "image/jpeg"

    class Settings:
        default_ai_provider = "test"
        default_ai_model = "test-model"

    async def analyze_image(*args, **kwargs):
        return Analysis()

    import app.services.generation.ai_vision as ai_vision

    monkeypatch.setattr(ai_vision, "analyze_image", analyze_image)

    import asyncio

    state = {
        "ai_title": None,
        "ai_summary": None,
        "ai_tags": [],
        "ai_token_count": None,
        "ai_provider": None,
        "ai_model": None,
    }
    provenance = {"source_vision": {}}
    asyncio.run(
        metadata._apply_source_vision(
            db=object(),
            client=Client(),
            source_asset=object(),
            source_asset_id="asset-1",
            people_context=None,
            settings=Settings(),
            task_id="task-1",
            state=state,
            metadata_provenance=provenance,
            _task_update=lambda **kwargs: None,
            _progress=lambda message: None,
        )
    )

    assert traces[-1]["stage"] == "source_vision_complete"
    assert traces[-1]["details"]["elapsed_seconds"] == 0.0
    assert traces[-1]["details"]["source_image"] == "immich_preview"


def test_isolated_worker_initializes_database_before_opening_session(monkeypatch):
    import asyncio

    import app.database as database
    import app.services.immich as immich
    from app.workers import generation_worker

    initialized = []
    closed = []
    messages = []

    class Session:
        def get(self, model, task_id):
            return None

        def close(self):
            closed.append(True)

    class ResultQueue:
        def put(self, value):
            messages.append(value)

    monkeypatch.setattr(database, "_ensure_engine", lambda: initialized.append(True))
    monkeypatch.setattr(database, "SessionLocal", lambda: Session())
    monkeypatch.setattr(immich, "get_or_create_settings", lambda session: object())

    asyncio.run(generation_worker._run_generation_task("missing-task", ResultQueue()))

    assert initialized == [True]
    assert messages == [{"status": "failed", "error": "Queued task was not found"}]
    assert closed == [True]
