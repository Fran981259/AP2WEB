"""Run a fixed scientific protocol evaluation and save an auditable JSON artifact.

Example:
    python backend/scripts/run_scientific_protocol.py --league-id 17 \
      --fixed-parameters '{"window":5,"home_adv":1.1,"feature":"goals","rho":0}' \
      --holdout-fraction 0.2 --output artifact.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.reproducibility_artifact import build_artifact, write_artifact  # noqa: E402
from backend.app.scientific_protocol import run_scientific_protocol  # noqa: E402
from backend.app import execution_store  # noqa: E402


def _fixed_parameters(value: str) -> dict[str, Any]:
    try:
        parameters = json.loads(value)
    except json.JSONDecodeError as error:
        raise argparse.ArgumentTypeError("--fixed-parameters must be a JSON object") from error
    if not isinstance(parameters, dict):
        raise argparse.ArgumentTypeError("--fixed-parameters must be a JSON object")
    return parameters


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--league-id", required=True, type=int, help="league to evaluate")
    parser.add_argument("--fixed-parameters", required=True, type=_fixed_parameters,
                        help="fixed model parameters as a JSON object")
    parser.add_argument("--holdout-fraction", required=True, type=float,
                        help="newest chronological fraction reserved for holdout (0 < value <= 0.5)")
    parser.add_argument("--bootstrap-resamples", type=int, default=1_000)
    parser.add_argument("--bootstrap-seed", type=int, default=0)
    parser.add_argument("--output", required=True, type=Path, help="new artifact path")
    parser.add_argument("--force", action="store_true", help="allow replacement of an existing artifact")
    args = parser.parse_args()

    inputs = {
        "league_id": args.league_id,
        "fixed_parameters": args.fixed_parameters,
        "holdout_fraction": args.holdout_fraction,
        "bootstrap_resamples": args.bootstrap_resamples,
        "bootstrap_seed": args.bootstrap_seed,
    }
    results = run_scientific_protocol(**inputs)
    artifact = build_artifact(input_parameters=inputs, output_results=results)
    write_artifact(args.output, artifact, force=args.force)
    execution = execution_store.start(
        execution_type="scientific_protocol",
        snapshot_hash=results["snapshot"]["hash"],
        parameters=inputs,
    )
    execution_store.finish(
        execution_id=execution["execution_id"],
        status=results["status"],
        artifact_content_hash=artifact["content_hash"],
        results=results,
    )
    print(f"wrote {args.output} ({artifact['content_hash']})")


if __name__ == "__main__":
    main()
