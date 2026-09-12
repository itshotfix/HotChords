"""
backend/analysis/lv_chordia_engine.py

Primary Modern Deep Learning Chord Recognition Engine using LV-Chordia.
Transcribes large vocabulary chords (triads, 7ths, maj7, min7, dim, aug, sus2, sus4, 6, min6, 9, 11, 13, slash/inversion chords)
using a 5-model deep convolutional-recurrent ensemble with HMM temporal decoding.
"""

import os
import io
import sys
from contextlib import redirect_stdout, redirect_stderr
from typing import List, Dict, Any, Optional
import numpy as np

from backend.analysis.engine_base import ChordRecognitionEngine, ChordRecognitionResult
from backend.models.analysis_types import TimingData
from backend.theory.normalization import normalize_chord_sequence


class LVChordiaEngine(ChordRecognitionEngine):
    """
    LV-Chordia Deep Learning Chord Recognition Engine.
    """

    def __init__(self, chord_dict_name: str = "submission"):
        self.chord_dict_name = chord_dict_name
        self._is_available: Optional[bool] = None
        self._init_error: Optional[str] = None

    @property
    def name(self) -> str:
        return "lv_chordia"

    def check_availability(self) -> tuple[bool, Optional[str]]:
        """Checks if lv_chordia is importable and functional."""
        if self._is_available is not None:
            return self._is_available, self._init_error

        try:
            import lv_chordia
            from lv_chordia.chord_recognition import chord_recognition
            self._is_available = True
            self._init_error = None
        except Exception as e:
            self._is_available = False
            self._init_error = str(e)

        return self._is_available, self._init_error

    def analyze(
        self,
        audio_path: str,
        timing_data: Optional[TimingData] = None,
        duration: Optional[float] = None
    ) -> ChordRecognitionResult:
        """
        Executes deep chord recognition with LV-Chordia.
        """
        is_avail, err = self.check_availability()
        if not is_avail:
            raise RuntimeError(f"LVChordiaEngine is unavailable: {err}")

        from lv_chordia.chord_recognition import chord_recognition

        abs_audio_path = os.path.abspath(audio_path)
        if not os.path.isfile(abs_audio_path):
            raise FileNotFoundError(f"Audio file not found: {abs_audio_path}")

        # Suppress verbose terminal output from ensemble iterations and manage torch memory
        import gc
        f_null = io.StringIO()
        try:
            import torch
            with torch.inference_mode():
                with redirect_stdout(f_null), redirect_stderr(f_null):
                    raw_predictions = chord_recognition(
                        audio_path=abs_audio_path,
                        chord_dict_name=self.chord_dict_name
                    )
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            with redirect_stdout(f_null), redirect_stderr(f_null):
                raw_predictions = chord_recognition(
                    audio_path=abs_audio_path,
                    chord_dict_name=self.chord_dict_name
                )
        finally:
            gc.collect()

        if not raw_predictions:
            return ChordRecognitionResult(
                engine=self.name,
                version="1.1.0",
                events=[],
                rawEvents=[],
                confidence=0.0
            )

        # Normalize raw predictions into HotChords structure
        normalized_events = normalize_chord_sequence(raw_predictions)

        # Objective duration-weighted heuristic confidence estimation
        confidences = []
        for ev in normalized_events:
            ev_dur = ev.get('end', 0.0) - ev.get('time', 0.0)
            if ev.get('is_no_chord'):
                conf = 0.50
            elif ev_dur >= 1.0:
                conf = 0.88
            elif ev_dur >= 0.5:
                conf = 0.80
            else:
                conf = 0.70
            ev['confidence'] = conf
            confidences.append(conf)

        avg_conf = float(np.mean(confidences)) if confidences else 0.80

        return ChordRecognitionResult(
            engine=self.name,
            version="1.1.0",
            events=normalized_events,
            rawEvents=raw_predictions,
            confidence=round(avg_conf, 3)
        )
