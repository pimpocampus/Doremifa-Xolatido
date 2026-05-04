"""
DoremiFa Xolatido — Creative Memory
Persistent taste / style preferences for an artist.

Stores and retrieves the creative fingerprint of an artist so that
DoremiFa can develop "style consciousness" over time.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger("doremifa.creative_memory")

# Defaults used when a preference has never been set
_DEFAULTS: Dict[str, Any] = {
    "preferred_bpm": 120,
    "visual_palette": ["dark", "cinematic"],
    "vocal_tone": "warm",
    "storytelling_patterns": [],
    "genre_preferences": [],
    "style_tags": [],
}


class CreativeMemory:
    """
    Persistent key-value store for an artist's creative preferences.

    Preferences are serialised as a JSON file so they survive restarts.
    Any key can be stored; a set of well-known keys is documented in
    ``_DEFAULTS`` above.
    """

    def __init__(self, memory_path: str = "creative_memory.json"):
        self.memory_path = memory_path
        self._data: Dict[str, Any] = dict(_DEFAULTS)
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """Return a stored preference, falling back to *default*."""
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Persist a preference."""
        self._data[key] = value
        self._save()
        logger.debug("Creative memory updated: %s = %r", key, value)

    def update(self, preferences: Dict[str, Any]) -> None:
        """Bulk-update multiple preferences."""
        self._data.update(preferences)
        self._save()

    def all(self) -> Dict[str, Any]:
        """Return a copy of the entire memory."""
        return dict(self._data)

    def append_to_list(self, key: str, value: Any) -> None:
        """Append *value* to a list-valued preference."""
        current = self._data.get(key, [])
        if not isinstance(current, list):
            raise TypeError(f"Preference {key!r} is not a list")
        current.append(value)
        self._data[key] = current
        self._save()

    def reset(self) -> None:
        """Reset all preferences to factory defaults."""
        self._data = dict(_DEFAULTS)
        self._save()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if os.path.exists(self.memory_path):
            try:
                with open(self.memory_path) as fh:
                    stored = json.load(fh)
                self._data.update(stored)
                logger.info("Creative memory loaded from %s", self.memory_path)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning(
                    "Could not read creative memory (%s); using defaults", exc
                )

    def _save(self) -> None:
        try:
            with open(self.memory_path, "w") as fh:
                json.dump(self._data, fh, indent=2)
        except OSError as exc:
            logger.error("Could not persist creative memory: %s", exc)
