import subprocess
import sys
import os
import tempfile
from pathlib import Path


def run(args, env_override=None):
    env = os.environ.copy()
    if env_override:
        env.update(env_override)
    result = subprocess.run(
        [sys.executable, "-m", "cctoken.cctoken"] + args,
        capture_output=True, text=True, env=env,
        cwd=str(Path(__file__).parent.parent.parent)
    )
    return result


def test_default_runs_without_error():
    result = run([])
    assert result.returncode == 0


def test_projects_runs_without_error():
    result = run(["projects"])
    assert result.returncode == 0


def test_trend_runs_without_error():
    result = run(["trend"])
    assert result.returncode == 0


def test_budget_set_prints_confirmation():
    result = run(["budget", "set", "9999999"])
    assert result.returncode == 0
    assert "Budget set to" in result.stdout
    assert "tokens/month" in result.stdout


def test_budget_set_invalid_number():
    result = run(["budget", "set", "notanumber"])
    assert result.returncode == 1
    assert "not a valid number" in result.stderr


def test_missing_projects_dir_exits_zero(tmp_path):
    """When ~/.claude/projects doesn't exist, exit 0 with a clear message."""
    import site
    fake_home = tmp_path / "fakehome"
    fake_home.mkdir()
    # Preserve PYTHONPATH so site-packages (rich) stay accessible under new HOME
    python_path = ":".join(site.getsitepackages() + [site.getusersitepackages()])
    result = run([], env_override={"HOME": str(fake_home), "PYTHONPATH": python_path})
    assert result.returncode == 0
    assert "No Claude Code session data found" in result.stdout
