# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from flask import Blueprint
from apps import db, login_manager

blueprint = Blueprint(
    'authentication_blueprint',
    __name__,
    url_prefix=''

)

from .models import (  # noqa: E402
    ChatFeedback,
    ChatMessage,
    ChromaIndexRecord,
    DocumentoOficial,
    DocumentoVersao,
    LogProcessamento,
    UserMemory,
    Users,
    request_loader,
    user_loader,
)
from .routes import admin_routes, auth_routes, error_handlers, profile_routes  # noqa: E402,F401

__all__ = [
    "blueprint",
    "db",
    "login_manager",
    "Users",
    "user_loader",
    "request_loader",
    "DocumentoOficial",
    "DocumentoVersao",
    "ChromaIndexRecord",
    "LogProcessamento",
    "ChatMessage",
    "UserMemory",
    "ChatFeedback",
]
