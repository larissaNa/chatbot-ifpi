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


db = SQLAlchemy()
login_manager = LoginManager()


def register_extensions(app):
    db.init_app(app)
    login_manager.init_app(app)


def register_blueprints(app):
    for module_name in ("authentication", "home.routes", "core"):
        module = import_module("apps.{}".format(module_name))
        app.register_blueprint(module.blueprint)


def configure_database(app):
    with app.app_context():
        engine_options = app.config.get("SQLALCHEMY_ENGINE_OPTIONS") or {}
        connect_args = dict(engine_options.get("connect_args") or {})
        connect_args.setdefault("connect_timeout", int(os.getenv("DB_CONNECT_TIMEOUT", "5")))
        engine_options["connect_args"] = connect_args
        engine_options.setdefault("pool_pre_ping", True)
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = engine_options

        try:
            db.create_all()
        except Exception as e:
            print("DB Error:", e)
            basedir = os.path.abspath(os.path.dirname(__file__))
            app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(basedir, "db.sqlite3")
            try:
                try:
                    db.engine.dispose()
                except Exception:
                    pass
                db.create_all()
            except Exception as e2:
                print("DB Error:", e2)

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
