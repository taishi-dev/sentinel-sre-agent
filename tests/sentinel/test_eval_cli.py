from pathlib import Path

from sentinel.eval_cli import DEFAULT_CATALOG, main, run


def test_run_writes_json_and_markdown(tmp_path: Path) -> None:
    out_json = tmp_path / "sc.json"
    out_md = tmp_path / "sc.md"
    sc = run(DEFAULT_CATALOG, version="test", out_json=out_json, out_md=out_md)
    assert sc.total == 10
    assert out_json.exists() and out_json.read_text(encoding="utf-8").strip().startswith("{")
    assert out_md.exists() and "Scorecard" in out_md.read_text(encoding="utf-8")


def test_main_returns_zero_when_baseline_is_safe() -> None:
    assert main(["--version", "ci-check"]) == 0
