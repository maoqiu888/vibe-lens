from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Vibe-Radar", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # V1.0 dev-open; tighten in V1.1
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}
