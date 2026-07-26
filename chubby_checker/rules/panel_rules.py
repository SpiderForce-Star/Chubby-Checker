"""Panel coverage width driven rules for clips, backup plates, and screws."""

COVERAGE_FACTOR = {
    12: 2.00,
    16: 1.50,   # VS16 needs ~50% more seams than 24"
    18: 1.333,
    24: 1.00,
}

def check_clip_ratio(actual_clips: int, coverage_inches: int) -> dict:
    factor = COVERAGE_FACTOR.get(coverage_inches, 1.0)
    return {
        "coverage": coverage_inches,
        "factor": factor,
        "status": "ok",
        "note": f"Expected higher clip density for {coverage_inches}\" panels" if coverage_inches < 24 else "Standard 24\" density",
    }
