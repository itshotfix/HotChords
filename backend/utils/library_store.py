"""
backend/utils/library_store.py

Persistent 10-Song Piano Tutorial Library Manager for HotChords.

Responsibilities:
1. Automatically saves the latest 10 completed song transcriptions/arrangements
   in `~/.hotchords/library/` (or configurable storage root).
2. Deduplicates uploads via SHA-256 audio hash so previously analyzed songs reopen
   instantly without redundant processing.
3. Stores song metadata, canonical SongTimeline + analysis dict (Beginner and
   Intermediate arrangements), original audio copy, and extracted stems
   (Vocals and Instrumental/Backing track).
4. Enforces the 10-song retention limit automatically, evicting the oldest entry
   and cleaning up its disk files safely.
5. Provides on-demand Vocal & Instrumental stem extraction for any saved library song.
"""

from __future__ import annotations

import os
import json
import time
import shutil
import hashlib
import logging
from typing import Dict, List, Any, Optional, Tuple
import numpy as np
import librosa
import soundfile as sf

logger = logging.getLogger(__name__)

MAX_LIBRARY_SONGS = 10
DEFAULT_LIBRARY_DIR = os.path.join(os.path.expanduser("~"), ".hotchords", "library")


class SongLibraryStore:
    def __init__(self, root_dir: Optional[str] = None, max_songs: int = MAX_LIBRARY_SONGS):
        self.root_dir = os.path.abspath(root_dir or DEFAULT_LIBRARY_DIR)
        self.max_songs = max(1, int(max_songs))
        self.index_path = os.path.join(self.root_dir, "library_index.json")
        self.folders_path = os.path.join(self.root_dir, "folders.json")
        os.makedirs(self.root_dir, exist_ok=True)

    def _load_index(self) -> List[Dict[str, Any]]:
        if not os.path.isfile(self.index_path):
            return []
        try:
            with open(self.index_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception as e:
            logger.warning(f"Failed to read library index: {e}")
            return []

    def _save_index(self, entries: List[Dict[str, Any]]) -> None:
        os.makedirs(self.root_dir, exist_ok=True)
        tmp_path = self.index_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2)
        os.replace(tmp_path, self.index_path)

    @staticmethod
    def compute_file_hash(filepath: str) -> str:
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()[:24]

    def find_by_hash(self, audio_hash: str) -> Optional[Dict[str, Any]]:
        """Returns an existing library entry if `audio_hash` is already analyzed and valid."""
        if not audio_hash:
            return None
        for entry in self._load_index():
            if entry.get("id") == audio_hash and entry.get("status") == "ready":
                song_dir = os.path.join(self.root_dir, audio_hash)
                res_file = os.path.join(song_dir, "analysis_result.json")
                if os.path.isfile(res_file):
                    return entry
        return None

    def list_songs(self) -> List[Dict[str, Any]]:
        """Returns up to `max_songs` saved songs ordered newest-first, verifying file integrity."""
        entries = self._load_index()
        valid_entries: List[Dict[str, Any]] = []
        for entry in entries:
            sid = entry.get("id", "")
            song_dir = os.path.join(self.root_dir, sid)
            res_path = os.path.join(song_dir, "analysis_result.json")
            audio_file = entry.get("audio_filename")
            audio_path = os.path.join(song_dir, audio_file) if audio_file else ""
            has_audio = bool(audio_path and os.path.isfile(audio_path))
            has_res = os.path.isfile(res_path)

            if not has_res and entry.get("status") != "failed":
                continue

            voc_path = os.path.join(song_dir, "vocals.wav")
            inst_path = os.path.join(song_dir, "instrumental.wav")
            stems_ready = os.path.isfile(voc_path) and os.path.isfile(inst_path)

            item = dict(entry)
            item.setdefault("folder", "Unsorted")
            item["analysis_available"] = has_res
            item["audio_available"] = has_audio
            if not has_res and item.get("status") != "failed":
                item["status"] = "incomplete"
            item["stems_available"] = {
                "vocals": os.path.isfile(voc_path),
                "instrumental": os.path.isfile(inst_path),
            }
            item["stems_ready"] = stems_ready
            item["audio_url"] = f"/library/{sid}/audio" if has_audio else None
            item["stems_urls"] = {
                "vocals": f"/library/{sid}/stems/vocals" if os.path.isfile(voc_path) else None,
                "instrumental": f"/library/{sid}/stems/instrumental" if os.path.isfile(inst_path) else None,
            }
            valid_entries.append(item)

        return valid_entries[: self.max_songs]

    def save_completed_song(
        self,
        audio_path: str,
        original_filename: str,
        analysis_data: Dict[str, Any],
        song_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Saves a completed song transcription and arrangement into the 10-song library.
        Automatically evicts the oldest song beyond `max_songs`.
        """
        sid = song_id or (
            self.compute_file_hash(audio_path)
            if (audio_path and os.path.isfile(audio_path))
            else hashlib.sha256(f"{original_filename}-{time.time()}".encode()).hexdigest()[:24]
        )
        song_dir = os.path.join(self.root_dir, sid)
        os.makedirs(song_dir, exist_ok=True)

        # Copy original audio file into song_dir if not already there
        ext = os.path.splitext(original_filename)[1] or ".wav"
        stored_audio_name = f"source_audio{ext}"
        stored_audio_path = os.path.join(song_dir, stored_audio_name)
        if audio_path and os.path.isfile(audio_path):
            if os.path.abspath(audio_path) != os.path.abspath(stored_audio_path):
                try:
                    shutil.copy2(audio_path, stored_audio_path)
                except Exception as e:
                    logger.warning(f"Could not copy audio into library: {e}")

        # Copy separated vocals & instrumental stems if already generated during pipeline
        stem_paths = analysis_data.get("_stem_paths") or {}
        for stem_key, target_name in [("vocals", "vocals.wav"), ("instrumental", "instrumental.wav"), ("other", "instrumental.wav")]:
            src_stem = stem_paths.get(stem_key)
            dst_stem = os.path.join(song_dir, target_name)
            if src_stem and os.path.isfile(src_stem) and not os.path.isfile(dst_stem):
                try:
                    shutil.copy2(src_stem, dst_stem)
                except Exception:
                    pass

        # Update stem URLs inside analysis_data to point to persistent library endpoints
        voc_exists = os.path.isfile(os.path.join(song_dir, "vocals.wav"))
        inst_exists = os.path.isfile(os.path.join(song_dir, "instrumental.wav"))
        stems_map: Dict[str, str] = {}
        if voc_exists:
            stems_map["vocals"] = f"/library/{sid}/stems/vocals"
        if inst_exists:
            stems_map["instrumental"] = f"/library/{sid}/stems/instrumental"

        persisted_data = dict(analysis_data)
        persisted_data["song_id"] = sid
        persisted_data["stems"] = stems_map
        if "timeline" in persisted_data and isinstance(persisted_data["timeline"], dict):
            persisted_data["timeline"]["stems"] = stems_map

        # Save analysis_result.json
        res_path = os.path.join(song_dir, "analysis_result.json")
        with open(res_path, "w", encoding="utf-8") as f:
            json.dump(persisted_data, f)

        title = os.path.splitext(os.path.basename(original_filename))[0] or "Untitled Song"
        existing = next((e for e in self._load_index() if e.get("id") == sid), None)
        entry = {
            "id": sid,
            "title": (existing.get("title") if existing else None) or title,
            "filename": original_filename,
            "folder": (existing.get("folder") if existing else None) or "Unsorted",
            "audio_filename": stored_audio_name if os.path.isfile(stored_audio_path) else None,
            "duration": float(analysis_data.get("duration", 0.0)),
            "key": analysis_data.get("key_full") or analysis_data.get("key") or "C Major",
            "tempo": round(float(analysis_data.get("tempo", 120.0))),
            "status": "ready",
            "arrangements": ["Beginner", "Intermediate"],
            "beginner_notes_count": len(analysis_data.get("beginner_notes") or []),
            "intermediate_notes_count": len(analysis_data.get("notes") or []),
            "created_at": (existing.get("created_at") if existing else None) or time.time(),
            "last_accessed_at": time.time(),
        }

        entries = [e for e in self._load_index() if e.get("id") != sid]
        entries.insert(0, entry)

        # Enforce 10-song cap and clean up evicted song directories
        while len(entries) > self.max_songs:
            evicted = entries.pop()
            ev_id = evicted.get("id")
            if ev_id and ev_id != sid:
                ev_dir = os.path.join(self.root_dir, ev_id)
                shutil.rmtree(ev_dir, ignore_errors=True)

        self._save_index(entries)
        return self.list_songs()[0]

    def load_song_data(self, song_id: str) -> Optional[Dict[str, Any]]:
        """Loads the full saved analysis/timeline dictionary for a library song."""
        song_dir = os.path.join(self.root_dir, song_id)
        res_path = os.path.join(song_dir, "analysis_result.json")
        if not os.path.isfile(res_path):
            return None
        try:
            with open(res_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            voc_path = os.path.join(song_dir, "vocals.wav")
            inst_path = os.path.join(song_dir, "instrumental.wav")
            stems_map: Dict[str, str] = {}
            stem_paths_map: Dict[str, str] = {}
            if os.path.isfile(voc_path):
                stems_map["vocals"] = f"/library/{song_id}/stems/vocals"
                stem_paths_map["vocals"] = voc_path
            if os.path.isfile(inst_path):
                stems_map["instrumental"] = f"/library/{song_id}/stems/instrumental"
                stem_paths_map["instrumental"] = inst_path
            data["song_id"] = song_id
            data["stems"] = stems_map
            data["_stem_paths"] = stem_paths_map
            if "timeline" in data and isinstance(data["timeline"], dict):
                data["timeline"]["stems"] = stems_map
            return data
        except Exception as e:
            logger.error(f"Failed to load song {song_id}: {e}")
            return None

    def get_audio_path(self, song_id: str) -> Optional[str]:
        entries = self._load_index()
        entry = next((e for e in entries if e.get("id") == song_id), None)
        if not entry or not entry.get("audio_filename"):
            return None
        p = os.path.join(self.root_dir, song_id, entry["audio_filename"])
        return p if os.path.isfile(p) else None

    def get_stem_path(self, song_id: str, stem_name: str) -> Optional[str]:
        norm = "vocals" if stem_name == "vocals" else "instrumental"
        p = os.path.join(self.root_dir, song_id, f"{norm}.wav")
        return p if os.path.isfile(p) else None

    def delete_song(self, song_id: str) -> bool:
        entries = self._load_index()
        new_entries = [e for e in entries if e.get("id") != song_id]
        if len(new_entries) == len(entries):
            return False
        self._save_index(new_entries)
        song_dir = os.path.join(self.root_dir, song_id)
        shutil.rmtree(song_dir, ignore_errors=True)
        return True

    def touch_last_accessed(self, song_id: str) -> Optional[Dict[str, Any]]:
        entries = self._load_index()
        now = time.time()
        target = None
        for entry in entries:
            if entry.get("id") == song_id:
                entry["last_accessed_at"] = now
                target = entry
                break
        if target is None:
            return None
        self._save_index(entries)
        return target

    def update_song_metadata(self, song_id: str, title: Optional[str] = None, folder: Optional[str] = None) -> Optional[Dict[str, Any]]:
        entries = self._load_index()
        target = None
        for entry in entries:
            if entry.get("id") == song_id:
                if title is not None and str(title).strip():
                    entry["title"] = str(title).strip()
                if folder is not None:
                    clean_folder = str(folder).strip() or "Unsorted"
                    entry["folder"] = clean_folder
                    if clean_folder != "Unsorted":
                        self.create_folder(clean_folder)
                target = entry
                break
        if target is None:
            return None
        self._save_index(entries)
        return next((s for s in self.list_songs() if s.get("id") == song_id), target)

    def list_folders(self) -> List[str]:
        folders: List[str] = []
        if os.path.isfile(self.folders_path):
            try:
                with open(self.folders_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    if isinstance(raw, list):
                        folders = [str(x).strip() for x in raw if str(x).strip()]
            except Exception:
                pass
        for entry in self._load_index():
            fld = str(entry.get("folder") or "").strip()
            if fld and fld != "Unsorted" and fld not in folders:
                folders.append(fld)
        return folders

    def create_folder(self, name: str) -> List[str]:
        clean = str(name or "").strip()
        if not clean or clean.lower() == "unsorted":
            return self.list_folders()
        folders = self.list_folders()
        if clean not in folders:
            folders.append(clean)
            tmp = self.folders_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(folders, f, indent=2)
            os.replace(tmp, self.folders_path)
        return folders

    def delete_folder(self, name: str) -> List[str]:
        clean = str(name or "").strip()
        folders = [f for f in self.list_folders() if f != clean]
        tmp = self.folders_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(folders, f, indent=2)
        os.replace(tmp, self.folders_path)
        entries = self._load_index()
        changed = False
        for entry in entries:
            if entry.get("folder") == clean:
                entry["folder"] = "Unsorted"
                changed = True
        if changed:
            self._save_index(entries)
        return folders

    def extract_stems_for_song(self, song_id: str, progress_cb=None) -> Dict[str, Any]:
        """
        Extracts `vocals.wav` and `instrumental.wav` for a saved library song.
        Uses Demucs if available; otherwise uses harmonic-vocal spectral masking
        so stem extraction always succeeds reliably offline.
        """
        song_dir = os.path.join(self.root_dir, song_id)
        voc_dst = os.path.join(song_dir, "vocals.wav")
        inst_dst = os.path.join(song_dir, "instrumental.wav")

        if os.path.isfile(voc_dst) and os.path.isfile(inst_dst):
            if progress_cb:
                progress_cb("Stems already available", 100)
            return {
                "song_id": song_id,
                "vocals": f"/library/{song_id}/stems/vocals",
                "instrumental": f"/library/{song_id}/stems/instrumental",
            }

        audio_path = self.get_audio_path(song_id)
        if not audio_path or not os.path.isfile(audio_path):
            raise FileNotFoundError(f"Source audio file missing for song {song_id}")

        if progress_cb:
            progress_cb("Separating vocals and backing track...", 20)

        from backend.analysis.source_separation import separate_stems
        sep_res = separate_stems(audio_path, upd_callback=progress_cb)

        if sep_res.success and sep_res.voc_path and os.path.isfile(sep_res.voc_path) and sep_res.inst_path and os.path.isfile(sep_res.inst_path):
            shutil.copy2(sep_res.voc_path, voc_dst)
            shutil.copy2(sep_res.inst_path, inst_dst)
        else:
            # High-speed DSP vocal / backing spectral separation fallback
            if progress_cb:
                progress_cb("Running spectral vocal & backing separation...", 55)
            y, sr = librosa.load(audio_path, sr=22050, mono=True)
            S_full, phase = librosa.magphase(librosa.stft(y, n_fft=2048, hop_length=512))
            S_filter = librosa.decompose.nn_filter(
                S_full,
                aggregate=np.median,
                metric="cosine",
                width=int(librosa.time_to_frames(1.0, sr=sr, hop_length=512)),
            )
            S_filter = np.minimum(S_full, S_filter)
            margin_i, margin_v = 2, 10
            power = 2
            mask_i = librosa.util.softmask(S_filter, margin_i * (S_full - S_filter), power=power)
            mask_v = librosa.util.softmask(S_full - S_filter, margin_v * S_filter, power=power)

            # Focus vocal mask on vocal frequency band (160 Hz - 4200 Hz)
            freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
            vocal_band = ((freqs >= 160.0) & (freqs <= 4200.0)).astype(np.float32)[:, None]
            S_vocals = S_full * mask_v * vocal_band
            S_inst = S_full * np.maximum(mask_i, 1.0 - mask_v * vocal_band)

            y_voc = librosa.istft(S_vocals * phase, hop_length=512, length=len(y))
            y_inst = librosa.istft(S_inst * phase, hop_length=512, length=len(y))

            sf.write(voc_dst, y_voc, sr)
            sf.write(inst_dst, y_inst, sr)

        # Update saved analysis_result.json with stem URLs
        data = self.load_song_data(song_id)
        if data:
            res_path = os.path.join(song_dir, "analysis_result.json")
            with open(res_path, "w", encoding="utf-8") as f:
                json.dump(data, f)

        if progress_cb:
            progress_cb("Stems ready", 100)

        return {
            "song_id": song_id,
            "vocals": f"/library/{song_id}/stems/vocals",
            "instrumental": f"/library/{song_id}/stems/instrumental",
        }


library_store = SongLibraryStore()
