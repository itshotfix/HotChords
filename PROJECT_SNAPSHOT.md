# Project Snapshot: HotChords V1 (Historical Archive)

> [!NOTE]
> **Historical Archive**: This document records the original monolithic v1.0 architecture prior to the v0.2/v0.3 modularization and Single Workspace transition. For current system documentation, see [README.md](README.md) and [APP_ARCHITECTURE.md](APP_ARCHITECTURE.md).


## Project Structure
- `hotchords.py`: The primary entry point and monolithic script containing all backend logic, API handling, and embedded frontend code.
- `backend/`: An existing directory structure containing modularized components (analysis, models, theory, utils). Currently, `hotchords.py` does not import from this directory, suggesting it is part of a nascent refactoring effort or the v2 migration.
- `frontend/`: Contains `css/` and `js/` subdirectories, which are currently empty, as the UI is embedded in `hotchords.py`.
- `requirements.txt`: Project dependencies (librosa, torch, numpy, etc.).
- `README.md`: Documentation for installation, usage, and features.

## Current Architecture
HotChords is a standalone web application served by a custom Python-based HTTP server. It combines signal processing, machine learning, and a rich web interface into a single-executable experience.

- **Backend**: Built with Python's `http.server.HTTPServer`. It handles file uploads, audio analysis, and MIDI generation.
- **Frontend**: A single-page application (SPA) embedded directly within the Python script as a large HTML/CSS/JS string. It uses Vanilla JS and the Web Audio API for playback and real-time processing.
- **Processing Engine**:
  - **Audio Loading**: `librosa` (22kHz mono).
  - **Separation**: Harmonic-Percussive Source Separation (HPSS) to isolate chords.
  - **Feature Extraction**: Chroma CQT (36 bins/octave).
  - **Classification**: Cosine similarity against 61 chord templates.
  - **Tempo/Structure**: Beat tracking and novelty curve-based segmentation.
- **Storage**: Temporary files are stored in a system-defined `hotchords_stems` directory.

## Current Features

### 1. Analysis
- **61 Chord Types**: Detection of major, minor, dominant 7th, minor 7th, and major 7th chords across all keys.
- **Key & Scale Detection**: Automatic identification using Krumhansl-Schmuckler profiles.
- **BPM & Time Signature**: Automatic beat tracking.
- **Song Structure**: Detection of sections like Intro, Verse, Chorus, Bridge, and Outro.
- **Roman Numeral Analysis**: Conversion of chords to functional harmony (I, IV, V, etc.).

### 2. Instruments & Visualization
- **Multi-Instrument Diagrams**:
  - **Piano**: 1-octave SVG with fingerings and scale highlights.
  - **Guitar**: Fretboard diagrams (35 shapes) and capo suggestions.
  - **Ukulele**: GCEA fretboard diagrams (24 shapes).
- **Waveform Visualization**: Interactive canvas showing the song's energy and section color bands.

### 3. Playback & Practice
- **Real Pitch Shifting**: Change key without affecting tempo using Web Audio detune.
- **Speed Control**: 0.5x to 1.5x playback speed.
- **A-B Looping**: Custom loop regions via waveform clicks or section buttons.
- **MIDI Input**: Real-time chord detection from connected MIDI controllers.
- **Live Mic Listening**: Experimental FFT-based chord detection from a microphone.
- **Metronome**: Beat-synced visual flash and audio click.

### 4. Export
- **MIDI Export**: Three styles: Block chords, Arpeggio, or Chords + Click track.
- **Printable Chord Sheets**: Clean layouts with simplified or full chord options.

## Current API Endpoints

### GET
- `/`: Serves the main SPA (HTML/CSS/JS).
- `/progress`: Returns a JSON object with the current analysis status (`msg` and `pct`).
- `/result`: Returns the final analysis data (chords, sections, key, etc.) in JSON format.

### POST
- `/analyze-path`: Accepts a local file path to begin analysis.
- `/analyze`: Accepts a multipart/form-data file upload to begin analysis.
- `/export-midi`: Accepts JSON configuration (style, data) and returns a generated MIDI file.

## Current UI Screens

### 1. Upload Screen
- Minimalist drag-and-drop interface.
- Supports MP3, WAV, FLAC, M4A, OGG, AAC.
- Privacy-focused messaging (local processing).

### 2. Progress Screen
- Visual progress bar.
- Step-by-step status indicators (Load -> Harmonics -> Chroma -> Tempo -> Key -> Chords -> Structure -> Done).

### 3. Main Dashboard (App Screen)
- **Header**: Logo and project branding.
- **Intel Bar**: Real-time stats (Key, BPM, Duration).
- **Playback Control**: Waveform, transport controls (Play/Pause, Seek), Transpose, and Speed.
- **Now Playing**: Horizontal trail of current and upcoming chords with a mini piano visualization.
- **Tabs**:
  - **Chords Tab**: Mode selection (Beginner/Full), Instrument selection, and chord cards with diagrams.
  - **Sections Tab**: Detailed list of song sections and their constituent chords.
  - **Practice Tab**: Speed presets, looping tools, metronome, MIDI input status, and mic listening.
  - **Export Tab**: Download options for MIDI and print layouts.
