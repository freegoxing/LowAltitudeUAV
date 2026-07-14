"""Launch native Microsoft SkillOpt for the SNR-only UAV Agent 1 skill."""

import argparse
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = PROJECT_ROOT / "src/SkillOpt/configs/uav_situation/default.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--out-root", type=Path)
    parser.add_argument("skillopt_args", nargs=argparse.REMAINDER)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    command = ["skillopt-train", "--config", str(args.config)]
    if args.out_root:
        command.extend(["--out_root", str(args.out_root)])
    command.extend(args.skillopt_args)
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)
