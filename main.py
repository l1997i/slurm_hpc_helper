import os.path

from flask import Flask
from flask_socketio import SocketIO
from flask import request, Flask, Blueprint, flash, g, redirect, render_template, session, url_for
from src import socketio, create_app
from src import resource_path
from engineio.async_drivers import gevent
import json


def run():
    app = create_app()
    socketio.init_app(app)
    app.secret_key = __import__('os').urandom(24)
    socketio.run(app, debug=True, port=int(json.load(open(os.path.join(os.getcwd(), 'config.json')))["port"]))


if __name__ == '__main__':
    run()
