import sys
from flask import Blueprint, render_template, session, escape, request
from functools import partial
from flask_login import login_required
import subprocess
import threading
import shutil
from . import socketio
from flask_socketio import emit, join_room
import json, os
import time
from datetime import datetime
from src import resource_path

bp = Blueprint('slurm', __name__, url_prefix='/slurm')

outputs = {}
scripts = {}
last_submit_form = {}

HPC_GUI_PATH = os.getcwd()


def myEscape(text):
    rep = '1g4x9s'  # random string
    text = text.replace('\n', rep)
    text = str(escape(text))
    text = text.replace(rep, '<br>')
    return text


@bp.route('/')
@login_required
def slurm():
    global last_submit_form
    os.makedirs('data', exist_ok=True)
    htmldata = json.load(open(os.path.join(os.getcwd(), 'config.json')))
    if os.path.exists(os.path.join(HPC_GUI_PATH, 'last_submit_form.json')):
        last_submit_form = json.load(open(os.path.join(HPC_GUI_PATH, 'last_submit_form.json')))
    session['last_submit_form'] = last_submit_form
    return render_template('slurm/slurm.html', htmldata=htmldata)


@bp.route('/attach_job', methods=['POST'])
@login_required
def attachJob():
    if 'g_selected_job_id' not in globals():
        return ('', 204)
    job_id = globals()['g_selected_job_id']
    name = request.form['name']
    script = request.form['job_script']
    manager.attachJob(job_id, name, script)
    return ('', 204)


@bp.route('/load_json_job', methods=['POST'])
@login_required
def loadJsonJob():
    htmldata = json.load(open(os.path.join(os.getcwd(), 'config.json')))
    htmldata["is_load"] = True
    json_path = os.path.expanduser(request.form['load_json_path'])
    if os.path.exists(json_path) and json_path.endswith('.json'):
        last_submit_form = json.load(open(json_path))
        session['last_submit_form'] = last_submit_form
        return render_template('slurm/slurm.html', htmldata=htmldata)

    else:
        socketio.emit('update', {'html': {'message_json': 'ERROR: json file not exsit!'}}, to='slurm')
    return ('', 204)


@bp.route('/submit_job', methods=['POST'])
@login_required
def submitJob():
    time_dir = int(time.time()).__str__()
    wk_dir = os.path.expanduser(request.form['#SBATCH --chdir '])
    raw_addi_args = request.form['additional args']
    if os.path.exists(wk_dir):
        cli(f"cd {wk_dir}")
    else:
        socketio.emit('update', {'html': {'message': 'ERROR: working dir (--chdir) not exsit!'}}, to='slurm')
        return ('', 204)
    os.makedirs(os.path.join(wk_dir, '.logs/job_scripts', time_dir), exist_ok=True)
    os.makedirs(os.path.join(wk_dir, '.logs/.temp', time_dir), exist_ok=True)
    script_loc = os.path.join(wk_dir, '.logs/job_scripts', time_dir, time_dir + '.sh')
    json_setting_loc = os.path.join(wk_dir, '.logs/job_scripts', time_dir, time_dir + '.json')
    user_sh_loc = os.path.join(wk_dir, '.logs/job_scripts', time_dir, 'script.sh')
    temp_sh_loc = os.path.join(wk_dir, '.logs/.temp/', time_dir, 'script.sh')
    sshd_sh_loc = os.path.join(HPC_GUI_PATH, 'src/templates/bash/sshd.sh')
    code_sh_loc = os.path.join(HPC_GUI_PATH, 'src/templates/bash/code_tunnel.sh')
    final_sh_loc = 'final_stage.sh'
    name = request.form['name']
    job_script = '#!/bin/bash\n#--------------------------------\n'
    job_script += f"#SBATCH -J {request.form['name']}\n"
    for k, v in request.form.items():
        if '#SBATCH' in k and v:
            job_script += f'{k}{v}\n'
    if raw_addi_args:
        addi_args = raw_addi_args.split(";")
        for kv in addi_args:
            job_script += f"#SBATCH {kv}\n"
    job_script += '#--------------------------------\n'

    job_script += '\n########################### BASH <<<<<<<<<<<<<<<<<<<<<<<<<<<<\n'
    command_lines = [line.strip() for line in request.form['job_script'].strip().split('\n') if line.strip()]
    commentted_lines = "\n".join(["# " + line for line in command_lines])
    job_script += commentted_lines

    code_enabled = 'interactive_code' in request.form
    sshd_enabled = 'interactive_sshd' in request.form
    final_stage_enabled = 'final_stage' in request.form
    is_wait = 'is_wait' in request.form

    if code_enabled:
        with open(code_sh_loc, 'r') as file:
            bash_script_content = file.read()
        job_script += '\n' + bash_script_content
    if sshd_enabled:
        with open(sshd_sh_loc, 'r') as file:
            bash_script_content = file.read()
        job_script += '\n' + bash_script_content

    job_script += f"\nexport HPC_GUI_PATH={HPC_GUI_PATH}"
    job_script += f"\nexport PY_SCRIPT_PATH={HPC_GUI_PATH}/src/templates/py"
    job_script += f"\nexport SH_SCRIPT_PATH={HPC_GUI_PATH}/src/templates/bash\n"

    job_script += '\n########################### 1st STAGE <<<<<<<<<<<<<<<<<<<<<<<<<<<<\n'
    with open(user_sh_loc, 'w') as file:
        file.write(request.form['job_script'].replace('\r\n', '\n'))
    shutil.copy(user_sh_loc, temp_sh_loc)
    job_script += f"python3 ${{PY_SCRIPT_PATH}}/run_script.py {temp_sh_loc} ${{SLURM_JOB_ID}}_1"

    if final_stage_enabled:
        job_script += '\n########################### 2nd STAGE <<<<<<<<<<<<<<<<<<<<<<<<<<<<\n'
        job_script += f"python3 ${{PY_SCRIPT_PATH}}/run_script.py ${{SH_SCRIPT_PATH}}/{final_sh_loc} ${{SLURM_JOB_ID}}_2"
    if is_wait:
        job_script += '\nwait'

    socketio.start_background_task(manager.submitJob, name, time_dir, wk_dir, job_script, script_loc,
                                   request.form['additional args'])

    last_submit_form = request.form
    with open(json_setting_loc, 'w') as file:
        json.dump(last_submit_form, file)
    json.dump(last_submit_form, open(os.path.join(HPC_GUI_PATH, 'last_submit_form.json'), 'w'))

    return ('', 204)


@socketio.on('connect')
def connect(message):
    join_room('slurm')
    print('Client connected')
    emit('update', manager.update_content, to='slurm')
    if 'selected_job_id' in session:
        emit('update', {'html': {
            'output': myEscape(outputs[session['selected_job_id']]),
            'job_script': myEscape(scripts[session['selected_job_id']])
        }}, to='slurm')

    #socketio.start_background_task(socketioLoop)


def socketioLoop():
    while True:
        socketio.emit('update', manager.update_content, to='slurm')

        if 'selected_job_id' in session:
            manager.UpdateOutput(session['selected_job_id'])
            if session['selected_job_id'] in outputs:
                socketio.emit('update', {'html': {'output': outputs[session['selected_job_id']]}}, to='slurm')
        socketio.sleep(5)


@socketio.on('update')
def update():
    emit('update', manager.update_content, to='slurm')
    #print('sacct', manager.update_content)
    if 'selected_job_id' in session:
        if manager.justSubmitted != None:
            emit('select', manager.justSubmitted, to='slurm')
            manager.justSubmitted = None
        manager.UpdateOutput(session['selected_job_id'])
        if session['selected_job_id'] in outputs and session['selected_job_id'] in scripts:
            emit('update', {'html': {
                'output': "<pre><code class='language-html'>" + myEscape(outputs[session['selected_job_id']]) + "</code></pre>",
                'job_script': "<pre><code class='shell'>" + myEscape(scripts[session['selected_job_id']]) + "</code></pre>",
            }}, to='slurm')


@socketio.on('disconnect')
def disconnect():
    print('Client disconnected')


@socketio.on('select_job')
def select_job(message):
    global g_selected_job_id
    job_id = message['job_id']
    session['selected_job_id'] = job_id
    manager.UpdateOutput(job_id)
    g_selected_job_id = job_id
    emit('update', {'html': {
        'output': myEscape(outputs[session['selected_job_id']]),
        'job_script': myEscape(scripts[session['selected_job_id']])
    }}, to='slurm')


@socketio.on('cancel_job')
def cancel_job(message):
    job_id = message['job_id']
    manager.cancelJob(job_id)


@socketio.on('kill_stage')
def kill_stage(message):
    job_id = message['job_id']
    manager.killStage(job_id)

class SlurmManager():
    def __init__(self):
        self.update_content = {}
        threading.Thread(target=self.Loop).start()

        if os.path.exists(os.path.join(HPC_GUI_PATH, 'data/jobs.json')):
            with open(os.path.join(HPC_GUI_PATH, 'data/jobs.json'), 'r') as f:
                self.jobs = json.load(f)

        else:
            self.jobs = {}

        self.justSubmitted = None

    def Loop(self):
        while True:
            self.Update()
            time.sleep(2)

    def update_job_outputs(self):
        for id in list(outputs.keys()):  # Use a list to avoid RuntimeError
            if self.jobs[id]['state'] in ['R', 'PD']:
                self.UpdateOutput(id)

    def update_job_states(self):
        sacct_output = cli('squeue -u $(whoami)')
        for id in list(self.jobs.keys()):
            is_id_in_line = False
            for line in sacct_output.split("\n"):
                if id in line:
                    self.update_job_details(line, id)
                    is_id_in_line = True
                    break
            if not is_id_in_line:
                self.jobs[id]['state'] = 'CP'  # Consider marking as COMPLETED
            self.UpdateOutput(id)  # Update output after state check

    def update_job_details(self, line, id):
        columns = line.split()
        self.jobs[id]['node'] = columns[-1]
        self.jobs[id]['state'] = columns[4]
        if self.jobs[id]['node']:
            self.fetch_process_ids(id)

    def fetch_process_ids(self, id):
        node = self.jobs[id]['node']
        pid_1 = cli(f"ssh {node} \"pgrep -f '^{id}_1'\"")
        pid_2 = cli(f"ssh {node} \"pgrep -f '^{id}_2'\"")
        self.jobs[id]['pid_1'] = pid_1
        self.jobs[id]['pid_2'] = pid_2

    def Update(self):
        sinfo = cli('sinfo')
        sacct = cli('squeue -u $(whoami)')
        # sacct_all = cli('sacct')
        self.update_job_outputs()
        self.update_job_states()

        self.update_content = {
            'html':  # Update html content
                {
                    'sinfo': formatSinfo(sinfo),
                    'sacct': formatSacct(sacct),
                    'jobs': generateJobList(self.jobs)
                }
        }

    def UpdateOutput(self, job_id):
        path = manager.jobs[job_id]['output']
        if os.path.exists(path):
            outputs[job_id] = cli(f'tail -n 1000 {path}')[-100000:]  #.replace('\n','<br>')
        else:
            outputs[job_id] = 'output file not found'

        path = manager.jobs[job_id]['script']
        if os.path.exists(path):
            scripts[job_id] = cli(f'cat {path}')  #.replace('\n','<br>')
        else:
            scripts[job_id] = 'missing'

    def submitJob(self, name, ts, wk_dir, job_script, script_loc, additional_args=''):
        print('submit ', name)
        os.makedirs(os.path.dirname(script_loc), exist_ok=True)
        # os.makedirs(os.path.dirname(output_loc),exist_ok=True)
        with open(script_loc, 'w') as f:
            f.write(job_script.replace('\r\n', '\n'))
        os.chmod(script_loc, 0o777)

        command = f'sbatch {script_loc}'
        print('command: ', command)
        o, err = cli(command, True)
        socketio.emit('update', {'html': {'message': o + '\n' + err}}, to='slurm')
        if 'Submitted batch job ' in o:
            job_id = o.split('Submitted batch job ')[-1].replace(' ', '').replace('\n', '')
            old_script_loc = script_loc
            old_json_loc = old_script_loc.replace(".sh", ".json")
            script_loc = old_script_loc.replace(ts, job_id)
            json_loc = script_loc.replace(".sh", ".json")
            output_loc = os.path.join(wk_dir, 'slurm-' + job_id + '.out')
            if os.path.exists(os.path.dirname(old_script_loc)):
                # Rename the old directory to the new directory
                old_script_dir = os.path.dirname(old_script_loc)
                script_dir = os.path.dirname(script_loc)
                os.rename(old_script_dir, script_dir)

                # Rename the old file to the new file
                old_script_loc = os.path.join(script_dir, ts + ".sh")
                old_json_loc = os.path.join(script_dir, ts + ".json")
                os.rename(old_script_loc, script_loc)
                os.rename(old_json_loc, json_loc)

            self.jobs[job_id] = {'id': job_id, 'name': name, 'state': 'PD', 'script': script_loc, 'output': output_loc,
                                 'ts': ts, 'node': 'UNKNOWN', 'pid_1': '', 'pid_2': ''}
            self.justSubmitted = job_id
            wk_script_directory = os.path.dirname(script_loc)
            wk_job_path = os.path.join(wk_script_directory, "job_info.json")
            with open(os.path.join(wk_job_path), 'w') as f:
                json.dump(self.jobs[job_id], f)
            with open(os.path.join(HPC_GUI_PATH, 'data/jobs.json'), 'w') as f:
                json.dump(self.jobs, f)

    def cancelJob(self, job_id):
        o = cli(f'scancel {job_id}')
        socketio.emit('update', {'html': {'message': o}}, to='slurm')

    def killStage(self, job_id):
        print(f"ssh {self.jobs[job_id]['node']} \"kill {self.jobs[job_id]['pid_1']}\"")
        o = cli(f"ssh {self.jobs[job_id]['node']} \"kill -9 {self.jobs[job_id]['pid_1']}\"")
        time.sleep(5)
        o = cli(f"ssh {self.jobs[job_id]['node']} \"kill -9 {self.jobs[job_id]['pid_2']}\"")
        socketio.emit('update', {'html': {'message': o}}, to='slurm')

    def callback_attachJob(self, job_id, result):
        # 更新UI或处理结果
        print("Received result:", result)
        socketio.emit('update', {'html': {'message_attach': f'Job {job_id} attached successfully.'}}, to='slurm')

    def attachJob(self, job_id, name, script):
        wk_dir = os.path.join('/', *os.path.split(self.jobs[job_id]['script'])[0].split(os.sep)[:-2], '')
        time_dir = int(time.time()).__str__()
        os.makedirs(os.path.join(wk_dir, 'attach', time_dir), exist_ok=True)
        print(os.path.join(wk_dir, 'attach', time_dir))
        temp_sh_loc = os.path.join(wk_dir, 'attach', time_dir, f'{name}.sh')
        temp_out_loc = os.path.join(wk_dir, 'attach', time_dir, f'{name}.out')
        with open(temp_sh_loc, 'w') as file:
            file.write(script.replace('\r\n', '\n'))

        callback_with_job_id = partial(self.callback_attachJob, job_id)
        cli_bg(f"ssh {self.jobs[job_id]['node']} \"source /etc/profile;source "
               f"~/anaconda3/etc/profile.d/conda.sh;conda activate slurmgui;"
               f"python3 {HPC_GUI_PATH}/src/templates/py/run_script.py {temp_sh_loc} {job_id}_1 {temp_out_loc}\"",
               return_err=True, callback=callback_with_job_id)


def cli_bg(command, return_err=False, callback=None):
    def run():
        print("Thread started")
        process = subprocess.Popen([command], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out = process.communicate()
        print("Command executed")
        if return_err:
            result = (out[0].decode("latin-1"), out[1].decode("latin-1"))
        else:
            result = out[0].decode("latin-1")

        if callback:
            callback(result)
        print("Callback called")

    thread = threading.Thread(target=run)
    thread.start()
    print("Thread launched")


def cli(command, return_err=False):
    process = subprocess.Popen([command], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out = process.communicate()
    '''
    if process.returncode != 0:
        raise Exception(out[1].decode("latin-1") )
    '''
    if return_err:
        return out[0].decode("latin-1"), out[1].decode("latin-1")
    else:
        return out[0].decode("latin-1")


def formatSinfo(sinfo):
    res = '<table class="w-full text-sm text-center rtl:text-center text-gray-500 dark:text-gray-400">'
    res += '<thead class="text-xs text-gray-700 uppercase bg-gray-50 dark:bg-gray-700 dark:text-gray-400">'
    res += '<tr><th>Partition</th><th>Avail</th><th>Timelimit</th><th>Nodes</th><th>State</th><th>Nodelist</th></tr>'
    res += '</thead>'
    res += '<tbody>'
    for idx, line in enumerate(sinfo.split('\n')):
        if idx:
            fields = line.split()
            l = '<tr class="odd:bg-white odd:dark:bg-gray-900 even:bg-gray-50 even:dark:bg-gray-800">'
            for f in fields:
                if 'drain' in f or 'alloc' in f or 'down' in f or 'drng' in f:
                    l += f'<td><span class="bg-red-100 text-red-800 text-sm font-medium me-2 px-2.5 py-0.5 rounded dark:bg-red-900 dark:text-red-300">{f}</span></td>'
                    continue
                if 'idle' in f:
                    l += f'<td><span class="bg-green-100 text-green-800 text-sm font-medium me-2 px-2.5 py-0.5 rounded dark:bg-green-900 dark:text-green-300">{f}</span></td>'
                    continue
                elif 'mix' in f or 'comp' in f:
                    l += f'<td><span class="bg-yellow-100 text-yellow-800 text-sm font-medium me-2 px-2.5 py-0.5 rounded dark:bg-yellow-900 dark:text-yellow-300">{f}</span></td>'
                    continue
                else:
                    l += f'<td>{f}</td>'
                    continue
            l += "</tr>"
            res += l
    res += '</tbody>'
    res += '</table>'
    return res


def formatSacct(sacct):
    res = '<table class="w-full text-sm text-center rtl:text-center text-gray-500 dark:text-gray-400">'
    res += '<thead class="text-xs text-gray-700 uppercase bg-gray-50 dark:bg-gray-700 dark:text-gray-400">'
    res += '<tr><th>JOBID</th><th>Partition</th><th>Name</th><th>User</th><th>ST</th><th>Time</th><th>Nodes</th><th>Nodelist</th></tr>'
    res += '</thead>'
    res += '<tbody>'
    for idx, line in enumerate(sacct.split('\n')):
        if idx:
            fields = line.split()
            l = '<tr class="odd:bg-white odd:dark:bg-gray-900 even:bg-gray-50 even:dark:bg-gray-800 border-b dark:border-gray-700">'
            for f in fields:
                l += f'<td>{f}</td>'
            l += "</tr>"
            res += l
    res += '</tbody>'
    res += '</table>'
    return res


def generateJobList(jobs):
    res = '<thead class="text-xs text-gray-700 uppercase bg-gray-50 dark:bg-gray-700 dark:text-gray-400">'
    res += f'<tr><th>JOBID</th><th>Nodelist</th><th>Name</th><th>State</th><th>SubmitOn</th><th>PID_1</th><th>PID_2</th></tr>'
    res += f'</thead>'
    res += '<tbody>'
    for job in jobs.values():
        if job["state"] == 'R' or job["state"] == 'PD':
            timestamp = os.path.basename(job["ts"])
            dt = datetime.fromtimestamp(int(timestamp)).strftime('%m-%d %H:%M:%S')
            res += f'<tr class="selectable text-gray-500 dark:text-gray-400" id="{job["id"]}"><td>{job["id"]}</td><td>{job["node"]}</td><td>{job["name"]}</td><td>{job["state"]}</td><td>{dt}</td><td style="color:#28C73F">{job["pid_1"]}</td><td style="color:#FE5F58">{job["pid_2"]}</td></tr>'
    res += f'</tbody>'
    res += f'</table>'
    return res


manager = SlurmManager()
