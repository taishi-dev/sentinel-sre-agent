import argparse
from pathlib import Path

from sentinel.domain import RootCauseClass
from sentinel.eval import Scorecard, evaluate, scorecard_to_markdown
from sentinel.heuristic import HeuristicDiagnoser
from sentinel.policy import PolicyConfig, PolicyGate
from sentinel.scenario import load_catalog

DEFAULT_CATALOG: Path = Path(__file__).parents[2] / "scenarios"

EVAL_POLICY: PolicyConfig = PolicyConfig(
    autonomous_eligible_services=["shop"],
    sensitive_root_causes=[RootCauseClass.SECURITY_REGRESSION, RootCauseClass.PII_EXPOSURE],
    min_confidence=0.8,
)


def run(
    catalog_dir: Path,
    version: str,
    out_json: Path | None,
    out_md: Path | None,
) -> Scorecard:
    scenarios = load_catalog(catalog_dir)
    gate = PolicyGate(EVAL_POLICY)
    sc = evaluate(scenarios, HeuristicDiagnoser(), gate, version=version)
    if out_json is not None:
        out_json.write_text(sc.model_dump_json(indent=2), encoding="utf-8")
    if out_md is not None:
        out_md.write_text(scorecard_to_markdown(sc), encoding="utf-8")
    return sc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Sentinel eval gate.")
    parser.add_argument("--version", default="v0.1.0-baseline")
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--out-json", type=Path, default=None)
    parser.add_argument("--out-md", type=Path, default=None)
    args = parser.parse_args(argv)

    sc = run(args.catalog, args.version, args.out_json, args.out_md)
    print(scorecard_to_markdown(sc))
    if not sc.safe:
        print(f"EVAL GATE FAILED: {sc.unsafe_autonomous_action_count} unsafe autonomous action(s)")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
