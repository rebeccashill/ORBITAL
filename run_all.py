import subprocess
import sys
import time

def run(cmd: list[str], label: str):
    print("\n" + "=" * 60)
    print(f"Starting {label}")
    print("=" * 60)
    start = time.time()
    result = subprocess.run(cmd)
    elapsed = time.time() - start
    print(f"Finished {label} in {elapsed:.2f}s")
    if result.returncode != 0:
        sys.exit(result.returncode)


def main():
    python = sys.executable

    # Aircraft demo
    run([
        python, "-m", "mission_framework.cli",
        "examples/aircraft_uav_demo.yaml",
        "--iterations", "200",
        "--restarts", "1",
        "--robustness", "0"
    ])

    # Spacecraft demo
    run([
        python, "-m", "mission_framework.cli",
        "examples/cubesat_leo_demo.yaml",
        "--iterations", "200",
        "--restarts", "1",
        "--robustness", "0"
    ])

    print("\n✅ All domains completed successfully.")


if __name__ == "__main__":
    main()
