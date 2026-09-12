"""
backend/analysis/pipeline.py

Main audio analysis pipeline for HotChords (Phase 3 Multi-Instrument & Source-Aware Architecture).

Processing stages (in order):
  1. Stem separation via Demucs (extracts drums, bass, other/harmonic, vocals, instrumental)
  2. Audio loading at 22kHz mono (efficient resolution for chroma & chord inference)
  3. Audio Profiling & QC check (silence, clipping, harmonic energy, SNR, status classification)
  4. Dynamic candidate generation (Mix, HPSS Harmonic, Other/Harmonic Stem, Bass Stem)
  5. Transparent harmonic evidence scoring & non-harmonic filtering
  6. Timing analysis (tempo, time signature, beat & downbeat grid)
  7. Key & scale estimation
  8. Multi-source chord recognition on qualifying candidates
  9. Cross-source musical agreement & bass root/slash-chord inversion fusion
  10. Best harmonic evidence selection with explainable reasoning
  11. Multi-dimensional reliability evaluation (harmonic strength, stability, beat alignment, agreement)
  12. Music theory enrichment & beginner chart simplification
  13. Canonical SongTimeline serialization
"""

import os
import gc
import tempfile
import soundfile as sf
import numpy as np
import librosa

from backend.theory.theory import (
    NOTE_NAMES, NOTE_FLAT, musician_friendly_name,
    chord_note_indices, get_chord_notes_musician, chord_fingers,
    chord_difficulty, chord_roman, _scale_notes, get_pitch_class,
    simplify_progression
)
from backend.analysis.source_separation import separate_stems, STEMS_DIR
from backend.analysis.profiling import profile_audio, compute_chunked_hpss
from backend.analysis.timing import TimingAnalyzer
from backend.analysis.harmonic_evidence import HarmonicEvidenceRouter
from backend.analysis.instrument_evidence import (
    build_instrument_evidence_registry,
    build_unclassified_instrument_registry
)
from backend.analysis.confidence import evaluate_detection_reliability
from backend.analysis.structure import detect_structure_and_repeats
from backend.analysis.loop_detection import detect_four_chord_loop
from backend.models.analysis_types import (
    AudioStatus,
    TimingData,
    DetectionReliability,
    SourceSelectionResult,
    StructureAnalysisResult,
    StructureSection,
    FourChordLoopResult,
)


# ══════════════════════════════════════════════════════════════
#  KEY, SCALE & TIME SIGNATURES
# ══════════════════════════════════════════════════════════════
from backend.theory.constants import KS_MAJOR, KS_MINOR


def detect_key_scale(chroma_mean):
    best_r, best_key, best_scale = -2.0, 'C', 'Major'
    for i in range(12):
        r = np.corrcoef(chroma_mean, np.roll(KS_MAJOR, i))[0, 1]
        if r > best_r:
            best_r, best_key, best_scale = r, NOTE_FLAT[i], 'Major'
        r = np.corrcoef(chroma_mean, np.roll(KS_MINOR, i))[0, 1]
        if r > best_r:
            best_r, best_key, best_scale = r, NOTE_FLAT[i], 'Minor'
    return best_key, best_scale


def detect_time_sig(y, sr, tempo):
    try:
        hop = 512
        onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
        ac = librosa.autocorrelate(onset_env, max_size=int(sr * 4 / hop))
        bp = int(round(60.0 / float(tempo) * sr / hop))
        if bp < 1:
            return '4/4'
        s4 = ac[bp * 4] if bp * 4 < len(ac) else 0
        s3 = ac[bp * 3] if bp * 3 < len(ac) else 0
        return '3/4' if s3 > s4 * 1.1 else '4/4'
    except Exception:
        return '4/4'


# ══════════════════════════════════════════════════════════════
#  MAIN ANALYSIS PIPELINE
# ══════════════════════════════════════════════════════════════
def analyze_song(filepath: str, progress_callback=None, upd_callback=None):
    """
    Main entry point for HotChords song analysis.
    Executes the complete Phase 3 Multi-Instrument & Source-Aware pipeline.
    """
    cb = upd_callback if upd_callback is not None else progress_callback

    def update(msg, pct):
        if cb:
            cb(msg, pct)
        else:
            print(f'  [{pct:3d}%] {msg}')

    update('Loading song...', 5)

    # ══════════════════════════════════════════════════════════════
    #  STAGE 1: MULTI-STEM SEPARATION WITH PROVENANCE PRESERVATION
    # ══════════════════════════════════════════════════════════════
    sep_res = separate_stems(filepath, upd_callback=update)
    inst_path = sep_res.inst_path
    voc_path = sep_res.voc_path
    bass_path = sep_res.bass_path
    other_path = sep_res.other_path
    drums_path = sep_res.drums_path
    sep_success = sep_res.success

    update('Profiling audio quality...', 25)
    try:
        y, sr = librosa.load(filepath, sr=22050, mono=True)
        duration = librosa.get_duration(y=y, sr=sr)
    except Exception as e:
        profile, status, status_msg = profile_audio(np.array([]), sr=22050)
        status = AudioStatus.UNSUPPORTED_AUDIO
        status_msg = f"Failed to load audio: {e}"
        instruments = build_unclassified_instrument_registry()
        return {
            'ready': True,
            'duration': 0.0,
            'key': 'C',
            'scale': 'Major',
            'key_full': 'C Major',
            'tempo': 120.0,
            'time_sig': '4/4',
            'scale_notes': [0, 2, 4, 5, 7, 9, 11],
            'chords': [],
            'unique_chords': [],
            'chord_data': {},
            'roman_numerals': {},
            'beginner_chords': [],
            'unique_beginner_chords': [],
            'easy_key': 'C',
            'easy_key_full': 'C Major',
            'transpose_offset': 0,
            'sections': [],
            'structure': StructureAnalysisResult(sections=[], repeating_sections=[], structure_confidence=0.0, total_sections=0, has_repeating_patterns=False).model_dump(by_alias=True),
            'four_chord_loop': FourChordLoopResult(available=False, reason="UNSUPPORTED_AUDIO").model_dump(by_alias=True),
            'status': status.value,
            'status_message': status_msg,
            'audio_profile': profile.model_dump(by_alias=True),
            'timing': TimingData(tempo=120.0, time_signature='4/4', beat_times=[], downbeat_times=None, beat_confidence=0.0).model_dump(by_alias=True),
            'reliability': DetectionReliability(overall=0.0, harmonic_strength=0.0, temporal_stability=0.0, beat_alignment=0.0, source_agreement=None, engine_agreement=None).model_dump(by_alias=True),
            'candidate_evidence': HarmonicEvidenceRouter().extract_evidence(),
            'instruments': {k: v.model_dump(by_alias=True) for k, v in instruments.items()},
        }

    # Execute Audio Profiling & QC check
    profile, status, status_msg = profile_audio(y, sr=sr)
    instruments = build_unclassified_instrument_registry()

    # Guard: Non-harmonic, empty, or silent audio -> Short-circuit without fabricating chords
    if status in [AudioStatus.EMPTY_AUDIO, AudioStatus.UNSUPPORTED_AUDIO, AudioStatus.NO_HARMONIC_CONTENT]:
        update(f'Analysis complete ({status.value})', 100)
        timing_data = TimingData(
            tempo=120.0,
            time_signature='4/4',
            beat_times=[],
            downbeat_times=None,
            beat_confidence=0.0
        )
        reliability = DetectionReliability(
            overall=0.0,
            harmonicStrength=0.0,
            temporalStability=0.0,
            beatAlignment=0.0,
            sourceAgreement=None,
            engineAgreement=None
        )
        evidence_router = HarmonicEvidenceRouter(sr=sr)
        evidence_router.register_source("mix", y, audio_path=filepath)
        candidate_evidence = evidence_router.extract_evidence()

        return {
            'ready': True,
            'duration': round(duration, 2),
            'key': 'C',
            'scale': 'Major',
            'key_full': 'C Major',
            'tempo': 120.0,
            'time_sig': '4/4',
            'scale_notes': [0, 2, 4, 5, 7, 9, 11],
            'chords': [],
            'unique_chords': [],
            'chord_data': {},
            'roman_numerals': {},
            'beginner_chords': [],
            'unique_beginner_chords': [],
            'easy_key': 'C',
            'easy_key_full': 'C Major',
            'transpose_offset': 0,
            'sections': [],
            'structure': StructureAnalysisResult(sections=[], repeating_sections=[], structure_confidence=0.0, total_sections=0, has_repeating_patterns=False).model_dump(by_alias=True),
            'four_chord_loop': FourChordLoopResult(available=False, reason="NO_HARMONIC_CONTENT").model_dump(by_alias=True),
            'status': status.value,
            'status_message': status_msg,
            'audio_profile': profile.model_dump(by_alias=True),
            'timing': timing_data.model_dump(by_alias=True),
            'reliability': reliability.model_dump(by_alias=True),
            'candidate_evidence': {k: v.model_dump(by_alias=True) for k, v in candidate_evidence.items()},
            'instruments': {k: v.model_dump(by_alias=True) for k, v in instruments.items()},
        }

    # ══════════════════════════════════════════════════════════════
    #  STAGE 2: DYNAMIC CANDIDATE REGISTRATION & EVIDENCE SCORING
    # ══════════════════════════════════════════════════════════════
    update('Preparing harmonic candidate sources...', 35)
    y_harm, _ = compute_chunked_hpss(y, sr=sr, margin=3.0, chunk_sec=30.0)

    # Create temporary WAV for HPSS harmonic component so deep models can infer on it
    hpss_wav_path = os.path.join(tempfile.gettempdir(), f"hotchords_hpss_{os.path.basename(filepath)}.wav")
    try:
        sf.write(hpss_wav_path, y_harm, sr)
    except Exception:
        hpss_wav_path = filepath

    evidence_router = HarmonicEvidenceRouter(sr=sr, hop_length=512)
    evidence_router.register_source("mix", y, audio_path=filepath)
    evidence_router.register_source("harmonic_hpss", y_harm, audio_path=hpss_wav_path)

    registered_waveforms: dict[str, np.ndarray] = {"mix": y, "harmonic_hpss": y_harm}
    y_bass_arr = None

    if sep_success:
        if other_path and os.path.isfile(other_path):
            try:
                y_other, _ = librosa.load(other_path, sr=sr, mono=True)
                evidence_router.register_source("other", y_other, audio_path=other_path)
                registered_waveforms["other"] = y_other
            except Exception:
                pass

        if bass_path and os.path.isfile(bass_path):
            try:
                y_bass_arr, _ = librosa.load(bass_path, sr=sr, mono=True)
                evidence_router.register_source("bass", y_bass_arr, audio_path=bass_path)
                registered_waveforms["bass"] = y_bass_arr
            except Exception:
                pass

        if inst_path and os.path.isfile(inst_path):
            try:
                y_inst, _ = librosa.load(inst_path, sr=sr, mono=True)
                evidence_router.register_source("inst", y_inst, audio_path=inst_path)
                registered_waveforms["inst"] = y_inst
            except Exception:
                pass

        if voc_path and os.path.isfile(voc_path):
            try:
                y_voc, _ = librosa.load(voc_path, sr=sr, mono=True)
                evidence_router.register_source("vocals", y_voc, audio_path=voc_path)
                registered_waveforms["vocals"] = y_voc
            except Exception:
                pass

        if drums_path and os.path.isfile(drums_path):
            try:
                y_drum, _ = librosa.load(drums_path, sr=sr, mono=True)
                evidence_router.register_source("drums", y_drum, audio_path=drums_path)
                registered_waveforms["drums"] = y_drum
            except Exception:
                pass

    candidate_evidence = evidence_router.extract_evidence()

    # ══════════════════════════════════════════════════════════════
    #  STAGE 3: TIMING & KEY DETECTION
    # ══════════════════════════════════════════════════════════════
    update('Extracting rhythm & timing grid...', 45)
    hop = 512
    timing_analyzer = TimingAnalyzer(y=y, sr=sr, hop_length=hop).analyze()
    tempo = timing_analyzer.get_tempo()
    time_sig = detect_time_sig(y, sr, tempo)
    timing_analyzer.time_signature = time_sig
    timing_data = timing_analyzer.get_timing_data()

    update('Finding song key...', 55)
    chroma = librosa.feature.chroma_cqt(y=y_harm, sr=sr, hop_length=hop, bins_per_octave=36)
    key, scale = detect_key_scale(chroma.mean(axis=1))
    root_idx = NOTE_FLAT.index(key) if key in NOTE_FLAT else 0
    is_minor = scale == 'Minor'
    scale_note_idxs = _scale_notes(root_idx, is_minor)

    # ══════════════════════════════════════════════════════════════
    #  STAGE 4: MULTI-SOURCE CHORD RECOGNITION & SELECTION
    # ══════════════════════════════════════════════════════════════
    update('Running multi-source chord recognition...', 70)
    from backend.analysis.engine_manager import ChordEngineManager
    engine_manager = ChordEngineManager()

    evidence_router.analyze_candidate_chords(
        engine_manager=engine_manager,
        timing_data=timing_data,
        duration=duration,
        key=key,
        scale=scale
    )

    update('Evaluating source agreement & selecting best evidence...', 80)
    # Perform Instrument Evidence profiling
    instruments = build_instrument_evidence_registry(sources=registered_waveforms, sr=sr)

    # Release unneeded waveform buffers from memory
    registered_waveforms.clear()
    gc.collect()

    fused_chords, source_selection, computed_status = evidence_router.select_best_evidence(
        duration=duration,
        y_bass=y_bass_arr,
        instruments=instruments
    )

    # ══════════════════════════════════════════════════════════════
    #  STAGE 5: RELIABILITY & CONFIDENCE
    # ══════════════════════════════════════════════════════════════
    update('Evaluating multi-dimensional reliability...', 86)
    reliability = evaluate_detection_reliability(
        profile=profile,
        chords=fused_chords,
        beat_confidence=timing_data.beat_confidence,
        source_agreement=source_selection.source_agreement
    )

    # ══════════════════════════════════════════════════════════════
    #  STAGE 6: THEORY ENRICHMENT & BEGINNER CHART
    # ══════════════════════════════════════════════════════════════
    update('Preparing piano view & chord dictionary...', 88)
    from backend.theory.piano_voicing import (
        voice_chord,
        voice_chord_progression,
        parse_chord_components,
        evaluate_loop_beginner_playability,
    )
    from backend.theory.simplification import reduce_chord_harmony

    # Enrich fused original chord events with Phase 8 canonical metadata & voice-leading
    fused_voicings = voice_chord_progression(fused_chords, beginner_mode=False)
    for c_dict, v in zip(fused_chords, fused_voicings):
        c_name = c_dict.get('chord', 'N')
        root, qual, bass = parse_chord_components(c_name)
        c_dict['root'] = root
        c_dict['quality'] = qual
        c_dict['bass'] = bass
        c_dict['simplified_chord'] = reduce_chord_harmony(c_name)
        c_dict['voicing'] = v
        c_dict['difficulty_score'] = v.get('difficultyScore', 0.0)
        c_dict['source_evidence'] = source_selection.selected_source

    freq = {}
    for c in fused_chords:
        freq[c['chord']] = freq.get(c['chord'], 0.0) + c.get('confidence', 1.0)
    unique_chords = [c for c in sorted(freq, key=lambda k: -freq[k]) if c != 'N']

    chord_data = {}
    for c in set(unique_chords):
        if c == 'N':
            continue
        v_static = voice_chord(c)
        chord_data[c] = {
            'notes': chord_note_indices(c),
            'note_names': get_chord_notes_musician(c),
            'fingers': chord_fingers(c),
            'difficulty': chord_difficulty(c),
            'difficulty_score': v_static.get('difficultyScore', 0.0),
            'voicing': v_static,
        }

    roman_numerals = {c: chord_roman(c, key, scale) for c in unique_chords}
    friendly_key = musician_friendly_name(key)

    update('Generating beginner chart...', 92)
    from backend.theory.simplification import simplify_progression as simplify_beginner_progression

    beginner_events = simplify_beginner_progression(
        chords=fused_chords,
        tempo=tempo,
        key=friendly_key,
        scale=scale
    )
    beginner_chords = [
        {
            'time': c.start_time,
            'end': c.end_time,
            'chord': c.chord_name,
            'raw_chord': c.raw_chord or c.chord_name,
            'confidence': c.confidence if c.confidence is not None else 1.0
        }
        for c in beginner_events
    ]

    # Enrich beginner chord events with voice leading
    beginner_voicings = voice_chord_progression(beginner_chords, beginner_mode=True)
    for c_dict, v in zip(beginner_chords, beginner_voicings):
        c_name = c_dict.get('chord', 'N')
        root, qual, bass = parse_chord_components(c_name)
        c_dict['root'] = root
        c_dict['quality'] = qual
        c_dict['bass'] = bass
        c_dict['simplified_chord'] = c_name
        c_dict['voicing'] = v
        c_dict['difficulty_score'] = v.get('difficultyScore', 0.0)
        c_dict['source_evidence'] = source_selection.selected_source

    b_freq = {}
    for c in beginner_chords:
        b_freq[c['chord']] = b_freq.get(c['chord'], 0.0) + c['confidence']
    unique_beginner_chords = [c for c in sorted(b_freq, key=lambda k: -b_freq[k]) if c != 'N']

    for c in set(unique_beginner_chords):
        if c == 'N' or c in chord_data:
            continue
        v_static = voice_chord(c, beginner_mode=True)
        chord_data[c] = {
            'notes': chord_note_indices(c),
            'note_names': get_chord_notes_musician(c),
            'fingers': chord_fingers(c),
            'difficulty': chord_difficulty(c),
            'difficulty_score': v_static.get('difficultyScore', 0.0),
            'voicing': v_static,
        }
    for c in unique_beginner_chords:
        if c not in roman_numerals:
            roman_numerals[c] = chord_roman(c, friendly_key, scale)

    # ══════════════════════════════════════════════════════════════
    #  STAGE 7: STRUCTURE & 4-CHORD LOOP DETECTION
    # ══════════════════════════════════════════════════════════════
    update('Analyzing song structure & repeating sections...', 95)
    structure_result = detect_structure_and_repeats(
        chroma=chroma,
        sr=sr,
        hop_length=hop,
        duration=duration,
        timing_data=timing_data
    )

    update('Detecting best 4-chord loop progression...', 98)
    four_chord_loop = detect_four_chord_loop(
        chords=fused_chords,
        duration=duration,
        structure=structure_result,
        timing_data=timing_data
    )

    sections_legacy = [
        {
            'label': s.label,
            'start': round(s.start, 3),
            'end': round(s.end, 3)
        }
        for s in structure_result.sections
    ]

    # ══════════════════════════════════════════════════════════════
    #  STAGE 8: BEGINNER PRACTICE INTELLIGENCE (Phase 9)
    # ══════════════════════════════════════════════════════════════
    from backend.theory.beginner_practice import generate_beginner_practice_plan

    # In case there are no active chords detected, preserve strict failure rule
    final_status = computed_status if computed_status != AudioStatus.SUCCESS else status

    practice_plan = generate_beginner_practice_plan(
        chords=fused_chords,
        tempo=tempo,
        key=friendly_key,
        scale=scale,
        duration=duration,
        four_chord_loop=four_chord_loop,
        structure=structure_result,
        reliability=reliability,
        audio_status=final_status
    )

    update('Done!', 100)

    return {
        'ready': True,
        'duration': round(duration, 2),
        'key': friendly_key,
        'scale': scale,
        'key_full': f'{friendly_key} {scale}',
        'tempo': round(tempo, 1),
        'time_sig': time_sig,
        'scale_notes': scale_note_idxs,
        'chords': fused_chords,
        'unique_chords': unique_chords,
        'chord_data': chord_data,
        'roman_numerals': roman_numerals,
        'beginner_chords': beginner_chords,
        'unique_beginner_chords': unique_beginner_chords,
        'easy_key': friendly_key,
        'easy_key_full': f'{friendly_key} {scale}',
        'transpose_offset': 0,
        'sections': sections_legacy,
        'structure': structure_result.model_dump(by_alias=True),
        'four_chord_loop': four_chord_loop.model_dump(by_alias=True),
        'practice': practice_plan.model_dump(by_alias=True),
        'practice_plan': practice_plan.model_dump(by_alias=True),
        # Phase 2-4 Engine, Source Selection & MIR Metadata
        'engine': engine_manager.primary_engine.name if engine_manager.primary_engine else "lv_chordia",
        'fallback_reason': None,
        'status': final_status.value,
        'status_message': status_msg,
        'chord_source': source_selection.selected_source,
        'source_selection_reason': source_selection.reason,
        'source_agreement': source_selection.source_agreement,
        'source_selection': source_selection.model_dump(by_alias=True),
        'audio_profile': profile.model_dump(by_alias=True),
        'timing': timing_data.model_dump(by_alias=True),
        'reliability': reliability.model_dump(by_alias=True),
        'candidate_evidence': {k: v.model_dump(by_alias=True) for k, v in candidate_evidence.items()},
        'instruments': {k: v.model_dump(by_alias=True) for k, v in instruments.items()},
    }


def run_pipeline(filepath: str, progress_callback=None, upd_callback=None):
    """Wrapper alias for analyze_song."""
    return analyze_song(filepath=filepath, progress_callback=progress_callback, upd_callback=upd_callback)

