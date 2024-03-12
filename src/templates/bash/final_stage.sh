################### Final Stage  <<<<<<<<<<<<<<<<<<<<<<<<<
source /etc/profile
source ~/anaconda3/etc/profile.d/conda.sh
module load cuda/11.1
conda activate virconv
cd /home2/mznv82/second-stage/tools
pwd
nohup python3 train.py --cfg_file cfgs/models/kitti/VirConv-T.yaml  > /dev/null &
final_pid=$!
server ${receipt_addr} "[NCC: ${host}] job #${SLURM_JOB_ID} +2 stage is running" "PID 2: ${final_pid}" > /dev/null 2>&1