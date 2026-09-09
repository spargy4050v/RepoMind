"""Optional, non-model external aggregate-data context for the local demo."""

from __future__ import annotations

import json
import os
from urllib.error import URLError
from urllib.request import urlopen


def external_context_status() -> dict[str, object]:
    """Return optional public-context availability without blocking local review flows.

    This uses no key and is off by default. Any fetched response is context only:
    it is never persisted into Tier 2 records or sent to the scoring pipeline.
    """
    if os.getenv("MPLAD_TRACE_EXTERNAL_CONTEXT_ENABLED", "false").lower() not in {"1", "true", "yes"}:
        return {"enabled": False, "available": False, "message": "External public-data sync is disabled; local data remains available."}
    source = os.getenv("MPLAD_TRACE_EXTERNAL_CONTEXT_URL", "")
    if not source:
        return {"enabled": True, "available": False, "message": "External public-data sync is enabled but no source URL is configured."}
    try:
        with urlopen(source, timeout=3) as response:  # nosec B310 - operator-configured optional public URL
            json.loads(response.read().decode("utf-8"))
        return {"enabled": True, "available": True, "message": "External public aggregate context is available; it is not a model input."}
    except (URLError, OSError, ValueError, UnicodeDecodeError):
        return {"enabled": True, "available": False, "message": "External sync unavailable; local Tier 1/Tier 2 data remains available."}
