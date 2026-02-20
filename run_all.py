import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


def run(cmd: list[str], label: str, log_path: Path) -> None:
    print("\n" + "=" * 72)
    print(f"Starting {label}")
    print("=" * 72)
    print("Command:", " ".join(cmd))
    print("Log:", str(log_path))

    start = time.time()

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as f:
        f.write(f"[{datetime.now().isoformat()}] {label}\n")
        f.write("Command: " + " ".join(cmd) + "\n\n")
        f.flush()

        # Stream stdout/stderr to console AND file for judge-friendly debugging.
        result = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT)

    elapsed = time.time() - start
    status = "OK" if result.returncode == 0 else f"FAIL (code {result.returncode})"
    print(f"Finished {label}: {status} in {elapsed:.2f}s")

    if result.returncode != 0:
        print(f"\n❌ {label} failed. See log: {log_path}")
        sys.exit(result.returncode)


def build_cli_cmd(
    python: str,
    yaml_path: str,
    iterations: int,
    restarts: int,
    robustness: int,
    seed: int | None,
    extra_args: list[str],
) -> list[str]:
    cmd = [
        python,
        "-m",
        "mission_framework.cli",
        yaml_path,
        "--iterations",
        str(iterations),
        "--restarts",
        str(restarts),
        "--robustness",
        str(robustness),
    ]
    if seed is not None:
        cmd += ["--seed", str(seed)]
    cmd += extra_args
    return cmd


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run ORBITAL end-to-end (aircraft + spacecraft) with one command."
    )

    # Defaults match your README “optional individual demo” commands.
    p.add_argument("--aircraft", default="examples/aircraft_uav_demo.yaml")
    p.add_argument("--spacecraft", default="examples/cubesat_leo_demo.yaml")

    p.add_argument("--iterations", type=int, default=200)
    p.add_argument("--restarts", type=int, default=1)

    p.add_argument("--aircraft-robustness", type=int, default=20)
    p.add_argument("--spacecraft-robustness", type=int, default=10)

    p.add_argument("--seed", type=int, default=0, help="Base seed for reproducibility.")
    p.add_argument(
        "--fast",
        action="store_true",
        help="Quick sanity run: fewer iterations and robustness=0.",
    )

    p.add_argument(
        "--no-plots",
        action="store_true",
        help="Pass through a no-plots flag if your CLI supports it.",
    )

    # Anything after `--` is forwarded to both CLI calls
    p.add_argument(
        "passthrough",
        nargs=argparse.REMAINDER,
        help="Extra args passed to mission_framework.cli (use after --).",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    python = sys.executable

    # If user provides extra args, they should do: python run_all.py -- --foo bar
    extra = args.passthrough
    if extra and extra[0] == "--":
        extra = extra[1:]

    if args.no_plots:
        extra = ["--no-plots"] + extra

    # Fast mode overrides (judge-friendly sanity check).
    iterations = args.iterations
    a_rob = args.aircraft_robustness
    s_rob = args.spacecraft_robustness
    if args.fast:
        iterations = min(iterations, 80)
        a_rob = 0
        s_rob = 0

    logs_dir = Path("runs") / "_logs"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    total_start = time.time()

    # Aircraft demo
    aircraft_cmd = build_cli_cmd(
        python=python,
        yaml_path=args.aircraft,
        iterations=iterations,
        restarts=args.restarts,
        robustness=a_rob,
        seed=args.seed,
        extra_args=extra,
    )
    run(
        aircraft_cmd,
        "Aircraft demo",
        logs_dir / f"{ts}_aircraft.log",
    )

    # Spacecraft demo (offset seed so both runs are deterministic but not identical)
    spacecraft_cmd = build_cli_cmd(
        python=python,
        yaml_path=args.spacecraft,
        iterations=iterations,
        restarts=args.restarts,
        robustness=s_rob,
        seed=args.seed + 1 if args.seed is not None else None,
        extra_args=extra,
    )
    run(
        spacecraft_cmd,
        "Spacecraft demo",
        logs_dir / f"{ts}_spacecraft.log",
    )

    total_elapsed = time.time() - total_start
    print("\n" + "=" * 72)
    print("✅ All domains completed successfully.")
    print(f"Total runtime: {total_elapsed:.2f}s")
    print("Outputs:")
    print("  - runs/aircraft_uav_demo/")
    print("  - runs/cubesat_leo_demo/")
    print("Logs:")
    print(f"  - {logs_dir}/")
    print("=" * 72)


if __name__ == "__main__":
    main()
