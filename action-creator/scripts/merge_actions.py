"""Merge PASS actions into final/actions.yaml.

Collects actions from actions/ and retry_*/actions/, keeping only the latest
version of each action that passed evaluation.

Usage:
    python merge_actions.py <work_dir>

    work_dir: Sprint working directory (e.g. output/action_creator/naver)
"""

import sys
from pathlib import Path

import yaml


def _find_eval(action_name: str, work_dir: Path, retry_level: int) -> Path | None:
    """Find the eval file for an action at a given retry level."""
    if retry_level == 0:
        candidates = [
            work_dir / "evals" / f"{action_name}.yaml",
            work_dir / "code_evals" / f"{action_name}.eval.yaml",
        ]
    else:
        retry_dir = work_dir / f"retry_{retry_level}"
        candidates = [
            retry_dir / "evals" / f"{action_name}.yaml",
            retry_dir / "code_evals" / f"{action_name}.eval.yaml",
        ]
    for c in candidates:
        if c.exists():
            return c
    return None


def _is_pass(eval_file: Path) -> bool:
    """Check if an eval file indicates PASS."""
    with open(eval_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    status = data.get("status", "").upper()
    return status == "PASS"


def merge(work_dir: Path) -> dict:
    """Collect latest PASS version of each action."""
    # Discover all retry levels
    retry_levels = [0]
    for d in sorted(work_dir.glob("retry_*")):
        if d.is_dir():
            try:
                level = int(d.name.split("_")[1])
                retry_levels.append(level)
            except (IndexError, ValueError):
                continue

    # Discover all action names across levels
    action_sources: dict[str, list[tuple[int, Path]]] = {}

    # Level 0: actions/
    actions_dir = work_dir / "actions"
    if actions_dir.is_dir():
        for f in actions_dir.glob("*.yaml"):
            action_sources.setdefault(f.stem, []).append((0, f))

    # Retry levels
    for level in retry_levels:
        if level == 0:
            continue
        retry_actions = work_dir / f"retry_{level}" / "actions"
        if retry_actions.is_dir():
            for f in retry_actions.glob("*.yaml"):
                action_sources.setdefault(f.stem, []).append((level, f))

    # Pick latest PASS version for each action
    merged = {}
    pass_count = 0
    fail_count = 0

    for name, sources in sorted(action_sources.items()):
        # Check from latest retry to earliest
        found = False
        for level, action_file in reversed(sources):
            eval_file = _find_eval(name, work_dir, level)
            if eval_file and _is_pass(eval_file):
                with open(action_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                merged.update(data)
                pass_count += 1
                found = True
                print(f"  PASS: {name} (level {level})")
                break
        if not found:
            fail_count += 1
            print(f"  FAIL: {name}")

    print(f"\n{pass_count} passed, {fail_count} failed")
    return merged


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    work_dir = Path(sys.argv[1])
    if not work_dir.exists():
        print(f"Error: {work_dir} does not exist")
        sys.exit(1)

    merged = merge(work_dir)

    if not merged:
        print("No PASS actions to merge.")
        sys.exit(1)

    out_dir = work_dir / "final"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "actions.yaml"

    with open(out_path, "w", encoding="utf-8") as f:
        yaml.dump(merged, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print(f"Merged → {out_path}")


if __name__ == "__main__":
    main()
