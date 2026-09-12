"""
backend/models/timeline.py

Canonical SongTimeline data model for HotChords.
Single source of truth for:
- original chords
- beginner chords
- playback timing
- piano playback
- lyrics / transcripts
- fingering & hand animation
- notation data
"""

from typing import List, Dict, Optional, Any, Union
from pydantic import BaseModel, Field, ConfigDict
from .analysis_types import (
    AudioStatus,
    AudioProfile,
    TimingData,
    CandidateSourceEvidence,
    InstrumentEvidence,
    DetectionReliability,
    AudioAnalysisMetadata,
    StructureSection,
    StructureAnalysisResult,
    FourChordLoopResult,
)


class HandVoicingNote(BaseModel):
    """Specific key/note in a hand voicing for piano rendering and animation."""
    midi: int
    note: Optional[str] = None  # Scientific pitch notation (e.g., 'C4', 'E4')
    finger: int  # 1=Thumb, 2=Index, 3=Middle, 4=Ring, 5=Pinky
    color: Optional[str] = None


class HandVoicing(BaseModel):
    """Voicing configuration for Left and Right hands."""
    left_hand: List[HandVoicingNote] = Field(default_factory=list, alias="leftHand")
    right_hand: List[HandVoicingNote] = Field(default_factory=list, alias="rightHand")

    model_config = ConfigDict(populate_by_name=True)


class ChordEvent(BaseModel):
    """
    Individual chord event in a song timeline.
    Supports seconds as the consistent time representation.
    """
    start_time: float = Field(..., alias="startTime", description="Start time in seconds")
    end_time: float = Field(..., alias="endTime", description="End time in seconds")
    chord_name: str = Field(..., alias="chordName", description="Musician-friendly chord symbol, e.g. 'Am', 'C7', 'N'")

    # Authoritative decomposed harmonic components (Phase 8)
    root: Optional[str] = Field(default=None, description="Root pitch class name, e.g. 'C', 'F#'")
    quality: Optional[str] = Field(default=None, description="Harmonic quality, e.g. 'maj', 'min', '7', 'maj7', 'min7', 'sus4', 'dim'")
    bass: Optional[str] = Field(default=None, description="Bass / slash note, e.g. 'E' in 'C/E'")
    simplified_chord: Optional[str] = Field(default=None, alias="simplifiedChord", description="Beginner-friendly simplified chord symbol, e.g. 'Dm'")

    # Optional raw / enharmonic chord representation
    raw_chord: Optional[str] = Field(default=None, alias="rawChord")

    # Pitch classes / note names
    notes: Optional[List[int]] = Field(default=None, description="Pitch class integers 0-11")
    note_names: Optional[List[str]] = Field(default=None, alias="noteNames", description="Musician-friendly note names")

    # Fingering & voicings for keyboard and hand animation
    voicing: Optional[Union[HandVoicing, Dict[str, Any]]] = None
    fingering: Optional[Dict[int, int]] = Field(default=None, description="Pitch class to finger mapping {0: 1, 4: 3, 7: 5}")

    # Analysis metadata
    confidence: Optional[float] = Field(default=None, description="Confidence score [0.0, 1.0]")
    difficulty: Optional[str] = Field(default=None, description="'easy', 'medium', or 'hard'")
    difficulty_score: Optional[float] = Field(default=None, alias="difficultyScore", description="Numerical beginner difficulty score [0.0, 1.0]")
    roman_numeral: Optional[str] = Field(default=None, alias="romanNumeral")
    source_evidence: Optional[str] = Field(default=None, alias="sourceEvidence", description="Harmonic stem or candidate providing evidence")

    # Musical grid timing
    musical_start: Optional[float] = Field(default=None, alias="musicalStart", description="Quantized / beat-aligned musical start time")
    musical_end: Optional[float] = Field(default=None, alias="musicalEnd", description="Quantized / beat-aligned musical end time")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class SectionEvent(BaseModel):
    """Musical section boundary (e.g. Intro, Verse, Chorus)."""
    label: str
    start_time: float = Field(..., alias="startTime")
    end_time: float = Field(..., alias="endTime")

    model_config = ConfigDict(populate_by_name=True)


class NotationData(BaseModel):
    """Optional future music notation / sheet music data."""
    clef: Optional[str] = "treble"
    key_signature: Optional[str] = None
    time_signature: Optional[str] = None
    measures: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    raw_data: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class SongMetadata(BaseModel):
    """Song metadata and musical analysis properties."""
    title: Optional[str] = None
    artist: Optional[str] = None
    file: Optional[str] = None
    duration: float = Field(..., description="Total duration in seconds")
    tempo: Optional[float] = Field(default=None, description="Tempo in BPM")
    time_sig: Optional[str] = Field(default="4/4", alias="timeSig")

    # Key and scale
    key: Optional[str] = None
    scale: Optional[str] = None
    key_full: Optional[str] = Field(default=None, alias="keyFull")
    scale_notes: Optional[List[int]] = Field(default_factory=list, alias="scaleNotes")

    # Beginner key details
    easy_key: Optional[str] = Field(default=None, alias="easyKey")
    easy_key_full: Optional[str] = Field(default=None, alias="easyKeyFull")
    transpose_offset: int = Field(default=0, alias="transposeOffset")

    # Phase 1-4 Audio Intelligence Foundation
    engine: Optional[str] = None
    fallback_reason: Optional[str] = Field(default=None, alias="fallbackReason")
    status: Optional[AudioStatus] = None
    status_message: Optional[str] = Field(default=None, alias="statusMessage")
    audio_profile: Optional[AudioProfile] = Field(default=None, alias="audioProfile")
    timing: Optional[TimingData] = None
    reliability: Optional[DetectionReliability] = None
    structure: Optional[StructureAnalysisResult] = None
    four_chord_loop: Optional[FourChordLoopResult] = Field(default=None, alias="fourChordLoop")
    practice: Optional[Any] = Field(default=None, description="Beginner practice intelligence and guidance plan")
    practice_plan: Optional[Any] = Field(default=None, alias="practicePlan", description="Alias for practice plan")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class SongTimeline(BaseModel):
    """
    Canonical SongTimeline: Single source of truth for HotChords.

    Contains separate timelines for original and beginner chords,
    unified timing in seconds, sections, notation data, and MIR analysis metadata.
    """
    metadata: SongMetadata
    duration: float = Field(..., description="Song duration in seconds")

    # Separate chord timelines
    original_chords: List[ChordEvent] = Field(default_factory=list, alias="originalChords")
    beginner_chords: Optional[List[ChordEvent]] = Field(default=None, alias="beginnerChords")

    # Optional structural & notation data
    sections: Optional[List[SectionEvent]] = Field(default_factory=list)
    structure: Optional[StructureAnalysisResult] = None
    four_chord_loop: Optional[FourChordLoopResult] = Field(default=None, alias="fourChordLoop")
    practice: Optional[Any] = Field(default=None, description="Beginner practice plan")
    practice_plan: Optional[Any] = Field(default=None, alias="practicePlan", description="Beginner practice plan alias")
    notation: Optional[NotationData] = None

    # Cached chord dictionary maps
    unique_chords: Optional[List[str]] = Field(default_factory=list, alias="uniqueChords")
    unique_beginner_chords: Optional[List[str]] = Field(default_factory=list, alias="uniqueBeginnerChords")
    roman_numerals: Optional[Dict[str, str]] = Field(default_factory=dict, alias="romanNumerals")
    chord_data: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="chordData")

    # Phase 1 MIR Foundation Metadata Container
    analysis_metadata: Optional[AudioAnalysisMetadata] = Field(default=None, alias="analysisMetadata")

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    @classmethod
    def from_analysis_dict(cls, data: Dict[str, Any]) -> "SongTimeline":
        """
        Creates a SongTimeline instance from the pipeline analysis dictionary.
        Preserves all musical metadata, original chords, confidence, and beginner chords.
        """
        duration = float(data.get("duration", 0.0))

        # Parse profile if dict
        prof = data.get("audio_profile") or data.get("profile")
        if isinstance(prof, dict):
            try:
                prof = AudioProfile.model_validate(prof)
            except Exception:
                prof = None

        # Parse timing if dict
        tim = data.get("timing")
        if isinstance(tim, dict):
            try:
                tim = TimingData.model_validate(tim)
            except Exception:
                tim = None

        # Parse reliability if dict
        rel = data.get("reliability")
        if isinstance(rel, dict):
            try:
                rel = DetectionReliability.model_validate(rel)
            except Exception:
                rel = None

        # Parse structure if dict
        struct_val = data.get("structure")
        if isinstance(struct_val, dict):
            try:
                struct_obj = StructureAnalysisResult.model_validate(struct_val)
            except Exception:
                struct_obj = None
        elif isinstance(struct_val, StructureAnalysisResult):
            struct_obj = struct_val
        else:
            struct_obj = None

        # Parse four_chord_loop if dict
        loop_val = data.get("four_chord_loop") or data.get("fourChordLoop")
        if isinstance(loop_val, dict):
            try:
                loop_obj = FourChordLoopResult.model_validate(loop_val)
            except Exception:
                loop_obj = None
        elif isinstance(loop_val, FourChordLoopResult):
            loop_obj = loop_val
        else:
            loop_obj = None

        status_val = data.get("status")
        if isinstance(status_val, str):
            try:
                status_enum = AudioStatus(status_val)
            except Exception:
                status_enum = None
        elif isinstance(status_val, AudioStatus):
            status_enum = status_val
        else:
            status_enum = None

        metadata = SongMetadata(
            file=data.get("file"),
            duration=duration,
            tempo=data.get("tempo"),
            time_sig=data.get("time_sig", "4/4"),
            key=data.get("key"),
            scale=data.get("scale"),
            key_full=data.get("key_full"),
            scale_notes=data.get("scale_notes", []),
            easy_key=data.get("easy_key"),
            easy_key_full=data.get("easy_key_full"),
            transpose_offset=int(data.get("transpose_offset", 0)),
            engine=data.get("engine"),
            fallback_reason=data.get("fallback_reason"),
            status=status_enum,
            status_message=data.get("status_message"),
            audio_profile=prof,
            timing=tim,
            reliability=rel,
            structure=struct_obj,
            four_chord_loop=loop_obj,
            practice=data.get("practice") or data.get("practice_plan") or data.get("practicePlan"),
            practice_plan=data.get("practice_plan") or data.get("practicePlan") or data.get("practice"),
        )

        chord_data_dict = data.get("chord_data", {})
        roman_dict = data.get("roman_numerals", {})

        from backend.theory.piano_voicing import parse_chord_components, voice_chord
        from backend.theory.simplification import reduce_chord_harmony

        def _to_chord_event(c: Union[Dict[str, Any], Any]) -> ChordEvent:
            if isinstance(c, dict):
                c_name = c.get("chord", "N")
                start = float(c.get("time", c.get("startTime", c.get("start", 0.0))))
                end = float(c.get("end", c.get("endTime", 0.0)))
                conf = float(c.get("confidence", 1.0)) if c.get("confidence") is not None else None
                raw = c.get("raw_chord", c.get("rawChord"))
                r_root = c.get("root")
                r_qual = c.get("quality")
                r_bass = c.get("bass")
                r_simp = c.get("simplified_chord", c.get("simplifiedChord"))
                r_voicing = c.get("voicing")
                r_diff_score = c.get("difficulty_score", c.get("difficultyScore"))
                r_source_ev = c.get("source_evidence", c.get("sourceEvidence"))
                r_m_start = c.get("musical_start", c.get("musicalStart"))
                r_m_end = c.get("musical_end", c.get("musicalEnd"))
            else:
                c_name = getattr(c, "chord", "N")
                start = float(getattr(c, "time", getattr(c, "startTime", getattr(c, "start", 0.0))))
                end = float(getattr(c, "end", getattr(c, "endTime", 0.0)))
                conf = float(getattr(c, "confidence", 1.0)) if getattr(c, "confidence", None) is not None else None
                raw = getattr(c, "raw_chord", getattr(c, "rawChord", None))
                r_root = getattr(c, "root", None)
                r_qual = getattr(c, "quality", None)
                r_bass = getattr(c, "bass", None)
                r_simp = getattr(c, "simplified_chord", getattr(c, "simplifiedChord", None))
                r_voicing = getattr(c, "voicing", None)
                r_diff_score = getattr(c, "difficulty_score", getattr(c, "difficultyScore", None))
                r_source_ev = getattr(c, "source_evidence", getattr(c, "sourceEvidence", None))
                r_m_start = getattr(c, "musical_start", getattr(c, "musicalStart", None))
                r_m_end = getattr(c, "musical_end", getattr(c, "musicalEnd", None))

            # Infer canonical harmonic components if missing
            if not r_root and c_name and c_name != "N":
                parsed_root, parsed_qual, parsed_bass = parse_chord_components(c_name)
                r_root = r_root or parsed_root
                r_qual = r_qual or parsed_qual
                r_bass = r_bass or parsed_bass
            if not r_simp and c_name and c_name != "N":
                r_simp = reduce_chord_harmony(c_name)
            if not r_voicing and c_name and c_name != "N":
                r_voicing = voice_chord(c_name)

            return ChordEvent(
                startTime=start,
                endTime=end,
                chordName=c_name,
                rawChord=raw,
                root=r_root,
                quality=r_qual,
                bass=r_bass,
                simplifiedChord=r_simp,
                voicing=r_voicing,
                notes=chord_data_dict.get(c_name, {}).get("notes") if isinstance(chord_data_dict.get(c_name), dict) else None,
                noteNames=chord_data_dict.get(c_name, {}).get("note_names") if isinstance(chord_data_dict.get(c_name), dict) else None,
                fingering=chord_data_dict.get(c_name, {}).get("fingers") if isinstance(chord_data_dict.get(c_name), dict) else None,
                confidence=conf,
                difficulty=chord_data_dict.get(c_name, {}).get("difficulty") if isinstance(chord_data_dict.get(c_name), dict) else None,
                difficultyScore=r_diff_score,
                sourceEvidence=r_source_ev,
                musicalStart=r_m_start,
                musicalEnd=r_m_end,
                romanNumeral=roman_dict.get(c_name)
            )

        orig_events = [_to_chord_event(c) for c in (data.get("chords") or [])]

        beg_data = data.get("beginner_chords")
        beg_events = [_to_chord_event(c) for c in beg_data] if beg_data is not None else None

        section_events = []
        for s in (data.get("sections") or []):
            if isinstance(s, dict):
                label = s.get("label", "")
                s_start = float(s.get("start", s.get("startTime", 0.0)))
                s_end = float(s.get("end", s.get("endTime", 0.0)))
            else:
                label = getattr(s, "label", "")
                s_start = float(getattr(s, "start", getattr(s, "startTime", 0.0)))
                s_end = float(getattr(s, "end", getattr(s, "endTime", 0.0)))
            section_events.append(SectionEvent(label=label, startTime=s_start, endTime=s_end))

        # Build analysis_metadata if present
        raw_analysis_meta = data.get("analysis_metadata")
        if isinstance(raw_analysis_meta, dict):
            try:
                analysis_meta = AudioAnalysisMetadata.model_validate(raw_analysis_meta)
            except Exception:
                analysis_meta = None
        elif isinstance(raw_analysis_meta, AudioAnalysisMetadata):
            analysis_meta = raw_analysis_meta
        else:
            raw_source_sel = data.get("source_selection")
            source_sel_obj = None
            if isinstance(raw_source_sel, dict):
                try:
                    from backend.models.analysis_types import SourceSelectionResult
                    source_sel_obj = SourceSelectionResult.model_validate(raw_source_sel)
                except Exception:
                    source_sel_obj = None
            elif hasattr(raw_source_sel, "selected_source"):
                source_sel_obj = raw_source_sel

            analysis_meta = AudioAnalysisMetadata(
                status=status_enum or AudioStatus.SUCCESS,
                status_message=data.get("status_message"),
                profile=prof,
                timing=tim,
                reliability=rel,
                candidate_evidence=data.get("candidate_evidence", {}),
                instruments=data.get("instruments", {}),
                source_selection=source_sel_obj,
                structure=struct_obj,
                four_chord_loop=loop_obj,
                practice=data.get("practice") or data.get("practice_plan") or data.get("practicePlan"),
                practice_plan=data.get("practice_plan") or data.get("practicePlan") or data.get("practice"),
            )

        return cls(
            metadata=metadata,
            duration=duration,
            originalChords=orig_events,
            beginnerChords=beg_events,
            sections=section_events,
            structure=struct_obj,
            four_chord_loop=loop_obj,
            practice=data.get("practice") or data.get("practice_plan") or data.get("practicePlan"),
            practice_plan=data.get("practice_plan") or data.get("practicePlan") or data.get("practice"),
            uniqueChords=data.get("unique_chords", []),
            uniqueBeginnerChords=data.get("unique_beginner_chords"),
            romanNumerals=roman_dict,
            chordData=chord_data_dict,
            analysisMetadata=analysis_meta
        )

    def to_analysis_dict(self) -> Dict[str, Any]:
        """
        Converts the canonical SongTimeline back into the analysis dictionary format
        for backward compatibility with the frontend and existing APIs.
        """
        chords_legacy = [
            {
                "time": round(c.start_time, 3),
                "end": round(c.end_time, 3),
                "chord": c.chord_name,
                "raw_chord": c.raw_chord or c.chord_name,
                "confidence": round(c.confidence, 3) if c.confidence is not None else 1.0
            }
            for c in self.original_chords
        ]

        sections_legacy = [
            {
                "label": s.label,
                "start": round(s.start_time, 3),
                "end": round(s.end_time, 3)
            }
            for s in (self.sections or [])
        ]

        result: Dict[str, Any] = {
            "ready": True,
            "file": self.metadata.file or "",
            "duration": round(self.duration, 2),
            "key": self.metadata.key or "C",
            "scale": self.metadata.scale or "Major",
            "key_full": self.metadata.key_full or f"{self.metadata.key or 'C'} {self.metadata.scale or 'Major'}",
            "tempo": round(self.metadata.tempo, 1) if self.metadata.tempo is not None else 120.0,
            "time_sig": self.metadata.time_sig or "4/4",
            "scale_notes": self.metadata.scale_notes or [],
            "chords": chords_legacy,
            "unique_chords": self.unique_chords or [],
            "chord_data": self.chord_data or {},
            "roman_numerals": self.roman_numerals or {},
            "sections": sections_legacy,
        }

        if self.beginner_chords is not None:
            beginner_legacy = [
                {
                    "time": round(c.start_time, 3),
                    "end": round(c.end_time, 3),
                    "chord": c.chord_name,
                    "confidence": round(c.confidence, 3) if c.confidence is not None else 1.0
                }
                for c in self.beginner_chords
            ]
            result["beginner_chords"] = beginner_legacy
            result["unique_beginner_chords"] = self.unique_beginner_chords or []
            result["easy_key"] = self.metadata.easy_key or self.metadata.key
            result["easy_key_full"] = self.metadata.easy_key_full or self.metadata.key_full
            result["transpose_offset"] = int(self.metadata.transpose_offset or 0)

        # Phase 1-4 Engine & MIR Metadata preservation
        if self.metadata.engine:
            result["engine"] = self.metadata.engine
        if self.metadata.fallback_reason:
            result["fallback_reason"] = self.metadata.fallback_reason
        if self.metadata.status is not None:
            result["status"] = self.metadata.status.value if hasattr(self.metadata.status, "value") else str(self.metadata.status)
        if self.metadata.status_message:
            result["status_message"] = self.metadata.status_message
        if self.metadata.audio_profile:
            result["audio_profile"] = self.metadata.audio_profile.model_dump(by_alias=True)
        if self.metadata.timing:
            result["timing"] = self.metadata.timing.model_dump(by_alias=True)
        if self.metadata.reliability:
            result["reliability"] = self.metadata.reliability.model_dump(by_alias=True)
        struct_obj = self.metadata.structure or self.structure
        if struct_obj:
            s_dict = struct_obj.model_dump()
            s_dict.update(struct_obj.model_dump(by_alias=True))
            result["structure"] = s_dict

        loop_obj = self.metadata.four_chord_loop or self.four_chord_loop
        if loop_obj:
            f_dict = loop_obj.model_dump()
            f_dict.update(loop_obj.model_dump(by_alias=True))
            result["four_chord_loop"] = f_dict
            result["fourChordLoop"] = f_dict

        if self.analysis_metadata:
            result["analysis_metadata"] = self.analysis_metadata.model_dump(by_alias=True)
            if self.analysis_metadata.candidate_evidence:
                result["candidate_evidence"] = {k: v.model_dump(by_alias=True) for k, v in self.analysis_metadata.candidate_evidence.items()}
            if self.analysis_metadata.instruments:
                result["instruments"] = {k: v.model_dump(by_alias=True) for k, v in self.analysis_metadata.instruments.items()}
            if self.analysis_metadata.source_selection:
                result["source_selection"] = self.analysis_metadata.source_selection.model_dump(by_alias=True)
            if self.analysis_metadata.structure:
                s_dict = self.analysis_metadata.structure.model_dump()
                s_dict.update(self.analysis_metadata.structure.model_dump(by_alias=True))
                result["structure"] = s_dict
            if self.analysis_metadata.four_chord_loop:
                f_dict = self.analysis_metadata.four_chord_loop.model_dump()
                f_dict.update(self.analysis_metadata.four_chord_loop.model_dump(by_alias=True))
                result["four_chord_loop"] = f_dict
                result["fourChordLoop"] = f_dict

        return result

    def create_practice_session(
        self,
        mode: str = "PIANO",
        target_loops: int = 0,
        simplification_level: int = 0,
        transposition_offset: int = 0,
        custom_bpm: Optional[float] = None
    ):
        """Creates an authoritative PracticeSession from this SongTimeline instance."""
        from backend.models.practice_session import create_practice_session, PracticeMode
        p_mode = PracticeMode.PIANO if str(mode).upper() == "PIANO" else PracticeMode.ORIGINAL
        chord_dicts = [
            {
                "chord": c.chord_name,
                "time": c.start_time,
                "end": c.end_time,
                "root": c.root,
                "quality": c.quality,
                "bass": c.bass,
                "simplified_chord": c.simplified_chord,
                "voicing": c.voicing.model_dump() if hasattr(c.voicing, "model_dump") else c.voicing
            }
            for c in self.original_chords
        ]
        tempo_val = float(self.metadata.tempo or 120.0) if self.metadata else 120.0
        practice_val = (self.metadata.practice if self.metadata else None) or self.practice
        return create_practice_session(
            chords=chord_dicts,
            tempo=tempo_val,
            practice_plan=practice_val,
            mode=p_mode,
            target_loops=target_loops,
            simplification_level=simplification_level,
            transposition_offset=transposition_offset,
            custom_bpm=custom_bpm,
        )



def analysis_to_song_timeline(data: Dict[str, Any]) -> SongTimeline:
    """Convenience adapter function: Analysis Result Dict -> SongTimeline."""
    return SongTimeline.from_analysis_dict(data)

