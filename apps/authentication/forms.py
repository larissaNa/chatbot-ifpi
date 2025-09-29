# -*- encoding: utf-8 -*-
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, IntegerField, FloatField, DateField, FileField, SelectField, TextAreaField, BooleanField
from wtforms.validators import Email, DataRequired, NumberRange, Length, URL, Optional
from flask_wtf.file import FileAllowed


# login and registration

class ServicoForm(FlaskForm):
    nome = StringField("Nome", validators=[DataRequired()])
    endpoint_api = StringField("Endpoint da API", validators=[Optional(), URL()])
    tipo_conteudo = SelectField(
    "Rede Social",
    choices=[
        ("instagram", "Instagram"),
        ("twitter", "Twitter"),
        ("facebook", "Facebook"),
        ("threads", "Threads")
    ],
    validators=[DataRequired()]
)
    custo_credito = FloatField("Custo por Crédito", validators=[DataRequired()])
    ativo = BooleanField("Ativo", default=True)

    api_token = StringField("Token da API", validators=[Optional()])
    api_username = StringField("Usuário da API", validators=[Optional()])
    api_password = StringField("Senha da API", validators=[Optional()])

    submit = SubmitField("Salvar")
    
class ContaSocialForm(FlaskForm):
    nome_usuario = StringField("Profile ID da Rede Social", validators=[DataRequired()])
    servico_id = SelectField("Serviço", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Salvar")


class ConsultaSocialForm(FlaskForm):
    conta_id = SelectField("Conta Vinculada", coerce=int, validators=[DataRequired()])
    data_inicio = DateField("Data Inicial", validators=[DataRequired()])
    data_fim = DateField("Data Final", validators=[DataRequired()])
    tipo_conteudo = SelectField(
    "Tipo de Conteúdo",
    choices=[("posts", "Posts"), ("stories", "Stories")],
    validators=[DataRequired()]
)
    submit = SubmitField("Consultar")
    
class LoginForm(FlaskForm):
    username = StringField('Username',
                         id='username_login',
                         validators=[DataRequired()])
    password = PasswordField('Password',
                             id='pwd_login',
                             validators=[DataRequired()])


class CreateAccountForm(FlaskForm):
    username = StringField('Username',
                         id='username_create',
                         validators=[DataRequired()])
    email = StringField('Email',
                      id='email_create',
                      validators=[DataRequired(), Email()])
    password = PasswordField('Password',
                             id='pwd_create',
                             validators=[DataRequired()])

class EditProfileForm(FlaskForm):
    username = StringField('Nome de usuário', validators=[DataRequired(), Length(3, 64)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    perfil = SelectField('Perfil', choices=[('Usuário', 'Usuário'), ('Administrador', 'Administrador')])
    avatar = FileField('Foto de perfil', validators=[FileAllowed(['jpg', 'png', 'jpeg'], 'Somente imagens.')])
    submit = SubmitField('Salvar alterações')


class SimularCompraForm(FlaskForm):
    quantidade = IntegerField('Quantidade de créditos', validators=[DataRequired(), NumberRange(min=1)])
    submit = SubmitField('Comprar')