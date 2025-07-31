# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from flask_login import UserMixin
import requests

from apps import db, login_manager

from apps.authentication.util import hash_pass

from datetime import datetime

from apps.integracoes.clientes import executar_consulta



class Users(db.Model, UserMixin):

    __tablename__ = 'Users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True)
    email = db.Column(db.String(64), unique=True)
    password = db.Column(db.LargeBinary)
    perfil = db.Column(db.String(20), default='Usuário')  # Novo campo
    avatar_url = db.Column(db.String(255), default='/static/img/avatar.png')  # Novo campo

    def __init__(self, **kwargs):
        for property, value in kwargs.items():
            # depending on whether value is an iterable or not, we must
            # unpack it's value (when **kwargs is request.form, some values
            # will be a 1-element list)
            if hasattr(value, '__iter__') and not isinstance(value, str):
                # the ,= unpack of a singleton fails PEP8 (travis flake8 test)
                value = value[0]

            if property == 'password':
                value = hash_pass(value)  # we need bytes here (not plain str)

            setattr(self, property, value)
    @property
    def is_admin(self):
        return self.perfil == 'Administrador'
    
    def __repr__(self):
        return str(self.username)

class UserCredits(db.Model):
    __tablename__ = 'user_credits'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False, unique=True)
    balance = db.Column(db.Integer, default=0)

class CreditOperation(db.Model):
    __tablename__ = 'credit_operations'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    type = db.Column(db.String(20))  # 'compra' ou 'uso'
    amount = db.Column(db.Integer)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.String(255))
    
    consulta_id = db.Column(db.Integer, db.ForeignKey("consulta_social.id", ondelete="CASCADE"), nullable=True)
    # consulta = db.relationship("ConsultaSocial", backref="credit_operations")
    consulta = db.relationship(
        "ConsultaSocial",
        backref=db.backref(
            "credit_operations",
            cascade="all, delete-orphan",
            passive_deletes=True
        ),
        passive_deletes=True
    )
class Servico(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    endpoint_api = db.Column(db.String(255), nullable=True)
    tipo_conteudo = db.Column(db.String(100))
    custo_credito = db.Column(db.Float, default=1.0)
    ativo = db.Column(db.Boolean, default=True)

    api_token = db.Column(db.String(255), nullable=True)
    api_username = db.Column(db.String(100), nullable=True)
    api_password = db.Column(db.String(100), nullable=True)

#ContaSocial#

class ContaSocial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome_usuario = db.Column(db.String(100), nullable=False)
    servico_id = db.Column(db.Integer, db.ForeignKey("servico.id"), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey("Users.id"), nullable=False)

    servico = db.relationship("Servico", backref="contas")
    usuario = db.relationship("Users", backref="contas_sociais")


class ConsultaSocial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conta_id = db.Column(db.Integer, db.ForeignKey("conta_social.id", ondelete="CASCADE"), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey("Users.id"), nullable=False)
    data_inicio = db.Column(db.Date)
    data_fim = db.Column(db.Date)
    tipo_conteudo = db.Column(db.String(100))
    limite_resultados = db.Column(db.Integer, default=10)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    creditos_consumidos = db.Column(db.Float)

    conta = db.relationship(
        "ContaSocial",
        backref=db.backref(
            "consultas",                 # cria ContaSocial.consultas
            cascade="all, delete-orphan",
            passive_deletes=True         # evita UPDATE para NULL
        ),
        passive_deletes=True             # idem do lado filho
    )
    usuario = db.relationship("Users", backref="consultas_sociais")
    
    def fetch_kpi_from_api(self, data_inicio, data_fim) -> dict:
        """
        Busca diretamente na API externa os KPIs
        relativos a este perfil.
        """
        # token      = current_app.config['FANPAGEKARMA_TOKEN']
        # profile_id = self.profile_id  # ou o campo correto no seu modelo
        resp = executar_consulta(
            self.conta.servico,
            {
                "profile_id": self.conta.nome_usuario,
                "task": "kpi",
                "inicio":data_inicio,
                "fim":data_fim
                
            }
        )
        return resp.get('data', {})

class ResultadoConsulta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    consulta_id = db.Column(db.Integer, db.ForeignKey("consulta_social.id", ondelete="CASCADE"), nullable=False)
    dados = db.Column(db.JSON)  # Pode ser JSON serializado como string

    consulta = db.relationship("ConsultaSocial", backref="resultados")


@login_manager.user_loader
def user_loader(id):
    return Users.query.filter_by(id=id).first()


@login_manager.request_loader
def request_loader(request):
    username = request.form.get('username')
    user = Users.query.filter_by(username=username).first()
    return user if user else None
