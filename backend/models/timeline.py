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


class HandVoicingNote(BaseModel):
    """Specific key/note in a hand voicing for piano rendering and animation."""
    midi: int
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
    roman_numeral: Optional[str] = Field(default=None, alias="romanNumeral")

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

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class SongTimeline(BaseModel):
    """
    Canonical SongTimeline: Single source of truth for HotChords.
    
    Contains separate timelines for original and beginner chords,
    unified timing in seconds, sections, and notation data.
    """
    metadata: SongMetadata
    duration: float = Field(..., description="Song duration in seconds")
    
    # Separate chord timelines
    original_chords: List[ChordEvent] = Field(default_factory=list, alias="originalChords")
    beginner_chords: Optional[List[ChordEvent]] = Field(default=None, alias="beginnerChords")
    
    # Optional structural & notation data
    sections: Optional[List[SectionEvent]] = Field(default_factory=list)
    notation: Optional[NotationData] = None
    
    # Cached chord dictionary maps
    unique_chords: Optional[List[str]] = Field(default_factory=list, alias="uniqueChords")
    unique_beginner_chords: Optional[List[str]] = Field(default_factory=list, alias="uniqueBeginnerChords")
    roman_numerals: Optional[Dict[str, str]] = Field(default_factory=dict, alias="romanNumerals")
    chord_data: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="chordData")

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    @classmethod
    def from_analysis_dict(cls, data: Dict[str, Any]) -> "SongTimeline":
        """
        Creates a SongTimeline instance from the pipeline analysis dictionary.
        Preserves all musical metadata, original chords, confidence, and beginner chords.
        """
        duration = float(data.get("duration", 0.0))
        
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
            transpose_offset=int(data.get("transpose_offset", 0))
        )
        
        chord_data_dict = data.get("chord_data", {})
        roman_dict = data.get("roman_numerals", {})
        
        def _to_chord_event(c: Union[Dict[str, Any], Any]) -> ChordEvent:
            if isinstance(c, dict):
                c_name = c.get("chord", "N")
                start = float(c.get("time", c.get("startTime", c.get("start", 0.0))))
                end = float(c.get("end", c.get("endTime", 0.0)))
                conf = float(c.get("confidence", 1.0)) if c.get("confidence") is not None else None
                raw = c.get("raw_chord", c.get("rawChord"))
            else:
                c_name = getattr(c, "chord", "N")
                start = float(getattr(c, "time", getattr(c, "startTime", getattr(c, "start", 0.0))))
                end = float(getattr(c, "end", getattr(c, "endTime", 0.0)))
                conf = float(getattr(c, "confidence", 1.0)) if getattr(c, "confidence", None) is not None else None
                raw = getattr(c, "raw_chord", getattr(c, "rawChord", None))
            
            return ChordEvent(
                startTime=start,
                endTime=end,
                chordName=c_name,
                rawChord=raw,
                notes=chord_data_dict.get(c_name, {}).get("notes") if isinstance(chord_data_dict.get(c_name), dict) else None,
                noteNames=chord_data_dict.get(c_name, {}).get("note_names") if isinstance(chord_data_dict.get(c_name), dict) else None,
                fingering=chord_data_dict.get(c_name, {}).get("fingers") if isinstance(chord_data_dict.get(c_name), dict) else None,
                confidence=conf,
                difficulty=chord_data_dict.get(c_name, {}).get("difficulty") if isinstance(chord_data_dict.get(c_name), dict) else None,
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
            
        return cls(
            metadata=metadata,
            duration=duration,
            originalChords=orig_events,
            beginnerChords=beg_events,
            sections=section_events,
            uniqueChords=data.get("unique_chords", []),
            uniqueBeginnerChords=data.get("unique_beginner_chords"),
            romanNumerals=roman_dict,
            chordData=chord_data_dict
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
            
        return result


def analysis_to_song_timeline(data: Dict[str, Any]) -> SongTimeline:
    """Convenience adapter function: Analysis Result Dict -> SongTimeline."""
    return SongTimeline.from_analysis_dict(data)

