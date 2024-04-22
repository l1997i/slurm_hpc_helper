#!/usr/bin/env python3

import subprocess
import sys
import os
import json

try:
    from setproctitle import setproctitle
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "setproctitle"])
    from setproctitle import setproctitle  # Retry the import after installation

slurm_job_id = os.environ.get('SLURM_JOB_ID')


def run_script(script_path, title, output_file=None):
    stage_id = title.split('_')[-1]
    setproctitle(title)
    if output_file:
        with open(output_file, 'w') as file:
            process = subprocess.Popen(["bash", script_path], stdout=file, stderr=subprocess.STDOUT)
    else:
        process = subprocess.Popen(["bash", script_path])

    print("[Stage {}] Started process PID: {}".format(stage_id, process.pid))
    process.wait()
    return process.pid


def pid2json(pid, stage_id):
    current_path = os.getcwd()
    hpc_gui_path = os.environ.get('HPC_GUI_PATH')
    json_path = os.path.join(current_path, ".logs/job_scripts/{}/job_info.json".format(slurm_job_id))
    job_path = os.path.join(hpc_gui_path, "data/jobs.json")
    write_job_json(pid, stage_id, job_path)
    write_json(pid, stage_id, json_path)


def write_json(pid, stage_id, json_path):
    with open(json_path, 'r') as file:
        data = json.load(file)
        key = 'pid_' + stage_id
        data[key] = pid
    with open(json_path, 'w') as file:
        json.dump(data, file)


def write_job_json(pid, stage_id, json_path):
    with open(json_path, 'r') as file:
        data = json.load(file)
        key = 'pid_' + stage_id
        data[slurm_job_id][key] = pid
    with open(json_path, 'w') as file:
        json.dump(data, file)


if __name__ == "__main__":
    script_path = sys.argv[1]
    title = sys.argv[2]
    if len(sys.argv) == 4:
        output_file = sys.argv[3]
        run_script(script_path, title, output_file)
    else:
        run_script(script_path, title)
