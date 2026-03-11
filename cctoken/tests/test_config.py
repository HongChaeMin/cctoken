import tempfile
from pathlib import Path
from cctoken.config import load_config, save_budget, Config


def test_load_config_no_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = load_config(config_path=Path(tmpdir) / "cctoken.json")
        assert cfg.monthly_token_budget is None


def test_save_and_load_budget():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "cctoken.json"
        save_budget(5_000_000, config_path=path)
        cfg = load_config(config_path=path)
        assert cfg.monthly_token_budget == 5_000_000


def test_load_config_invalid_json():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "cctoken.json"
        path.write_text("not json")
        cfg = load_config(config_path=path)
        assert cfg.monthly_token_budget is None
