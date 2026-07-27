"""Weight roll-up verification."""

from typing import Dict, Any, List, Optional
from chubby_checker.models.piece import Piece


def check_weight_rollup(
    categories: Dict[str, List[Piece]],
    summary_weights: Optional[Dict[str, float]] = None,
    tolerance_pct: float = 5.0,
) -> List[Dict[str, Any]]:
    """
    Compare summed piece weights to category totals from the Load Out / Index.
    Returns list of findings.
    """
    findings = []
    summary_weights = summary_weights or {}

    for cat, pieces in categories.items():
        calculated = 0.0
        missing_weight = 0
        for p in pieces:
            if p.weight is not None:
                calculated += p.weight * (p.quantity or 1)
            else:
                missing_weight += 1

        reported = summary_weights.get(cat)
        if reported is None:
            # try fuzzy match
            for k, v in summary_weights.items():
                if cat.lower() in k.lower() or k.lower() in cat.lower():
                    reported = v
                    break

        if reported is None or reported == 0:
            continue

        if calculated == 0 and missing_weight > 0:
            findings.append({
                "severity": "INFO",
                "category": cat,
                "message": f"Category '{cat}' has reported weight {reported:,.1f} lbs but no piece-level weights extracted.",
                "expected": reported,
                "actual": calculated,
            })
            continue

        if calculated > 0:
            diff_pct = abs(calculated - reported) / reported * 100.0
            if diff_pct > tolerance_pct:
                findings.append({
                    "severity": "WARNING",
                    "category": cat,
                    "message": f"Weight roll-up mismatch for '{cat}': pieces sum to {calculated:,.1f} lbs, index shows {reported:,.1f} lbs ({diff_pct:.1f}% difference).",
                    "expected": reported,
                    "actual": calculated,
                })

    return findings
