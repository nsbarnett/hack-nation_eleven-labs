# Knowledge and learner evaluation

Implemented in `apprentice/evaluation.py`, `apprentice/agents/assessor.py`, the
session contracts in `apprentice/domain.py`, and the backend service. This is the
production adaptation of the ideas in `EvalTest`; the original sandbox remains
separate so its tests and behavior can still be compared.

## Authority and data flow

1. Capture remains local. The browser analyzes only approved, rendered frames.
2. The observer reports structured visible events, not questions or inferred intent.
3. The evaluator creates persistent decisions and applicable knowledge gaps.
4. The semantic assessor proposes field assessments with exact expert-text quotes.
5. Deterministic validation accepts or rejects the proposal and recomputes gap state.
6. The question selector picks one unresolved gap; specific fields use fixed wording.
7. An expert reviews the map and separately reviews executable predicates.
8. Structured learner answers are evaluated by verified predicates. Free-text
   explanations receive explicitly labeled AI advisory feedback.

Models cannot set verification authority. No single numerical score represents
the probability that a workflow is correct or safe. The dimensions below are
independent, inspectable signals.

## Dimensions and parameters

| Dimension | Inputs and interpretation | Decision and limits |
| --- | --- | --- |
| Observation quality | Visible event type, case/field, before/after readability, model-reported confidence. Text decisions do not receive a visual confidence score. | A visible event is usable at confidence **>= 0.50**. Unreadable field changes/reversals are capped at **0.35**. Uncertain events require clarification and cannot trigger live questions. Confidence measures the screen interpretation, not correctness of the expert's rule. |
| Answer sufficiency | Exact quoted expert text, explicit decision/field, proposed claim, assessment outcome and confidence. | `sufficient` requires confidence **>= 0.80**, non-placeholder content, and no uncertainty/acknowledgement guard. Qualified rules, scopes, thresholds and operators remain partial. This is a conservative acceptance threshold, not a calibrated accuracy claim. |
| Rule completeness | Applicable gaps: reason, rule, scope, threshold, operator, exception, guardrail, escalation, contradiction and cue. | Open, partial and disputed gaps remain unresolved. New gaps need retained evidence. A populated string such as `Not established` is not knowledge. Debrief completion requires at least one decision, no unresolved gaps and no unassessed expert text; it has **no minimum question count**. |
| Consistency | New assessments, prior claims, current map and explicit expert clarifications. | Differing sufficient claim strings for the same decision/field conservatively produce a dispute. Applicable executable checks with incompatible consequences produce `unknown`. Paraphrases may need review; matching strings do not prove semantic equivalence or consistency. |
| Expert verification | Explicit map review or a recorded gap clarification. Executable checks require a separate checkbox. | AI-produced assessments can reach `expert_stated`, never `verified`. Proposed inapplicability remains partial until the expert reviews it. Text edits clear executable checks and their verification. |
| Learner correctness | Immutable exercise scenario, explicit learner decision fields, applicable verified and separately reviewed checks. | Structured outcomes are `ok`, `warn`, or `unknown`, with method `verified_rules`. Missing/invalid/uncovered/conflicting input cannot pass. Written reasoning uses method `advisory`; it is not a structured rule pass. |

All initial thresholds are **engineering defaults awaiting calibration**, not
empirically validated confidence probabilities. `EvaluationConfig` is the single
source of numerical policy values; the API evaluation report includes its values.

### Question selection parameters

| Parameter | Default | Meaning |
| --- | --- | --- |
| Priority 0 | Guardrail, escalation, contradiction | Ask about critical constraints and conflicting guidance first. |
| Priority 1 | Threshold, exact operator, exception, scope | Establish applicability and boundaries. |
| Priority 2 | Reason, rule | Establish the decision and its explanation. |
| Priority 3 | Cue | Clarify diagnostic signals. |
| Tie breaking | Fewer prior attempts, clearer evidence, creation order | Rotate among equally important unresolved gaps instead of repeatedly asking one unanswered question. |
| Active questions | 1 | Requesting another debrief does not overwrite an unanswered question. |
| Live invitation | Explicit Ready | Silence and a motionless screen are not treated as permission. The browser uses post-review debrief, not live uploads. |
| Live cooldown | 45 session seconds | Applies between live questions. |
| Live budget | 5 per rolling 600 session seconds | Separate from provider quotas and debrief questions. |
| Live evidence age | 120 session seconds | Older live questions wait for retrospective debrief. |
| Trace retention | 100 entries; latest 30 in summary | Decision trace is stored with the session and cleared on privacy/deletion invalidation. |

The 0.55 blended score and mandatory three-follow-up completion rule from the
sandbox are intentionally not used. Ten field-focused templates replace the
invoice-oriented 26-question sandbox library. A constrained interviewer can
contextualize broad `rule` gaps; it receives the selected gap, and citations must
belong to that gap. Empty, overlong or multi-question output falls back to the
fixed template. Semantic wording quality still requires evaluation: source-ID
and syntax validation alone cannot prove a question is relevant or non-leading.

## Gap transitions and evaluation decisions

| State | Meaning | How it is reached |
| --- | --- | --- |
| `open` | Not established | Initial gap; uncertain answer; missing supporting evidence. |
| `partial` | Some explanation or a proposed applicability boundary remains incomplete | Low-confidence/qualified assessment or proposed `not_applicable`. |
| `observed` | Reliable visible event already states this field | Observer explicitly reports the field as answered on screen; not expert verification. |
| `expert_stated` | Supported explicit expert explanation | Validated sufficient assessment with exact quotes. |
| `disputed` | Contradictory guidance needs review | Contradictory assessment, differing sufficient claims, conflicting map status/values. |
| `verified` | Explicitly reviewed expert knowledge | Current verified map field or recorded expert gap review. |
| `not_applicable` | Expert explicitly excluded the field for this decision | Recorded expert applicability review. |

An ordinary answer is saved before assessment and does not itself close a gap.
`I don't know`, `I'm not sure`, `Fine`, and `Yes` cannot become sufficient through
a high model score. Regex guards are deliberately narrow safeguards, not a full
language understanding system. The assessor handles other phrasing; replay and
human-reviewed evaluation must cover it.

An answer is bound to the question's gap and decision. Assigning it to another
decision is rejected. Unprompted notes retain their own source decision and can
be assessed against existing supplied decisions without guessing the last event.
Repeated observations with the same visible case and field share a decision.
Without reliable identifiers, events remain separate instead of guessing a merge.

Deleting a supporting answer removes its assessments and reviews. Rejecting map
knowledge removes its verification contribution. A later assessment supersedes
an older gap review when it brings new evidence; unresolved disputes cannot be
silently cleared by simply marking a map item verified. The expert can resolve
them in the evaluation panel with a new, explicitly recorded clarification.

### Concrete examples

| Evidence or action | Result |
| --- | --- |
| “I don't know who can approve this.” | Escalation remains open. |
| “Usually above 5,000 EUR.” | Threshold remains partial; exact equality and exceptions need clarification where applicable. |
| “Invoice 5000 was opened.” | A case identifier is not a threshold. Observer only reports the event. |
| “Because this is equipment.” | May establish a reason; does not automatically establish threshold, scope, exception or verification. |
| Two sufficient explanations give different claims for the same field | Disputed until reviewed; conservative false alarms are visible. |
| Frame captured at 10 seconds is reviewed after a 300-second recording | Valid historical evidence; no live staleness rejection. |
| Verified map item is rejected | Its verification contribution is removed on recomputation. |
| `amount > 5000` with amount exactly 5000 | This predicate does not apply; the exact-boundary rule must cover the case, otherwise `unknown`. |
| Learner omits a requested field or supplies NaN for a numeric condition | `unknown`; never a pass. |
| Two applicable reviewed checks require different values for the same field | `unknown`, with conflicting knowledge IDs. |

## Persistence, privacy and concurrency

`Session.evaluation` stores decisions, gaps, assessments, processed evidence IDs,
question attempts, explicit reviews and the trace. Existing saved sessions load
with an empty default evaluation state and are projected from retained evidence.
Active/deferred questions survive a normal save/reopen. Restarting does not
invent a new answer or erase the need for verification.

States are recomputed from retained evidence and current map reviews, rather than
incrementally marking fields known forever. Trainee evidence is excluded. Answers
whose source dependencies have been deleted/redacted are excluded from expert
context. Privacy reset/forget clears derived evaluation state alongside the map
and observations; source deletions cannot leave quotations in the evaluation log.

Assessment, map generation and contextual question generation each pass through
the hosted quota runner as a separate provider operation. Every pipeline stage
checks the service generation; a privacy/session change prevents later stages
and discards stale results. A failed assessment preserves evidence and leaves it
pending. No API keys or provider request bodies are placed in evaluation state.

Manual expert review of a map's cited evidence counts that evidence as reviewed.
New expert notes conservatively invalidate existing map verification and executable
checks; a scoped gap clarification invalidates the map items bound to that decision.
Rebuild and review the affected rules before grading with them again.
New uncited expert text remains pending. Map confirmation requires reviewed
retained items, valid sources, no relevant critical gaps/disputes, and no pending
expert evidence. Noncritical unknowns remain visible and limit what teaching can
claim; a confirmed map is not universal coverage.

## Executable rule review and learner evaluation

The Work Map review dialog shows the predicate fields/operators and asks the
expert to review the executable interpretation separately. The model cannot set
`check_verified`. Changing any substantive step text removes the check; rebuild
the map to regenerate it, then review again. Existing maps default to unreviewed
checks, so no historical predicate silently gains grading authority.

Structured practice generation must use reviewed checks, allowed fields, unique
scenario keys and distinct learner answer fields. The server keeps the scenario
immutable. It evaluates cited checks and other reviewed checks with the same
requested output fields, catching overlapping contradictory consequences.
Results apply only to the requested decision fields and applicable checks, not
the entire workflow or an external application. This application does not block
another application's Save action.

An omitted learner field is unanswered (`unknown`). The "No value" control sends
an explicit null, allowing reviewed `present`/`absent` checks to evaluate an
intentional missing value without treating a blank form as a completed answer.

Practice answers are stored as trainee evidence and never become expert rules.
Unstructured explanations remain useful, but their advisory verdict is kept
distinct from deterministic structured evaluation.

## Validation and measurement

Run the regression suites with:

```powershell
.\.venv\Scripts\python.exe -m pytest tests EvalTest -q
.\.venv\Scripts\python.exe tools/evaluate_logic.py tests/fixtures/evaluation_replays.json
```

The replay corpus is synthetic and versioned. It tests decision policy against
recorded assessment proposals; it is not a benchmark of a live model's semantic
accuracy, and its labels have not received independent human review. It reports:

- **False gap closures:** unresolved gold cases promoted to an established state.
- **Unsafe learner passes:** non-pass gold cases returned as `ok`.
- **State/verdict agreement:** exact match with the expected replay decision.

Release regression target: zero false closures or unsafe passes on this corpus.
This target does not imply zero errors in production. The unit/integration suite
also covers fabricated quotations, wrong decision bindings, deleted evidence,
map rejection/edit invalidation, restoration, cancellation and privacy boundaries.

Before tuning confidence thresholds or claiming model quality, add independently
reviewed real workflow cases with expected fields, applicability, contradictions,
acceptable questions and learner outcomes. Run observation and assessment models
on a held-out split, measure false closures, unsafe passes, missed useful gaps and
unnecessary questions, and inspect results by workflow type. Keep model version,
prompt version and configuration with each report. Use a second model only as
an auxiliary reviewer; it must not replace the expert-labeled reference decisions.

## Design decisions

| ID | Decision | Reason/tradeoff |
| --- | --- | --- |
| E01 | Independent dimensions, no overall confidence percentage | Populated fields and model certainty do not prove correctness. |
| E02 | Model extraction + deterministic authority | Language understanding is flexible; transitions and verification remain inspectable. |
| E03 | Exact expert-text citations and explicit answer bindings | Prevent fabricated references and accidental cross-decision closure; does not prove semantic entailment. |
| E04 | Recompute gap state from retained sources | Rejection, deletion and redaction must undo prior conclusions. |
| E05 | Historical evidence has no live expiry | Privacy review happens after recording; age alone must not discard useful evidence. |
| E06 | Applicability-based completion | Question counts are reporting metrics, not proof of learning. |
| E07 | Separate executable-check review | Correct prose does not guarantee a correctly compiled comparison operator. |
| E08 | Unknown on insufficient/conflicting structured input | Avoid false passes; uncovered cases remain explicit. |
| E09 | Explicit live invitation | Reliable user activity/speech telemetry is not available across all capture surfaces. |
| E10 | Preserve the sandbox independently | Production contracts and safeguards can evolve without claiming the original prototype is integrated unchanged. |
