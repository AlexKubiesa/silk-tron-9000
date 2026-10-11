"""Compares training runs on lowest_boss_hp_mean and on training stability metrics.

Usage:
    uv run python .claude/skills/rl-tune/compare_runs.py RUN_DIR [RUN_DIR ...] [--at STEPS]

The first run is the reference: config differences and deltas are shown relative to it.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from tbparse import SummaryReader

OBJECTIVE = "episode/lowest_boss_hp_mean"
STABILITY_TAGS = [
    "train/approx_kl",
    "train/clip_fraction",
    "train/explained_variance",
    "train/entropy_loss",
    "train/value_loss",
]
IGNORED_CONFIG_KEYS = {"created_at"}


def load_scalars(run_dir: Path) -> pd.DataFrame:
    df = SummaryReader(str(run_dir / "logs"), pivot=True).scalars
    return df.sort_values("step").reset_index(drop=True)


def load_config(run_dir: Path) -> dict:
    path = run_dir / "config.json"
    return json.loads(path.read_text()) if path.exists() else {}


def config_diff(reference: dict, other: dict) -> dict:
    keys = (set(reference) | set(other)) - IGNORED_CONFIG_KEYS
    return {
        k: (reference.get(k), other.get(k))
        for k in sorted(keys)
        if reference.get(k) != other.get(k)
    }


def value_at(series: pd.DataFrame, tag: str, step: int) -> float:
    s = series[["step", tag]].dropna()
    s = s[s["step"] <= step]
    return float(s[tag].iloc[-1]) if len(s) else float("nan")


def window(series: pd.DataFrame, tag: str, start: int, end: int) -> pd.Series:
    s = series[["step", tag]].dropna()
    return s[(s["step"] > start) & (s["step"] <= end)][tag]


def regression(series: pd.DataFrame, end: int) -> float:
    """Largest rise of the objective above its running minimum, up to `end`.

    The objective is minimized, so a rise is the agent getting worse after having been better.
    """
    s = series[["step", OBJECTIVE]].dropna()
    s = s[s["step"] <= end][OBJECTIVE]
    if s.empty:
        return float("nan")
    return float((s - s.cummin()).max())


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("runs", nargs="+", type=Path)
    parser.add_argument(
        "--at",
        type=int,
        help="Step to compare at (default: the last step that every run reached)",
    )
    args = parser.parse_args()

    data = {run: load_scalars(run) for run in args.runs}
    configs = {run: load_config(run) for run in args.runs}
    last_steps = {run: int(df["step"].max()) for run, df in data.items()}
    at = args.at or min(last_steps.values())
    reference = args.runs[0]

    print(f"Comparing at step {at:,} (reference: {reference.name})\n")

    print("Config differences from the reference:")
    for run in args.runs[1:]:
        diff = config_diff(configs[reference], configs[run])
        changes = ", ".join(f"{k}: {a} -> {b}" for k, (a, b) in diff.items())
        print(f"  {run.name}: {changes or 'none'}")
    print()

    milestones = sorted({int(at * f) for f in (0.25, 0.5, 0.75, 1.0)})
    print(f"{OBJECTIVE} (lower is better):")
    header = f"  {'run':<40}" + "".join(f"{m:>12,}" for m in milestones)
    print(header + f"{'delta':>10}{'last step':>12}")
    ref_value = value_at(data[reference], OBJECTIVE, at)
    for run in args.runs:
        values = [value_at(data[run], OBJECTIVE, m) for m in milestones]
        delta = values[-1] - ref_value
        row = f"  {run.name:<40}" + "".join(f"{v:>12.1f}" for v in values)
        print(row + f"{delta:>+10.1f}{last_steps[run]:>12,}")
    print()

    # Stability over the last quarter of the compared range, where differences in schedules and
    # late-training collapse show up.
    start = int(at * 0.75)
    print(f"Stability over steps {start:,}-{at:,} (mean, with max for approx_kl):")
    print(
        f"  {'run':<40}{'approx_kl':>10}{'kl_max':>10}{'clip_frac':>10}"
        f"{'expl_var':>10}{'entropy':>10}{'value_loss':>11}{'regress':>9}"
    )
    for run in args.runs:
        df = data[run]
        kl = window(df, "train/approx_kl", start, at)
        cols = [
            kl.mean(),
            kl.max(),
            window(df, "train/clip_fraction", start, at).mean(),
            window(df, "train/explained_variance", start, at).mean(),
            window(df, "train/entropy_loss", start, at).mean(),
        ]
        value_loss = window(df, "train/value_loss", start, at).mean()
        print(
            f"  {run.name:<40}"
            + "".join(f"{c:>10.4f}" for c in cols)
            + f"{value_loss:>11.4f}{regression(df, at):>9.1f}"
        )
    print(
        "\n  regress: largest rise of the objective above its best value so far "
        "(0 means it never got worse)."
    )

    missing = [t for t in [OBJECTIVE, *STABILITY_TAGS] if any(t not in d for d in data.values())]
    if missing:
        print(f"\nWarning: some runs are missing tags: {missing}")
    if any(np.isnan(value_at(d, OBJECTIVE, at)) for d in data.values()):
        print("\nWarning: some runs have no objective value by the compared step.")


if __name__ == "__main__":
    main()
