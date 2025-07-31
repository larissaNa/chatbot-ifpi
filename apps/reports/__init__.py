# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from flask import Blueprint

blueprint = Blueprint("reports", __name__, url_prefix="/",template_folder='templates', static_folder='static')
