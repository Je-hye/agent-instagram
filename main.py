import argparse
import os
from dotenv import load_dotenv

load_dotenv()


def main():
    parser = argparse.ArgumentParser(description="Agent Instagram Simulator")
    parser.add_argument("--agents", type=int, default=5, help="에이전트 수")
    parser.add_argument("--db", default="data/simulation.db", help="DB 경로")
    parser.add_argument("--images", default="images", help="이미지 저장 경로")
    parser.add_argument("--interval", type=int, default=300, help="wake cycle 간격(초)")
    args = parser.parse_args()

    from src.scheduler import run_simulation
    run_simulation(
        n_agents=args.agents,
        db_path=args.db,
        image_dir=args.images,
        interval_seconds=args.interval,
    )


if __name__ == "__main__":
    main()
