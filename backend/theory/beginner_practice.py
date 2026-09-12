"""
backend/theory/beginner_practice.py

Deterministic Beginner Practice Intelligence & Musical Simplification Engine for HotChords (Phase 9).
Provides structured pedagogical practice guidance, difficulty categorization,
learning order ranking, tempo recommendations, practice loop selection, and multi-level simplification.

Strict Architectural Principles:
1. Pure Deterministic Python (Zero ML, zero external network calls).
2. Non-Destructive Simplification (never turns minor to major, preserves root & bass).
3. Explainable Pedagogy (every difficult chord and simplification carries a clear reason).
4. Safety Gating (honestly disables practice plans on non-harmonic or low-confidence audio).
"""

from typing import List, Dict, Optional, Tuple, Any, Union
from pydantic import BaseModel, Field, ConfigDict
import numpy as np

from backend.theory.piano_voicing import (
    parse_chord_components,
    voice_chord,
    voice_chord_progression,
    voice_four_chord_loop,
    calculate_chord_difficulty_score,
    evaluate_loop_beginner_playability,
)
from backend.theory.simplification import (
    reduce_chord_harmony,
    evaluate_beginner_difficulty,
    EASY_CHORDS,
)
from backend.theory.transposition import (
    transpose_chord_symbol,
    transpose_progression,
    evaluate_key_transpositions,
)
from backend.models.analysis_types import (
    AudioStatus,
    FourChordLoopResult,
    StructureAnalysisResult,
    DetectionReliability,
)


class ChordPracticeInfo(BaseModel):
    """Pedagogical details for an individual chord in the song's learning curriculum."""
    chord: str
    canonical_root: Optional[str] = Field(default=None, alias="canonicalRoot")
    quality: Optional[str] = None
    bass: Optional[str] = None
    difficulty_score: float = Field(..., alias="difficultyScore", description="Difficulty index [0.0, 1.0]")
    difficulty_category: str = Field(..., alias="difficultyCategory", description="'EASY', 'MODERATE', 'DIFFICULT', or 'VERY_DIFFICULT'")
    occurrence_count: int = Field(default=1, alias="occurrenceCount")
    occurrence_percentage: float = Field(default=0.0, alias="occurrencePercentage")
    learning_priority: int = Field(default=1, alias="learningPriority", description="1 = Learn First, 2 = Learn Second, etc.")
    reason: Optional[str] = None
    suggested_simplification: Optional[str] = Field(default=None, alias="suggestedSimplification")
    voicing: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class HardChordItem(BaseModel):
    """Diagnostic details for a difficult chord requiring extra practice or simplification."""
    chord: str
    difficulty_score: float = Field(..., alias="difficultyScore")
    difficulty_category: str = Field(..., alias="difficultyCategory")
    reason: str
    occurrence_count: int = Field(default=1, alias="occurrenceCount")
    suggested_simplification: Optional[str] = Field(default=None, alias="suggestedSimplification")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class PracticeSection(BaseModel):
    """Selected target section for loop practice."""
    label: str
    start: float
    end: float
    duration: float
    chords: List[str] = Field(default_factory=list)
    voicings: Optional[List[Dict[str, Any]]] = None
    available: bool = Field(default=True, description="Whether this practice section is available and valid")
    reason: Optional[str] = Field(default=None, description="Diagnostic classification ('FOUR_CHORD_LOOP', 'REPEATING_SECTION', 'ONE_CHORD_VAMP', 'NO_RELIABLE_PRACTICE_SECTION')")
    is_four_chord_loop: bool = Field(default=False, alias="isFourChordLoop")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class SimplificationOption(BaseModel):
    """Multi-level progression simplification option."""
    level: int  # 0=Original, 1=Remove Extensions, 2=Basic Triads, 3=Aggressive Reduction
    description: str
    progression: List[str] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class BeginnerPracticePlan(BaseModel):
    """
    Canonical Beginner Practice Plan contract for HotChords.
    Single unified representation consumed by frontend practice views and controllers.
    """
    available: bool = Field(default=True, description="Whether practice plan was generated successfully")
    reason: Optional[str] = Field(default=None, description="Diagnostic note or reason why plan is disabled")
    original_tempo: float = Field(..., alias="originalTempo", description="Original song tempo in BPM")
    recommended_tempo: float = Field(..., alias="recommendedTempo", description="Recommended beginner starting tempo in BPM")
    minimum_tempo: float = Field(..., alias="minimumTempo", description="Slowest recommended tempo for initial drill in BPM")
    tempo_reduction_factor: float = Field(default=0.75, alias="tempoReductionFactor", description="Scale factor applied to original tempo")
    
    # Practice Section / Loop
    recommended_section: Optional[PracticeSection] = Field(default=None, alias="recommendedSection")
    practice_loop_start: Optional[float] = Field(default=None, alias="practiceLoopStart")
    practice_loop_end: Optional[float] = Field(default=None, alias="practiceLoopEnd")
    four_chord_loop_available: bool = Field(default=False, alias="fourChordLoopAvailable")
    practice_section_available: bool = Field(default=False, alias="practiceSectionAvailable")
    
    # Vocabulary & Learning Order
    unique_chords: List[str] = Field(default_factory=list, alias="uniqueChords")
    chord_learning_order: List[ChordPracticeInfo] = Field(default_factory=list, alias="chordLearningOrder")
    hardest_chords: List[HardChordItem] = Field(default_factory=list, alias="hardestChords")
    easiest_chords: List[str] = Field(default_factory=list, alias="easiestChords")
    average_song_difficulty: float = Field(default=0.0, alias="averageSongDifficulty")
    
    # Multi-Level Simplifications
    simplification_levels: List[SimplificationOption] = Field(default_factory=list, alias="simplificationLevels")
    
    # Key Recommendations
    key_recommendation: Optional[Dict[str, Any]] = Field(default=None, alias="keyRecommendation")
    
    # Practice Coaching Tips
    practice_notes: List[str] = Field(default_factory=list, alias="practiceNotes")
    confidence: Optional[float] = Field(default=None, description="Reliability of the practice recommendations")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


def classify_difficulty_category(score: float, chord_name: str) -> str:
    """
    Step 3: Classifies a numeric difficulty score into standard categories:
    - EASY: score <= 0.25 (Natural white-key triads C, G, F, Am, Em, Dm)
    - MODERATE: 0.25 < score <= 0.55 (Single black key, simple 7ths, suspensions)
    - DIFFICULT: 0.55 < score <= 0.75 (Multi-black key minor, 4-note 7ths, slash chords)
    - VERY_DIFFICULT: score > 0.75 (Diminished, augmented, altered m7b5)
    """
    clean = chord_name.strip()
    if clean in EASY_CHORDS:
        return "EASY"
    if "dim" in clean or "°" in clean or "aug" in clean or "+" in clean or "m7b5" in clean:
        return "VERY_DIFFICULT"
    theory_diff = evaluate_beginner_difficulty(clean)
    if theory_diff == "DIFFICULT" or score >= 0.50:
        return "DIFFICULT" if score <= 0.75 else "VERY_DIFFICULT"
    elif theory_diff == "MODERATE" or score >= 0.25:
        return "MODERATE"
    elif score <= 0.25:
        return "EASY"
    else:
        return "MODERATE"


def explain_chord_difficulty(chord_name: str, score: float) -> str:
    """
    Generates transparent, human-readable pedagogical reason for chord difficulty.
    """
    root, quality, bass = parse_chord_components(chord_name)
    reasons = []

    if chord_name in EASY_CHORDS:
        return "Standard white-key natural triad; comfortable hand position."

    if bass and bass != root:
        reasons.append(f"inverted slash bass on {bass}")

    if quality in ("dim", "dim7", "°"):
        reasons.append("diminished harmony with narrow tritone interval")
    elif quality in ("aug", "+"):
        reasons.append("augmented harmony with sharp 5th interval")
    elif quality in ("m7b5",):
        reasons.append("half-diminished complex 4-note cluster")
    elif quality in ("maj7", "min7", "7"):
        reasons.append("4-note seventh chord with extended finger span")
    elif quality in ("sus2", "sus4"):
        reasons.append("suspended chord requiring finger substitution")

    # Black key analysis
    v = voice_chord(chord_name)
    rh = v.get("rightHand", [])
    black_keys = [n["note"] for n in rh if "#" in n["note"] or "b" in n["note"]]
    if len(black_keys) >= 2:
        reasons.append(f"{len(black_keys)} black keys ({', '.join(black_keys)})")
    elif len(black_keys) == 1:
        reasons.append(f"black key on {black_keys[0]}")

    if not reasons:
        return "Standard diatonic chord."
    return "; ".join(reasons).capitalize() + "."


def calculate_beginner_tempo_recommendations(
    original_bpm: float,
    avg_difficulty: float,
    confidence: Optional[float] = None
) -> Tuple[float, float, float]:
    """
    Step 6: Deterministic Beginner Tempo Recommendation Formula.
    Outputs: (recommended_tempo, minimum_tempo, reduction_factor)
    """
    safe_bpm = max(40.0, min(240.0, float(original_bpm)))

    if avg_difficulty <= 0.25:
        reduction = 0.85  # Easy: 85% BPM
    elif avg_difficulty <= 0.50:
        reduction = 0.70  # Moderate: 70% BPM
    elif avg_difficulty <= 0.75:
        reduction = 0.55  # Difficult: 55% BPM
    else:
        reduction = 0.45  # Very Difficult: 45% BPM

    # Adjust for low confidence
    if confidence is not None and confidence < 0.60:
        reduction = min(reduction, 0.60)

    recommended = round(safe_bpm * reduction, 1)
    minimum = round(max(30.0, recommended * 0.70), 1)

    return recommended, minimum, round(reduction, 2)


def generate_multi_level_simplifications(
    chords: List[str]
) -> List[SimplificationOption]:
    """
    Step 4: Generates Multi-Level Simplifications (Levels 0–3).
    - Level 0: Original detected chords
    - Level 1: Remove non-essential 7ths/extensions (Cmaj7 -> C, Am7 -> Am)
    - Level 2: Strict triads (flatten slash bass: C/E -> C)
    - Level 3: Modal beginner reduction (all to easiest core triads)
    """
    # Level 0
    l0 = list(chords)

    # Level 1: Remove extensions, keep slash chords
    l1 = []
    for c in chords:
        root, quality, bass = parse_chord_components(c)
        if not root:
            l1.append(c)
            continue
        # Preserve minor vs major
        is_minor = quality in ("min", "m", "min7", "m7", "min9", "m9", "m7b5")
        base = f"{root}m" if is_minor else root
        if bass:
            l1.append(f"{base}/{bass}")
        else:
            l1.append(base)

    # Level 2: Basic Triads (flatten slash bass)
    l2 = [reduce_chord_harmony(c) for c in chords]

    # Level 3: Core diatonic anchors
    l3 = []
    for c in l2:
        if c in ("Abm", "G#m"):
            l3.append("Am")
        elif c in ("F#", "Gb"):
            l3.append("F")
        elif c in ("B",):
            l3.append("G")
        else:
            l3.append(c)

    return [
        SimplificationOption(level=0, description="Original Harmony (Full Extensions)", progression=l0),
        SimplificationOption(level=1, description="Triads with Inversions (Safe 7th removal)", progression=l1),
        SimplificationOption(level=2, description="Standard Piano Triads (Root Position)", progression=l2),
        SimplificationOption(level=3, description="Simplified Beginner Anchors", progression=l3),
    ]


def generate_beginner_practice_plan(
    chords: List[Dict[str, Any]],
    tempo: float,
    key: str = "C",
    scale: str = "Major",
    duration: float = 0.0,
    four_chord_loop: Optional[FourChordLoopResult] = None,
    structure: Optional[StructureAnalysisResult] = None,
    reliability: Optional[DetectionReliability] = None,
    audio_status: Optional[AudioStatus] = None
) -> BeginnerPracticePlan:
    """
    Step 2: Main entry point for Beginner Practice Intelligence.
    Executes all pedagogical analyses on canonical song data.
    """
    # Safety Gating: Check for empty, silent, or non-harmonic audio
    if audio_status in (AudioStatus.EMPTY_AUDIO, AudioStatus.NO_HARMONIC_CONTENT, AudioStatus.UNSUPPORTED_AUDIO) or not chords or duration <= 0:
        return BeginnerPracticePlan(
            available=False,
            reason=f"Practice plan unavailable for audio state: {audio_status.value if audio_status else 'EMPTY'}",
            originalTempo=tempo,
            recommendedTempo=tempo,
            minimumTempo=max(30.0, tempo * 0.5),
            tempoReductionFactor=1.0,
            practiceNotes=["Audio exhibits insufficient or non-harmonic content. Upload a musical recording to generate practice recommendations."]
        )

    # Filter valid chord names
    chord_names = [
        c.get("chord") or c.get("chord_name") or c.get("chordName") or "N"
        for c in chords
    ]
    valid_chords = [c for c in chord_names if c and c.upper() not in ("N", "NONE", "NO_CHORD", "")]
    if not valid_chords:
        return BeginnerPracticePlan(
            available=False,
            reason="No reliable chord progression found in audio timeline",
            originalTempo=tempo,
            recommendedTempo=tempo,
            minimumTempo=max(30.0, tempo * 0.5),
            tempoReductionFactor=1.0,
            practiceNotes=["No harmonic chord transitions detected in audio."]
        )

    # 1. Frequency and Difficulty per Chord
    freq_map: Dict[str, int] = {}
    for c in valid_chords:
        freq_map[c] = freq_map.get(c, 0) + 1

    total_valid = len(valid_chords)
    unique_chords = sorted(list(freq_map.keys()), key=lambda k: -freq_map[k])

    chord_info_list: List[ChordPracticeInfo] = []
    hard_chords: List[HardChordItem] = []
    easiest_chords: List[str] = []
    diff_scores_all: List[float] = []

    for c in unique_chords:
        root, qual, bass = parse_chord_components(c)
        v = voice_chord(c)
        d_score = v.get("difficultyScore", 0.0)
        d_cat = classify_difficulty_category(d_score, c)
        diff_scores_all.append(d_score)

        reason = explain_chord_difficulty(c, d_score)
        simp = reduce_chord_harmony(c) if c != reduce_chord_harmony(c) else None

        info = ChordPracticeInfo(
            chord=c,
            canonicalRoot=root,
            quality=qual,
            bass=bass,
            difficultyScore=round(d_score, 3),
            difficultyCategory=d_cat,
            occurrenceCount=freq_map[c],
            occurrencePercentage=round(freq_map[c] / total_valid * 100.0, 1),
            reason=reason,
            suggestedSimplification=simp,
            voicing=v,
        )
        chord_info_list.append(info)

        if d_cat in ("DIFFICULT", "VERY_DIFFICULT"):
            hard_chords.append(HardChordItem(
                chord=c,
                difficultyScore=round(d_score, 3),
                difficultyCategory=d_cat,
                reason=reason,
                occurrenceCount=freq_map[c],
                suggestedSimplification=simp,
            ))
        elif d_cat == "EASY":
            easiest_chords.append(c)

    avg_diff = float(np.mean(diff_scores_all)) if diff_scores_all else 0.0

    # 2. Step 8: Deterministic Chord Learning Order
    # Ranking logic: EASY frequent -> MODERATE frequent -> DIFFICULT frequent -> VERY_DIFFICULT
    cat_order = {"EASY": 1, "MODERATE": 2, "DIFFICULT": 3, "VERY_DIFFICULT": 4}
    chord_info_list.sort(key=lambda x: (cat_order.get(x.difficulty_category, 5), -x.occurrence_count))
    for i, item in enumerate(chord_info_list):
        item.learning_priority = i + 1

    # 3. Step 6: Tempo Recommendations
    overall_conf = reliability.overall if reliability else None
    rec_tempo, min_tempo, red_factor = calculate_beginner_tempo_recommendations(
        original_bpm=tempo,
        avg_difficulty=avg_diff,
        confidence=overall_conf
    )

    # 4. Step 7: Practice Loop Selection & Evidence Classification
    rec_section = None
    loop_start = None
    loop_end = None
    four_chord_loop_available = False
    practice_section_available = False

    if four_chord_loop and four_chord_loop.available and four_chord_loop.chords:
        # Priority 1: Valid Four-Chord Loop
        loop_chords = four_chord_loop.simplified_chords or four_chord_loop.chords
        v_loop = voice_four_chord_loop(loop_chords)
        loop_start = four_chord_loop.start or 0.0
        loop_end = four_chord_loop.end or (loop_start + 8.0)
        four_chord_loop_available = True
        practice_section_available = True
        rec_section = PracticeSection(
            label="Four-Chord Practice Loop",
            start=round(loop_start, 3),
            end=round(loop_end, 3),
            duration=round(loop_end - loop_start, 3),
            chords=loop_chords,
            voicings=v_loop,
            available=True,
            reason="FOUR_CHORD_LOOP",
            isFourChordLoop=True,
        )
    elif structure and structure.repeating_sections:
        # Priority 2: Structurally Meaningful Repeating Section
        sec = structure.repeating_sections[0]
        loop_start = sec.start
        loop_end = sec.end
        sec_chords = [
            c.get("chord") for c in chords
            if sec.start <= float(c.get("time", c.get("start", 0.0))) <= sec.end
        ]
        unique_sec = [c for c in sec_chords if c and c not in ("N", "NO_CHORD", "NONE", "")]
        # Deduplicate consecutive while preserving order
        dedup_sec = []
        for c in unique_sec:
            if not dedup_sec or dedup_sec[-1] != c:
                dedup_sec.append(c)
        if not dedup_sec:
            dedup_sec = valid_chords[:4]

        four_chord_loop_available = False
        practice_section_available = True
        rec_section = PracticeSection(
            label=sec.label or "Repeating Section",
            start=round(sec.start, 3),
            end=round(sec.end, 3),
            duration=round(sec.duration, 3),
            chords=dedup_sec,
            voicings=voice_chord_progression(dedup_sec),
            available=True,
            reason="REPEATING_SECTION",
            isFourChordLoop=False,
        )
    elif len(unique_chords) == 1 and duration > 0:
        # Priority 3: One-Chord Vamp (e.g. RapGod or static drone progression)
        # Explicitly distinguish: PRACTICE_SECTION_AVAILABLE=True, FOUR_CHORD_LOOP_AVAILABLE=False
        vamp_chord = unique_chords[0]
        loop_start = 0.0
        loop_end = min(8.0, duration)
        four_chord_loop_available = False
        practice_section_available = True
        rec_section = PracticeSection(
            label="One-Chord Practice Vamp",
            start=0.0,
            end=round(loop_end, 3),
            duration=round(loop_end, 3),
            chords=[vamp_chord],
            voicings=voice_chord_progression([vamp_chord]),
            available=True,
            reason="ONE_CHORD_VAMP",
            isFourChordLoop=False,
        )
    else:
        # No objective repeating section or loop found in timeline (e.g. through-composed or unstructured)
        # Never fabricate an arbitrary 4-chord progression
        four_chord_loop_available = False
        practice_section_available = False
        loop_start = None
        loop_end = None
        rec_section = PracticeSection(
            label="No Practice Section Available",
            start=0.0,
            end=0.0,
            duration=0.0,
            chords=[],
            voicings=[],
            available=False,
            reason="NO_RELIABLE_PRACTICE_SECTION",
            isFourChordLoop=False,
        )

    # 5. Step 10 & 11: Key Recommendation & Transposition
    key_rec = evaluate_key_transpositions(valid_chords, current_key=key, current_scale=scale)

    # 6. Step 4: Multi-Level Simplifications
    simplifications = generate_multi_level_simplifications(unique_chords)

    # 7. Pedagogical Practice Notes
    practice_tips = []
    if hard_chords:
        top_hard = hard_chords[0]
        practice_tips.append(f"Master difficult chord '{top_hard.chord}' first ({top_hard.reason}).")
    if key_rec and key_rec.get("recommendedOffset") != 0:
        practice_tips.append(
            f"Consider practicing in '{key_rec['recommendedKey']}' (transpose {key_rec['recommendedOffset']:+d} semitones) for simpler white-key chords."
        )
    practice_tips.append(
        f"Start practicing at {rec_tempo:.0f} BPM ({red_factor*100:.0f}% of song tempo) before speeding up."
    )

    return BeginnerPracticePlan(
        available=True,
        originalTempo=round(tempo, 1),
        recommendedTempo=rec_tempo,
        minimumTempo=min_tempo,
        tempoReductionFactor=red_factor,
        recommendedSection=rec_section,
        practiceLoopStart=loop_start,
        practiceLoopEnd=loop_end,
        fourChordLoopAvailable=four_chord_loop_available,
        practiceSectionAvailable=practice_section_available,
        uniqueChords=unique_chords,
        chordLearningOrder=chord_info_list,
        hardestChords=hard_chords,
        easiestChords=easiest_chords,
        averageSongDifficulty=round(avg_diff, 3),
        simplificationLevels=simplifications,
        keyRecommendation=key_rec,
        practiceNotes=practice_tips,
        confidence=round(overall_conf, 3) if overall_conf else 0.85,
    )
