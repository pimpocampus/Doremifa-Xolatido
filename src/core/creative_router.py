"""
DoremiFa Xolatido — Creative Router
Analyses a natural-language prompt and decides which engine(s) should
handle it.

The router keeps DoremiFaEngine free of hard-coded ``if/elif`` chains.
As new engines are registered the router automatically considers them.
"""

import logging
import re
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .base_engine import BaseEngine

logger = logging.getLogger("doremifa.creative_router")

# ---------------------------------------------------------------------------
# Keyword → engine-name mapping
# ---------------------------------------------------------------------------
# Each rule maps a compiled regex to one or more engine names that should
# handle prompts matching that pattern.  Rules are evaluated in order; the
# first match wins for single-engine routing, but multi-engine routing
# collects all matches.
_ROUTING_RULES: List[Dict] = [
    {
        "pattern": re.compile(
            r"\b(music[\s-]?video|mv|visual[\s-]?track)\b", re.IGNORECASE
        ),
        "engines": ["audio", "video"],
        "label": "music_video",
    },
    {
        "pattern": re.compile(
            r"\b(song|track|beat|melody|chord|rhythm|bpm|audio|sound|music)\b",
            re.IGNORECASE,
        ),
        "engines": ["audio"],
        "label": "audio",
    },
    {
        "pattern": re.compile(
            r"\b(video|visual|animation|clip|film|cinematic|scene)\b",
            re.IGNORECASE,
        ),
        "engines": ["video"],
        "label": "video",
    },
    {
        "pattern": re.compile(
            r"\b(voice|vocal|sing|speech|narrat)\b", re.IGNORECASE
        ),
        "engines": ["voice"],
        "label": "voice",
    },
    {
        "pattern": re.compile(
            r"\b(lyric|word|poem|rap|verse|chorus)\b", re.IGNORECASE
        ),
        "engines": ["lyrics"],
        "label": "lyrics",
    },
    {
        "pattern": re.compile(
            r"\b(image|photo|picture|artwork|album[\s-]?art|poster)\b",
            re.IGNORECASE,
        ),
        "engines": ["image"],
        "label": "image",
    },
]

_FALLBACK_ENGINE = "audio"


class CreativeRouter:
    """
    Routes a prompt to one or more registered engines.

    Usage::

        router = CreativeRouter(engine_registry)
        engines = router.route("dark cinematic trap video")
        # → [VideoEngine, AudioEngine]
    """

    def __init__(self, engines: Optional[Dict[str, "BaseEngine"]] = None):
        self.engines: Dict[str, "BaseEngine"] = engines or {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def route(self, prompt: str) -> List["BaseEngine"]:
        """
        Return the ordered list of engine instances best suited for
        *prompt*.  Falls back to the audio engine (or the first registered
        engine) when no rule matches.
        """
        engine_names = self._resolve_names(prompt)
        result: List["BaseEngine"] = []
        for name in engine_names:
            engine = self.engines.get(name)
            if engine is not None:
                result.append(engine)
            else:
                logger.debug(
                    "Engine %r required by routing rule but not registered", name
                )

        if not result:
            fallback = self.engines.get(_FALLBACK_ENGINE) or (
                next(iter(self.engines.values()), None)
            )
            if fallback:
                logger.info(
                    "No rule matched prompt %r; falling back to %s",
                    prompt,
                    _FALLBACK_ENGINE,
                )
                result.append(fallback)

        return result

    def route_label(self, prompt: str) -> str:
        """Return the label of the best-matching rule (for logging/UI)."""
        for rule in _ROUTING_RULES:
            if rule["pattern"].search(prompt):
                return rule["label"]
        return _FALLBACK_ENGINE

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_names(self, prompt: str) -> List[str]:
        """Return deduplicated engine names that match *prompt*."""
        seen: Dict[str, None] = {}  # preserve insertion order, deduplicate
        for rule in _ROUTING_RULES:
            if rule["pattern"].search(prompt):
                for name in rule["engines"]:
                    seen[name] = None
        return list(seen)
