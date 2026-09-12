"""
backend/models/__init__.py
"""

from .responses import (
    ProgressResponse,
    ChordInfo,
    SectionInfo,
    ChordData,
    AnalysisResult,
    AnalysisResponse,
)
from .timeline import (
    HandVoicingNote,
    HandVoicing,
    ChordEvent,
    SectionEvent,
    NotationData,
    SongMetadata,
    SongTimeline,
    analysis_to_song_timeline,
)
from .analysis_types import (
    AudioStatus,
    AudioProfile,
    TimingData,
    CandidateSourceEvidence,
    InstrumentEvidence,
    DetectionReliability,
    AudioAnalysisMetadata,
)

from .practice_session import (
    PracticeStatus,
    PracticeMode,
    PracticeChordGuidance,
    PracticeNoteFeedbackContract,
    PracticeSession,
    create_practice_session,
    update_practice_session_time,
    seek_practice_session,
    pause_practice_session,
    resume_practice_session,
    reset_practice_session,
    set_practice_tempo,
    set_practice_simplification,
    set_practice_transposition,
)

APP_VERSION = "0.4.0"

__all__ = [
    "APP_VERSION",
    "ProgressResponse",
    "ChordInfo",
    "SectionInfo",
    "ChordData",
    "AnalysisResult",
    "AnalysisResponse",
    "HandVoicingNote",
    "HandVoicing",
    "ChordEvent",
    "SectionEvent",
    "NotationData",
    "SongMetadata",
    "SongTimeline",
    "analysis_to_song_timeline",
    "AudioStatus",
    "AudioProfile",
    "TimingData",
    "CandidateSourceEvidence",
    "InstrumentEvidence",
    "DetectionReliability",
    "AudioAnalysisMetadata",
    "PracticeStatus",
    "PracticeMode",
    "PracticeChordGuidance",
    "PracticeNoteFeedbackContract",
    "PracticeSession",
    "create_practice_session",
    "update_practice_session_time",
    "seek_practice_session",
    "pause_practice_session",
    "resume_practice_session",
    "reset_practice_session",
    "set_practice_tempo",
    "set_practice_simplification",
    "set_practice_transposition",
]

