# Vibe-Radar V1.0

Chrome extension + FastAPI backend for personalized "Vibe" matching on
book / game / movie / music sites. Highlights text → extracts Vibe tags via
LLM → scores against your dual-weight profile → lets you confirm with
💎/💣 buttons.

## Quick start

### Backend
```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate  # or .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env            # fill in your LLM API key
python -m app.services.seed     # first time only
uvicorn app.main:app --reload --port 8000
pytest                          # run tests
```

### Extension
```bash
cd extension
npm install
npm run build
```
Then Chrome → `chrome://extensions` → Developer mode → Load unpacked → pick `extension/build/`.

## Docs
- Design spec: `docs/superpowers/specs/2026-04-14-vibe-radar-v1-design.md`
- Implementation plan: `docs/superpowers/plans/2026-04-14-vibe-radar-v1.md`
- Manual smoke test: `extension/SMOKE.md`

## Scope
V1.0 is a single-user local dev build (`user_id=1` hardcoded, no auth).
Recommendation pool / JWT / deployment deferred to V1.1+.
