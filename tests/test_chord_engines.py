"""
tests/test_chord_engines.py

Tests for Chord Engines & Engine Manager:
- LVChordiaEngine execution
- LegacyTemplateEngine fallback execution
- ChordEngineManager orchestration & fallback handling
"""

import os
import tempfile
import numpy as np
import soundfile as sf
import pytest

from backend.analysis.lv_chordia_engine import LVChordiaEngine
from backend.analysis.legacy_engine import LegacyTemplateEngine
from backend.analysis.engine_manager import ChordEngineManager
from backend.models.analysis_types import TimingData


@pytest.fixture
def temp_c_major_wav():
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    sr = 22050
    t = np.linspace(0, 3.0, int(sr * 3.0), endpoint=False)
    y = 0.5 * (np.sin(2 * np.pi * 261.63 * t) + np.sin(2 * np.pi * 329.63 * t) + np.sin(2 * np.pi * 392.00 * t))
    sf.write(path, y.astype(np.float32), sr)
    yield path
    if os.path.exists(path):
        os.remove(path)


class TestChordEngines:

    def test_lv_chordia_engine_availability(self):
        engine = LVChordiaEngine()
        is_avail, err = engine.check_availability()
        assert is_avail is True
        assert err is None
        assert engine.name == "lv_chordia"

    def test_lv_chordia_engine_analyze(self, temp_c_major_wav):
        engine = LVChordiaEngine()
        result = engine.analyze(temp_c_major_wav)
        assert result.engine == "lv_chordia"
        assert len(result.events) > 0
        assert result.fallback_reason is None

    def test_legacy_engine_analyze(self, temp_c_major_wav):
        engine = LegacyTemplateEngine()
        assert engine.name == "legacy_template"
        result = engine.analyze(
            audio_path=temp_c_major_wav,
            key="C",
            scale="Major",
            fallback_reason="primary_model_unavailable"
        )
        assert result.engine == "legacy_template"
        assert result.fallback_reason == "primary_model_unavailable"
        assert len(result.events) > 0

    def test_engine_manager_primary_and_fallback(self, temp_c_major_wav):
        mgr = ChordEngineManager()
        # Normal execution -> uses primary (lv_chordia)
        res_primary = mgr.recognize_chords(temp_c_major_wav)
        assert res_primary.engine == "lv_chordia"
        assert res_primary.fallback_reason is None

        # Forced fallback -> uses legacy template engine with explicit reason
        res_fallback = mgr.recognize_chords(temp_c_major_wav, force_fallback=True)
        assert res_fallback.engine == "legacy_template"
        assert res_fallback.fallback_reason == "force_fallback"
