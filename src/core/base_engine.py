"""
DoremiFa Xolatido — Base Engine
Abstract interface that every generation engine must implement.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict

from .engine_types import GenerationParams


class BaseEngine(ABC):
    """
    Universal interface for all DoremiFa generation engines.

    Every engine (audio, video, voice, image, lyrics, avatar, …) must
    inherit from this class and implement the three abstract methods below.
    This contract allows the DoremiFaEngine to treat all engines uniformly
    and makes the plugin architecture possible.
    """

    # ------------------------------------------------------------------
    # Required interface
    # ------------------------------------------------------------------

    @abstractmethod
    def generate(self, params: GenerationParams) -> str:
        """
        Generate media from the supplied parameters.

        Returns
        -------
        str
            Absolute path to the generated output file.
        """

    @abstractmethod
    def health_check(self) -> bool:
        """
        Verify that the engine is ready to generate.

        Returns
        -------
        bool
            True if the engine is operational, False otherwise.
        """

    @abstractmethod
    def capabilities(self) -> Dict[str, Any]:
        """
        Describe what this engine can produce.

        Returns
        -------
        dict
            A free-form dictionary describing supported styles, quality
            levels, maximum duration, etc.
        """
