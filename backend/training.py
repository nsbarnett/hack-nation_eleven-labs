"""Practice scenarios cite confirmed knowledge; attempts never become expert facts."""
from pydantic import Field
from apprentice.domain import Contract


class Exercise(Contract):
    question: str
    knowledge_ids: list[str]


class Exercises(Contract):
    items: list[Exercise] = Field(max_length=5)


def generate(gateway, session):
    items = [k for k in session.knowledge if k.status == "verified"]
    if not session.confirmed or not items:
        raise ValueError("Confirm a Work Map before creating practice.")
    result = gateway.request(Exercises, "Create up to five clearly hypothetical practice questions "
        "using ONLY the confirmed knowledge. Do not invent policy, thresholds or missing rules. "
        "Cite supporting knowledge IDs for each question. Return no items if knowledge is insufficient.",
        {"knowledge": [k.model_dump() for k in items]})
    allowed = {k.id for k in items}
    for item in result.items:
        if not item.knowledge_ids or not set(item.knowledge_ids) <= allowed:
            raise ValueError("Practice referenced unsupported knowledge.")
    return result.model_dump()
