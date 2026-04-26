from src.core.atomic_fact import AtomicFact
from src.core.enums import FactStatus
from src.core.fact_validation import FactValidationResult


def compute_score(
    validations: list[FactValidationResult], facts: list[AtomicFact]
) -> float:
    """
    Weighted average: Σ(accuracy × confidence × weight) / Σ(weight) × 100

    accuracy:  Found=1.0, Partial=0.5, Missing/Contradicted=0.0
    confidence: 0.0–1.0 from the LLM (only used for Found/Partial)
    For Missing/Contradicted, confidence is ignored because accuracy=0 ⇒ product=0.
    """
    fact_map = {f.id: f for f in facts}
    total_weight = 0.0
    weighted_confident_accuracy = 0.0

    for v in validations:
        fact = fact_map.get(v.atomic_fact_id)
        if not fact:
            continue

        weight = fact.rank.to_rank()
        total_weight += weight

        # Determine base accuracy from status
        if v.status == FactStatus.FOUND:
            accuracy = 1.0
        elif v.status == FactStatus.PARTIAL:
            accuracy = 0.5
        else:
            accuracy = 0.0

        # Multiply by confidence (confidence only matters when accuracy > 0)
        # For missing/contradicted, product is 0 regardless of confidence.
        confident_accuracy = accuracy * v.confidence

        weighted_confident_accuracy += weight * confident_accuracy

    return (
        (weighted_confident_accuracy / total_weight * 100) if total_weight > 0 else 0.0
    )
