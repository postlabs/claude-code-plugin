"""
List existing actions for a domain from web_dough.

Usage:
    python list_existing_actions.py <domain>  [--profile-dir <path>]
    python list_existing_actions.py <url>     [--profile-dir <path>]

Outputs YAML list of existing action names + descriptions to stdout.
Exit code 0 even if no actions found (prints empty list).

Example:
    python list_existing_actions.py www.naver.com
    python list_existing_actions.py https://www.naver.com/finance
"""

import sys
from pathlib import Path
from urllib.parse import urlparse

import yaml


def get_default_web_dough_dir() -> Path:
    """Auto-detect web_dough directory from standard Mojo user data path."""
    import os

    appdata = os.environ.get("APPDATA", "")
    if appdata:
        mojo_dir = Path(appdata) / "Mojo"
    else:
        mojo_dir = Path.home() / ".mojo"

    profiles_dir = mojo_dir / "profiles"
    if not profiles_dir.exists():
        return profiles_dir

    for d in profiles_dir.iterdir():
        if d.is_dir() and (d / "doughs").exists():
            return d / "web_dough"

    for d in profiles_dir.iterdir():
        if d.is_dir():
            return d / "web_dough"

    return profiles_dir / "default" / "web_dough"


def extract_domain(input_str: str) -> str:
    """Extract domain from URL or return as-is if already a domain."""
    if "://" in input_str:
        return urlparse(input_str).netloc
    return input_str


def list_actions(domain: str, web_dough_dir: Path) -> list[dict]:
    """Load existing actions for a domain and return name+description list."""
    actions_dir = web_dough_dir / domain / "actions"
    if not actions_dir.is_dir():
        return []

    results = []
    for f in sorted(actions_dir.glob("*.yaml")):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
            for name, action in data.items():
                entry = {"name": name}
                if action.get("description"):
                    entry["description"] = action["description"]
                if action.get("steps"):
                    entry["step_count"] = len(action["steps"])
                results.append(entry)
        except Exception:
            continue

    return results


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip(), file=sys.stderr)
        sys.exit(1)

    domain = extract_domain(sys.argv[1])

    web_dough_dir = None
    if "--profile-dir" in sys.argv:
        idx = sys.argv.index("--profile-dir")
        if idx + 1 < len(sys.argv):
            web_dough_dir = Path(sys.argv[idx + 1])

    if web_dough_dir is None:
        web_dough_dir = get_default_web_dough_dir()

    actions = list_actions(domain, web_dough_dir)
    print(yaml.dump(actions, allow_unicode=True, default_flow_style=False, sort_keys=False))


if __name__ == "__main__":
    main()
