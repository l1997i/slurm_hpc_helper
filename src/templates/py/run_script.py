import sys
import subprocess
from setproctitle import setproctitle
import os
import json

slurm_job_id = os.environ.get('SLURM_JOB_ID')

def run_script(script_path, title):
    stage_id = title.split('_')[-1]
    setproctitle(title)
    process = subprocess.Popen(["bash", script_path])
    print(f"[Stage {stage_id}] Started process PID:", process.pid)
    # pid2json(process.pid, stage_id)
    process.wait()
    return process.pid

def pid2json(pid, stage_id):
    current_path = os.getcwd()
    hpc_gui_path = os.environ.get('HPC_GUI_PATH')
    json_path: str = os.path.join(current_path, f".logs/job_scripts/{slurm_job_id}/job_info.json")
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
    if len(sys.argv) != 3:
        print("Usage: python run_script_with_title.py <path_to_script.sh> <process_title>")
        sys.exit(1)
    
    script_path = sys.argv[1]
    title = sys.argv[2]
    
    run_script(script_path, title)
