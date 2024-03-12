#!/bin/bash

cleanup() {
    echo "Signal caught, stopping python main.py..."
    kill -9 $PID
}

trap cleanup SIGINT SIGHUP

PID=$(lsof -ti :15001)
if [ ! -z "$PID" ]; then
    kill -9 $PID
fi

cd ~/slurm_gui && source ~/anaconda3/etc/profile.d/conda.sh && conda activate slurmgui
python main.py &
PID=$!

wait $PID
