"""
backend/analysis/source_separation.py

AI Source Separation using Demucs (htdemucs).
Extracts and preserves distinct separated stems (drums, bass, other/harmonic, vocals, instrumental)
with hardware acceleration (CUDA/MPS/CPU) and file caching.
"""

import os
import gc
import tempfile
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Tuple, Any
import librosa
import numpy as np

logger = logging.getLogger(__name__)

STEMS_DIR = os.path.join(tempfile.gettempdir(), 'hotchords_stems')
if not os.path.exists(STEMS_DIR):
    os.makedirs(STEMS_DIR, exist_ok=True)


class SeparatedSourcesResult:
    """
    Structured container for separated stem audio paths with provenance preservation.
    Supports 3-tuple unpacking (inst_path, voc_path, success) for 100% backward compatibility.
    """

    def __init__(
        self,
        inst_path: str,
        voc_path: Optional[str] = None,
        bass_path: Optional[str] = None,
        other_path: Optional[str] = None,
        drums_path: Optional[str] = None,
        success: bool = True,
        device: str = "cpu"
    ):
        self.inst_path = inst_path
        self.voc_path = voc_path
        self.bass_path = bass_path
        self.other_path = other_path
        self.drums_path = drums_path
        self.success = success
        self.device = device

    @property
    def available_stems(self) -> Dict[str, str]:
        """Dictionary of valid, existing stem files."""
        stems = {}
        for name, path in [
            ("instrumental", self.inst_path),
            ("vocals", self.voc_path),
            ("bass", self.bass_path),
            ("other", self.other_path),
            ("drums", self.drums_path)
        ]:
            if path and os.path.isfile(path) and os.path.getsize(path) > 0:
                stems[name] = path
        return stems

    def __iter__(self):
        """Allows unpacking: inst_path, voc_path, success = separate_stems(file)"""
        return iter((self.inst_path, self.voc_path, self.success))

    def __getitem__(self, index: int) -> Any:
        return (self.inst_path, self.voc_path, self.success)[index]

    def __repr__(self) -> str:
        return (
            f"SeparatedSourcesResult(success={self.success}, device='{self.device}', "
            f"stems={list(self.available_stems.keys())})"
        )


def get_stem_paths(filepath: str) -> Dict[str, str]:
    """Get the expected cached paths for all separated stems."""
    base_name = os.path.splitext(os.path.basename(filepath))[0]
    return {
        "inst": os.path.join(STEMS_DIR, f"{base_name}_inst.wav"),
        "vocals": os.path.join(STEMS_DIR, f"{base_name}_vocals.wav"),
        "bass": os.path.join(STEMS_DIR, f"{base_name}_bass.wav"),
        "other": os.path.join(STEMS_DIR, f"{base_name}_other.wav"),
        "drums": os.path.join(STEMS_DIR, f"{base_name}_drums.wav"),
    }


def cleanup_stems(filepath: str) -> None:
    """Removes all cached stem files for a given input file."""
    paths = get_stem_paths(filepath)
    for p in paths.values():
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError as e:
                logger.warning(f"Could not remove stem file {p}: {e}")


class SourceSeparationEngine(ABC):
    """Abstract interface for modular audio source separation engines."""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    def check_availability(self) -> Tuple[bool, Optional[str]]:
        return True, None

    @abstractmethod
    def separate(self, filepath: str, upd_callback=None) -> SeparatedSourcesResult:
        pass


class HTDemucsSeparationEngine(SourceSeparationEngine):
    """Default 4-stem separation engine using Meta Demucs (htdemucs)."""

    @property
    def name(self) -> str:
        return "htdemucs"

    def check_availability(self) -> Tuple[bool, Optional[str]]:
        try:
            import torch  # noqa: F401
            from demucs import pretrained  # noqa: F401
        except ImportError as e:
            return False, f"Demucs/PyTorch unavailable: {e}"
        return True, None

    def separate(self, filepath: str, upd_callback=None) -> SeparatedSourcesResult:
        paths = get_stem_paths(filepath)
        inst_path = paths["inst"]
        voc_path = paths["vocals"]
        bass_path = paths["bass"]
        other_path = paths["other"]
        drums_path = paths["drums"]

        if all(os.path.isfile(p) and os.path.getsize(p) > 0 for p in paths.values()):
            if upd_callback:
                upd_callback('Using cached separated stems...', 20)
            logger.info(f"Reusing cached stems for {filepath}: {list(paths.keys())}")
            return SeparatedSourcesResult(
                inst_path=inst_path,
                voc_path=voc_path,
                bass_path=bass_path,
                other_path=other_path,
                drums_path=drums_path,
                success=True,
                device="cache"
            )

        if upd_callback:
            upd_callback('Preparing stem separation...', 10)

        import torch
        from demucs import pretrained
        from demucs.apply import apply_model
        from demucs.audio import save_audio

        device = 'cpu'
        if torch.cuda.is_available():
            device = 'cuda'
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            device = 'mps'

        logger.info(f"Running Demucs separation on target device: {device}")

        if upd_callback:
            upd_callback('Loading stem separation model...', 12)

        model = pretrained.get_model('htdemucs')
        model.to(device)

        if upd_callback:
            upd_callback('Extracting audio waveforms...', 16)

        wav, sr = librosa.load(filepath, sr=model.samplerate, mono=False)
        if wav.ndim == 1:
            wav = np.stack([wav, wav])
        wav_torch = torch.tensor(wav, device=device).unsqueeze(0)

        if upd_callback:
            upd_callback('Separating stems (drums, bass, harmonic, vocals)...', 20)

        with torch.no_grad():
            sources = apply_model(model, wav_torch, device=device)[0]

        sources = sources.cpu()
        drums_audio = sources[0]
        bass_audio = sources[1]
        other_audio = sources[2]
        vocal_audio = sources[3]
        instrumental_audio = sources[0] + sources[1] + sources[2]

        save_audio(drums_audio, drums_path, samplerate=model.samplerate)
        save_audio(bass_audio, bass_path, samplerate=model.samplerate)
        save_audio(other_audio, other_path, samplerate=model.samplerate)
        save_audio(vocal_audio, voc_path, samplerate=model.samplerate)
        save_audio(instrumental_audio, inst_path, samplerate=model.samplerate)

        del sources, wav_torch, model
        if device == 'cuda':
            torch.cuda.empty_cache()
        elif device == 'mps' and hasattr(torch, 'mps') and hasattr(torch.mps, 'empty_cache'):
            torch.mps.empty_cache()
        gc.collect()

        return SeparatedSourcesResult(
            inst_path=inst_path,
            voc_path=voc_path,
            bass_path=bass_path,
            other_path=other_path,
            drums_path=drums_path,
            success=True,
            device=device
        )


class RoFormerSeparationEngine(SourceSeparationEngine):
    """
    Optional 2-stem vocal/instrumental separation adapter via audio-separator
    (BS-RoFormer / Mel-Band RoFormer). Falls back to HTDemucs when unavailable.
    """

    def __init__(self, model_filename: Optional[str] = None):
        self.model_filename = model_filename or os.environ.get(
            "HOTCHORDS_ROFORMER_MODEL",
            "model_bs_roformer_ep_317_sdr_12.9755.ckpt",
        )

    @property
    def name(self) -> str:
        return "roformer"

    def check_availability(self) -> Tuple[bool, Optional[str]]:
        try:
            from audio_separator.separator import Separator  # noqa: F401
        except ImportError as e:
            return False, f"audio-separator package unavailable: {e}"
        return True, None

    def separate(self, filepath: str, upd_callback=None) -> SeparatedSourcesResult:
        ok, reason = self.check_availability()
        if not ok:
            raise RuntimeError(reason or "RoFormerSeparationEngine unavailable")

        from audio_separator.separator import Separator
        paths = get_stem_paths(filepath)
        inst_path = paths["inst"]
        voc_path = paths["vocals"]

        if upd_callback:
            upd_callback('Running RoFormer vocal/instrumental separation...', 18)

        separator = Separator(output_dir=STEMS_DIR, output_format="WAV")
        separator.load_model(model_filename=self.model_filename)
        out_files = separator.separate(filepath)

        resolved_voc = None
        resolved_inst = None
        for f in out_files:
            full = f if os.path.isabs(f) else os.path.join(STEMS_DIR, f)
            low = os.path.basename(full).lower()
            if "vocal" in low:
                resolved_voc = full
            elif "instrument" in low or "no_vocal" in low:
                resolved_inst = full

        if resolved_voc and os.path.isfile(resolved_voc):
            os.replace(resolved_voc, voc_path)
        if resolved_inst and os.path.isfile(resolved_inst):
            os.replace(resolved_inst, inst_path)

        gc.collect()
        return SeparatedSourcesResult(
            inst_path=inst_path if os.path.isfile(inst_path) else filepath,
            voc_path=voc_path if os.path.isfile(voc_path) else None,
            bass_path=None,
            other_path=inst_path if os.path.isfile(inst_path) else None,
            drums_path=None,
            success=os.path.isfile(inst_path) and os.path.isfile(voc_path),
            device="roformer",
        )


def get_separation_engine(engine_name: Optional[str] = None) -> SourceSeparationEngine:
    """Factory returning the configured SourceSeparationEngine (defaults to HTDemucs)."""
    selected = (engine_name or os.environ.get("HOTCHORDS_SEPARATION_ENGINE", "htdemucs")).strip().lower()
    if selected in ("roformer", "bs-roformer", "melband-roformer"):
        return RoFormerSeparationEngine()
    return HTDemucsSeparationEngine()


def separate_stems(
    filepath: str,
    upd_callback=None,
    engine: Optional[str] = None,
) -> SeparatedSourcesResult:
    """
    Extracts stems using the selected SourceSeparationEngine (default: HTDemucs),
    automatically falling back to HTDemucs if an optional engine fails or is unavailable,
    and bypassing gracefully if separation fails completely.
    """
    primary = get_separation_engine(engine)
    fallback = HTDemucsSeparationEngine()

    if primary.name != fallback.name:
        ok, reason = primary.check_availability()
        if ok:
            try:
                return primary.separate(filepath, upd_callback=upd_callback)
            except Exception as e:
                logger.warning(f"{primary.name} separation failed ({e}); falling back to htdemucs")
        else:
            logger.info(f"{primary.name} unavailable ({reason}); using htdemucs fallback")

    try:
        return fallback.separate(filepath, upd_callback=upd_callback)
    except Exception as e:
        logger.warning(f"Demucs source separation failed or bypassed: {e}")
        if upd_callback:
            upd_callback('Stem separation bypassed, proceeding...', 22)
        return SeparatedSourcesResult(
            inst_path=filepath,
            voc_path=None,
            bass_path=None,
            other_path=None,
            drums_path=None,
            success=False,
            device="bypass"
        )
