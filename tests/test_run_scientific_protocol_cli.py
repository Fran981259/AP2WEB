import runpy
import sys
from pathlib import Path

from backend.app import db, execution_store


SCRIPT = Path(__file__).resolve().parents[1] / "backend/scripts/run_scientific_protocol.py"


def test_cli_persists_execution_only_after_artifact_write(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "cli.db")
    db.init_db()
    output = tmp_path / "artifact.json"
    calls = []

    def protocol(**inputs):
        return {"snapshot": {"hash": "snapshot-hash"}, "status": "completed", "inputs": inputs}

    def artifact(*, input_parameters, output_results):
        return {"content_hash": "artifact-hash", "input_parameters": input_parameters,
                "output_results": output_results}

    def write(path, value, *, force):
        calls.append((path, value, force))
        path.write_text("artifact\n")

    monkeypatch.setattr("backend.app.scientific_protocol.run_scientific_protocol", protocol)
    monkeypatch.setattr("backend.app.reproducibility_artifact.build_artifact", artifact)
    monkeypatch.setattr("backend.app.reproducibility_artifact.write_artifact", write)
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--league-id", "7", "--fixed-parameters", '{"window":5}',
                                       "--holdout-fraction", "0.2", "--output", str(output)])

    runpy.run_path(str(SCRIPT), run_name="__main__")

    assert calls and output.read_text() == "artifact\n"
    executions = execution_store.list(execution_type="scientific_protocol")
    assert len(executions) == 1
    assert executions[0]["status"] == "completed"
    assert executions[0]["snapshot_hash"] == "snapshot-hash"
    assert executions[0]["parameters"]["fixed_parameters"] == {"window": 5}
    assert executions[0]["artifact_content_hash"] == "artifact-hash"
    assert executions[0]["results"]["status"] == "completed"
