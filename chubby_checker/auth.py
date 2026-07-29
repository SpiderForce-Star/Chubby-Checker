"""
Cryptographic license validation for Chubby Checker.

Design
------
- License key = base64url(JSON payload) + "." + base64url(HMAC-SHA256 signature)
- Signed with a master secret known only to Ascent license administrators
- Verified offline with the embedded verification secret (derived / same for internal use)
- Supports optional expiry, licensee name, and feature flags
- No phone-home / no external network calls

This is appropriate for internal Ascent Buildings licensing. It is NOT a DRM system
against determined attackers who possess the source and secret; it prevents casual
unauthorized use and provides an auditable license record.

Environment overrides (for CI / automation):
  ASCENT_SHIPPER_CHECKER_LICENSE   full license key string
  ASCENT_SHIPPER_CHECKER_LICENSE_FILE  path to a .lic file
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Product identity
# ---------------------------------------------------------------------------
PRODUCT_NAME = "Chubby Checker"
PRODUCT_ID = "chubby-checker"

# ---------------------------------------------------------------------------
# Signing secret
# ---------------------------------------------------------------------------
# INTERNAL USE ONLY. In a stricter deployment, move the *signing* secret out of
# the distributed package and keep only a verification key here.
# Rotate by issuing new licenses and updating this constant (or loading from
# a secure config path that is not in the public tree).
_LICENSE_SECRET = b"AscentBuildings-ShipperChecker-2026-HMAC-TwistRoot-v1"

# Legacy bootstrap still accepted for transition
_LEGACY_ACCESS_CODE = "Twist1960"


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def _sign_payload(payload_bytes: bytes) -> str:
    sig = hmac.new(_LICENSE_SECRET, payload_bytes, hashlib.sha256).digest()
    return _b64url_encode(sig)


def _verify_signature(payload_bytes: bytes, signature_b64: str) -> bool:
    expected = _sign_payload(payload_bytes)
    return hmac.compare_digest(expected, signature_b64)


@dataclass
class LicenseInfo:
    valid: bool
    product: str = ""
    licensee: str = ""
    issued: Optional[str] = None
    expires: Optional[str] = None
    features: List[str] = field(default_factory=list)
    message: str = ""
    raw_payload: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        if not self.expires:
            return False
        try:
            exp = datetime.fromisoformat(self.expires.replace("Z", "+00:00"))
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            return datetime.now(timezone.utc) > exp
        except Exception:
            return True


def create_license(
    licensee: str = "Ascent Buildings",
    expires: Optional[str] = None,
    features: Optional[List[str]] = None,
    issued: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Create a signed license key string.

    expires: ISO-8601 date/datetime string, or None for no expiry.
    """
    payload: Dict[str, Any] = {
        "product": PRODUCT_ID,
        "product_name": PRODUCT_NAME,
        "licensee": licensee,
        "issued": issued or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires": expires,
        "features": features or ["full"],
    }
    if extra:
        payload.update(extra)

    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    token = _b64url_encode(payload_bytes)
    signature = _sign_payload(payload_bytes)
    return f"{token}.{signature}"


def validate_license_key(license_key: str) -> LicenseInfo:
    """Validate a signed license key. Returns LicenseInfo."""
    if not license_key or not isinstance(license_key, str):
        return LicenseInfo(valid=False, message="No license key provided.")

    license_key = license_key.strip()

    # Legacy transitional path (simple access code)
    if license_key == _LEGACY_ACCESS_CODE:
        return LicenseInfo(
            valid=True,
            product=PRODUCT_ID,
            licensee="Ascent Buildings (legacy access code)",
            features=["full"],
            message="Accepted access code.",
        )

    if "." not in license_key:
        return LicenseInfo(valid=False, message="Malformed license key (missing signature).")

    try:
        token_b64, sig_b64 = license_key.rsplit(".", 1)
        payload_bytes = _b64url_decode(token_b64)
    except Exception:
        return LicenseInfo(valid=False, message="Malformed license key (base64 decode failed).")

    if not _verify_signature(payload_bytes, sig_b64):
        return LicenseInfo(valid=False, message="Invalid license signature.")

    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        return LicenseInfo(valid=False, message="Invalid license payload JSON.")

    product = payload.get("product") or payload.get("product_id") or ""
    if product not in (PRODUCT_ID, PRODUCT_NAME, "ascent-shipper-checker", "Ascent Shipper Checker"):
        return LicenseInfo(
            valid=False,
            message=f"License product mismatch: {product!r}",
            raw_payload=payload,
        )

    info = LicenseInfo(
        valid=True,
        product=product,
        licensee=str(payload.get("licensee", "")),
        issued=payload.get("issued"),
        expires=payload.get("expires"),
        features=list(payload.get("features") or []),
        raw_payload=payload,
        message="License valid.",
    )

    if info.is_expired:
        info.valid = False
        info.message = f"License expired on {info.expires}."

    return info


def load_license_from_file(path: str | Path) -> Optional[str]:
    p = Path(path)
    if not p.exists():
        return None
    text = p.read_text(encoding="utf-8").strip()
    # Allow files with comments / blank lines — first non-empty non-comment line
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line
    return text or None


def resolve_license_key(
    cli_key: Optional[str] = None,
    cli_file: Optional[str] = None,
) -> Optional[str]:
    """
    Resolve license key from (in order):
      1. CLI --license / --access-code value
      2. CLI --license-file
      3. ENV ASCENT_SHIPPER_CHECKER_LICENSE
      4. ENV ASCENT_SHIPPER_CHECKER_LICENSE_FILE
      5. Local default file ./ascent_shipper_checker.lic or ~/.ascent_shipper_checker.lic
    """
    if cli_key:
        return cli_key.strip()

    if cli_file:
        key = load_license_from_file(cli_file)
        if key:
            return key

    env_key = os.environ.get("ASCENT_SHIPPER_CHECKER_LICENSE")
    if env_key:
        return env_key.strip()

    env_file = os.environ.get("ASCENT_SHIPPER_CHECKER_LICENSE_FILE")
    if env_file:
        key = load_license_from_file(env_file)
        if key:
            return key

    for candidate in (
        Path.cwd() / "ascent_shipper_checker.lic",
        Path.home() / ".ascent_shipper_checker.lic",
    ):
        key = load_license_from_file(candidate)
        if key:
            return key

    return None


def require_license(
    cli_key: Optional[str] = None,
    cli_file: Optional[str] = None,
    interactive: bool = True,
) -> LicenseInfo:
    """
    Resolve and validate license. On failure, print message and exit.
    Returns LicenseInfo on success.
    """
    key = resolve_license_key(cli_key=cli_key, cli_file=cli_file)

    if key is None and interactive and sys.stdin.isatty():
        try:
            import getpass
            key = getpass.getpass(f"{PRODUCT_NAME} access code or license key: ")
        except (KeyboardInterrupt, EOFError):
            key = None

    if not key:
        print(
            f"\n{PRODUCT_NAME} requires a valid access code or license.\n"
            "Provide one of:\n"
            "  --license <key>\n"
            "  --license-file <path>\n"
            "  env ASCENT_SHIPPER_CHECKER_LICENSE\n"
            "  file ./ascent_shipper_checker.lic\n",
            file=sys.stderr,
        )
        raise SystemExit(1)

    info = validate_license_key(key)
    if not info.valid:
        print(f"\nLicense validation failed: {info.message}\n", file=sys.stderr)
        raise SystemExit(1)

    return info


# Backward-compatible aliases used by older CLI wiring
def check_access(provided: Optional[str] = None, interactive: bool = True) -> bool:
    info = validate_license_key(provided or "") if provided else LicenseInfo(valid=False)
    if provided and info.valid:
        return True
    if provided is None:
        try:
            require_license(interactive=interactive)
            return True
        except SystemExit:
            return False
    return False


def require_access(provided: Optional[str] = None) -> None:
    require_license(cli_key=provided, interactive=True)
