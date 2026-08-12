def transcribe_notes(audio_path, upd_callback=None):
    """
    Interface for future AI note transcription (e.g. Basic Pitch).
    Currently returns None as we rely on Chroma-based chord detection.
    """
    if upd_callback:
        upd_callback('Finding musical notes...', 45)
    
    # Placeholder for future integration
    return None
