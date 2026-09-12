"""
tests/test_source_separation.py

Unit tests for Phase 3 Demucs stem separation and provenance preservation:
- SeparatedSourcesResult container properties and backward-compatible 3-tuple unpacking
- get_stem_paths dictionary mapping
- Cache lookup and cleanup
"""

import os
import tempfile
import pytest
from backend.analysis.source_separation import (
    SeparatedSourcesResult,
    get_stem_paths,
    cleanup_stems,
    STEMS_DIR
)


def test_separated_sources_result_tuple_unpacking():
    """Verify SeparatedSourcesResult can be unpacked as a 3-tuple for legacy code."""
    res = SeparatedSourcesResult(
        inst_path="/tmp/test_inst.wav",
        voc_path="/tmp/test_voc.wav",
        bass_path="/tmp/test_bass.wav",
        other_path="/tmp/test_other.wav",
        drums_path="/tmp/test_drums.wav",
        success=True,
        device="cpu"
    )

    inst, voc, ok = res
    assert inst == "/tmp/test_inst.wav"
    assert voc == "/tmp/test_voc.wav"
    assert ok is True

    # Direct attribute access for Phase 3 components
    assert res.bass_path == "/tmp/test_bass.wav"
    assert res.other_path == "/tmp/test_other.wav"
    assert res.drums_path == "/tmp/test_drums.wav"
    assert res.device == "cpu"


def test_get_stem_paths():
    """Verify get_stem_paths returns complete set of expected stem paths."""
    filepath = "/tmp/my_song.mp3"
    paths = get_stem_paths(filepath)

    assert "inst" in paths
    assert "vocals" in paths
    assert "bass" in paths
    assert "other" in paths
    assert "drums" in paths

    assert paths["bass"].endswith("my_song_bass.wav")
    assert paths["other"].endswith("my_song_other.wav")
    assert paths["drums"].endswith("my_song_drums.wav")
    assert paths["vocals"].endswith("my_song_vocals.wav")
    assert paths["inst"].endswith("my_song_inst.wav")


def test_cleanup_stems():
    """Verify cleanup_stems removes cached stem files."""
    filepath = os.path.join(tempfile.gettempdir(), "test_cleanup_track.wav")
    paths = get_stem_paths(filepath)

    # Create dummy files
    for p in paths.values():
        with open(p, "w") as f:
            f.write("dummy")
        assert os.path.exists(p)

    cleanup_stems(filepath)

    for p in paths.values():
        assert not os.path.exists(p)
