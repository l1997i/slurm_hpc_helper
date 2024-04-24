from flask import Flask
from flask_login import LoginManager
from flask_socketio import SocketIO
from flask import session, redirect, render_template, url_for
import os, sys

socketio = SocketIO(async_mode='gevent')
login_manager = LoginManager()


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = ""
    return os.path.join(base_path, relative_path)


def create_app():
    app = Flask(__name__.split('.')[0])

    login_manager.init_app(app)

    from . import auth, posts, slurm
    for module in [auth, posts, slurm]:
        app.register_blueprint(module.bp)

    @app.route('/', methods=["GET", "POST"])
    def index():
        if not session.get('logged_in', False):
            return redirect(url_for('auth.login'))
        return render_template('index.html')

    return app
