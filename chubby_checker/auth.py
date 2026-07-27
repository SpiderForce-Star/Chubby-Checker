"""
Simple internal access control for Ascent Shipper Checker.

Password is intentional for internal Ascent Buildings use only.
This is NOT cryptographic security — anyone with the source can read it.
For internal licensing / casual access control only.
"""

import os
import getpass
from typing import Optional

# Official product name
PRODUCT_NAME = "Ascent Shipper Checker"
CODENAME = "Chubby Checker"

# Internal access code (Ascent Buildings)
ACCESS_CODE = "Twist"

# Allow override via environment for automation / CI
ENV_ACCESS_VAR = "ASCENT_SHIPPER_CHECKER_CODE"


def check_access(provided: Optional[str] = None, interactive: bool = True) -> bool:
    """
    Verify access code.

    Order of precedence:
      1. Explicit `provided` argument
      2. Environment variable ASCENT_SHIPPER_CHECKER_CODE
      3. Interactive prompt (if interactive=True)
    """
    if provided is not None:
        return provided.strip() == ACCESS_CODE

    env_val = os.environ.get(ENV_ACCESS_VAR)
    if env_val is not None:
        return env_val.strip() == ACCESS_CODE

    if not interactive:
        return False

    try:
        entered = getpass.getpass(f"{PRODUCT_NAME} access code: ")
        return entered.strip() == ACCESS_CODE
    except (KeyboardInterrupt, EOFError):
        return False


def require_access(provided: Optional[str] = None) -> None:
    """Raise SystemExit if access is denied."""
    if not check_access(provided=provided, interactive=True):
        raise SystemExit(
            f"\nAccess denied. {PRODUCT_NAME} is licensed for internal Ascent Buildings use.\n"
        )
