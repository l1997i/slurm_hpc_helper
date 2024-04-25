################### Mail and sshd  <<<<<<<<<<<<<<<<<<<<<<<<<
receipt_addr="i@luisli.org"
host=$(hostname -s)
date=$(date "+%Y%m%d%H%M%S")
PORT=$(python -c 'import socket; s=socket.socket(); s.bind(("", 0)); print(s.getsockname()[1]); s.close()')
nohup /usr/sbin/sshd -D -p ${PORT} -f /dev/null -h ~/.ssh/id_rsa > /dev/null 2>&1 &
server_pid=$!
content="Slurm job name: ${SLURM_JOB_NAME},     Server PID: ${server_pid}. 
Slurm jobs overview: http://ncc.clients.dur.ac.uk/grafana/d/5UwAWAzWk/slurm-jobs?orgId=1&var-user=$(whoami)&var-job=All&from=now-6h&to=now. 
[SSH] To get the access to the node, please run the command locally: 
> ssh -J $(whoami)@ncc1.clients.dur.ac.uk $(whoami)@${host} -p ${PORT} -i ~/.ssh/id_rsa
$(nvidia-smi)"
echo ${content}
server ${receipt_addr} "[NCC: ${host}] job #${SLURM_JOB_ID} is running" "${content}" > /dev/null 2>&1