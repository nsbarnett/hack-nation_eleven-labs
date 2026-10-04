"""Practice scenarios cite confirmed knowledge; attempts never become expert facts."""
from pydantic import Field
from apprentice.domain import Contract, TutorResult
from apprentice.rules import evaluate


class CaseValue(Contract):
    field: str
    value: str


class Exercise(Contract):
    question: str
    knowledge_ids: list[str]
    scenario: list[CaseValue] = Field(default_factory=list)
    answer_fields: list[str] = Field(default_factory=list)


class Exercises(Contract):
    items: list[Exercise] = Field(max_length=5)


def generate(gateway, session):
    items = [k for k in session.knowledge if k.status == "verified"]
    if not session.confirmed or not items:
        raise ValueError("Confirm a Work Map before creating practice.")
    result = gateway.request(Exercises, "Create up to five clearly hypothetical practice questions "
        "using ONLY the confirmed knowledge. Do not invent policy, thresholds or missing rules. "
        "Cite supporting knowledge IDs for each question. Return no items if knowledge is insufficient. "
        "When cited items have check_verified=true and a structured check, prefer a structured exercise: "
        "supply hypothetical scenario field/value pairs and answer_fields for the learner to fill. "
        "Use only fields from those checks. Do not put answer_fields in scenario. Include all condition "
        "inputs needed to decide the case. Include exact threshold boundary cases when supported. "
        "Otherwise leave scenario and answer_fields empty for advisory free-text practice.",
        {"knowledge": [k.model_dump() for k in items]})
    allowed = {k.id for k in items}
    for item in result.items:
        if not item.knowledge_ids or not set(item.knowledge_ids) <= allowed:
            raise ValueError("Practice referenced unsupported knowledge.")
        if item.answer_fields:
            cited = [k for k in items if k.id in item.knowledge_ids]
            if not all(k.check and k.check_verified for k in cited):
                raise ValueError("Structured practice requires explicitly reviewed executable checks.")
            inputs = {c.field for k in cited for c in k.check.conditions}
            outputs = {k.check.field for k in cited}
            fields = [v.field for v in item.scenario]
            if (len(set(fields)) != len(fields) or len(set(item.answer_fields)) != len(item.answer_fields)
                    or not set(fields) <= inputs | outputs or not set(item.answer_fields) <= outputs
                    or set(fields) & set(item.answer_fields)
                    or not inputs <= set(fields) | set(item.answer_fields)):
                raise ValueError("Practice scenario does not match its verified rule fields.")
        elif item.scenario:
            raise ValueError("A structured scenario needs explicit learner answer fields.")
    return result.model_dump()


def evaluate_exercise(session, item, values):
    """Immutable scenario + explicit learner inputs; no model can award a structured pass."""
    if not session.confirmed:
        raise ValueError("Confirm the Work Map before evaluating practice.")
    expected = set(item.get("answer_fields", []))
    if not expected or not isinstance(values, dict) or not set(values) <= expected:
        raise ValueError("Answer only the fields requested by this exercise.")
    if any(v is not None and (not isinstance(v, str) or len(v) > 1000) for v in values.values()):
        raise ValueError("Structured answers must be short text values.")
    items = [k for k in session.knowledge if k.status == "verified" and k.check_verified and k.check]
    if not set(item["knowledge_ids"]) <= {k.id for k in items}:
        raise ValueError("The exercise's reviewed checks changed. Generate practice again.")
    if not expected <= values.keys() or any(value == "" or (isinstance(value, str) and not value.strip()) for value in values.values()):
        return TutorResult(verdict="unknown", explanation="Complete each requested decision field before evaluation.",
                           knowledge_ids=[], evaluation_method="verified_rules")
    case = {v["field"]: v["value"] for v in item.get("scenario", [])}
    case.update({key: value.strip() if value is not None else None for key, value in values.items()})
    relevant = [k for k in items if k.id in item["knowledge_ids"] or k.check.field in expected]
    result = evaluate(relevant, case, required_fields=expected)
    result.evaluation_method = "verified_rules"
    return result
