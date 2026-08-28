from pydantic import BaseModel
from typing import List, Dict, Optional, Any

class ProgressResponse(BaseModel):
    msg: str
    pct: int

class ChordInfo(BaseModel):
    time: float
    end: float
    chord: str
    confidence: float

class SectionInfo(BaseModel):
    label: str
    start: float
    end: float

class ChordData(BaseModel):
    notes: List[int]
    note_names: List[str]
    fingers: Dict[int, int]
    difficulty: str

class AnalysisResult(BaseModel):
    file: str
    duration: float
    key: str
    scale: str
    key_full: str
    tempo: float
    time_sig: str
    scale_notes: List[int]
    chords: List[ChordInfo]
    unique_chords: List[str]
    chord_data: Dict[str, ChordData]
    roman_numerals: Dict[str, str]
    simplified_map: Optional[Dict[str, str]] = None
    sections: Optional[List[SectionInfo]] = None
    beginner_chords: Optional[List[ChordInfo]] = None
    unique_beginner_chords: Optional[List[str]] = None
    easy_key: Optional[str] = None
    easy_key_full: Optional[str] = None
    transpose_offset: Optional[int] = 0

class AnalysisResponse(BaseModel):
    ready: bool
    data: Optional[AnalysisResult] = None
    error: Optional[str] = None

