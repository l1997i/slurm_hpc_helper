################### Final Stage  <<<<<<<<<<<<<<<<<<<<<<<<<
receipt_addr="i@luisli.org"
source .pytorch/bin/activate
module load cuda/11.3
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd $DIR/../py
pwd
#nohup python3 pytorch_stage2.py > /dev/null 2>&1 &
python3 pytorch_stage2.py
final_pid=$!
server ${receipt_addr} "[NCC: ${host}] job #${SLURM_JOB_ID} +2 stage is running" "PID 2: ${final_pid}" > /dev/null 2>&1