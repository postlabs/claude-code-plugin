"""
Publish: sprint output → web_dough/<domain>/actions/<name>.yaml

Usage:
    python publish.py <output_dir> [--profile-dir <path>]

    output_dir:    sprint output (e.g. output/action_creator/naver)
    --profile-dir: web_dough root (default: auto-detect from MOJO_USER_DATA_DIR)

Example:
    python publish.py output/action_creator/naver
"""

import sys
from pathlib import Path
from urllib.parse import urlparse

import yaml


def load_final_actions(output_dir: Path) -> dict:
    final_path = output_dir / "final" / "actions.yaml"
    if not final_path.exists():
        # fallback: merge from sprint dirs
        return merge_sprint_actions(output_dir)

    with open(final_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def merge_sprint_actions(output_dir: Path) -> dict:
    """Fallback: collect actions from sprint_N/actions.yaml files."""
    merged = {}
    sprint_dirs = sorted(output_dir.glob("sprint_*"))
    for sprint_dir in sprint_dirs:
        if not sprint_dir.is_dir():
            continue
        # use latest retry if exists
        retry_dirs = sorted(sprint_dir.glob("retry_*"))
        actions_file = (
            retry_dirs[-1] / "actions.yaml" if retry_dirs
            else sprint_dir / "actions.yaml"
        )
        if actions_file.exists():
            with open(actions_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                merged.update(data)
    return merged


def extract_domain(action: dict) -> str | None:
    """Extract domain from action's url or first navigate step."""
    url = action.get("url", "")
    if not url:
        for step in action.get("steps", []):
            if step.get("action") == "navigate" and step.get("url"):
                url = step["url"]
                break
    if not url:
        return None
    # Strip template markers like {{param}}
    clean = url.replace("{{", "").replace("}}", "")
    parsed = urlparse(clean)
    return parsed.netloc or None


def get_default_web_dough_dir() -> Path:
    """Auto-detect web_dough directory from standard Mojo user data path."""
    import os
    # Windows: %APPDATA%/Mojo
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        mojo_dir = Path(appdata) / "Mojo"
    else:
        mojo_dir = Path.home() / ".mojo"

    profiles_dir = mojo_dir / "profiles"
    if not profiles_dir.exists():
        return profiles_dir  # will fail later with clear error

    # Use first profile found
    for d in profiles_dir.iterdir():
        if d.is_dir() and (d / "doughs").exists():
            return d / "web_dough"

    # Fallback: first profile dir
    for d in profiles_dir.iterdir():
        if d.is_dir():
            return d / "web_dough"

    return profiles_dir / "default" / "web_dough"


def publish(output_dir: Path, web_dough_dir: Path):
    actions = load_final_actions(output_dir)

    if not actions:
        print(f"No actions found in {output_dir}")
        sys.exit(1)

    # Group actions by domain
    domain_actions: dict[str, dict[str, dict]] = {}
    no_domain: list[str] = []

    for name, action in actions.items():
        domain = extract_domain(action)
        if domain:
            domain_actions.setdefault(domain, {})[name] = action
        else:
            no_domain.append(name)

    if no_domain:
        print(f"Warning: {len(no_domain)} actions have no URL, skipping: {no_domain}")

    # Write to web_dough/<domain>/actions/<name>.yaml
    total = 0
    for domain, domain_acts in sorted(domain_actions.items()):
        site_dir = web_dough_dir / domain
        actions_dir = site_dir / "actions"
        actions_dir.mkdir(parents=True, exist_ok=True)

        # Ensure manifest.yaml
        manifest_path = site_dir / "manifest.yaml"
        if not manifest_path.exists():
            with open(manifest_path, "w", encoding="utf-8") as f:
                yaml.dump(
                    {"site": domain},
                    f, allow_unicode=True, default_flow_style=False, sort_keys=False,
                )

        for name, action in domain_acts.items():
            action_path = actions_dir / f"{name}.yaml"
            with open(action_path, "w", encoding="utf-8") as f:
                yaml.dump(
                    {name: action},
                    f, default_flow_style=False, allow_unicode=True, sort_keys=False,
                )
            total += 1

        print(f"  {domain}: {len(domain_acts)} actions")

    print(f"\nPublished {total} actions → {web_dough_dir}")


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    output_dir = Path(sys.argv[1])

    # Parse --profile-dir flag
    web_dough_dir = None
    if "--profile-dir" in sys.argv:
        idx = sys.argv.index("--profile-dir")
        if idx + 1 < len(sys.argv):
            web_dough_dir = Path(sys.argv[idx + 1])

    if web_dough_dir is None:
        web_dough_dir = get_default_web_dough_dir()

    if not output_dir.exists():
        print(f"Error: {output_dir} does not exist")
        sys.exit(1)

    print(f"Target: {web_dough_dir}")
    publish(output_dir, web_dough_dir)


if __name__ == "__main__":
    main()
