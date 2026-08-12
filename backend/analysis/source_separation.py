import os, tempfile, librosa, torch

STEMS_DIR = os.path.join(tempfile.gettempdir(), 'hotchords_stems')
if not os.path.exists(STEMS_DIR): os.makedirs(STEMS_DIR)

def separate_stems(filepath, upd_callback=None):
    """
    Extracts instrumental and vocal stems.
    Interface for future AI source separation (e.g. Demucs).
    """
    if upd_callback:
        upd_callback('Separating vocals and instruments...', 12)
    
    # Placeholder: In the future, this will use a dedicated Demucs module.
    # For now, we return the original file as the 'instrumental' stem.
    # To keep the current functionality if desired, we could import demucs here.
    
    try:
        from demucs import pretrained
        from demucs.apply import apply_model
        from demucs.audio import save_audio
        
        model = pretrained.get_model('htdemucs')
        model.cpu() 
        
        wav, sr = librosa.load(filepath, sr=model.samplerate, mono=False)
        wav = torch.tensor(wav).unsqueeze(0)
        
        if upd_callback:
            upd_callback('Separating vocals and instruments...', 20)
            
        sources = apply_model(model, wav, device='cpu')[0]
        
        instrumental = sources[0] + sources[1] + sources[2]
        vocals = sources[3]
        
        base_name = os.path.basename(filepath).split('.')[0]
        inst_path = os.path.join(STEMS_DIR, f"{base_name}_inst.wav")
        voc_path = os.path.join(STEMS_DIR, f"{base_name}_vocals.wav")
        
        save_audio(instrumental, inst_path, samplerate=model.samplerate)
        save_audio(vocals, voc_path, samplerate=model.samplerate)
        
        return inst_path, voc_path
    except Exception as e:
        print(f"  [Source Separation] AI Separation bypassed or failed: {e}")
        return filepath, filepath
