# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from flask_login import UserMixin
import requests
from apps import db, login_manager
from apps.authentication.util import hash_pass
from datetime import datetime

class Users(db.Model, UserMixin):

    __tablename__ = 'Users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True)
    email = db.Column(db.String(64), unique=True)
    password = db.Column(db.LargeBinary)
    perfil = db.Column(db.String(20), default='Usuário')  # Novo campo
    chat_messages = db.relationship("ChatMessage", backref="user", lazy=True)

    def __init__(self, **kwargs):
        for property, value in kwargs.items():
            if hasattr(value, '__iter__') and not isinstance(value, str):
                value = value[0]

            if property == 'password':
                value = hash_pass(value) 

            setattr(self, property, value)
    @property
    def is_admin(self):
        return self.perfil == 'Administrador'
    
    def __repr__(self):
        return str(self.username)

@login_manager.user_loader
def user_loader(id):
    return Users.query.filter_by(id=id).first()


@login_manager.request_loader
def request_loader(request):
    username = request.form.get('username')
    user = Users.query.filter_by(username=username).first()
    return user if user else None

class DocumentoOficial(db.Model):
    __tablename__ = "documentos_oficiais"

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(255), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    descricao = db.Column(db.Text)
    ativo = db.Column(db.Boolean, default=True)
    obsoleto = db.Column(db.Boolean, default=False)  # Confirmado pelo usuário
    sugerido_obsoleto = db.Column(db.Boolean, default=False)  # Sugerido pelo agente
    criado_em = db.Column(db.DateTime, server_default=db.func.now())
    ultima_verificacao = db.Column(db.DateTime)
    ultimo_status_http = db.Column(db.Integer)

    # relacionamento -> versões
    versoes = db.relationship("DocumentoVersao", backref="documento", lazy=True)

    def __repr__(self):
        return f"<DocumentoOficial {self.titulo}>"

class DocumentoVersao(db.Model):
    __tablename__ = "documento_versoes"

    id = db.Column(db.Integer, primary_key=True)
    documento_id = db.Column(
        db.Integer, db.ForeignKey("documentos_oficiais.id"), nullable=False
    )

    versao_numero = db.Column(db.Integer, nullable=False)
    url_arquivo = db.Column(db.String(500))
    hash_conteudo = db.Column(db.String(128))
    status_processamento = db.Column(db.String(32))
    chroma_document_id = db.Column(db.String(255))

    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    processado_em = db.Column(db.DateTime)
    indexado_em = db.Column(db.DateTime)

    # relacionamento -> chroma chunks
    chroma_chunks = db.relationship("ChromaIndexRecord", backref="versao", lazy=True)

    def __repr__(self):
        return f"<DocumentoVersao {self.id} Doc={self.documento_id}>"

class ChromaIndexRecord(db.Model):
    __tablename__ = "chroma_index_records"

    id = db.Column(db.Integer, primary_key=True)
    versao_id = db.Column(
        db.Integer, db.ForeignKey("documento_versoes.id"), nullable=False
    )

    chroma_document_id = db.Column(db.String(255))
    ativo = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ChromaIndex {self.chroma_document_id}>"

class LogProcessamento(db.Model):
    __tablename__ = "logs_processamento"

    id = db.Column(db.Integer, primary_key=True)
    versao_id = db.Column(
        db.Integer, db.ForeignKey("documento_versoes.id"), nullable=True
    )
    agente = db.Column(db.String(64))
    acao = db.Column(db.String(64))
    detalhe = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    documento_id = db.Column(
        db.Integer, db.ForeignKey("documentos_oficiais.id"), nullable=True
    )

    def __repr__(self):
        return f"<Log {self.id} {self.acao}>"


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("Users.id"), nullable=True)
    thread_id = db.Column(db.String(64), nullable=False)
    sender = db.Column(db.String(10), nullable=False)
    content = db.Column(db.Text, nullable=False)
    thoughts = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ChatMessage {self.id} {self.sender}>"
