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


def separate_stems(filepath: str, upd_callback=None) -> SeparatedSourcesResult:
    """
    Extracts individual stems (drums, bass, other/harmonic, vocals) and combined instrumental
    using Demucs (htdemucs). Preserves individual stem provenance.

    Parameters
    ----------
    filepath : str
        Path to the input audio file.
    upd_callback : callable, optional
        Progress callback (msg, pct).

    Returns
    -------
    SeparatedSourcesResult
        Container with inst_path, voc_path, bass_path, other_path, drums_path, success, device.
        Also acts as a 3-tuple (inst_path, voc_path, success) for legacy consumers.
    """
    paths = get_stem_paths(filepath)
    inst_path = paths["inst"]
    voc_path = paths["vocals"]
    bass_path = paths["bass"]
    other_path = paths["other"]
    drums_path = paths["drums"]

    # Check cache: if all 5 stems exist and are non-empty, reuse them
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

    try:
        import torch
        from demucs import pretrained
        from demucs.apply import apply_model
        from demucs.audio import save_audio

        # Determine best available hardware accelerator
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
        # Ensure 2D tensor shape (channels, samples)
        if wav.ndim == 1:
            wav = np.stack([wav, wav])
        wav_torch = torch.tensor(wav, device=device).unsqueeze(0)

        if upd_callback:
            upd_callback('Separating stems (drums, bass, harmonic, vocals)...', 20)

        with torch.no_grad():
            sources = apply_model(model, wav_torch, device=device)[0]

        sources = sources.cpu()
        # Demucs htdemucs source mapping:
        # sources[0] = drums
        # sources[1] = bass
        # sources[2] = other (harmonic mix: guitars, keyboards, synth, strings)
        # sources[3] = vocals
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

        # Cleanup torch resources
        del sources, wav_torch
        if device != 'cpu':
            if device == 'cuda':
                torch.cuda.empty_cache()
            else:
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
