from backend.app.reproducibility_artifact import artifact_content_hash, build_artifact, write_artifact
import pytest


def _results():
    return {
        "snapshot": {"league_id": 7, "completed_match_count": 2, "usable_match_count": 2, "hash": "abc"},
        "status": "completed",
        "promotion_enabled": False,
    }


def test_artifact_content_hash_is_deterministic_and_excludes_itself():
    first = build_artifact(
        input_parameters={"league_id": 7, "fixed_parameters": {"window": 5}},
        output_results=_results(), generated_at="2026-09-14T00:00:00Z")
    second = build_artifact(
        input_parameters={"fixed_parameters": {"window": 5}, "league_id": 7},
        output_results=_results(), generated_at="2026-09-14T00:00:00Z")

    assert first == second
    assert first["content_hash"] == artifact_content_hash(first)
    first["content_hash"] = "not-the-hash"
    assert artifact_content_hash(first) == second["content_hash"]


def test_write_artifact_refuses_overwrite_without_force(tmp_path):
    artifact = build_artifact(input_parameters={}, output_results=_results(), generated_at="2026-09-14T00:00:00Z")
    output = tmp_path / "artifact.json"

    write_artifact(output, artifact)
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        write_artifact(output, artifact)

    write_artifact(output, artifact, force=True)
