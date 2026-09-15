from backend.app import db, execution_store


def test_execution_events_are_append_only_and_latest_state_is_derived(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "executions.db")
    db.init_db()

    started = execution_store.start(
        execution_type="scientific_protocol",
        snapshot_hash="snapshot-1",
        parameters={"window": 5, "nested": {"b": 2, "a": 1}},
    )
    finished = execution_store.finish(
        execution_id=started["execution_id"],
        status="completed",
        artifact_content_hash="artifact-1",
        results={"status": "completed", "metric": 0.2},
    )

    rows = db.run_query("SELECT * FROM execution_events WHERE execution_id=?", (started["execution_id"],))
    assert len(rows) == 2
    assert started["event_type"] == "started"
    assert started["parameters"] == {"window": 5, "nested": {"a": 1, "b": 2}}
    assert finished["event_type"] == "finished"
    assert finished["artifact_content_hash"] == "artifact-1"
    assert execution_store.get(started["execution_id"]) == finished
    assert execution_store.list(execution_type="scientific_protocol") == [finished]


def test_execution_store_requires_a_single_started_then_terminal_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "executions.db")
    db.init_db()

    try:
        execution_store.finish(
            execution_id="missing", status="failed", artifact_content_hash="artifact", results={})
    except ValueError as error:
        assert "must be started" in str(error)
    else:
        raise AssertionError("finishing a missing execution must fail")

    started = execution_store.start(
        execution_type="scientific_protocol", snapshot_hash="snapshot", parameters={})
    execution_store.finish(
        execution_id=started["execution_id"], status="blocked",
        artifact_content_hash="artifact", results={"status": "blocked"})
    try:
        execution_store.finish(
            execution_id=started["execution_id"], status="completed",
            artifact_content_hash="other", results={})
    except ValueError as error:
        assert "already has a terminal event" in str(error)
    else:
        raise AssertionError("a second terminal event must fail")


def test_canonical_json_is_stable():
    assert execution_store.canonical_json({"b": 2, "a": {"z": 1}}) == '{"a":{"z":1},"b":2}'
