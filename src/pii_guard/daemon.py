"""
pii-guard-daemon — the only process that loads the spaCy model. Everything
that talks to it (a Claude Code hook, etc.) is a thin HTTP client — see
adapters/. No AUTH_TOKEN, no hosted-tier branch: this tool has exactly one
deployment target, local, by design — see README "Why no hosted tier."
"""

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

from pii_guard import config, engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pii_guard")


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine.load_engines()
    logger.info("pii-guard-daemon ready on %s:%s", config.HOST, config.PORT)
    yield


app = FastAPI(title="pii-guard", lifespan=lifespan)


class AnalyzeRequest(BaseModel):
    text: str


class EntityResult(BaseModel):
    entity_type: str
    start: int
    end: int
    score: float


class AnalyzeResponse(BaseModel):
    found: bool
    redacted_text: str
    entities: list[EntityResult]


@app.get("/health")
def health():
    return {"status": "ok", "engines_loaded": engine._analyzer is not None}


@app.get("/about")
def about():
    return {
        "service": "pii-guard",
        "engine": "Microsoft Presidio (MIT)",
        "default_model": "spacy/en_core_web_lg (MIT, Explosion)",
        "language_scope": "English only (v1) — see README",
        "hosted_tier": "none — local only by design, see README",
    }


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    return engine.analyze_and_redact(req.text)


def main() -> None:
    uvicorn.run(app, host=config.HOST, port=config.PORT)


if __name__ == "__main__":
    main()
