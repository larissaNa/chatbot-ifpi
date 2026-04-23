# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from flask import Blueprint

blueprint = Blueprint("core", __name__, url_prefix="/",template_folder='templates', static_folder='static')

from apps.core.chat.agents.institutional_agent import melhorar_resposta_com_feedback  # noqa: E402
from apps.core.chat.graph.builder import graph  # noqa: E402
from apps.core.chat.graph.runner import (  # noqa: E402
    build_history_messages,
    run_chatbot,
    sanitize_messages,
)
from apps.core.chat.graph.state import StateSchema  # noqa: E402

from .routes_parts import chat_routes, conversation_routes, feedback_routes  # noqa: E402,F401

__all__ = [
    "blueprint",
    "StateSchema",
    "graph",
    "sanitize_messages",
    "build_history_messages",
    "run_chatbot",
    "melhorar_resposta_com_feedback",
]
