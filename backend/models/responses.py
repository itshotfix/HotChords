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
    simplified_map: Dict[str, str]
    chord_data: Dict[str, ChordData]
    roman_numerals: Dict[str, str]
    sections: List[SectionInfo]

class AnalysisResponse(BaseModel):
    ready: bool
    data: Optional[AnalysisResult] = None
    error: Optional[str] = None
