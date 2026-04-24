# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from flask import Blueprint

blueprint = Blueprint("core", __name__, url_prefix="/",template_folder='templates', static_folder='static')

from .routes_parts import chat_routes, conversation_routes, feedback_routes  # noqa: E402,F401


def run_chatbot(*args, **kwargs):
    from apps.core.chat.graph.runner import run_chatbot as _impl

    return _impl(*args, **kwargs)


def sanitize_messages(*args, **kwargs):
    from apps.core.chat.graph.runner import sanitize_messages as _impl

    return _impl(*args, **kwargs)


def build_history_messages(*args, **kwargs):
    from apps.core.chat.graph.runner import build_history_messages as _impl

    return _impl(*args, **kwargs)


def melhorar_resposta_com_feedback(*args, **kwargs):
    from apps.core.chat.agents.institutional_agent import melhorar_resposta_com_feedback as _impl

    return _impl(*args, **kwargs)


__all__ = [
    "blueprint",
    "sanitize_messages",
    "build_history_messages",
    "run_chatbot",
    "melhorar_resposta_com_feedback",
]
