from flask import Blueprint,render_template,session, request, redirect,url_for, escape
from flask_login import login_required
import flask
import subprocess
import threading
import shutil
from . import socketio
from flask_socketio import emit, join_room
import json, os
import re
from datetime import datetime
bp = Blueprint('slurm', __name__, url_prefix='/slurm')

outputs = {}
scripts = {}
last_submit_form = {}

HPC_GUI_PATH = os.getcwd()

def relative(path):
    return os.path.join(os.path.dirname(os.path.realpath(__file__)), path)

def relative_to_root(path):
    return os.path.join(os.getcwd(), path)

def myEscape(text):
    rep = '1g4x9s' # random string
    text = text.replace('\n',rep)
    text = str(escape(text))
    text = text.replace(rep,'<br>')
    return text

@bp.route('/')
@login_required
def slurm():
    global last_submit_form
    os.makedirs('data',exist_ok=True)
    htmldata = json.load(open('config.json'))
    if os.path.exists('last_submit_form.json'):
        last_submit_form = json.load(open('last_submit_form.json'))
    session['last_submit_form'] = last_submit_form 
    return render_template('slurm/slurm.html',htmldata=htmldata)

@bp.route('/load_json_job', methods=['POST'])
@login_required
def loadJsonJob():
    htmldata = json.load(open('config.json'))
    htmldata["is_load"] = True
    json_path = os.path.expanduser(request.form['load_json_path'])
    if os.path.exists(json_path) and json_path.endswith('.json'):
        last_submit_form = json.load(open(json_path))
        session['last_submit_form'] = last_submit_form 
        return render_template('slurm/slurm.html',htmldata=htmldata)

    else:
        socketio.emit('update', {'html':{'message_json':'ERROR: json file not exsit!'}},to='slurm')
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
        socketio.emit('update', {'html':{'message':'ERROR: working dir (--chdir) not exsit!'}},to='slurm')
        return ('', 204)
    os.makedirs(os.path.join(wk_dir, '.logs/job_scripts', time_dir), exist_ok=True)
    os.makedirs(os.path.join(wk_dir, '.logs/.temp', time_dir), exist_ok=True)
    script_loc = os.path.join(wk_dir, '.logs/job_scripts', time_dir, time_dir+'.sh')
    json_setting_loc = os.path.join(wk_dir, '.logs/job_scripts', time_dir, time_dir+'.json')
    user_sh_loc = os.path.join(wk_dir, '.logs/job_scripts', time_dir, 'script.sh')
    temp_sh_loc = os.path.join(wk_dir, '.logs/.temp/', time_dir, 'script.sh')
    sshd_sh_loc = 'src/templates/bash/sshd.sh'
    code_sh_loc = 'src/templates/bash/code_tunnel.sh'
    final_sh_loc = 'final_stage.sh'
    name = request.form['name']
    job_script='#!/bin/bash\n#--------------------------------\n'
    job_script +=f"#SBATCH -J {request.form['name']}\n"
    for k,v in request.form.items():
        if '#SBATCH' in k and v: 
            job_script += f'{k}{v}\n'
    if raw_addi_args:
        addi_args = raw_addi_args.split(";")
        for kv in addi_args:
            job_script +=f"#SBATCH {kv}\n"
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
        job_script += '\n'+ bash_script_content
    if sshd_enabled:
        with open(sshd_sh_loc, 'r') as file:
            bash_script_content = file.read()
        job_script += '\n'+ bash_script_content
    
    job_script += f"\nPY_SCRIPT_PATH={HPC_GUI_PATH}/src/templates/py"
    job_script += f"\nSH_SCRIPT_PATH={HPC_GUI_PATH}/src/templates/bash\n"
    
    job_script += '\n########################### 1st STAGE <<<<<<<<<<<<<<<<<<<<<<<<<<<<\n'
    with open(user_sh_loc, 'w') as file:
        file.write(request.form['job_script'].replace('\r\n','\n'))
    shutil.copy(user_sh_loc, temp_sh_loc)
    job_script += f"python ${{PY_SCRIPT_PATH}}/run_script.py {temp_sh_loc} ${{SLURM_JOB_ID}}_1a"
    
    if final_stage_enabled:
        job_script += '\n########################### 2nd STAGE <<<<<<<<<<<<<<<<<<<<<<<<<<<<\n'
        job_script += f"python ${{PY_SCRIPT_PATH}}/run_script.py ${{SH_SCRIPT_PATH}}/{final_sh_loc} ${{SLURM_JOB_ID}}_2"
    if is_wait:
        job_script += '\nwait'
    
    socketio.start_background_task(manager.submitJob, name, time_dir, wk_dir, job_script, script_loc, request.form['additional args'])

    last_submit_form = request.form
    with open(json_setting_loc, 'w') as file:
        json.dump(last_submit_form, file)
    json.dump(last_submit_form, open('last_submit_form.json','w'))

    return ('', 204)

@socketio.on('connect')
def connect(message):
    join_room('slurm')
    print('Client connected')
    emit('update', manager.update_content,to='slurm')
    if 'selected_job_id' in session:
        emit('update', {'html':{
            'output':myEscape(outputs[session['selected_job_id']]),
            'job_script':myEscape(scripts[session['selected_job_id']])
        }},to='slurm')

 
    #socketio.start_background_task(socketioLoop)


def socketioLoop():
    while True:
        socketio.emit('update', manager.update_content,to='slurm')
        
        if  'selected_job_id' in session:
            manager.UpdateOutput(session['selected_job_id'])
            if session['selected_job_id'] in outputs:
                socketio.emit('update', {'html':{'output':outputs[session['selected_job_id']]}},to='slurm')
        socketio.sleep(5)

@socketio.on('update')
def update():
    emit('update', manager.update_content,to='slurm')
    #print('sacct', manager.update_content)
    if  'selected_job_id' in session:
        if manager.justSubmitted != None:
            emit('select', manager.justSubmitted,to='slurm')
            manager.justSubmitted = None
        manager.UpdateOutput(session['selected_job_id'])
        if session['selected_job_id'] in outputs and session['selected_job_id'] in scripts:
            emit('update', {'html':{
                'output':myEscape(outputs[session['selected_job_id']]),
                'job_script':myEscape(scripts[session['selected_job_id']])
            }},to='slurm')

@socketio.on('disconnect')
def disconnect():
    print('Client disconnected')

@socketio.on('select_job')
def select_job(message):
    job_id = message['job_id']
    session['selected_job_id'] = job_id
    manager.UpdateOutput(job_id)
    emit('update', {'html':{
            'output':myEscape(outputs[session['selected_job_id']]),
            'job_script':myEscape(scripts[session['selected_job_id']])
        }},to='slurm')

@socketio.on('cancel_job')
def cancel_job(message):
    job_id = message['job_id']
    manager.cancelJob(job_id)
    

import time
class SlurmManager():
    def __init__(self):
        self.update_content = {}
        threading.Thread(target=self.Loop).start()

        if os.path.exists('data/jobs.json'):
            with open('data/jobs.json', 'r') as f:
                self.jobs = json.load(f)
            # command = 'squeue -u mznv82 -o "%.18i %.9P %.8j %.8u %.2t %.10M %.6D %R"'
            # result = cli(command)
            
            # lines = result.strip().split('\n')
            # jobs_data = []
            # for line in lines:
            #     fields = line.split()
            #     if len(fields) == 8:
            #         job_dict = {
            #             "id": fields[0],
            #             "partition": fields[1],
            #             "name": fields[2],
            #             "user": fields[3],
            #             "state": fields[4],
            #             "time": fields[5],
            #             "nodes": fields[6],
            #             "nodelist": fields[7]
            #         }
                    
            #         if job_dict["id"] != "JOBID":
            #             jobs_data.append(job_dict)
            
            # jobs_data = {d['id']: d for d in jobs_data}
            # self.jobs = jobs_data

        else:
            self.jobs = {}

        self.justSubmitted = None

    def Loop(self):
        while True:
            self.Update()
            time.sleep(2)

    
    def Update(self):
        sinfo = cli('sinfo')
        sacct_all = cli('sacct')
        sacct = cli('squeue -u $(whoami)')
        
        for id in outputs.keys():
            if self.jobs[id]['state'] == 'R' or self.jobs[id]['state'] == 'PD':
                self.UpdateOutput(id)

        for id in self.jobs.keys():
            if self.jobs[id]['state'] == 'R' or self.jobs[id]['state'] == 'PD':
                is_id_in_line = 0 # NOT in Lines
                for line in sacct.split("\n"):
                    if id in line:
                        columns = line.split()
                        self.jobs[id]['node'] = columns[-1]
                        self.jobs[id]['state'] = columns[4]
                        is_id_in_line = 1
                if not is_id_in_line:
                    self.jobs[id]['state'] = 'CP'  # CP for COMPLETED
                self.UpdateOutput(id)
                    

        self.update_content = {
            'html': # Update html content
                {
                    'sinfo':formatSinfo(sinfo),
                    'sacct':formatSacct(sacct),
                    'jobs':generateJobList(self.jobs)
                }
            }

    def UpdateOutput(self,job_id):
        path = manager.jobs[job_id]['output']
        if os.path.exists(path):
            outputs[job_id] = cli(f'tail -n 1000 {path}')[-100000:]#.replace('\n','<br>')
        else:
            outputs[job_id] = 'output file not found'

        path = manager.jobs[job_id]['script']
        if os.path.exists(path):
            scripts[job_id] = cli(f'cat {path}')#.replace('\n','<br>')
        else:
            scripts[job_id] = 'missing'

    def submitJob(self,name, ts,wk_dir, job_script,script_loc, additional_args = ''):
        print('submit' ,name)
        os.makedirs(os.path.dirname(script_loc),exist_ok=True)
        # os.makedirs(os.path.dirname(output_loc),exist_ok=True)
        with open(script_loc,'w') as f:
            f.write(job_script.replace('\r\n','\n'))
        os.chmod(script_loc, 0o777)
        
        command = f'sbatch {script_loc}'
        print('command: ',command)
        o, err = cli(command,True)
        socketio.emit('update', {'html':{'message':o +'\n'+ err}},to='slurm')
        if 'Submitted batch job ' in o:
            job_id = o.split('Submitted batch job ')[-1].replace(' ','').replace('\n','')
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
                old_script_loc = os.path.join(script_dir, ts+".sh")
                old_json_loc = os.path.join(script_dir, ts+".json")
                os.rename(old_script_loc, script_loc)
                os.rename(old_json_loc, json_loc)
                
            self.jobs[job_id]={'id':job_id,'name':name,'state':'PD','script':script_loc,'output':output_loc,'ts':ts,'node':'UNKNOWN'}
            self.justSubmitted = job_id
            wk_script_directory = os.path.dirname(script_loc)
            wk_job_path = os.path.join(wk_script_directory, "job_info.json")
            with open(os.path.join(wk_job_path), 'w') as f:
                json.dump(self.jobs[job_id],f)
            with open('data/jobs.json', 'w') as f:
                json.dump(self.jobs,f)

    def cancelJob(self,job_id):
        o = cli(f'scancel {job_id}')
        socketio.emit('update', {'html':{'message':o}},to='slurm')

def cli(command,return_err = False):
    process = subprocess.Popen([command],shell = True ,stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
    res = '<tr><th>Partition</th><th>Availability</th><th>Timelimit</th><th>Nodes</th><th>State</th><th>Nodelist</th></tr>'
    for idx, line in enumerate(sinfo.split('\n')):
        if idx:
            fields = line.split()
            l = "<tr>"
            for f in fields:
                if 'drain' in f or 'alloc' in f or 'down' in f or 'drng' in f:
                    l += f'<td style="color:#FE5F58">{f}</td>'
                    continue
                if 'idle' in f:
                    l += f'<td style="color:#28C73F">{f}</td>'
                    continue
                elif 'mix' in f or 'comp' in f:
                    l += f'<td style="color:#FEBB2C">{f}</td>'
                    continue
                else:
                    l += f'<td>{f}</td>'
                    continue
            l += "</tr>"
            res += l
        res += line
    return res 

def formatSacct(sacct):
    res = '<tr><th>JOBID</th><th>Partition</th><th>Name</th><th>User</th><th>ST</th><th>Time</th><th>Nodes</th><th>Nodelist</th></tr>'
    for idx, line in enumerate(sacct.split('\n')):
        if idx:
            fields = line.split()
            l = "<tr>"
            for f in fields:
                l += f'<td>{f}</td>'
            l += "</tr>"
            res += l
    return res

def generateJobList(jobs):
    res = '<tr><th>JOBID</th><th>Nodelist</th><th>Name</th><th>State</th><th>SubmitOn</th></tr>'
    for job in jobs.values():
        if job["state"] == 'R' or job["state"] == 'PD':
            timestamp = os.path.basename(job["ts"])
            dt = datetime.fromtimestamp(int(timestamp)).strftime('%Y-%m-%d %H:%M:%S')
            res += f'<tr class="selectable" id="{job["id"]}"><td>{job["id"]}</td><td>{job["node"]}</td><td>{job["name"]}</td><td>{job["state"]}</td><td>{dt}</td></tr>'
    return res

manager = SlurmManager()