# Vibe-Radar V1.0

Chrome extension + FastAPI backend for personalized "Vibe" matching on book/game/movie/music sites.

See `docs/superpowers/specs/2026-04-14-vibe-radar-v1-design.md` for the design.
See `docs/superpowers/plans/2026-04-14-vibe-radar-v1.md` for the implementation plan.

## Quick start

1. Start backend: `cd backend && uvicorn app.main:app --reload --port 8000`
2. Build extension: `cd extension && npm run build`
3. Chrome → Extensions → Developer mode → Load unpacked → pick `extension/build/`

See `extension/SMOKE.md` for the manual smoke test.
