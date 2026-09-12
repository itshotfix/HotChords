"""
backend/analysis/engine_base.py

Abstract Base Class & Interfaces for Chord Recognition Engines.
Allows interchangeable primary and fallback chord models (e.g. LVChordiaEngine, LegacyTemplateEngine).
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict
from backend.models.analysis_types import TimingData


class ChordRecognitionResult(BaseModel):
    """
    Standardized result contract returned by any ChordRecognitionEngine.
    """
    engine: str = Field(..., description="Engine identifier (e.g. 'lv_chordia', 'legacy_template')")
    version: str = Field(default="1.0.0", description="Model or engine version")
    fallback_reason: Optional[str] = Field(default=None, alias="fallbackReason", description="Reason if fallback engine was invoked")
    events: List[Dict[str, Any]] = Field(default_factory=list, description="Time-aligned normalized chord events")
    raw_events: List[Dict[str, Any]] = Field(default_factory=list, alias="rawEvents", description="Unmodified model output events")
    confidence: Optional[float] = Field(default=None, description="Overall recognition confidence score [0.0, 1.0]")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class ChordRecognitionEngine(ABC):
    """
    Abstract interface for all chord recognition implementations.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique engine identifier."""
        pass

    def check_availability(self) -> tuple[bool, Optional[str]]:
        """Checks if the chord recognition engine is available."""
        return True, None

    @abstractmethod
    def analyze(
        self,
        audio_path: str,
        timing_data: Optional[TimingData] = None,
        duration: Optional[float] = None
    ) -> ChordRecognitionResult:
        """
        Executes chord recognition on the given audio file.

        Parameters
        ----------
        audio_path : str
            Absolute path to audio file.
        timing_data : Optional[TimingData]
            Beat and downbeat timing grid from TimingAnalyzer.
        duration : Optional[float]
            Total duration in seconds.

        Returns
        -------
        ChordRecognitionResult
        """
        pass
