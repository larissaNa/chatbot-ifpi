# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from datetime import datetime
import json
import os
import random
import re
from typing import Counter
from flask import Response, abort, jsonify, render_template, redirect, request, session, url_for, flash, current_app
import requests
from sqlalchemy.orm.attributes import flag_modified
from flask_login import (
    login_required,
    current_user,
    login_user,
    logout_user
)
# from .models import ResultadoConsulta, db, UserCredits, CreditOperation
from apps import db, login_manager
from apps.authentication import blueprint
from apps.authentication.forms import LoginForm, CreateAccountForm, ServicoForm, ConsultaSocialForm, ContaSocialForm, EditProfileForm, SimularCompraForm
from apps.authentication.models import Users, Servico, ConsultaSocial, ContaSocial, ResultadoConsulta, UserCredits, CreditOperation, db
from apps.authentication.util import verify_pass
from werkzeug.utils import secure_filename
from apify_client import ApifyClient
# from apps.reports.services.utils import get_sentiment
import base64

# from PIL import Image
# from io import BytesIO



@blueprint.route('/')
def route_default():
    return redirect(url_for('authentication_blueprint.login'))

# Middleware para acesso restrito a admin
def admin_required(func):
    from functools import wraps
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("Acesso não autorizado.", "danger")
            return redirect(url_for("home_blueprint.index"))
        return func(*args, **kwargs)
    return decorated_view

# Login & Registration

@blueprint.route('/login', methods=['GET', 'POST'])
def login():
    login_form = LoginForm(request.form)
    if 'login' in request.form:

        # read form data
        username = request.form['username']
        password = request.form['password']

        # Locate user
        user = Users.query.filter_by(username=username).first()

        # Check the password
        if user and verify_pass(password, user.password):

            login_user(user)
            return redirect(url_for('authentication_blueprint.route_default'))

        # Something (user or pass) is not ok
        return render_template('accounts/login.html',
                               msg='Wrong user or password',
                               form=login_form)

    if not current_user.is_authenticated:
        return render_template('accounts/login.html',
                               form=login_form)
    return redirect(url_for('home_blueprint.index'))


@blueprint.route('/register', methods=['GET', 'POST'])
def register():
    create_account_form = CreateAccountForm(request.form)
    if 'register' in request.form:

        username = request.form['username']
        email = request.form['email']

        # Check usename exists
        user = Users.query.filter_by(username=username).first()
        if user:
            return render_template('accounts/register.html',
                                   msg='Username already registered',
                                   success=False,
                                   form=create_account_form)

        # Check email exists
        user = Users.query.filter_by(email=email).first()
        if user:
            return render_template('accounts/register.html',
                                   msg='Email already registered',
                                   success=False,
                                   form=create_account_form)

        # else we can create the user
        user = Users(**request.form)
        db.session.add(user)
        db.session.commit()

        # Delete user from session
        logout_user()

        return render_template('accounts/register.html',
                               msg='User created successfully.',
                               success=True,
                               form=create_account_form)

    else:
        return render_template('accounts/register.html', form=create_account_form)


@blueprint.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('authentication_blueprint.login')) 

@blueprint.route('/creditos', methods=['GET', 'POST'])
@login_required
def creditos():
    form = SimularCompraForm()
    user_credits = UserCredits.query.filter_by(user_id=current_user.id).first()
    if not user_credits:
        user_credits = UserCredits(user_id=current_user.id, balance=0)
        db.session.add(user_credits)
        db.session.commit()

    operations = CreditOperation.query.filter_by(user_id=current_user.id).order_by(CreditOperation.timestamp.desc()).all()

    if form.validate_on_submit():
        qtd = form.quantidade.data
        user_credits.balance += qtd
        op = CreditOperation(user_id=current_user.id, type='compra', amount=qtd, description='Compra simulada')
        db.session.add(op)
        db.session.commit()
        flash(f'{qtd} créditos adicionados com sucesso!', 'success')
        return redirect(url_for('authentication_blueprint.creditos'))

    return render_template('accounts/creditos.html', form=form, saldo=user_credits.balance, operacoes=operations)

@blueprint.route('/perfil')
@login_required
def perfil_usuario():
    usuario = current_user
    notificacoes = [
        {"titulo": "Créditos adicionados", "hora": "Hoje, 10:30"},
        {"titulo": "Senha alterada", "hora": "Ontem, 18:45"},
    ]
    mensagens = [
        {"de": "Admin", "assunto": "Bem-vindo!", "hora": "Ontem"},
        {"de": "Suporte", "assunto": "Atualização de sistema", "hora": "2 dias atrás"},
    ]
    return render_template('accounts/perfil-usuario.html', usuario=usuario, notificacoes=notificacoes, mensagens=mensagens)


@blueprint.route('/editar-perfil', methods=['GET', 'POST'])
@login_required
def editar_perfil():
    form = EditProfileForm(obj=current_user)

    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.email = form.email.data
        current_user.perfil = form.perfil.data

        # TRATAMENTO DE IMAGEM BASE64 (avatar_cortado)
        base64_data = request.form.get('avatar_cortado')
        if base64_data:
            base64_data = base64_data.split(',')[1]  # remove o cabeçalho "data:image/png;base64,"
            image_data = base64.b64decode(base64_data)
            filename = f"user_{current_user.id}_avatar.png"
            filepath = os.path.join('static/assets/images', filename)

            with open(os.path.join(current_app.root_path, filepath), 'wb') as f:
                f.write(image_data)

            current_user.avatar_url = '/' + filepath  # caminho usado nos templates

        db.session.commit()
        flash('Perfil atualizado com sucesso!', 'success')
        return redirect(url_for('authentication_blueprint.perfil_usuario'))
    elif request.method == 'POST':
        # Exibe erros do formulário (opcional: console ou logs)
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Erro no campo '{getattr(form, field).label.text}': {error}", 'danger')

    return render_template('accounts/editar-perfil.html', form=form, usuario=current_user)

#SERVIÇOS#

# LISTAR SERVIÇOS
@blueprint.route("/admin/servicos")
@login_required
@admin_required
def list_servicos():
    servicos = Servico.query.all()
    return render_template("admin/list.html", servicos=servicos)

# CRIAR NOVO SERVIÇO
@blueprint.route("/admin/servicos/create", methods=["GET", "POST"])
@login_required
@admin_required
def create_servico():
    form = ServicoForm()
    if form.validate_on_submit():
        novo = Servico(
            nome=form.nome.data,
            endpoint_api=form.endpoint_api.data,
            tipo_conteudo=form.tipo_conteudo.data,
            custo_credito=form.custo_credito.data,
            ativo=form.ativo.data,
            api_token=form.api_token.data,
            api_username=form.api_username.data,
            api_password=form.api_password.data,
        )
        db.session.add(novo)
        db.session.commit()
        flash("Serviço criado com sucesso!", "success")
        return redirect(url_for("authentication_blueprint.list_servicos"))
    return render_template("admin/create.html", form=form)

# EDITAR SERVIÇO
@blueprint.route("/admin/servicos/edit/<int:id>", methods=["GET", "POST"])
@login_required
@admin_required
def edit_servico(id):
    servico = Servico.query.get_or_404(id)
    form = ServicoForm(obj=servico)
    if form.validate_on_submit():
        servico.nome = form.nome.data
        servico.endpoint_api = form.endpoint_api.data
        servico.tipo_conteudo = form.tipo_conteudo.data
        servico.custo_credito = form.custo_credito.data
        servico.ativo = form.ativo.data
        servico.api_token = form.api_token.data
        servico.api_username = form.api_username.data
        servico.api_password = form.api_password.data
        db.session.commit()
        flash("Serviço atualizado com sucesso!", "success")
        return redirect(url_for("authentication_blueprint.list_servicos"))
    return render_template("admin/edit.html", form=form, servico=servico)

# EXCLUIR SERVIÇO
@blueprint.route("/admin/servicos/delete/<int:id>", methods=["GET", "POST"])
@login_required
@admin_required
def delete_servico(id):
    servico = Servico.query.get_or_404(id)
    if request.method == "POST":
        db.session.delete(servico)
        db.session.commit()
        flash("Serviço excluído com sucesso.", "success")
        return redirect(url_for("authentication_blueprint.list_servicos"))
    return render_template("admin/delete.html", servico=servico)

#CADASTRO SOCIAL#
@blueprint.route("/contas", methods=["GET", "POST"])
@login_required
def contas():
    form = ContaSocialForm()
    form.servico_id.choices = [(s.id, s.nome) for s in Servico.query.filter_by(ativo=True)]
    
    if form.validate_on_submit():
        conta = ContaSocial(
            nome_usuario=form.nome_usuario.data,
            servico_id=form.servico_id.data,
            usuario_id=current_user.id
        )
        db.session.add(conta)
        db.session.commit()
        flash("Conta cadastrada com sucesso!", "success")
        return redirect(url_for("authentication_blueprint.contas"))

    contas = ContaSocial.query.filter_by(usuario_id=current_user.id).all()
    return render_template("social/contas.html", form=form, contas=contas)

@blueprint.route("/buscar_contas")
@login_required
def buscar_contas():
    rede = request.args.get("rede")
    query = request.args.get("query")

    # Aqui você implementaria chamadas reais à API da rede social ou scraping leve
    # Para exemplo:
    resultados_falsos = [
        {"nome": f"{query} Oficial", "username": f"{query.lower()}_oficial"},
        {"nome": f"{query} Fanpage", "username": f"{query.lower()}_fans"},
    ]

    return jsonify(resultados=resultados_falsos)

@blueprint.route("/contas/delete/<int:id>", methods=["POST"])
@login_required
def delete_conta(id):
    conta = ContaSocial.query.get_or_404(id)
    if conta.usuario_id != current_user.id:
        flash("Acesso negado.", "danger")
        return redirect(url_for("authentication_blueprint.contas"))
    db.session.delete(conta)
    db.session.commit()
    flash("Conta excluída.", "success")
    return redirect(url_for("authentication_blueprint.contas"))

# ------------------- CONSULTA -------------------

from flask import Blueprint, render_template

# supondo que seu blueprint já seja definido assim

@blueprint.route('/radial-chart')
# @login_required
def radial_chart():
    # Exemplo de dados — você pode substituir por dados dinâmicos
    data = {
        'labels': ['Felicidade', 'Tristeza', 'Raiva', 'Surpresa', 'Desgosto'],
        'values': [65, 59, 90, 81, 56]
    }
    return render_template('social/radial_chart.html', data=data)


@blueprint.route('consultas/<int:consulta_id>/analise')
@login_required
def analise(consulta_id):
    # 1) Validação de acesso
    consulta = ConsultaSocial.query.get_or_404(consulta_id)
    if consulta.usuario_id != current_user.id:
        abort(403)

    # 2) Carrega o JSON já armazenado
    resultado = ResultadoConsulta.query.filter_by(
        consulta_id=consulta.id
    ).first_or_404()
    raw = resultado.dados or {}
    data = raw.get('data', {})
    period = consulta.data_inicio.strftime("%Y-%m-%d")+"_"+consulta.data_fim.strftime("%Y-%m-%d")
    # kpi     = data.get('kpi', {})
    # KPI vindos do banco
    # kpi_db = data.get('kpi', {})
    
    kpi_db = data.get('kpi') or {}

    # 4) Busca na API apenas se não existir nada salvo
    kpi_api = {}
    # print(kpi_db)
    # if not kpi_db:
    #     kpi_api = consulta.fetch_kpi_from_api(
    #         consulta.data_inicio, consulta.data_fim
    #     )
    #     # 4.1) Persiste os KPIs retornados no JSON do resultado
    #     print(kpi_api)
    #     raw.setdefault('data', {})['kpi'] = kpi_api
    #     print(raw)
    #     resultado.dados = raw
    #     db.session.commit()
    # print(resultado.dados)
    avatar_url = resultado.dados.get('metadata').get('avatar_url') or getpost(consulta.conta.nome_usuario)
    # print("DB >>>", kpi_db)
    # KPI adicionais da API
    # kpi_api = consulta.fetch_kpi_from_api(consulta.data_inicio, consulta.data_fim)
    # print("API >>>", kpi_api)
    kpi = {**kpi_db, **kpi_api}
    # print("KPI >>>", kpi)
    posts   = data.get('posts', [])
    stories = data.get('stories', [])
    items   = posts + stories

    # 4) Função utilitária para ler métricas
    def metric(item, *keys):
        for k in keys:
            v = item.get('kpi', {}).get(k, {}).get('value')
            if v is not None:
                return v
        return 0
    # 5) Top 25 por engajamento
    top_engagement = sorted(
        items,
        key=lambda i: metric(i, 'page_total_engagement_count', 'profile_story_total_interactions'),
        reverse=True
    )[:25]

    # 6) Sentimento geral (soma de positivos e negativos de posts)
    total_pos = 0 #kpi_api['post_text_sentiment_pos_count'].get('value', 0) or 0
    total_neg = 0 #kpi_api['post_text_sentiment_neg_count'].get('value', 0) or 0
    sentiment = {
        'positive': total_pos,
        'negative': total_neg,
        'percent_positive': (total_pos * 100 / (total_pos + total_neg)) if (total_pos + total_neg) else 0
    }
    # print('-------------------------------')
    # sen = []
    # texto = items[0].get('message') or ''
    # r = classificar_emocoes(texto)
    # # for i in items:
    # #     texto = i.get('message') or ''
    # #     r = classificar_emocoes(texto)
    # print(f"\nTexto: {texto}")
    # print(r)

    # 7) Crescimento de seguidores
    growth = {
        'absolute': kpi.get('profile_followers_growth_absolute', {}).get('formatted_value', 0),
        'percent':  kpi.get('profile_followers_growth_percent',  {}).get('formatted_value', 0)
    }

    # 8) Top 25 por sentimento positivo
    top_positive = sorted(
        items,
        key=lambda i: metric(i, 'post_text_sentiment_pos_count'),
        reverse=True
    )[:25]

    # 9) Top 25 por sentimento negativo
    top_negative = sorted(
        items,
        key=lambda i: metric(i, 'post_text_sentiment_neg_count'),
        reverse=True
    )[:25]

    # 10) Top 25 por alcance
    top_reach = sorted(
        items,
        key=lambda i: metric(i, 'profile_post_reach', 'profile_story_reach'),
        reverse=True
    )[:25]

    # 11) Nuvem de palavras
    STOPWORDS = {
        'que', 'quem', 'para','com','este','esta','isso','aquele','por','como',
        'mais','muito','sobre','entre','também','dos','das'
    }
    word_pattern = re.compile(r'\w+', re.UNICODE)

    
    def top_words(sublist, category, n=50):
        cnt = Counter()
        for it in sublist:
            text = (it.get('message') or '').lower()
            for w in word_pattern.findall(text):
                if len(w) > 3 and w not in STOPWORDS:
                    cnt[w] += 1

        return [
            {"x": word, "value": count, "category": category}
            for word, count in cnt.most_common(n)
        ]
    words_engagement = top_words(top_engagement, "Engajamento")
    words_reach      = top_words(top_reach, "Alcance")
    words_positive   = top_words(top_positive, "Positivo")
    words_negative   = top_words(top_negative, "Negativo")
    words_geral      = words_engagement+words_reach+words_positive+words_negative
    sentimento = {
        'labels': ['Felicidade', 'Tristeza', 'Raiva', 'Surpresa', 'Desgosto'],
        'values': [65, 59, 90, 81, 56]
    }
    # print(words_engagement)
    # print(type(words_engagement))
    # words_engagement = jsonify(words_engagement)
    # print(type(words_engagement))
    # print(type(consulta))
    return render_template(
        'accounts/analise.html',
        consulta=consulta,
        kpi=kpi,
        avatar_url=avatar_url,
        growth=growth,
        sentiment=sentiment,
        sentimento=sentimento,
        top_engagement=top_engagement,
        top_reach=top_reach,
        top_positive=top_positive,
        top_negative=top_negative,
        words_engagement=words_engagement,
        words_reach=words_reach,
        words_positive=words_positive,
        words_negative=words_negative,
        words_geral=words_geral
    )


@blueprint.route("/consultas/delete/<int:id>", methods=["POST"])
@login_required
def delete_consulta(id):
    if not current_user.is_admin:
        flash("Apenas administradores podem excluir consultas.", "danger")
        return redirect(url_for("authentication_blueprint.consultas_salvas"))

    consulta = ConsultaSocial.query.get_or_404(id)

    # Exclui resultado vinculado
    resultado = ResultadoConsulta.query.filter_by(consulta_id=consulta.id).first()
    if resultado:
        db.session.delete(resultado)

    # Opcional: remover operações relacionadas
    CreditOperation.query.filter_by(consulta_id=consulta.id).delete()

    db.session.delete(consulta)
    db.session.commit()

    flash("Consulta excluída com sucesso.", "success")
    return redirect(url_for("authentication_blueprint.consultas_salvas"))

async def getComments(from_data, to_data, account, nro_posts = 25): 
    print(from_data, to_data, account)
    apify_client = ApifyClient(APIKEY_VORTICE)
    # Start an Actor and wait for it to finish.
    print("Iniciando busca comentários")
    actor_client = apify_client.actor('apify/instagram-api-scraper')
    input_data = {
        "addParentData": False,
        "directUrls": [
            f"https://www.instagram.com/{account}/"
        ],
        "enhanceUserSearchWithFacebookPage": False,
        "isUserReelFeedURL": False,
        "isUserTaggedFeedURL": False,
        "onlyPostsNewerThan": from_data,
        "resultsLimit": nro_posts,
        "resultsType": "comments",
        "searchLimit": 250,
        "searchType": "hashtag"
    }
    call_result = actor_client.call(run_input=input_data, timeout_secs=1000)
    
    if call_result is None:
        print('Actor run failed.')
        return
    
    # Fetch results from the Actor run's default dataset.
    dataset_client = apify_client.dataset(call_result['defaultDatasetId'])
    dataset_items = dataset_client.list_items().items  # <- lista de dicionários

    post_comments = {}
    # print(dataset_client)
    for c in dataset_items:
        print('---------------')
        print(c)
        if c['latestComments']:
            comments = {c['url']: c['latestComments']}
            post_comments.update(comments)
        # print(c)
        if c.get('locationId'):
            location_id = c['locationId']
            location_name = c['locationName']
            coordinates = location_id_to_coordinates(location_id, location_name)
            c['location'] = coordinates
    return post_comments
    
def location_id_to_coordinates(location_id, location_name):
    """
    Transforma um locationID em coordenadas (latitude e longitude).
    Primeiro tenta um mapeamento fixo para IDs conhecidos.
    Caso não encontre, utiliza o locationName para geocodificação via Nominatim.
    """
    # Mapeamento fixo para alguns location IDs conhecidos
    mapping = {
        "0000": {"lat": -5.091, "lon": -42.803}
    }
    if location_id in mapping:
        return mapping[location_id]
    
    # Se o mapeamento fixo não encontrar, tenta geocodificar usando locationName
    if location_name:
        try:
            response = requests.get("https://nominatim.openstreetmap.org/search", params={
                "q": location_name,
                "format": "json"
            }, headers={"User-Agent": "Chrome"})
            data = response.json()
            if data and len(data) > 0:
                return {"lat": float(data[0]["lat"]), "lon": float(data[0]["lon"])}
        except Exception as e:
            print(f"Erro ao geocodificar '{location_name}': {e}")
    
    return {"lat": None, "lon": None}


@blueprint.route("/consultar", methods=["GET", "POST"])
@login_required
async def consultar():
    form = ConsultaSocialForm()
    form.conta_id.choices = [
        (c.id, f"{c.nome_usuario} ({c.servico.nome})") 
        for c in ContaSocial.query.filter_by(usuario_id=current_user.id)
    ]

    if form.validate_on_submit():
        consulta = ConsultaSocial(
            data_inicio=form.data_inicio.data,
            data_fim=form.data_fim.data,
            tipo_conteudo=form.tipo_conteudo.data,
            conta_id=form.conta_id.data,
            usuario_id=current_user.id
        )
        db.session.add(consulta)
        db.session.commit()

        servico = consulta.conta.servico
        conta = consulta.conta
        parametros = {
            "inicio": consulta.data_inicio,
            "fim": consulta.data_fim,
            "task": consulta.tipo_conteudo or "posts",  # TASK = posts, kpi, stories
            "profile_id": conta.nome_usuario  # deve conter o profile_id real
        }
        parametros2 = {
            "inicio": consulta.data_inicio,
            "fim": consulta.data_fim,
            "task": "kpi",
            "profile_id": conta.nome_usuario  # deve conter o profile_id real
        }

        try:
            resposta_api = executar_consulta(servico, parametros)
            # print(json.dumps(resposta_api, indent=2, ensure_ascii=False))
            # print("Quantidade >>>", len(resposta_api))
            resposta_kpi = executar_consulta(servico, parametros2)
            # print(json.dumps(resposta_kpi, indent=2, ensure_ascii=False))
            comments = await getComments(consulta.data_inicio, consulta.data_fim, conta.nome_usuario)
            posts = resposta_api.get("data", {}).get(consulta.tipo_conteudo, [])
            print('Concluído...')
            # print(comments)
            for post in posts:
                post_url = post.get('link')
                post['comments'] = comments.get(post_url, [])
                imagem_url_original = post.get("image")
                if imagem_url_original:
                    caminho_local = salvar_imagem_local(imagem_url_original, f"post_{post['id']}")
                    post["image"] = caminho_local
            qtd_resultados = len(resposta_api['data'][consulta.tipo_conteudo]) if isinstance(resposta_api, list) else 1
            custo = servico.custo_credito
            creditos = qtd_resultados * custo
            # print("RESPOSTA >>>", resposta_api)
            # print(json.dumps(resposta_api, indent=2, ensure_ascii=False))
            user_credit = UserCredits.query.filter_by(user_id=current_user.id).first()
            if not user_credit or user_credit.balance < creditos:
                flash("Saldo insuficiente para realizar a consulta.", "danger")
                return redirect(url_for("authentication_blueprint.consultar"))

            # Debita créditos
            user_credit.balance -= creditos

            # Salva consulta e resultado
            consulta.creditos_consumidos = creditos
            resultado = ResultadoConsulta(consulta_id=consulta.id, dados=resposta_api)

            operacao = CreditOperation(
                user_id=current_user.id,
                type='uso',
                amount=creditos,
                description=f"Consulta no serviço {servico.nome}",
                consulta_id=consulta.id
            )

            db.session.add(resultado)
            db.session.add(operacao)
            db.session.commit()

            flash(f"Consulta realizada com sucesso! Créditos consumidos: {creditos:.2f}", "info")
            return redirect(url_for("authentication_blueprint.resultados", consulta_id=consulta.id))
        except APINaoDefinida as e:
            flash(str(e), "warning")
            return redirect(url_for("authentication_blueprint.erro_api_nao_definida"))
        
        except Exception as e:
            flash(f"Erro ao consultar API externa: {e}", "danger")
            return redirect(url_for("authentication_blueprint.consultar"))

    return render_template("social/consultar.html", form=form)

@blueprint.route("/erro-api-nao-definida")
@login_required
def erro_api_nao_definida():
    return render_template("home/erro-api-nao-definida.html"), 400

def get_avatar_url(profile_id: str, rede: str) -> str:
    rede = (rede or "").strip().lower()

    if rede == "instagram":
        return get_instagram_avatar(profile_id)

    elif rede == "facebook":
        return f"https://graph.facebook.com/{profile_id}/picture?type=large"

    # outras redes podem ser adicionadas aqui com regras específicas
    else:
        return "/static/assets/image/avatar.png"

@blueprint.route("/resultados/<int:consulta_id>")
@login_required
async def resultados(consulta_id):
    consulta = ConsultaSocial.query.get_or_404(consulta_id)
    # print(consulta.conta.nome_usuario)
    # print(consulta.tipo_conteudo)
    # avatar_url =  getpost(consulta.conta.nome_usuario) 
    # print(avatar_url)
    resultado = ResultadoConsulta.query.filter_by(consulta_id=consulta_id).first_or_404()
    dados = resultado.dados or {}
    # print(dados)
    metadata = dados.get('metadata')
    if metadata is None:
        metadata = {}
        dados['metadata'] = metadata

    # 4) verifica avatar existente
    avatar_url = metadata.get('avatar_url')
    # print(avatar_url)
    if not avatar_url:
        # chama sua função para obter
        avatar_url = getpost(resultado.consulta.conta.nome_usuario)
        metadata['avatar_url'] = avatar_url

        # 5) sinaliza alteração e persiste
        resultado.dados = dados            # opcional mas claro
        flag_modified(resultado, 'dados')  # marca o campo JSON como modificado
        db.session.commit()
    
    # 4) verifica se comentários já foram resgatados
    comentarios = metadata.get('comments')
    # not comentarios
    if 1==1:
        print('Sem comentários')
        # chama sua função para obter
        comentarios = await getComments(consulta.data_inicio, consulta.data_fim, consulta.conta.nome_usuario)
        # print(comentarios)
        print('Comentarios')
        sentimentos_post = []
        for c in comentarios:
            print("Comentarios >>>", len(comentarios[c]))
            for cc in comentarios[c]:    
                text = cc['text']
                sentimento = get_sentiment(text)
                # print(sentimento)
                print("gravando sentimento")
                sentimentos_post.append(sentimento)
                # print("SENTIMENTO_POST >>>", sentimentos_post)
                cc['sentimento'] = sentimento
            for p in dados.get('data').get(consulta.tipo_conteudo):
                print('link post >>>', p.get('link'))
                print('LINK cOMENTÁRIOS >>>',c)
                if p.get('link') == c:
                    print("ACHOU")
                    p['comments'] = comentarios[c]
                    p['sentimentos_post'] = sentimentos_post
                    # print(p)
                    # print("Comentarios >>>", len(comentarios[c]))
                    # print("SENTIMENTO_POST >>>", sentimentos_post)
                    # print("SENTIMENTO_POST >>>", cc['sentimento'])
                    # print("SENTIMENTO_POST >>>", cc)
            # print('COMENTARIOS >>>>>>', comentarios)
            # print(sentimentos_post)
            # break
        metadata['comments'] = comentarios
        # 5) sinaliza alteração e persiste
        
        resultado.dados = dados            
        flag_modified(resultado, 'dados')  
        db.session.commit()
    metadata = dados.get('metadata')  
    
    print('-------------------------------')
    print('POSTS >>>>', dados.get('data'))  
    print('Com comentários')
    
    sentimento = {
        'labels': ['Felicidade', 'Tristeza', 'Raiva', 'Surpresa', 'Desgosto'],
        'values': [0, 0, 0, 0,0]
    }
    # print(resultado)
    header = {'posts':['#', 'Autor', 'Data', 'Texto', 'Imagem', 'Likes', 'Comentários', 'Engajamento'], 
              'stories':['#', 'Autor', 'Data', 'Texto', 'Imagem', 'Interações', 'Visitas ao Perfil', 'Alcance']}
    return render_template("social/resultados.html", sentimento=sentimento, avatar_url = avatar_url, consulta = consulta, task=consulta.tipo_conteudo ,header=header, resultado=resultado)

@blueprint.route('/privacy')
def privacy():
    return render_template('social/privacy.html')

@blueprint.route('/terms')
def terms():
    connector = InstagramConnector("IGAAUZCTZACFsVxBZAE5Rb1NWZAnB3b2l1NVotMDJmOUZAnSFpxQVU4U2xGdVlFMkV6X1VKakM2TmkxTXRzLVNpeEs4SWR4Nm9lTlhUTkpxTHlIWGRIMlduNlNpTF9TUWk4Q0pIdDU1VWxXZA1U4b3ktaTJPQnZAPT3VxMVA4R2kyLThqRQZDZD")
    username = "prof.ricardosekeff"
    user_id = connector.get_user_id(username)
    return user_id
    print(user_id)
    posts = connector.get_posts(user_id, "2022-01-01", "2022-01-31", hashtag="")
    print(posts)
    return render_template('social/terms.html')


@blueprint.route("/proxy-image")
def proxy_image():
    import requests
    url = request.args.get("url")
    response = requests.get(url, stream=True)
    return Response(response.raw, content_type=response.headers["Content-Type"])


@blueprint.route("/consultas-salvas")
@login_required
def consultas_salvas():
    consultas = ConsultaSocial.query.filter_by(usuario_id=current_user.id).order_by(ConsultaSocial.timestamp.desc()).all()
    return render_template("social/consultas_salvas.html", consultas=consultas)


# Errors

@login_manager.unauthorized_handler
def unauthorized_handler():
    return render_template('home/page-403.html'), 403


@blueprint.errorhandler(403)
def access_forbidden(error):
    return render_template('home/page-403.html'), 403


@blueprint.errorhandler(404)
def not_found_error(error):
    return render_template('home/page-404.html'), 404


@blueprint.errorhandler(500)
def internal_error(error):
    return render_template('home/page-500.html'), 500
