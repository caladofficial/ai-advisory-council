"""Evaluation Lab endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.evaluation.benchmarks import run_evaluation_suite
from app.schemas.evaluation import BenchmarkRunOut

router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])


@router.post("/run", response_model=BenchmarkRunOut)
async def run_benchmarks(include_live_models: bool = False, db: Session = Depends(get_db)):
    res = await run_evaluation_suite(db, include_live_models=include_live_models)
    db.commit()
    return res
