"""Simulates the desktop app's flow against the bridge using stand-in objects (no Qt / pydantic needed)."""
from types import SimpleNamespace as NS
from apprentice_bridge import QuestionEngine, classify_summary, EngineConfig
from confidence import EventType as E

def obs(i, summary, evs, **kw): return NS(id=f"obs-{i}", summary=summary, evidence_ids=evs, **kw)
POLL = dict(input_idle_s=5, screen_stable_s=5, user_speaking=False, agent_speaking=False)

def test_classifier():
    c = classify_summary("The expert changed the cost center from 4711 OPEX to 0400 CAPEX on invoice 4471.")
    assert (c["type"], c["case_id"], c["field_name"], c["before"], c["after"]) == (E.FIELD_CHANGED, "inv-4471", "cost_center", "4711 OPEX", "0400 CAPEX")
    assert classify_summary("Invoice 4471 was put on hold pending approval")["type"] == E.CASE_HELD
    assert classify_summary("Opened the supplier's previous invoices history")["type"] == E.RECORD_OPENED
    assert classify_summary("Opened next invoice 4472")["type"] == E.NAVIGATION
    assert classify_summary("Undid the cost center change")["type"] == E.ACTION_REVERSED

def test_full_loop():
    en = QuestionEngine(); en.begin_capture()
    times = {"f1": 10.0, "f2": 20.0}
    en.on_observations([obs(1, "Expert changed the cost center from 4711 OPEX to 0400 CAPEX on invoice 4471", ["f1"])], 12, times)
    # typing -> waits; idle alone (no boundary, no Ready) -> still waits
    assert en.poll(13, input_idle_s=0.5, screen_stable_s=5, user_speaking=False, agent_speaking=False) is None
    assert en.poll(30, **POLL) is None
    # expert moves to the next invoice = completed-step boundary -> Q01, linked to the screen frame
    en.on_observations([obs(2, "Opened next invoice 4472", ["f2"])], 22, times)
    plan = en.poll(40, **POLL)
    assert plan.question_id == "Q01" and plan.evidence_ids == ["f1"], en.trace
    # voice answer -> follow-ups are queued for debrief (no cutoff invented)
    en.on_note("Equipment over 5000 is always capex.", 45, "note-1", answering=True)
    assert en.poll(100, **POLL) is None                                  # general_rule etc. are debrief-only
    en.begin_debrief(120)
    asked = []
    for t in range(200, 3000, 20):
        p = en.poll(t, **POLL)
        if not p: break
        assert p.text.startswith("Going back to inv-4471")
        asked.append(p.question_id)
        en.on_note("Only for purchases; the controller decides.", t + 5, f"note-{t}", answering=True)
    assert len(asked) >= 3 and en.status()["debrief"]["followups_done"] >= 3, (asked, en.trace)
    assert "Q08" in asked                                                  # exact boundary asked with the expert's own cutoff

def test_defer_moves_to_debrief_and_pause_blocks():
    en = QuestionEngine(); en.begin_capture()
    en.on_observations([obs(1, "Changed the cost center from 4711 to 0400 on invoice 4471", ["f1"]),
                        obs(2, "Opened next invoice 4472", ["f2"])], 12, {"f1": 10, "f2": 11})
    assert en.poll(30, **POLL, paused=True) is None
    assert en.poll(30, **POLL).question_id == "Q01"
    en.on_defer()
    assert en.poll(200, **POLL, ) is None                                 # not re-asked live
    en.begin_debrief(300)
    asked = []
    for t in range(400, 2000, 10):
        p = en.poll(t, **POLL)
        if not p: break
        asked.append(p.question_id); en.on_note("Fine.", t + 1, f"n{t}", answering=True)
    assert "Q01" in asked                                                # deferred question returns in debrief

def test_revoke_and_sync():
    en = QuestionEngine(); en.begin_capture()
    en.on_observations([obs(1, "Changed the cost center from 4711 to 0400 on invoice 4471", ["f1"]),
                        obs(2, "Opened next invoice 4472", ["f2"])], 12, {"f1": 10, "f2": 11})
    hit = en.revoke_evidence("f1")
    assert hit and en.poll(30, **POLL) is None

    en = QuestionEngine(); en.begin_capture()
    en.on_observations([obs(1, "Changed the cost center from 4711 to 0400 on invoice 4471", ["f1"]),
                        obs(2, "Opened next invoice 4472", ["f2"])], 12, {"f1": 10, "f2": 11})
    k_inferred = NS(id="k1", title="Equipment is capex", reason="Because it is equipment", guardrail="", exception="",
                    escalation="", rule="", evidence_ids=["f1"], status="inferred")
    en.sync_knowledge([k_inferred], [NS(id="f1", kind="screen")])
    assert en.poll(30, **POLL).question_id == "Q01"                       # model inference does not close the gap
    en2 = QuestionEngine(); en2.begin_capture()
    en2.on_observations([obs(1, "Changed the cost center from 4711 to 0400 on invoice 4471", ["f1"]),
                         obs(2, "Opened next invoice 4472", ["f2"])], 12, {"f1": 10, "f2": 11})
    k_conf = NS(**{**k_inferred.__dict__, "status": "verified"})
    en2.sync_knowledge([k_conf], [NS(id="f1", kind="screen")])
    assert en2.poll(30, **POLL) is None                                   # confirmed by the expert: no question

def test_batched_latency_not_stale():
    en = QuestionEngine(); en.begin_capture()
    en.on_observations([obs(1, "Changed the cost center from 4711 to 0400 on invoice 4471", ["f1"]),
                        obs(2, "Opened next invoice 4472", ["f2"])], 18, {"f1": 10, "f2": 11})   # 8s analysis latency
    assert en.poll(40, **POLL) is not None

def test_intervention():
    en = QuestionEngine()
    k = NS(id="k9", guardrail="No asset number, no capex booking.", rule="", reason="Capex needs an asset record.", evidence_ids=["f1"])
    p = en.intervention(k)
    assert p.critical and p.text == "Pause here. The expert required No asset number, no capex booking because Capex needs an asset record. What needs to change?"
