"""
Publish: final/actions.yaml → 2-tier action folder structure.

Usage:
    python publish.py <output_dir> <actions_dir>

    output_dir:  sprint output (e.g. output/action_creator/naver)
    actions_dir: publish target (e.g. actions)

Example:
    python publish.py output/action_creator/naver actions
"""

import sys
import os
from pathlib import Path

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


def extract_site_name(output_dir: Path) -> str:
    return output_dir.name


def extract_site_meta(output_dir: Path) -> dict:
    """Extract site metadata from sprint_plan.yaml if available."""
    plan_path = output_dir / "sprint_plan.yaml"
    if not plan_path.exists():
        return {}
    with open(plan_path, "r", encoding="utf-8") as f:
        plan = yaml.safe_load(f) or {}

    meta = {}
    if "site" in plan:
        meta["site"] = plan["site"]
    # look for entry_url in scenarios or top level
    for scenario in plan.get("scenarios", []):
        for action in scenario.get("actions", []):
            if "entry_url" in action:
                meta["url"] = action["entry_url"].split("/")[0:3]
                meta["url"] = "/".join(action["entry_url"].split("/")[:3])
                break
        if "url" in meta:
            break
    return meta


def publish(output_dir: Path, actions_dir: Path):
    site_name = extract_site_name(output_dir)
    actions = load_final_actions(output_dir)

    if not actions:
        print(f"No actions found in {output_dir}")
        sys.exit(1)

    site_dir = actions_dir / site_name
    site_dir.mkdir(parents=True, exist_ok=True)

    # 1. Write individual action files
    action_count = 0
    for name, action in actions.items():
        action_path = site_dir / f"{name}.yaml"
        with open(action_path, "w", encoding="utf-8") as f:
            yaml.dump(
                {name: action},
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )
        action_count += 1

    # 2. Write site manifest (Tier 2)
    site_manifest = {
        "site": site_name,
        "actions": {},
    }
    site_meta = extract_site_meta(output_dir)
    if "url" in site_meta:
        site_manifest["url"] = site_meta["url"]

    for name, action in actions.items():
        entry = {"description": action.get("description", "")}
        if "params" in action:
            entry["input"] = list(action["params"].keys())
        if "output" in action:
            entry["output"] = action["output"].get("type", "text")
        site_manifest["actions"][name] = entry

    manifest_path = site_dir / "manifest.yaml"
    with open(manifest_path, "w", encoding="utf-8") as f:
        yaml.dump(
            site_manifest,
            f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )

    # 3. Update global manifest (Tier 1)
    global_manifest_path = actions_dir / "manifest.yaml"
    if global_manifest_path.exists():
        with open(global_manifest_path, "r", encoding="utf-8") as f:
            global_manifest = yaml.safe_load(f) or {}
    else:
        global_manifest = {"sites": {}}

    if "sites" not in global_manifest:
        global_manifest["sites"] = {}

    global_manifest["sites"][site_name] = {
        "description": site_meta.get("site", site_name),
        "action_count": action_count,
    }
    if "url" in site_meta:
        global_manifest["sites"][site_name]["url"] = site_meta["url"]

    with open(global_manifest_path, "w", encoding="utf-8") as f:
        yaml.dump(
            global_manifest,
            f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )

    print(f"Published {action_count} actions → {site_dir}")
    print(f"Site manifest → {manifest_path}")
    print(f"Global manifest → {global_manifest_path}")


def main():
    if len(sys.argv) < 3:
        print(__doc__.strip())
        sys.exit(1)

    output_dir = Path(sys.argv[1])
    actions_dir = Path(sys.argv[2])

    if not output_dir.exists():
        print(f"Error: {output_dir} does not exist")
        sys.exit(1)

    publish(output_dir, actions_dir)


if __name__ == "__main__":
    main()
