"""BacktestLoop composition root and process-wide singleton."""
from __future__ import annotations

from typing import Optional

from .cycle import LoopCycleMixin
from .detailed import LoopDetailedMixin
from .state import LoopStateMixin


class BacktestLoop(LoopStateMixin, LoopCycleMixin, LoopDetailedMixin):
    """Executa ciclos síncronos; agendamento e cancelamento pertencem aos jobs."""


_loop: Optional[BacktestLoop] = None


def get_loop() -> BacktestLoop:
    """Retorna instância singleton do BacktestLoop."""
    global _loop
    if _loop is None:
        _loop = BacktestLoop()
    return _loop
