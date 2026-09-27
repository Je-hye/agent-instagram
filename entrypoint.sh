#!/bin/bash
set -e

python main.py simulate --agents 5 --interval 300 --db /data/simulation.db &

exec python main.py web --port 8000 --db /data/simulation.db
