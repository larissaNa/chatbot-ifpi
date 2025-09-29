# -*- encoding: utf-8 -*-
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, FileField, SelectField
from wtforms.validators import Email, DataRequired, Length
from flask_wtf.file import FileAllowed


# login and registration
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
