from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "research_baseline_manifest.json"
ENGINE_PATH = ROOT / "play_step_0902.py"
PROFILE_PATH = ROOT / "strategy_profiles.json"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def normalized_text_file_hash(path: Path) -> str:
    return sha256_bytes(path.read_bytes().replace(b"\r\n", b"\n"))


def canonical_json_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(encoded)


def source_hash(value: Any) -> str:
    source = inspect.getsource(value).replace("\r\n", "\n").encode("utf-8")
    return sha256_bytes(source)


def load_modules() -> tuple[Any, Any]:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import play_research_adaptive as adaptive
    import play_step_0902 as engine

    return adaptive, engine


def current_snapshot() -> dict[str, Any]:
    adaptive, engine = load_modules()
    profiles = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    tempo_profile = profiles["tempo_baseline"]
    return {
        "engine_file_sha256": normalized_text_file_hash(ENGINE_PATH),
        "engine_functions": {
            "recognize": source_hash(engine.recognize),
            "info_beats": source_hash(engine.info_beats),
            "legal_play_options": source_hash(engine.legal_play_options),
            "choose_lead_play": source_hash(engine.choose_lead_play),
            "choose_play": source_hash(engine.choose_play),
        },
        "adaptive_functions": {
            "choose_profiled_play": source_hash(adaptive.choose_profiled_play),
            "offline_baseline_action_info": source_hash(adaptive.offline_baseline_action_info),
        },
        "tempo_baseline_profile_sha256": canonical_json_hash(tempo_profile),
        "tempo_baseline_profile": tempo_profile,
    }


def git_head() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def write_manifest() -> dict[str, Any]:
    manifest = {
        "schema_version": 1,
        "baseline_name": "tempo_baseline",
        "frozen_at": "2026-07-12",
        "frozen_git_commit": git_head(),
        "invariants": [
            "tempo_baseline core decisions are immutable",
            "website rules and legal action semantics are immutable",
            "server communication and leaderboard Elo semantics are immutable",
        ],
        "snapshot": current_snapshot(),
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def verify_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        raise RuntimeError(f"baseline manifest not found: {MANIFEST_PATH}")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    expected = manifest.get("snapshot") or {}
    actual = current_snapshot()
    mismatches: list[dict[str, Any]] = []

    def compare(path: str, expected_value: Any, actual_value: Any) -> None:
        if expected_value != actual_value:
            mismatches.append(
                {
                    "path": path,
                    "expected": expected_value,
                    "actual": actual_value,
                }
            )

    compare("engine_file_sha256", expected.get("engine_file_sha256"), actual["engine_file_sha256"])
    compare(
        "tempo_baseline_profile_sha256",
        expected.get("tempo_baseline_profile_sha256"),
        actual["tempo_baseline_profile_sha256"],
    )
    for group in ("engine_functions", "adaptive_functions"):
        for name, actual_hash in actual[group].items():
            compare(f"{group}.{name}", (expected.get(group) or {}).get(name), actual_hash)
    return {
        "baseline_name": manifest.get("baseline_name"),
        "frozen_git_commit": manifest.get("frozen_git_commit"),
        "baseline_freeze_checked": True,
        "baseline_freeze_mismatch_count": len(mismatches),
        "baseline_freeze_mismatches": mismatches,
        "threshold_passed": not mismatches,
    }


def run_equivalence(sample_count: int, out_path: Path | None) -> dict[str, Any]:
    adaptive, _engine = load_modules()
    profiles = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    components = adaptive.offline_load_guandan_components()
    result = adaptive.offline_baseline_equivalence_check(
        components,
        profiles["tempo_baseline"],
        sample_count=sample_count,
    )
    result["requested_samples"] = sample_count
    result["threshold_passed"] = bool(
        int(result.get("baseline_equivalence_samples") or 0) >= sample_count
        and int(result.get("baseline_equivalence_mismatch_count") or 0) == 0
    )
    if out_path is not None:
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify the immutable tempo baseline snapshot.")
    parser.add_argument("--write-manifest", action="store_true")
    parser.add_argument("--equivalence-samples", type=int, default=0)
    parser.add_argument("--equivalence-out")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.write_manifest:
        write_manifest()
    result = {"freeze": verify_manifest()}
    if int(args.equivalence_samples) > 0:
        result["equivalence"] = run_equivalence(
            int(args.equivalence_samples),
            Path(args.equivalence_out) if args.equivalence_out else None,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["freeze"]["threshold_passed"]:
        raise SystemExit(1)
    if result.get("equivalence") and not result["equivalence"]["threshold_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
