#!/usr/bin/env python3
"""
Generate a signed license key for Ascent Shipper Checker.

Usage examples:
  python tools/generate_license.py
  python tools/generate_license.py --licensee "Ascent Buildings" --expires 2027-12-31
  python tools/generate_license.py --out ascent_shipper_checker.lic
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running from repo root without install
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chubby_checker.auth import create_license, PRODUCT_NAME, validate_license_key


def main() -> None:
    parser = argparse.ArgumentParser(description=f"Generate license for {PRODUCT_NAME}")
    parser.add_argument("--licensee", default="Ascent Buildings", help="Licensee name")
    parser.add_argument(
        "--expires",
        default=None,
        help="Expiry date ISO-8601 (YYYY-MM-DD or full datetime). Omit for no expiry.",
    )
    parser.add_argument(
        "--features",
        default="full",
        help="Comma-separated feature flags (default: full)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Write key to this .lic file (in addition to stdout)",
    )
    args = parser.parse_args()

    expires = args.expires
    if expires and len(expires) == 10:
        # Expand bare date to end-of-day UTC
        expires = f"{expires}T23:59:59Z"

    features = [f.strip() for f in args.features.split(",") if f.strip()]
    key = create_license(licensee=args.licensee, expires=expires, features=features)

    # Self-check
    info = validate_license_key(key)
    if not info.valid:
        print(f"ERROR: generated key failed validation: {info.message}", file=sys.stderr)
        raise SystemExit(1)

    print(key)
    print(f"\n# licensee : {info.licensee}", file=sys.stderr)
    print(f"# issued   : {info.issued}", file=sys.stderr)
    print(f"# expires  : {info.expires or 'never'}", file=sys.stderr)
    print(f"# features : {', '.join(info.features)}", file=sys.stderr)

    if args.out:
        path = Path(args.out)
        path.write_text(
            "# Ascent Shipper Checker license file\n"
            f"# Licensee: {info.licensee}\n"
            f"# Expires:  {info.expires or 'never'}\n"
            f"{key}\n",
            encoding="utf-8",
        )
        print(f"# wrote    : {path}", file=sys.stderr)


if __name__ == "__main__":
    main()
