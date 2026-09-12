"""
backend/benchmarks/real_song_dataset.py

Real-Song Dataset Interface & Provenance Management for HotChords.
Supports:
- User-provided local audio
- Legally licensed audio
- Public-domain recordings
- Appropriately licensed MIR datasets

Every track tracks:
- track_id
- audio_hash
- duration
- source
- license/provenance
- optional ground_truth
- ground_truth_status ("AVAILABLE", "UNAVAILABLE")
- instrument_profile
- notes
"""

import os
import hashlib
from typing import List, Dict, Any, Optional
import soundfile as sf
import librosa


class RealSongTrack:
    """Represents a real-song audio track with strict provenance and ground-truth metadata."""

    def __init__(
        self,
        track_id: str,
        filepath: str,
        source: str = "user_provided",
        license_provenance: str = "Local User Audio / Private Fair Use",
        ground_truth: Optional[List[Dict[str, Any]]] = None,
        instrument_profile: Optional[Dict[str, Any]] = None,
        notes: str = "",
        expected_key: Optional[str] = None,
        expected_bpm: Optional[float] = None
    ):
        self.track_id = track_id
        self.filepath = filepath
        self.source = source
        self.license_provenance = license_provenance
        self.ground_truth = ground_truth
        self.ground_truth_status = "AVAILABLE" if ground_truth is not None and len(ground_truth) > 0 else "UNAVAILABLE"
        self.instrument_profile = instrument_profile or {}
        self.notes = notes
        self.expected_key = expected_key
        self.expected_bpm = expected_bpm
        self.duration = 0.0
        self.audio_hash = ""

        self._inspect_audio()

    def _inspect_audio(self):
        """Computes SHA-256 hash and audio duration if file exists."""
        if os.path.isfile(self.filepath):
            try:
                # Fast SHA-256 hash calculation
                hasher = hashlib.sha256()
                with open(self.filepath, "rb") as f:
                    for chunk in iter(lambda: f.read(65536), b""):
                        hasher.update(chunk)
                self.audio_hash = hasher.hexdigest()[:16]

                # Duration check
                info = sf.info(self.filepath)
                self.duration = round(info.duration, 2)
            except Exception:
                try:
                    y, sr = librosa.load(self.filepath, sr=22050, mono=True)
                    self.duration = round(float(len(y) / sr), 2)
                except Exception:
                    self.duration = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serializes track metadata for diagnostic reports."""
        return {
            "track_id": self.track_id,
            "filepath": self.filepath,
            "audio_hash": self.audio_hash,
            "duration": self.duration,
            "source": self.source,
            "license_provenance": self.license_provenance,
            "ground_truth_status": self.ground_truth_status,
            "has_ground_truth": self.ground_truth_status == "AVAILABLE",
            "instrument_profile": self.instrument_profile,
            "notes": self.notes,
            "expected_key": self.expected_key,
            "expected_bpm": self.expected_bpm
        }


class RealSongDatasetRegistry:
    """Manages collection of real-song test tracks with validation and filtering."""

    def __init__(self):
        self._tracks: Dict[str, RealSongTrack] = {}

    def register_track(self, track: RealSongTrack) -> None:
        self._tracks[track.track_id] = track

    def get_track(self, track_id: str) -> Optional[RealSongTrack]:
        return self._tracks.get(track_id)

    def list_tracks(self, has_ground_truth_only: bool = False) -> List[RealSongTrack]:
        tracks = list(self._tracks.values())
        if has_ground_truth_only:
            tracks = [t for t in tracks if t.ground_truth_status == "AVAILABLE"]
        return tracks

    def scan_test_songs_dir(self, test_songs_dir: str) -> int:
        """Scans directory for audio files and registers them."""
        if not os.path.isdir(test_songs_dir):
            return 0

        registered_count = 0
        for fname in sorted(os.listdir(test_songs_dir)):
            if fname.startswith("."):
                continue
            ext = os.path.splitext(fname)[1].lower()
            if ext in [".mp3", ".wav", ".flac", ".ogg", ".m4a"]:
                t_id = os.path.splitext(fname)[0]
                fpath = os.path.join(test_songs_dir, fname)
                
                # Derive instrument profile and notes from known test songs
                profile = {}
                notes = "User-provided local song audio"
                expected_key = None
                
                if "TuMera" in fname:
                    profile = {"lead": "vocals_guitar", "genre": "pop_acoustic", "tempo_category": "mid"}
                    notes = "Acoustic guitar and vocal arrangement with extended harmonies"
                elif "Die With A Smile" in fname:
                    profile = {"lead": "vocals_guitar_piano", "genre": "pop_ballad", "tempo_category": "slow_mid"}
                    notes = "Duet with electric/acoustic guitar, piano fills, and lush 7th chords"
                elif "NahinMilta" in fname:
                    profile = {"lead": "rock_band", "genre": "alt_rock", "tempo_category": "mid_fast"}
                    notes = "Dense mix with distorted electric guitar, drums, bass, and synth pads"
                elif "RapGod" in fname:
                    profile = {"lead": "rap_vocals_electronic", "genre": "hip_hop", "tempo_category": "fast"}
                    notes = "Rapid vocal delivery over electronic synth bassline and trap drum loop"

                track = RealSongTrack(
                    track_id=t_id,
                    filepath=fpath,
                    source="local_test_songs_folder",
                    license_provenance="Local Test Audio (Fair Use Analysis)",
                    ground_truth=None,  # Real songs without public ground truth marked UNAVAILABLE
                    instrument_profile=profile,
                    notes=notes,
                    expected_key=expected_key
                )
                self.register_track(track)
                registered_count += 1

        return registered_count
