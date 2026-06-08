"""Audit scoring."""

from __future__ import annotations

from src.domain import AtomicFact, FactStatus, FactValidationResult


def compute_score(
    validations: list[FactValidationResult], facts: list[AtomicFact]
) -> float:
    """Return weighted score in the range 0-100."""
    fact_map = {fact.id: fact for fact in facts}
    total_weight = 0.0
    weighted_confident_accuracy = 0.0

    for validation in validations:
        fact = fact_map.get(validation.atomic_fact_id)
        if not fact:
            continue

        weight = fact.rank.to_rank()
        total_weight += weight

        if validation.status == FactStatus.FOUND:
            accuracy = 1.0
        elif validation.status == FactStatus.PARTIAL:
            accuracy = 0.5
        else:
            accuracy = 0.0

        weighted_confident_accuracy += weight * accuracy * validation.confidence

    return (
        (weighted_confident_accuracy / total_weight * 100) if total_weight > 0 else 0.0
    )
