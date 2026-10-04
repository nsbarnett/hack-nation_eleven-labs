"""Replay policy fixtures without providers; this does not measure model accuracy."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from apprentice import evaluation as ev
from apprentice.demo import create_demo
from apprentice.domain import AssessmentResult, Evidence, EvidenceQuote, FieldAssessment, Session
from backend.training import evaluate_exercise


def replay(case):
    if case["kind"] == "gap":
        source = Evidence(kind="note", text=case["text"])
        session = Session(title="Synthetic replay", evidence=[source])
        ev.refresh(session)
        decision = session.evaluation.decisions[0]
        gap = ev.ensure_gap(session, decision.id, case.get("field", "reason"), [source.id])
        assessment = FieldAssessment(decision_id=decision.id, field=gap.field,
            outcome=case["outcome"], claim=case["text"], confidence=case["confidence"],
            citations=[EvidenceQuote(evidence_id=source.id, quote=source.text)], rationale="Recorded synthetic proposal")
        ev.apply_assessment(session, AssessmentResult(assessments=[assessment], gaps=[]), [source.id])
        return gap.status
    session = create_demo()
    session.confirmed = True
    for item in session.knowledge:
        item.status, item.check_verified = "verified", True
    exercise = {"knowledge_ids": [k.id for k in session.knowledge[:2]], "answer_fields": ["category"],
        "scenario": [{"field": "amount", "value": case["amount"]}, {"field": "currency", "value": case["currency"]},
                     {"field": "purchase_type", "value": "equipment"}]}
    return evaluate_exercise(session, exercise, {"category": case["answer"]}).verdict


def evaluate(corpus):
    results = [{"id": case["id"], "kind": case["kind"], "expected": case["expected"], "actual": replay(case)}
               for case in corpus["cases"]]
    closures = [r for r in results if r["kind"] == "gap" and r["expected"] in ev.OPEN]
    passes = [r for r in results if r["kind"] == "learner" and r["expected"] != "ok"]
    false_closures = sum(r["actual"] not in ev.OPEN for r in closures)
    unsafe_passes = sum(r["actual"] == "ok" for r in passes)
    return {"corpus_version": corpus["version"], "label_status": corpus["label_status"],
        "scope": "Deterministic policy replay; no live model calls or semantic accuracy claim",
        "parameters": asdict(ev.CONFIG), "cases": len(results),
        "agreement": sum(r["actual"] == r["expected"] for r in results),
        "false_gap_closures": {"count": false_closures, "eligible_cases": len(closures)},
        "unsafe_learner_passes": {"count": unsafe_passes, "eligible_cases": len(passes)}, "results": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = evaluate(json.loads(args.corpus.read_text(encoding="utf-8")))
    payload = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    raise SystemExit(0 if report["agreement"] == report["cases"] else 1)
