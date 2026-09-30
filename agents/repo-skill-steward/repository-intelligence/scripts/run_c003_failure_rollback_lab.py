#!/usr/bin/env python3
"""Execute a real isolated failure and rollback transaction for C003."""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("rollback_evidence", HERE / "rollback_evidence.py")
ROLLBACK = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(ROLLBACK)


def _run(args: list[str], *, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def _git(cwd: Path, *args: str) -> str:
    return _run(["git", *args], cwd=cwd).stdout.strip()


def _functional(cwd: Path) -> subprocess.CompletedProcess[str]:
    return _run(
        [
            "python3",
            "-B",
            "-c",
            "from app import transform; assert transform(3) == 6; print('functional-validation=passed')",
        ],
        cwd=cwd,
        check=False,
    )


def run_lab() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="c003-rollback-") as td:
        root = Path(td)
        source = root / "source"
        worktree = root / "candidate"
        source.mkdir()

        (source / "app.py").write_text(
            "def transform(value):\n    return value * 2\n",
            encoding="utf-8",
        )

        _run(["git", "init", "-q", "-b", "main"], cwd=source)
        _git(source, "config", "user.email", "ci@example.invalid")
        _git(source, "config", "user.name", "Sazan C003 CI")
        _git(source, "add", "app.py")
        _git(source, "commit", "-qm", "verified baseline")

        rollback_revision = _git(source, "rev-parse", "HEAD")
        rollback_tree = _git(source, "rev-parse", "HEAD^{tree}")
        parent_status_before = _git(source, "status", "--porcelain")

        _git(source, "worktree", "add", "-q", "-b", "c003-failure-lab", str(worktree), rollback_revision)

        (worktree / "app.py").write_text(
            "def transform(value):\n    return value * 3\n",
            encoding="utf-8",
        )
        _git(worktree, "add", "app.py")
        _git(worktree, "commit", "-qm", "intentional breaking mutation")
        mutation_revision = _git(worktree, "rev-parse", "HEAD")

        failed = _functional(worktree)
        if failed.returncode == 0:
            raise RuntimeError("intentional failure was not observed")

        _git(worktree, "reset", "--hard", rollback_revision)

        restored_revision = _git(worktree, "rev-parse", "HEAD")
        restored_tree = _git(worktree, "rev-parse", "HEAD^{tree}")
        restored_status = _git(worktree, "status", "--porcelain")
        passed = _functional(worktree)

        parent_revision_after = _git(source, "rev-parse", "HEAD")
        parent_tree_after = _git(source, "rev-parse", "HEAD^{tree}")
        parent_status_after = _git(source, "status", "--porcelain")

        parent_unchanged = (
            parent_revision_after == rollback_revision
            and parent_tree_after == rollback_tree
            and parent_status_after == parent_status_before
        )

        receipt = {
            "schema_version": 1,
            "transaction_id": "c003-rollback-fixture-001",
            "repository_id": "fixture_repo_rollback_01",
            "isolation": {
                "mode": "git-worktree",
                "evidence": ["git:worktree-add:candidate-branch"],
            },
            "rollback_point": {
                "revision": rollback_revision,
                "tree_hash": rollback_tree,
                "evidence": ["git:verified-baseline-commit", "git:baseline-tree-hash"],
            },
            "mutation": {
                "revision": mutation_revision,
                "evidence": ["git:intentional-breaking-mutation-commit"],
            },
            "failure": {
                "status": "observed",
                "command": "python3 functional assertion: transform(3) == 6",
                "exit_code": failed.returncode,
                "evidence": ["runtime:functional-assertion-failed-after-mutation"],
            },
            "rollback": {
                "method": "git-reset-hard-to-verified-revision",
                "target_revision": rollback_revision,
                "evidence": ["git:reset-hard:verified-baseline"],
            },
            "post_rollback": {
                "revision": restored_revision,
                "tree_hash": restored_tree,
                "clean_worktree": restored_status == "",
                "parent_workspace_unchanged": parent_unchanged,
                "functional_validation": {
                    "status": "passed" if passed.returncode == 0 else "failed",
                    "evidence": ["runtime:functional-assertion-passed-after-rollback"],
                },
            },
            "private_data": {
                "status": "compliant",
                "evidence": ["fixture:opaque-repository-id", "fixture:no-absolute-paths-persisted"],
            },
        }

        result = ROLLBACK.validate(receipt)
        result["execution"] = {
            "failure_exit_code": failed.returncode,
            "post_rollback_exit_code": passed.returncode,
            "baseline_equals_final_revision": restored_revision == rollback_revision,
            "baseline_equals_final_tree": restored_tree == rollback_tree,
            "parent_workspace_unchanged": parent_unchanged,
        }
        return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-verified", action="store_true")
    args = parser.parse_args()

    report = run_lab()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.require_verified and report["status"] != "verified":
        return 17
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
