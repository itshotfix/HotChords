"""
backend/analysis/engine_manager.py

Chord Engine Manager for HotChords.
Manages primary (LVChordiaEngine) and fallback (LegacyTemplateEngine) engines,
orchestrating recognition, normalization, and temporal post-processing.
"""

import logging
from typing import Optional, List, Dict, Any
from backend.analysis.engine_base import ChordRecognitionEngine, ChordRecognitionResult
from backend.analysis.lv_chordia_engine import LVChordiaEngine
from backend.analysis.legacy_engine import LegacyTemplateEngine
from backend.analysis.temporal_postprocessing import postprocess_chord_progression
from backend.models.analysis_types import TimingData

logger = logging.getLogger(__name__)


class ChordEngineManager:
    """
    Orchestrates chord recognition across primary and fallback engines.
    """

    def __init__(self, primary_engine: Optional[ChordRecognitionEngine] = None, fallback_engine: Optional[ChordRecognitionEngine] = None):
        self.primary_engine = primary_engine or LVChordiaEngine()
        self.fallback_engine = fallback_engine or LegacyTemplateEngine()

    def recognize_chords(
        self,
        audio_path: str,
        timing_data: Optional[TimingData] = None,
        duration: Optional[float] = None,
        key: str = "C",
        scale: str = "Major",
        force_fallback: bool = False
    ) -> ChordRecognitionResult:
        """
        Executes chord recognition with automatic fallback.
        """
        result: Optional[ChordRecognitionResult] = None

        if not force_fallback:
            try:
                result = self.primary_engine.analyze(
                    audio_path=audio_path,
                    timing_data=timing_data,
                    duration=duration
                )
            except Exception as e:
                logger.warning(f"Primary chord engine ({self.primary_engine.name}) failed: {e}. Triggering fallback.")
                result = None

        if result is None:
            reason = "force_fallback" if force_fallback else "primary_engine_failed"
            result = self.fallback_engine.analyze(
                audio_path=audio_path,
                timing_data=timing_data,
                duration=duration,
                key=key,
                scale=scale,
                fallback_reason=reason
            )

        # Apply temporal post-processing and beat alignment
        if result.events:
            result.events = postprocess_chord_progression(
                events=result.events,
                timing_data=timing_data,
                min_duration=0.15,
                snap_to_beats=True
            )

        return result
