"""
backend/theory/__init__.py
"""

from .constants import NOTE_NAMES, NOTE_FLAT
from .theory import (
    musician_friendly_name,
    chord_note_indices,
    get_chord_notes_musician,
    chord_difficulty,
    chord_fingers,
    chord_roman,
    get_pitch_class,
    simplify_chord,
)
from .simplification import (
    simplify_timeline,
    simplify_progression,
    reduce_chord_harmony,
    evaluate_beginner_difficulty,
)

__all__ = [
    "NOTE_NAMES",
    "NOTE_FLAT",
    "musician_friendly_name",
    "chord_note_indices",
    "get_chord_notes_musician",
    "chord_difficulty",
    "chord_fingers",
    "chord_roman",
    "get_pitch_class",
    "simplify_chord",
    "simplify_timeline",
    "simplify_progression",
    "reduce_chord_harmony",
    "evaluate_beginner_difficulty",
]
