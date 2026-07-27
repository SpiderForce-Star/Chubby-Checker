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
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _fail(msg: str, code: int = 1) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)


def _validate_expires(expires: str | None) -> str | None:
    if expires is None:
        return None
    expires = expires.strip()
    if not expires:
        return None
    if len(expires) == 10:
        # YYYY-MM-DD -> end of day UTC
        try:
            datetime.strptime(expires, "%Y-%m-%d")
        except ValueError:
            _fail(f"Invalid --expires date '{expires}'. Use YYYY-MM-DD or full ISO-8601.")
        return f"{expires}T23:59:59Z"
    # Accept broader ISO-ish forms
    try:
        datetime.fromisoformat(expires.replace("Z", "+00:00"))
    except ValueError:
        _fail(f"Invalid --expires value '{expires}'. Use YYYY-MM-DD or ISO-8601 datetime.")
    return expires


def main(argv: list[str] | None = None) -> int:
    try:
        from chubby_checker.auth import create_license, PRODUCT_NAME, validate_license_key
    except ImportError as exc:
        _fail(
            f"Could not import chubby_checker.auth ({exc}). "
            "Run from the repo root or install the package (pip install -e .)."
        )

    parser = argparse.ArgumentParser(
        description=f"Generate cryptographic license for {PRODUCT_NAME}",
        epilog="Exit codes: 0=ok, 1=validation/usage error, 2=I/O error, 3=unexpected failure",
    )
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
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only print the license key (no metadata on stderr)",
    )
    args = parser.parse_args(argv)

    try:
        licensee = (args.licensee or "").strip()
        if not licensee:
            _fail("--licensee cannot be empty")

        expires = _validate_expires(args.expires)

        features = [f.strip() for f in (args.features or "").split(",") if f.strip()]
        if not features:
            _fail("--features must include at least one flag (e.g. full)")

        try:
            key = create_license(licensee=licensee, expires=expires, features=features)
        except Exception as exc:
            _fail(f"License creation failed: {exc}")

        try:
            info = validate_license_key(key)
        except Exception as exc:
            _fail(f"License self-check crashed: {exc}")

        if not info.valid:
            _fail(f"Generated key failed validation: {info.message}")

        # Success output
        print(key)
        if not args.quiet:
            print(f"\n# licensee : {info.licensee}", file=sys.stderr)
            print(f"# issued   : {info.issued}", file=sys.stderr)
            print(f"# expires  : {info.expires or 'never'}", file=sys.stderr)
            print(f"# features : {', '.join(info.features)}", file=sys.stderr)

        if args.out:
            path = Path(args.out)
            try:
                if path.parent and not path.parent.exists():
                    path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    "# Ascent Shipper Checker license file\n"
                    f"# Licensee: {info.licensee}\n"
                    f"# Expires:  {info.expires or 'never'}\n"
                    f"# Generated: {datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
                    f"{key}\n",
                    encoding="utf-8",
                )
            except OSError as exc:
                print(f"ERROR: could not write license file '{path}': {exc}", file=sys.stderr)
                return 2
            if not args.quiet:
                print(f"# wrote    : {path.resolve()}", file=sys.stderr)

        return 0

    except SystemExit:
        raise
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: unexpected failure: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
