# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

import os

from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from importlib import import_module
from datetime import datetime
<<<<<<< Updated upstream
from apps.reports.agents.ifpia import carregar_documentos

=======
>>>>>>> Stashed changes

db = SQLAlchemy()
login_manager = LoginManager()


def register_extensions(app):
    db.init_app(app)
    login_manager.init_app(app)


def register_blueprints(app):
    for module_name in ('authentication', 'home', 'reports'):
        module = import_module('apps.{}.routes'.format(module_name))
        app.register_blueprint(module.blueprint)


def configure_database(app):

    @app.before_first_request
    def initialize_database():
        try:
            db.create_all()
        except Exception as e:

            print('> Error: DBMS Exception: ' + str(e) )

            # fallback to SQLite
            basedir = os.path.abspath(os.path.dirname(__file__))
            app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'db.sqlite3')

            print('> Fallback to SQLite ')
            db.create_all()

    @app.teardown_request
    def shutdown_session(exception=None):
        db.session.remove()


def create_app(config):
    app = Flask(__name__)
    MESES = {
        1: "janeiro", 2: "fevereiro", 3: "março",   4: "abril",
        5: "maio",    6: "junho",    7: "julho",   8: "agosto",
        9: "setembro",10:"outubro", 11:"novembro",12:"dezembro"
    }

    def format_pt_datetime(value):
        try:
            dt = datetime.strptime(value, "%a %b %d %H:%M:%S UTC %Y")
            return f"{dt:%H:%M} de {dt.day:02d} de {MESES[dt.month]} de {dt.year}"
        except:
            return value
    app.jinja_env.filters['format_pt_datetime'] = format_pt_datetime        
    app.config.from_object(config)
    register_extensions(app)
    register_blueprints(app)
    configure_database(app)
    return app

<<<<<<< Updated upstream
def inicializar_chatbot():
    try:
        carregar_documentos()
        print("Documentos carregados com sucesso.")
    except Exception as e:
        print(f"Erro ao carregar documentos: {e}")
=======

>>>>>>> Stashed changes
