# -*- encoding: utf-8 -*-
from apps.home import blueprint
from flask import current_app, redirect, render_template, request, url_for
from flask_login import current_user
from jinja2 import TemplateNotFound


@blueprint.route('/index')
def index():
    # Em prod, qualquer pessoa acessa sem login.
    # Em dev, exige autenticação.
    if current_app.config.get('APP_ENV') != 'prod' and not current_user.is_authenticated:
        return redirect(url_for('authentication_blueprint.login'))
    return render_template('home/index.html', segment='index')


@blueprint.route('/<template>')
def route_template(template):
    # Rotas genéricas sempre exigem login (são páginas administrativas)
    if not current_user.is_authenticated:
        return redirect(url_for('authentication_blueprint.login'))

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
    except:
        return None
