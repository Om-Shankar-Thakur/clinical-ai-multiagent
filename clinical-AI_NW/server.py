# server.py

"""
FastAPI backend for the Clinical AI Multi-Agent System.
Exposes the ClinicalOrchestrator pipeline as a REST API.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from orchestrator import ClinicalOrchestrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
#  Singleton orchestrator (loaded once at startup)
# ------------------------------------------------------------------ #
orchestrator: ClinicalOrchestrator | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load heavy resources (FAISS indices, models) once on startup."""
    global orchestrator
    logger.info("Loading ClinicalOrchestrator …")
    orchestrator = ClinicalOrchestrator()
    logger.info("Orchestrator ready.")
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="MedOrchestrator — Multi-Agent Clinical Decision Support",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------ #
#  Request / Response models
# ------------------------------------------------------------------ #
class PatientInput(BaseModel):
    chief_complaint: str = Field(..., min_length=1, examples=["High fever with body ache"])
    symptoms: list[str] = Field(..., min_length=1, examples=[["fever", "body pain", "headache"]])
    lab_results: dict[str, float] = Field(
        default_factory=dict,
        examples=[{"platelets": 80000, "hematocrit": 52}],
    )
    current_medications: list[str] = Field(
        default_factory=list,
        examples=[["Ibuprofen"]],
    )


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "MedOrchestrator"


# ------------------------------------------------------------------ #
#  Endpoints
# ------------------------------------------------------------------ #
@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse()


@app.post("/analyze")
async def analyze_patient(patient: PatientInput):
    """Run the full clinical decision-support pipeline."""
    if orchestrator is None:
        raise HTTPException(status_code=503, detail="Orchestrator not ready")

    try:
        report = orchestrator.run(
            chief_complaint=patient.chief_complaint,
            symptoms=patient.symptoms,
            lab_results=patient.lab_results,
            current_medications=patient.current_medications,
        )
        return report
    except Exception as e:
        logger.exception("Pipeline failed")
        raise HTTPException(status_code=500, detail=str(e))
