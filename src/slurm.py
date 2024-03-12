from flask import Blueprint,render_template,session, request, redirect,url_for, escape
from flask_login import login_required
import flask
import subprocess
import threading
from . import socketio
from flask_socketio import emit, join_room
import json, os
import re
bp = Blueprint('slurm', __name__, url_prefix='/slurm')

outputs = {}
scripts = {}
last_submit_form = {}

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

@bp.route('/submit_job', methods=['POST'])
@login_required
def submitJob():
    script_loc = 'data/job_scripts/'+int(time.time()).__str__()+'.sh'
    output_loc =  relative_to_root('data/outputs/'+int(time.time()).__str__())
    sshd_sh_loc = 'src/templates/bash/sshd.sh'
    code_sh_loc = 'src/templates/bash/code_tunnel.sh'
    final_sh_loc = 'src/templates/bash/final_stage.sh'
    name = request.form['name']
    job_script='#!/bin/bash\n#--------------------------------\n'
    job_script +=f"#SBATCH -J {request.form['name']}\n"
    job_script +=f"#SBATCH --output={output_loc}\n"
    for k,v in request.form.items():
        if '#SBATCH' in k and v: 
            job_script += f'{k}{v}\n'
    job_script += '#--------------------------------\n'
    
    code_enabled = 'interactive_code' in request.form
    sshd_enabled = 'interactive_sshd' in request.form
    final_stage_enabled = 'final_stage'  in request.form
    if code_enabled:
        with open(code_sh_loc, 'r') as file:
            bash_script_content = file.read()
        job_script += '\n'+ bash_script_content
    if sshd_enabled:
        with open(sshd_sh_loc, 'r') as file:
            bash_script_content = file.read()
        job_script += '\n'+ bash_script_content
        
    job_script += '\n###########################  <<<<<<<<<<<<<<<<<<<<<<<<<<<<\n'
    job_script += '\n'+ request.form['job_script']
    if final_stage_enabled:
        with open(final_sh_loc, 'r') as file:
            bash_script_content = file.read()
        job_script += '\n'+ bash_script_content
        job_script += '\n'+ 'wait'
    socketio.start_background_task(manager.submitJob, name, job_script, script_loc, output_loc, request.form['additional args'])

    last_submit_form = request.form
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
        sacct = cli('squeue -u $(whoami) | awk \'{printf "%-10s %-10s %-10s %-10s %-10s %-10s %-10s %-10s %-10s\\n", $1, $2, $3, $4, $5, $6, $7, $8, $9}\'')
        
        for id in outputs.keys():
            if self.jobs[id]['state'] == 'RUNNING'or self.jobs[id]['state'] == 'PENDING':
                self.UpdateOutput(id)

        for id in self.jobs.keys():
            if self.jobs[id]['state'] == 'RUNNING' or self.jobs[id]['state'] == 'PENDING':
                for line in sacct_all.split('\n'):
                    if len(re.findall("[0-9]+ ",line))>0 and re.findall("[0-9]+ ",line)[0][:-1] == id:
                        self.jobs[id]['state'] = list(filter(lambda x: x!='', line.split(' ')))[5]
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

    def submitJob(self,name, job_script,script_loc,output_loc, additional_args = ''):
        print('submit' ,name)
        os.makedirs(os.path.dirname(script_loc),exist_ok=True)
        os.makedirs(os.path.dirname(output_loc),exist_ok=True)
        with open(script_loc,'w') as f:
            f.write(job_script.replace('\r\n','\n'))
        os.chmod(script_loc, 0o777)
        
        command = f'sbatch {additional_args} {script_loc}'
        print('command: ',command)
        o, err = cli(command,True)
        socketio.emit('update', {'html':{'message':o +'\n'+ err}},to='slurm')
        print('submit message',o)
        if 'Submitted batch job ' in o:
            job_id = o.split('Submitted batch job ')[-1].replace(' ','').replace('\n','')
            self.jobs[job_id]={'id':job_id,'name':name,'state':'PENDING','script':script_loc,'output':output_loc}
            self.justSubmitted = job_id
        else: 
            print("submit failed!")
            print(o)
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
                if 'drain' in f or 'alloc' in f:
                    l += f'<td style="color:#FE5F58">{f}</td>'
                    continue
                if 'idle' in f:
                    l += f'<td style="color:#28C73F">{f}</td>'
                    continue
                elif 'mix' in f:
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
    res = '<tr><th>JOBID</th><th>Name</th><th>State</th></tr>'
    for job in jobs.values():
        if job["state"] == 'RUNNING' or job["state"] == 'PENDING':
            res += f'<tr class="selectable" id="{job["id"]}"><td>{job["id"]}</td><td>{job["name"]}</td><td>{job["state"]}</td></tr>'
    return res

manager = SlurmManager()