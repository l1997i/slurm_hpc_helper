import os.path
import subprocess

from flask import Flask
from flask_socketio import SocketIO
from flask import request, Flask, Blueprint, flash, g, redirect, render_template, session, url_for
from src import socketio, create_app
from src import resource_path
from engineio.async_drivers import gevent
import json

def get_executable_path(executable_name):
    result = subprocess.run(["which", executable_name], capture_output=True, text=True)
    if result.returncode == 0:
        return result.stdout.strip()
    else:
        return None

def change_to_executable_directory(executable_name):
    path = get_executable_path(executable_name)
    if path:
        directory = os.path.dirname(path)
        os.chdir(directory)
        print(f"Changed working directory to {directory}")

def run():
    app = create_app()
    socketio.init_app(app)
    app.secret_key = __import__('os').urandom(24)
    socketio.run(app, debug=True, port=int(json.load(open(os.path.join(os.getcwd(), 'config.json')))["port"]))


if __name__ == '__main__':
    executable_name = "hpc_helper"
    change_to_executable_directory(executable_name)
    run()
