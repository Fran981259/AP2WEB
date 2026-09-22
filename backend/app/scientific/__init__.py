"""In-memory, reproducible evaluation protocol for completed match data.

This package deliberately creates no database schema and never promotes models.

Decomposto em submódulos temáticos; este pacote reexporta o API pública do
antigo módulo ``scientific_protocol``.
"""
from __future__ import annotations

from .baselines import _baseline_evaluations, _comparison
from .metrics import scientific_metrics
from .protocol import run_scientific_protocol
from .records import _metric_records
from .snapshot import build_snapshot_manifest, temporal_split

__all__ = [
    "_baseline_evaluations",
    "_comparison",
    "_metric_records",
    "build_snapshot_manifest",
    "run_scientific_protocol",
    "scientific_metrics",
    "temporal_split",
]
