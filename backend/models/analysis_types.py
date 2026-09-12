"""
backend/models/analysis_types.py

Structured data models for Phase 1 Audio Intelligence Foundation:
- AudioStatus (explicit failure and quality states)
- AudioProfile (objective acoustic and MIR measurements)
- TimingData (timing, beat and downbeat grid metadata)
- CandidateSourceEvidence & HarmonicEvidence (multi-source harmonic information)
- InstrumentEvidence (explicit non-fabricated instrument reporting)
- DetectionReliability (multi-dimensional reliability indicators)
- AudioAnalysisMetadata (canonical container for all MIR metadata)
"""

from enum import Enum
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field, ConfigDict


class AudioStatus(str, Enum):
    """
    Explicit analysis states for audio evaluation.
    Represents objective physical and harmonic conditions of the audio signal.
    """
    SUCCESS = "SUCCESS"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    NO_HARMONIC_CONTENT = "NO_HARMONIC_CONTENT"
    EMPTY_AUDIO = "EMPTY_AUDIO"
    UNSUPPORTED_AUDIO = "UNSUPPORTED_AUDIO"


class AudioProfile(BaseModel):
    """
    Objective acoustic and MIR profile of an audio input.
    Contains measurable physical characteristics without arbitrary subjective percentages.
    """
    duration: float = Field(..., description="Audio duration in seconds")
    sample_rate: int = Field(..., description="Sampling rate in Hz (e.g., 22050 or 44100)")
    channels: int = Field(default=1, description="Number of audio channels (1=mono, 2=stereo)")
    rms: float = Field(..., description="Mean Root Mean Square energy / loudness estimate [0.0, 1.0]")
    silence_ratio: float = Field(..., description="Proportion of frames below the silence threshold (-60 dBFS) [0.0, 1.0]")
    clipping_ratio: float = Field(..., description="Proportion of samples near or exceeding digital saturation [0.0, 1.0]")
    harmonic_energy: float = Field(..., description="Mean harmonic energy ratio from HPSS decomposition [0.0, 1.0]")
    pitch_activity: float = Field(..., description="Proportion of temporal frames exhibiting salient pitch content [0.0, 1.0]")
    spectral_flatness: float = Field(..., description="Wiener entropy / spectral flatness (0=tonal harmonic, 1=white noise) [0.0, 1.0]")
    chroma_strength: float = Field(..., description="Mean peak prominence of the pitch class energy distribution [0.0, 1.0]")
    chroma_entropy: float = Field(..., description="Shannon entropy of normalized chroma (low=focused pitch, high=uniform noise) [0.0, 1.0]")
    beat_confidence: Optional[float] = Field(default=None, description="Objective beat tracking periodicity / pulse clarity score [0.0, 1.0]")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class TimingData(BaseModel):
    """
    Beat and downbeat timing grid metadata.
    Provides decoupled rhythm foundations for future chord and measure segmentation.
    """
    tempo: float = Field(..., description="Estimated tempo in beats per minute (BPM)")
    time_signature: str = Field(default="4/4", alias="timeSignature", description="Estimated musical time signature (e.g., '4/4', '3/4')")
    beat_times: List[float] = Field(default_factory=list, alias="beatTimes", description="Array of beat timestamps in seconds")
    downbeat_times: Optional[List[float]] = Field(default=None, alias="downbeatTimes", description="Array of measure downbeat timestamps in seconds")
    beat_confidence: Optional[float] = Field(default=None, alias="beatConfidence", description="Confidence score in the detected pulse grid [0.0, 1.0]")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class CandidateSourceEvidence(BaseModel):
    """
    Evidence extracted from a specific audio source or stem candidate
    (e.g., Original Mix, HPSS Harmonic, Other/Harmonic Stem, Bass Stem).
    """
    source_name: str = Field(..., alias="sourceName", description="Source identifier (e.g., 'mix', 'harmonic_hpss', 'other', 'bass')")
    source_type: Optional[str] = Field(default="mix", alias="sourceType", description="Category: 'mix', 'stem', or 'hpss'")
    instrument: Optional[str] = Field(default=None, description="Inferred or associated instrument family")
    is_available: bool = Field(default=True, alias="isAvailable", description="Whether this candidate source was extracted and analyzed")
    harmonic_energy: Optional[float] = Field(default=None, alias="harmonicEnergy", description="Harmonic energy ratio of this source")
    pitch_activity: Optional[float] = Field(default=None, alias="pitchActivity", description="Salient pitch presence ratio")
    chroma_strength: Optional[float] = Field(default=None, alias="chromaStrength", description="Chroma peak prominence")
    chroma_entropy: Optional[float] = Field(default=None, alias="chromaEntropy", description="Shannon entropy of chroma distribution")
    spectral_flatness: Optional[float] = Field(default=None, alias="spectralFlatness", description="Spectral Wiener entropy (tonal vs noise)")
    temporal_stability: Optional[float] = Field(default=None, alias="temporalStability", description="Harmonic continuity over time")
    instrument_confidence: Optional[float] = Field(default=None, alias="instrumentConfidence", description="Confidence in specific instrument presence")
    chord_confidence: Optional[float] = Field(default=None, alias="chordConfidence", description="Confidence in chord candidate extraction from this source")
    composite_score: Optional[float] = Field(default=None, alias="compositeScore", description="Overall measured harmonic suitability score")
    rejection_reason: Optional[str] = Field(default=None, alias="rejectionReason", description="Reason if candidate was filtered out prior to chord inference")
    is_selected: bool = Field(default=False, alias="isSelected", description="Whether this candidate was chosen as the primary chord progression source")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class SourceSelectionResult(BaseModel):
    """
    Diagnostic result from HarmonicEvidenceRouter source selection.
    """
    selected_source: str = Field(..., alias="selectedSource", description="Best candidate source identifier")
    selected_instrument: Optional[str] = Field(default=None, alias="selectedInstrument", description="Associated instrument name or 'mix'")
    selection_confidence: float = Field(..., alias="selectionConfidence", description="Overall selection confidence score [0.0, 1.0]")
    reason: str = Field(..., description="Transparent, evidence-driven justification for selection")
    candidate_scores: Dict[str, float] = Field(default_factory=dict, alias="candidateScores", description="Measured composite scores per candidate")
    source_agreement: Optional[float] = Field(default=None, alias="sourceAgreement", description="Cross-source musical progression agreement score")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class InstrumentEvidence(BaseModel):
    """
    Structured representation of instrument identification.
    Strictly marked as unavailable or uncertain when no confident classification is present.
    """
    instrument: str = Field(..., description="Target instrument family (e.g., 'guitar', 'piano', 'bass', 'synth', 'drums', 'harmonic_mix')")
    confidence: Optional[float] = Field(default=None, description="Classification confidence [0.0, 1.0]. None if unclassified.")
    source: Optional[str] = Field(default=None, description="Stem or classifier origin providing this evidence")
    is_available: bool = Field(default=False, alias="isAvailable", description="Whether instrument classification was performed")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class DetectionReliability(BaseModel):
    """
    Multi-dimensional internal reliability evaluation.
    Avoids pseudo-'accuracy' terminology and only computes measurably verified dimensions.
    """
    overall: Optional[float] = Field(default=None, description="Synthesized reliability score across active indicators [0.0, 1.0]")
    harmonic_strength: Optional[float] = Field(default=None, alias="harmonicStrength", description="Reliability based on harmonic tonality vs noise")
    temporal_stability: Optional[float] = Field(default=None, alias="temporalStability", description="Reliability based on chord duration consistency (penalizes jitter)")
    beat_alignment: Optional[float] = Field(default=None, alias="beatAlignment", description="Reliability based on chord boundary alignment with onset beats")
    source_agreement: Optional[float] = Field(default=None, alias="sourceAgreement", description="Agreement across multi-stem candidates")
    engine_agreement: Optional[float] = Field(default=None, alias="engineAgreement", description="Agreement across multiple chord recognition models (None in Phase 1/2)")

    model_config = ConfigDict(populate_by_name=True, extra="allow")



class StructureSection(BaseModel):
    """
    Individual musical section boundary and repetition evidence.
    """
    label: str = Field(..., description="Evidence-driven section label (e.g., 'INTRO', 'OUTRO', 'REPEATING_SECTION_A', 'SECTION_1')")
    start: float = Field(..., description="Section start time in seconds")
    end: float = Field(..., description="Section end time in seconds")
    duration: float = Field(..., description="Section duration in seconds")
    repetition_group: Optional[str] = Field(default=None, alias="repetitionGroup", description="Cluster ID if this section repeats elsewhere")
    similarity_score: Optional[float] = Field(default=None, alias="similarityScore", description="Self-similarity score within group [0.0, 1.0]")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class StructureAnalysisResult(BaseModel):
    """
    Musical structure analysis diagnostic and section breakdown.
    """
    sections: List[StructureSection] = Field(default_factory=list, description="Ordered list of structural sections")
    repeating_sections: List[StructureSection] = Field(default_factory=list, alias="repeatingSections", description="Sub-list of repeating sections")
    structure_confidence: float = Field(default=0.0, alias="structureConfidence", description="Confidence in structural segmentation [0.0, 1.0]")
    total_sections: int = Field(default=0, alias="totalSections", description="Total number of detected sections")
    has_repeating_patterns: bool = Field(default=False, alias="hasRepeatingPatterns", description="Whether repeating harmonic structures were detected")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class FourChordLoopResult(BaseModel):
    """
    Structured representation of the best detected four-chord loop / progression.
    If no reliable 4-chord loop exists, available is False with an explanatory reason.
    """
    available: bool = Field(default=False, description="Whether a reliable 4-chord loop was identified")
    chords: List[str] = Field(default_factory=list, description="Musician-friendly 4-chord progression symbols")
    raw_chords: Optional[List[str]] = Field(default=None, alias="rawChords", description="Original raw chord symbols before simplification")
    simplified_chords: Optional[List[str]] = Field(default=None, alias="simplifiedChords", description="Beginner-friendly normalized chords")
    section: Optional[str] = Field(default=None, description="Structural section where this loop best manifests")
    start: Optional[float] = Field(default=None, description="Start timestamp of the primary occurrence in seconds")
    end: Optional[float] = Field(default=None, description="End timestamp of the primary occurrence in seconds")
    duration: Optional[float] = Field(default=None, description="Duration of the 4-chord loop in seconds")
    confidence: Optional[float] = Field(default=None, description="Loop detection and stability confidence [0.0, 1.0]")
    occurrences: List[float] = Field(default_factory=list, description="Array of start timestamps where this progression repeats")
    repetition_count: int = Field(default=0, alias="repetitionCount", description="Number of occurrences found across the song")
    reason: Optional[str] = Field(default=None, description="Reason for selection or reason why loop is unavailable")
    voicings: Optional[List[Dict[str, Any]]] = Field(default=None, description="Voice-led hand voicings for the 4-chord loop")
    playability_score: Optional[float] = Field(default=None, alias="playabilityScore", description="Beginner playability index [0.0, 1.0]")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class AudioAnalysisMetadata(BaseModel):
    """
    Canonical container for all Phase 1-4 Audio Intelligence Foundation metadata.
    """
    status: AudioStatus = Field(default=AudioStatus.SUCCESS, description="Audio analysis quality status")
    status_message: Optional[str] = Field(default=None, alias="statusMessage", description="Descriptive status diagnostic note")
    profile: Optional[AudioProfile] = Field(default=None, description="Objective acoustic profile")
    timing: Optional[TimingData] = Field(default=None, description="Timing and rhythm grid metadata")
    candidate_evidence: Dict[str, CandidateSourceEvidence] = Field(default_factory=dict, alias="candidateEvidence", description="Evidence from audio candidate sources")
    instruments: Dict[str, InstrumentEvidence] = Field(default_factory=dict, description="Instrument evidence registry")
    reliability: Optional[DetectionReliability] = Field(default=None, description="Detection reliability assessment")
    source_selection: Optional[SourceSelectionResult] = Field(default=None, alias="sourceSelection", description="Harmonic evidence router selection result")
    structure: Optional[StructureAnalysisResult] = Field(default=None, description="Musical structure and section analysis")
    four_chord_loop: Optional[FourChordLoopResult] = Field(default=None, alias="fourChordLoop", description="Best detected 4-chord loop progression")
    practice: Optional[Any] = Field(default=None, description="Beginner practice intelligence and guidance plan")
    practice_plan: Optional[Any] = Field(default=None, alias="practicePlan", description="Alias for practice intelligence plan")

    model_config = ConfigDict(populate_by_name=True, extra="allow")

