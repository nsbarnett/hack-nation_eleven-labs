"""Deterministic pre-save checks for structured cases. Never execute AI code."""

from decimal import Decimal, InvalidOperation
from typing import Any

from apprentice.domain import Condition, Knowledge, TutorResult


def compare(value: Any, operator: str, expected: str) -> bool | None:
    if operator == "present":
        return value is not None and str(value).strip() != ""
    if operator == "absent":
        return value is None or str(value).strip() == ""
    if value is None:
        return None
    if operator in ("eq", "ne"):
        equal = str(value).strip().casefold() == expected.strip().casefold()
        return equal if operator == "eq" else not equal
    try:
        a, b = Decimal(str(value)), Decimal(expected)
        if not a.is_finite() or not b.is_finite():
            return None
        return {"gt": a > b, "gte": a >= b, "lt": a < b, "lte": a <= b}[operator]
    except (InvalidOperation, KeyError):
        return None


def evaluate(items: list[Knowledge], case: dict, required_fields: set[str] | None = None) -> TutorResult:
    applicable, failures, incomplete = [], [], []
    covered = set()
    for item in items:
        if item.status != "verified" or item.check is None:
            continue
        check = item.check
        tests = [compare(case.get(c.field), c.operator, c.value) for c in check.conditions]
        if False in tests:
            continue
        if None in tests:
            incomplete.append(item.id)
            continue
        applicable.append(item.id)
        covered.add(check.field)
        outcome = compare(case.get(check.field), check.operator, check.value)
        if outcome is None:
            incomplete.append(item.id)
        elif not outcome:
            failures.append(item)
    if failures:
        return TutorResult(verdict="warn", explanation="\n\n".join(
            f"{i.title}: {i.rule}\nWhy: {i.reason}\nGuardrail: {i.guardrail}" for i in failures
        ), knowledge_ids=[i.id for i in failures])
    if incomplete or not applicable or not (required_fields or set()).issubset(covered):
        return TutorResult(verdict="unknown", explanation="The verified map does not cover this case completely. Ask an expert before proceeding.", knowledge_ids=incomplete)
    return TutorResult(verdict="ok", explanation="This case passes the applicable structured checks in the verified Work Map. This is limited to those checks.", knowledge_ids=applicable)
