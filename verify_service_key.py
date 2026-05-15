"""
One-shot verification that .streamlit/secrets.toml's
[supabase].service_role_key actually authenticates against the
project. Reads `public.plans` (4 rows expected) and prints the result.

Run from the project root:
    python3 verify_service_key.py

This script is throwaway — delete it after verification if you like.
"""
from __future__ import annotations

import sys
import tomllib  # py3.11+
from pathlib import Path


SECRETS_PATH = Path(__file__).parent / ".streamlit" / "secrets.toml"


def _load_secrets() -> dict:
    if not SECRETS_PATH.exists():
        sys.exit(f"FAIL — secrets file not found at {SECRETS_PATH}")
    with SECRETS_PATH.open("rb") as f:
        data = tomllib.load(f)
    if "supabase" not in data:
        sys.exit("FAIL — [supabase] block missing from secrets.toml")
    sb = data["supabase"]
    for k in ("url", "service_role_key"):
        if k not in sb:
            sys.exit(f"FAIL — secrets.toml [supabase].{k} missing")
    return sb


def main() -> None:
    sb = _load_secrets()

    try:
        from supabase import create_client
    except ImportError:
        sys.exit(
            "FAIL — `supabase` package not installed.\n"
            "       Run: pip install supabase"
        )

    print(f"Connecting to {sb['url']} with service_role_key ...")
    client = create_client(sb["url"], sb["service_role_key"])

    try:
        resp = client.table("plans").select("id,name,seats").order("id").execute()
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"FAIL — query raised: {exc}")

    rows = resp.data or []
    if not rows:
        sys.exit("FAIL — query returned 0 rows. Did the migration run?")

    print(f"\nOK — service_role_key authenticated. Got {len(rows)} plan(s):")
    for r in rows:
        print(f"  {r['id']:<12} {r['name']:<14} seats={r['seats']}")

    expected = {"free", "solo_pro", "family_pro", "coach_pro"}
    got = {r["id"] for r in rows}
    if expected - got:
        print(f"\nWARN — missing expected plan ids: {sorted(expected - got)}")
    else:
        print("\nAll 4 expected plans present. Step 2 verified.")


if __name__ == "__main__":
    main()
