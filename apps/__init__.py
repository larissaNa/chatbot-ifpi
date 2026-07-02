# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

import os
import time

from flask import Flask

# Instala interceptor de logs antes de qualquer print do sistema
from apps.log_buffer import install as _install_log_buffer
_install_log_buffer()
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

        retries = 5
        while retries > 0:
            try:
                db.create_all()
                print(f"Conexão com o banco de dados estabelecida com sucesso. URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
                break
            except Exception as e:
                retries -= 1
                print(f"Erro ao conectar ao banco de dados ({app.config['SQLALCHEMY_DATABASE_URI']}): {e}. Tentando novamente em 5 segundos... ({retries} tentativas restantes)")
                if retries == 0:
                    print("Falha ao conectar ao banco de dados após várias tentativas. Alternando para SQLite.")
                    basedir = os.path.abspath(os.path.dirname(__file__))
                    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(basedir, "db.sqlite3")
                    try:
                        try:
                            db.engine.dispose()
                        except Exception:
                            pass
                        db.create_all()
                        print("Banco de dados SQLite configurado como fallback.")
                    except Exception as e2:
                        print("Erro fatal ao configurar SQLite fallback:", e2)
                else:
                    time.sleep(5)

    @app.teardown_request
    def shutdown_session(exception=None):
        db.session.remove()


def register_revision_scheduler(app):
    """
    Registra o ciclo de revisão de crenças no scheduler compartilhado,
    executado de forma recorrente a cada 24 horas sobre todos os documentos
    oficiais ativos (ver executar_ciclo_revisao no revision_orchestrator).

    Pode ser desabilitado com REVISION_CYCLE_ENABLED=0 (útil em testes e
    ambientes de desenvolvimento com auto-reload, que criam múltiplos processos).
    """
    if os.getenv("REVISION_CYCLE_ENABLED", "1").strip().lower() in ("0", "false", "no"):
        print("[SCHEDULER] Ciclo de revisão de crenças desabilitado via REVISION_CYCLE_ENABLED.")
        return

    # Import tardio: apps.core.config valida variáveis de ambiente na importação
    # e o orchestrator importa `apps.db` (evita import circular no topo do módulo).
    from apps.core.config import scheduler

    def _executar_ciclo_com_contexto():
        with app.app_context():
            from apps.core.documents.services.revision_orchestrator import executar_ciclo_revisao
            executar_ciclo_revisao()

    scheduler.add_job(
        _executar_ciclo_com_contexto,
        trigger="interval",
        hours=24,
        id="ciclo_revisao_crencas",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    print("[SCHEDULER] Ciclo de revisão de crenças registrado (intervalo: 24 horas).")


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
    register_revision_scheduler(app)
    return app
