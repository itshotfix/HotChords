# HotChords v0.4.0 Release Checklist

Pre-flight release checklist for publishing HotChords v0.4.0 to GitHub.

---

## 1. Versioning & Package Metadata
- [x] Package version synchronized to `0.4.0` in `package.json`
- [x] Backend package constant `APP_VERSION = "0.4.0"` in `backend/models/__init__.py`
- [x] API documentation version matches `0.4.0` in `backend/api/router.py`
- [x] Desktop workstation header branding updated to `VER 0.4` in `frontend/index.html`
- [x] Data contract version set to `0.4.0` in `SONG_RESULT_CONTRACT.md`
- [x] macOS DMG build script version set to `0.4.0` in `scripts/build_macos_dmg.sh`
- [x] UI/UX test assertion updated for `v0.4` / `0.4.0` in `tests/test_phase_7c_ui_ux.js`

---

## 2. Codebase Cleanliness & Security
- [x] No private machine paths (`/Users/`, `/Volumes/`) in active source files or scripts
- [x] Zero API keys, secrets, private tokens, or credentials in repository
- [x] `.env.example` created with sanitized configuration placeholders
- [x] `.gitignore` verified to exclude OS files, caches, `.env`, logs, and temporary test audio while preserving bundled piano sample assets
- [x] Temporary cache files (`__pycache__`, `.pytest_cache`, `.DS_Store`) removed

---

## 3. Documentation & Governance
- [x] `README.md` rewritten with professional architecture flow, truthful confidence explanation, and verified commands
- [x] `docs/ARCHITECTURE.md` updated with complete technical description of all 6 core sub-systems
- [x] Real-world screenshots prepared and stored in `docs/images/`
- [x] `CONTRIBUTING.md` updated with accurate developer setup and test guidelines
- [x] `CODE_OF_CONDUCT.md` created with Contributor Covenant 2.1 standard
- [x] `SECURITY.md` created with responsible disclosure guidelines
- [x] `CHANGELOG.md` updated with comprehensive `v0.4.0` release notes
- [x] `THIRD_PARTY_LICENSE_AUDIT.md` verified for MIT/Apache/BSD/CC-BY compliance

---

## 4. Test Suite Verification
- [x] Python backend test suite passes: `pytest tests/` (195/195 tests passed)
- [x] Node frontend UI/UX test suite passes: `npm test` (37/37 tests passed)
- [x] Playback lifecycle test suite passes: `node tests/test_playback_lifecycle.js` (6/6 scenarios passed)
- [x] Client pitch detection test suite passes: `node tests/test_phase11_client_pitch_and_feedback.js` (7/7 tests passed)
- [x] Client practice metrics test suite passes: `node tests/test_phase12_client_metrics.js` (5/5 tests passed)

---

## 5. Ready for User Review
- [x] Git working tree inspected and clean of junk artifacts
- [x] Release packaging report generated: `GITHUB_RELEASE_PREPARATION_REPORT.md`
- [x] Git commit and tag commands prepared for user review (NO automatic push or commit performed)
