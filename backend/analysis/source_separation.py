"""
backend/analysis/source_separation.py

AI Source Separation using Demucs (htdemucs).
Extracts instrumental and vocal stems from audio files with hardware acceleration (CUDA/MPS/CPU)
and file caching.
"""

import os
import gc
import tempfile
import logging
import librosa
import numpy as np

logger = logging.getLogger(__name__)

STEMS_DIR = os.path.join(tempfile.gettempdir(), 'hotchords_stems')
if not os.path.exists(STEMS_DIR):
    os.makedirs(STEMS_DIR, exist_ok=True)


def get_stem_paths(filepath: str) -> tuple[str, str]:
    """Get the expected cached paths for instrumental and vocal stems."""
    base_name = os.path.splitext(os.path.basename(filepath))[0]
    inst_path = os.path.join(STEMS_DIR, f"{base_name}_inst.wav")
    voc_path = os.path.join(STEMS_DIR, f"{base_name}_vocals.wav")
    return inst_path, voc_path


def cleanup_stems(filepath: str) -> None:
    """Removes cached stem files for a given input file."""
    inst_path, voc_path = get_stem_paths(filepath)
    for p in (inst_path, voc_path):
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError as e:
                logger.warning(f"Could not remove stem file {p}: {e}")


def separate_stems(filepath: str, upd_callback=None) -> tuple[str, str | None, bool]:
    """
    Extracts instrumental and vocal stems using Demucs.

    Parameters
    ----------
    filepath : str
        Path to the input audio file.
    upd_callback : callable, optional
        Progress callback (msg, pct).

    Returns
    -------
    tuple[str, str | None, bool]
        (instrumental_path, vocal_path, success_flag)
        If Demucs fails or is unavailable, returns (filepath, None, False).
    """
    inst_path, voc_path = get_stem_paths(filepath)

    # Check cache: if both stems exist and are non-empty, reuse them
    if (
        os.path.isfile(inst_path)
        and os.path.getsize(inst_path) > 0
        and os.path.isfile(voc_path)
        and os.path.getsize(voc_path) > 0
    ):
        if upd_callback:
            upd_callback('Using cached separated stems...', 20)
        logger.info(f"Reusing cached stems for {filepath}: {inst_path}, {voc_path}")
        return inst_path, voc_path, True

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
            upd_callback('Loading vocal separation model...', 12)

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
            upd_callback('Separating vocals and instruments...', 20)

        with torch.no_grad():
            sources = apply_model(model, wav_torch, device=device)[0]

        sources = sources.cpu()
        # Instrumental stem = drums (0) + bass (1) + other (2)
        instrumental_audio = sources[0] + sources[1] + sources[2]
        # Vocal stem = vocals (3)
        vocal_audio = sources[3]

        save_audio(instrumental_audio, inst_path, samplerate=model.samplerate)
        save_audio(vocal_audio, voc_path, samplerate=model.samplerate)

        # Cleanup torch resources
        del sources, wav_torch
        if device != 'cpu':
            if device == 'cuda':
                torch.cuda.empty_cache()
            else:
                gc.collect()

        return inst_path, voc_path, True

    except Exception as e:
        logger.warning(f"Demucs source separation failed or bypassed: {e}")
        if upd_callback:
            upd_callback('Stem separation bypassed, proceeding...', 22)
        return filepath, None, False
