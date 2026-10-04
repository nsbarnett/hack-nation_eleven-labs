"""Smallest tests that verify the spec's acceptance behaviors (timing, provenance, suppression, revocation)."""
from confidence import Readiness, ScreenEvent, EventType as E, FieldStatus
from question_controller import QuestionController, Action, SessionState


def ev(i, ts, typ, case="inv-4471", dec="inv-4471:cost_center", **kw):
    kw.setdefault("vision_confidence", 0.9)
    return ScreenEvent(f"evt-{i}", ts, typ, case, dec, **kw)

def ready(**kw):  # a safe moment: boundary, quiet, telemetry available
    d = dict(typing_active=False, screen_quiet_s=4, step_boundary=True)
    d.update(kw); return Readiness(**d)

def ctl():
    c = QuestionController(); c.start_capture(); return c

def changed(c, ts=10):
    c.on_event(ev(1, ts, E.FIELD_CHANGED, field_name="cost_center", before="4711", after="0400", was_default=True))


def test_typing_keeps_question_queued():
    c = ctl(); changed(c)
    d = c.decide(20, ready(typing_active=True))
    assert d.action == Action.QUEUE and "typing_active" in d.blockers
    assert c.decide(21, ready()).action == Action.ASK_NOW      # same question, later, at a safe moment

def test_default_change_asks_q01_at_boundary():
    c = ctl(); changed(c)
    d = c.decide(20, ready())
    assert d.question_id == "Q01" and d.text == "What made you change that classification?"

def test_silence_alone_never_asks():
    c = ctl(); changed(c)
    assert c.decide(30, Readiness(typing_active=False, screen_quiet_s=30)).action == Action.QUEUE  # no boundary/Ready
    assert c.decide(30, Readiness(typing_active=None, screen_quiet_s=30, step_boundary=True)).action == Action.QUEUE  # no telemetry
    assert c.decide(30, Readiness(typing_active=None, explicit_ready=True)).action == Action.ASK_NOW

def test_reading_motionless_record_no_question():
    c = ctl(); c.on_event(ev(1, 5, E.IDLE, dec=None))
    assert c.decide(60, ready()).action == Action.SUPPRESS

def test_unprompted_reason_cancels_candidate():
    c = ctl(); changed(c)
    c.on_utterance(12, "Equipment over 5000 is always capex because it gets depreciated.")
    d = c.decide(30, ready())
    assert d.action == Action.SUPPRESS
    assert any("CANCEL Q01" in m for m in c.log)

def test_screen_already_answers_it_is_rejected():
    c = ctl()
    c.on_event(ev(1, 5, E.CASE_HELD, field_name="status", answered_on_screen=frozenset({"guardrail"})))
    assert not any(x.spec.id == "Q15" for x in c.candidates.values())     # banner already states the requirement
    assert any(x.spec.id == "Q13" for x in c.candidates.values())          # risk is still unknown

def test_hold_prioritises_guardrail_over_reason():
    c = ctl(); changed(c)
    c.on_event(ev(2, 12, E.CASE_HELD, dec="inv-4471:status", field_name="status"))
    assert c.decide(60, ready()).question_id == "Q15"                       # rank 0 beats rank 2

def test_cooldown_and_budget():
    c = ctl(); changed(c)
    d = c.decide(20, ready()); c.on_answer(d.candidate_id, 25, "Because it is equipment.")
    c.on_event(ev(2, 26, E.RECORD_OPENED, dec="inv-4471:history", field_name="history"))
    assert "cooldown" in c.decide(40, ready()).blockers[0]                  # 45s cooldown
    assert c.decide(70, ready(explicit_ready=True)).action == Action.ASK_NOW

def test_low_confidence_vision_is_not_asked_live():
    c = ctl()
    c.on_event(ev(1, 5, E.FIELD_CHANGED, field_name="cost_center", was_default=True, after_readable=False, vision_confidence=0.9))
    assert not c.candidates and c.rejected

def test_stale_vision_holds_decision():
    c = ctl()
    c.on_event(ev(1, 10, E.FIELD_CHANGED, field_name="cost_center", was_default=True, frame_ts=2.0))
    assert not c.candidates

def test_case_switch_keeps_candidate_but_anchors_it():
    c = ctl(); changed(c)
    c.on_event(ev(2, 15, E.NAVIGATION, case="inv-4472", dec=None))      # expert moved on = step boundary
    d = c.decide(20, ready())
    assert d.question_id == "Q01" and d.anchor == "Going back to inv-4471 (cost_center):"   # no ambiguity about the case

def test_live_candidate_expires_by_age_and_debrief_reasks():
    c = ctl(); changed(c, ts=10)
    assert c.decide(500, ready(explicit_ready=True)).action == Action.SUPPRESS
    assert any("EXPIRE Q01" in m for m in c.log)
    c.on_finish(600)
    asked = []
    for t in range(700, 1500, 10):
        d = c.decide(t, Readiness())
        if d.action != Action.ASK_NOW: break
        asked.append(d.question_id); c.on_answer(d.candidate_id, t + 1, "Fine.")
    assert "Q01" in asked                      # spec priority puts boundary questions (Q10) ahead of the reason question

def test_qualified_answer_defers_q06_to_debrief_and_q08_needs_cutoff():
    c = ctl(); changed(c)
    d = c.decide(20, ready())
    c.on_answer(d.candidate_id, 25, "Usually it is capex if the amount is over 5,000.")
    ids = {x.spec.id for x in c.candidates.values()}
    assert "Q06" in ids and "Q08" in ids                                    # boundary + exact-operator gaps
    q08 = next(x for x in c.candidates.values() if x.spec.id == "Q08")
    assert "5,000" in q08.text                                              # cutoff came from expert's own words

def test_q08_never_invents_cutoff():
    c = ctl(); changed(c)
    c.set_flag("inv-4471:cost_center", "operator_unclear", 12)              # no cutoff slot supplied
    assert not any(x.spec.id == "Q08" for x in c.candidates.values())

def test_debrief_flow_and_completion():
    c = ctl(); changed(c)
    c.on_event(ev(2, 12, E.CASE_HELD, dec="inv-4471:status", field_name="status"))
    c.on_utterance(13, "We always hold that supplier in December, it double-bills.", decision_id="inv-4471:status")
    c.on_finish(100)
    assert c.state == SessionState.DEBRIEF
    asked = []
    for t in range(200, 2000, 10):
        d = c.decide(t, Readiness(typing_active=False))
        if d.action != Action.ASK_NOW: break
        assert d.anchor and d.anchor.startswith("Going back to")            # debrief re-anchors to the screen moment
        asked.append(d.question_id)
        c.on_answer(d.candidate_id, t + 5, "Only for this supplier; the controller decides.")
    assert len(asked) >= 3
    assert asked[0] in ("Q15", "Q17", "Q16", "Q18", "Q25")                   # guardrail-class first

def test_off_record_revokes():
    c = ctl(); changed(c)
    hit = c.revoke(event_ids=["evt-1"])
    assert hit and c.decide(30, ready()).action == Action.SUPPRESS
    assert c.decide(30, ready(off_record=True)).action == Action.SUPPRESS

def test_guardrail_intervention_overrides_timing():
    c = ctl(); c.start_teach()
    d = c.guardrail_intervention(Readiness(user_speaking=True, typing_active=True), "Sabine",
                                 "an asset number before capex booking", "no asset number means no capex booking", "rule-04")
    assert d.action == Action.ASK_NOW and d.critical
    assert c.guardrail_intervention(Readiness(paused=True), "Sabine", "x", "y", "r").action == Action.SUPPRESS

def test_tutor_q26_and_verify_q23():
    c = ctl(); changed(c); c.on_finish(50); c.enter_verify([{"decision_id": "inv-4471:cost_center", "scope": "equipment over EUR 5,000"}])
    d = c.decide(60, Readiness())
    assert d.question_id == "Q23" and "equipment over EUR 5,000" in d.text
    c.on_answer(d.candidate_id, 70, "yes"); c.confirm_map(); c.start_teach()
    c.on_event(ev(9, 80, E.NOVICE_DECISION_POINT, case="inv-9001", dec="inv-9001:cost_center", field_name="cost_center"))
    assert c.decide(90, Readiness()).question_id == "Q26"

def test_q23_verify_needs_scope_slot():
    c = ctl(); changed(c); c.state = SessionState.VERIFY
    c.set_flag("inv-4471:cost_center", "map_condition_ready", 1)
    assert not any(x.spec.id == "Q23" for x in c.candidates.values())       # no scope -> no generic 'Yes' question
