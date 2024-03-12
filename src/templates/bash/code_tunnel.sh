################### Mail and code tunnel  <<<<<<<<<<<<<<<<<<<<<<<<<
receipt_addr="i@luisli.org"
host=$(hostname -s)
date=$(date "+%Y%m%d%H%M%S")
mkdir -p /home2/$(whoami)/.jobs/${date}_${SLURM_JOB_ID}
mkdir -p .logs/runner/${SLURM_JOB_ID}
nohup code tunnel --accept-server-license-terms --name "${host}-${SLURM_JOB_ID}" --cli-data-dir /home2/$(whoami)/.jobs/${date}_${SLURM_JOB_ID} > .logs/runner/${SLURM_JOB_ID}/runner-${SLURM_JOB_ID}.log 2>&1 &
server_pid=$!
content="Slurm job name: ${SLURM_JOB_NAME}. 
Online dev: https://vscode.dev/tunnel/${host}-${SLURM_JOB_ID}$(pwd). 
Slurm jobs overview: http://ncc.clients.dur.ac.uk/grafana/d/5UwAWAzWk/slurm-jobs?orgId=1&var-user=$(whoami)&var-job=All&from=now-6h&to=now. 
To get the code, please run the command remotely: 
> more $(pwd)/.logs/runner/${SLURM_JOB_ID}/runner-${SLURM_JOB_ID}.log | grep -o 'code [A-Z0-9-]*' | tail -n 1
Then, log into https://github.com/login/device to grant the server access.
$(nvidia-smi)"
echo ${content}
server ${receipt_addr} "[NCC: ${host}] job #${SLURM_JOB_ID} is running" "${content}" > /dev/null 2>&1