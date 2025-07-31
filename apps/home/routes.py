# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from apps.home import blueprint
<<<<<<< Updated upstream
from flask import render_template, request
from flask_login import login_required
from jinja2 import TemplateNotFound


@blueprint.route('/index')
# @login_required
def index():
    return render_template('home/index.html', segment='index')
    
@blueprint.route('/chatbot', methods=['POST'])
def chatbot():
    data = request.get_json()
    user_message = data.get("message", "")
    resposta = obter_resposta_do_chatbot(user_message)  # sua função principal
    return jsonify({"reply": resposta})
=======
from flask import render_template, request, jsonify
from flask_login import login_required
from jinja2 import TemplateNotFound

@blueprint.route('/index')
def index():
    return render_template('home/index.html', segment='index')

>>>>>>> Stashed changes

@blueprint.route('/<template>')
@login_required
def route_template(template):
<<<<<<< Updated upstream

    try:

        if not template.endswith('.html'):
            template += '.html'

        # Detect the current page
        segment = get_segment(request)

        # Serve the file (if exists) from app/templates/home/FILE.html
        return render_template("home/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except:
        return render_template('home/page-500.html'), 500


# Helper - Extract current page name from request
def get_segment(request):

    try:

        segment = request.path.split('/')[-1]

        if segment == '':
            segment = 'index'

        return segment

=======
    try:
        if not template.endswith('.html'):
            template += '.html'
        segment = get_segment(request)
        return render_template("home/" + template, segment=segment)
    except TemplateNotFound:
        return render_template('home/page-404.html'), 404
    except:
        return render_template('home/page-500.html'), 500

def get_segment(request):
    try:
        segment = request.path.split('/')[-1]
        if segment == '':
            segment = 'index'
        return segment
>>>>>>> Stashed changes
    except:
        return None
