from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from . import models, schemas
from .database import engine, get_db, Base
from .risk_engine import compute_risk_flags
from .sample_engine import trace_address  # calls Person A's real tracing_engine.trace_wallet (see sample_engine.py docstring)
from .report_generator import generate_case_report

Base.metadata.create_all(bind=engine)

app = FastAPI(title="SIH26182 - Wallet Attribution API")

# Wide-open CORS for hackathon dev; tighten before any real deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/trace", response_model=schemas.CaseDetail)
def submit_trace(req: schemas.TraceRequest, db: Session = Depends(get_db)):
    """
    Core case-submission endpoint (Day 5 deliverable).
    1. Calls the tracing engine (sample stand-in today, Person A's real
       module after Day 8 integration) to get hops/matched_vasp/confidence.
    2. Computes risk_flags ourselves from the hops.
    3. Persists the case and returns the full record.
    """
    raw_trace = trace_address(req.address, max_hops=req.max_hops)
    risk_flags = compute_risk_flags(raw_trace["hops"])
    raw_trace["risk_flags"] = risk_flags

    # Validate shape against the contract before storing
    trace_result = schemas.TraceResult(**raw_trace)

    case = models.Case(
        query_address=trace_result.query_address,
        matched_vasp=trace_result.matched_vasp,
        confidence=trace_result.confidence,
        match_method=trace_result.match_method,
        risk_flags=trace_result.risk_flags,
        trace_json=trace_result.model_dump(),
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    return _to_case_detail(case)


@app.get("/api/cases", response_model=list[schemas.CaseSummary])
def list_cases(db: Session = Depends(get_db)):
    cases = db.query(models.Case).order_by(models.Case.created_at.desc()).all()
    return [_to_case_summary(c) for c in cases]


@app.get("/api/cases/{case_id}", response_model=schemas.CaseDetail)
def get_case(case_id: int, db: Session = Depends(get_db)):
    case = db.query(models.Case).filter(models.Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return _to_case_detail(case)


@app.get("/api/cases/{case_id}/report")
def download_report(case_id: int, db: Session = Depends(get_db)):
    case = db.query(models.Case).filter(models.Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    pdf_bytes = generate_case_report({
        "id": case.id,
        "query_address": case.query_address,
        "matched_vasp": case.matched_vasp,
        "confidence": case.confidence,
        "match_method": case.match_method,
        "risk_flags": case.risk_flags,
        "trace": case.trace_json,
        "created_at": case.created_at.isoformat(),
    })
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="case_{case_id}_report.pdf"'},
    )


def _to_case_summary(case: models.Case) -> schemas.CaseSummary:
    return schemas.CaseSummary(
        id=case.id,
        query_address=case.query_address,
        matched_vasp=case.matched_vasp,
        confidence=case.confidence,
        risk_flags=case.risk_flags,
        created_at=case.created_at.isoformat(),
    )


def _to_case_detail(case: models.Case) -> schemas.CaseDetail:
    return schemas.CaseDetail(
        **_to_case_summary(case).model_dump(),
        trace=schemas.TraceResult(**case.trace_json),
    )
