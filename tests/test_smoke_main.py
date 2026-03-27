from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_smoke_python_module_main_dry_run(tmp_path: Path) -> None:
    db_path = tmp_path / "smoke.sqlite3"
    env = os.environ.copy()
    env["DRY_RUN"] = "true"
    env["FIRST_RUN_IMMEDIATELY"] = "false"
    env["SCHEDULER_ONLY"] = "true"
    env["SQLITE_PATH"] = str(db_path)

    result = subprocess.run(
        [sys.executable, "-m", "app.main", "--dry-run", "--once"],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stderr
    combined_output = f"{result.stdout}\n{result.stderr}"
    assert "run_once_finished" in combined_output or "cycle_end" in combined_output
