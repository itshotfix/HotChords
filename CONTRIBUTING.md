# Contributing to HotChords

Thank you for your interest in contributing to HotChords! 

We welcome contributions from Developers, DSP engineers, MIR researchers, Musicians, Piano players, Piano teachers, and UX designers. Whether you want to improve chord detection accuracy, refine the piano visualization, or help beginners learn better, there is a place for you here.

## Project Philosophy

HotChords operates on two core principles:

1. **Free and Local**: The application must run entirely offline on a user's machine. No cloud APIs, no telemetry, no subscriptions.
2. **Accuracy over Features**: A smaller number of reliable, highly accurate features is better than a large number of inaccurate ones. New features are welcome, but never at the expense of detection quality or application stability.

## Development Setup

### Local Environment
- **Python 3.10, 3.11, or 3.12**
- **FFmpeg**: Bundled automatically via the `imageio-ffmpeg` package. No manual installation is required for most platforms.

### Initializing the Project

```bash
git clone https://github.com/hotfix/hotchords.git
cd hotchords

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt

python3 hotchords.py
```

The app will be available locally at `http://localhost:5500`.

## Code Organization

Our architecture is simple and requires no build step:

- `backend/api/` - FastAPI endpoints (`router.py`)
- `backend/analysis/` - DSP, harmonic separation, and Viterbi HMM pipeline
- `backend/theory/` - Music theory, enharmonics, and simplification algorithms
- `frontend/index.html` - SPA shell
- `frontend/css/` - Vanilla CSS styles
- `frontend/js/` - Vanilla JS modules (Fingering engine, UI renderers, GSAP animation)

## Coding Conventions

- **Python**: Follow PEP 8. Use standard `try/except Exception as e` blocks. Keep `router.py` thin by delegating to `pipeline.py`.
- **JavaScript**: Vanilla JS only. No npm, no Webpack, no frameworks. Keep all logic organized into modular objects on the global `window` object.
- **CSS**: All styles must reside in `piano.css`. No inline styles. Use CSS variables for theme colors.

## Documentation Expectations

- All public Python functions, especially those involving DSP or Music Theory, must include a docstring explaining **what** it does and **why**. 
- Javascript comments should explain the *algorithmic or musical decisions* behind the code, rather than just narrating the syntax.
- If you change a core algorithm, please update `docs/ARCHITECTURE.md` or the relevant pipeline markdown files.

## Testing Expectations

We do not currently have a comprehensive automated test suite, but all pull requests must be manually verified:
1. Ensure the app starts without errors.
2. Upload a test audio file.
3. Verify the chord timeline, piano visualization, and hand animations render correctly at different viewport sizes.

## Issue Reporting

When reporting a bug, please include:
- Your OS and Python version.
- The audio format that caused the issue.
- The full terminal traceback.
- Steps to reproduce.

## Feature Proposals

If you have an idea for a major feature (e.g., a new simplification algorithm, moving to WASM for DSP), please open a GitHub Discussion first. This ensures alignment with the product vision before you write code.

## Pull Requests

1. **Fork** the repository and create a branch (`feature/my-improvement`).
2. **Make your changes** with focused, atomic commits.
3. **Test manually** using the steps above.
4. **Write a clear commit message** explaining the *why* behind your changes.
5. **Open a Pull Request** against `main`.

Thank you for helping us turn any song into something a beginner pianist can play!
