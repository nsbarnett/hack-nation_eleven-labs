"""Explicitly fictional offline fixture; never used as a live AI fallback."""

from apprentice.domain import Condition, Evidence, Knowledge, Message, Observation, RuleCheck, Session


def create_demo() -> Session:
    s = Session(title="Equipment purchase review", context="Fictional training policy. Learn classification and the asset-number guardrail.", mode="demo", phase="review", duration=195)
    statements = [
        ("Open the invoice", "Opened invoice INV-4471: equipment, EUR 7,200, known supplier.", 15),
        ("Choose a classification", "For equipment in EUR, amounts strictly above 5,000 use CAPEX. Positive amounts at or below 5,000 use OPEX, including exactly 5,000. Other purchase types and currencies need separate guidance.", 72),
        ("Check the asset number", "When category is CAPEX, an asset number is required. If it is missing, hold the invoice and ask the controller; never invent an asset number.", 126),
        ("Check the supplier", "An unknown supplier must be reviewed by the controller before proceeding. This demonstration does not establish all supplier approval rules.", 180),
    ]
    for title, text, timestamp in statements:
        e = Evidence(kind="demo", text=text, timestamp=timestamp)
        s.evidence.append(e)
        s.observations.append(Observation(summary=title, evidence_ids=[e.id]))
    e0, e1, e2, e3 = s.evidence
    s.knowledge = [
        Knowledge(title="Classify equipment above EUR 5,000", action="Review amount and purchase type", decision="Choose CAPEX", reason="The fictional expert uses a strict equipment capitalization threshold.", rule="For equipment in EUR, amount > 5,000 requires CAPEX.", exception="Exactly EUR 5,000 uses OPEX. Other currencies or purchase types are not established.", guardrail="Do not generalize this rule beyond EUR equipment purchases.", escalation="Ask an expert for another purchase type or currency.", evidence_ids=[e0.id, e1.id], check=RuleCheck(conditions=[Condition(field="purchase_type", operator="eq", value="equipment"), Condition(field="currency", operator="eq", value="EUR"), Condition(field="amount", operator="gt", value="5000")], field="category", operator="eq", value="CAPEX")),
        Knowledge(title="Classify equipment up to EUR 5,000", action="Check the threshold boundary", decision="Choose OPEX", reason="The fictional expert explicitly clarified the threshold boundary.", rule="For equipment in EUR, amount <= 5,000 requires OPEX.", exception="Other currencies and purchase types are outside this rule.", guardrail="Check currency before applying the threshold.", escalation="Ask the expert when the case differs.", evidence_ids=[e1.id], check=RuleCheck(conditions=[Condition(field="purchase_type", operator="eq", value="equipment"), Condition(field="currency", operator="eq", value="EUR"), Condition(field="amount", operator="lte", value="5000")], field="category", operator="eq", value="OPEX")),
        Knowledge(title="Require an asset number for CAPEX", action="Inspect the asset reference before saving", decision="Hold when missing", reason="A CAPEX entry must identify its asset.", rule="If category is CAPEX, asset_number must be present.", exception="No exception was established.", guardrail="Do not save CAPEX without an asset number.", escalation="Ask the controller for the correct asset number.", evidence_ids=[e2.id], check=RuleCheck(conditions=[Condition(field="category", operator="eq", value="CAPEX")], field="asset_number", operator="present", value="")),
        Knowledge(title="Escalate an unknown supplier", action="Check supplier status", decision="Use the review path", reason="Supplier identity must be reviewed before proceeding.", rule="Supplier status must be known before this training case can be saved.", exception="Detailed supplier approval criteria are not established.", guardrail="Hold when the supplier is unknown.", escalation="Contact the controller.", evidence_ids=[e3.id], check=RuleCheck(conditions=[], field="supplier_status", operator="eq", value="known")),
    ]
    s.messages.append(Message(role="assistant", text="Offline demonstration: all evidence here is a fictional fixture. Review each draft rule, inspect its evidence, and confirm the map. Then try the EUR 7,200 case in Teach with OPEX selected and no asset number.", evidence_ids=[e.id for e in s.evidence]))
    return s
