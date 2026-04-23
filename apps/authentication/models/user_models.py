# -*- encoding: utf-8 -*-
"""
Modelos e carregadores relacionados a autenticacao e usuario.
"""

from flask_login import UserMixin

from apps import db, login_manager
from apps.authentication.util import hash_pass


class Users(db.Model, UserMixin):
    __tablename__ = "Users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True)
    email = db.Column(db.String(64), unique=True)
    password = db.Column(db.LargeBinary)
    perfil = db.Column(db.String(20), default="Usuário")
    chat_messages = db.relationship("ChatMessage", backref="user", lazy=True)
    memories = db.relationship("UserMemory", backref="user", lazy=True)
    feedbacks = db.relationship("ChatFeedback", backref="user", lazy=True)

    def __init__(self, **kwargs):
        for property_name, value in kwargs.items():
            if hasattr(value, "__iter__") and not isinstance(value, str):
                value = value[0]

            if property_name == "password":
                value = hash_pass(value)

            setattr(self, property_name, value)

    @property
    def is_admin(self):
        return self.perfil == "Administrador"

    def __repr__(self):
        return str(self.username)


@login_manager.user_loader
def user_loader(id):
    return Users.query.filter_by(id=id).first()


@login_manager.request_loader
def request_loader(request):
    username = request.form.get("username")
    user = Users.query.filter_by(username=username).first()
    return user if user else None
