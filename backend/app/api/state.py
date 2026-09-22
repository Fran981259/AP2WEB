"""Process-level API state shared between the lifespan and the health router."""
from __future__ import annotations

APP_VERSION = "0.2.0"

# ``None`` = startup not finished yet; ``True`` = ready; ``False`` = startup
# failed. Written by ``main._lifespan`` and read by ``api.health.ready``.
started_ok: bool | None = None
