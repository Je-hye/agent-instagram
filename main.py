import argparse
import os

from dotenv import load_dotenv

load_dotenv()


def _simulate(args):
    from src.scheduler import run_simulation
    run_simulation(
        n_agents=args.agents,
        db_path=args.db,
        image_dir=args.images,
        interval_seconds=args.interval,
    )


def _web(args):
    import uvicorn
    from src.web.app import create_app
    app = create_app(args.db)
    uvicorn.run(app, host="0.0.0.0", port=args.port)


def main():
    parser = argparse.ArgumentParser(description="agent-instagram")
    subparsers = parser.add_subparsers(dest="command", required=True)

    sim = subparsers.add_parser("simulate", help="시뮬레이션 실행")
    sim.add_argument("--agents", type=int, default=5)
    sim.add_argument("--db", default=os.environ.get("DB_PATH", "data/simulation.db"))
    sim.add_argument("--images", default=os.environ.get("IMAGE_DIR", "images"))
    sim.add_argument("--interval", type=int, default=300)

    web = subparsers.add_parser("web", help="웹 대시보드 실행")
    web.add_argument("--port", type=int, default=8000)
    web.add_argument("--db", default=os.environ.get("DB_PATH", "data/simulation.db"))

    args = parser.parse_args()
    if args.command == "simulate":
        _simulate(args)
    else:
        _web(args)


if __name__ == "__main__":
    main()
