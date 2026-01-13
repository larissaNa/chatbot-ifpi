# -*- encoding: utf-8 -*-
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, IntegerField, FloatField, DateField, FileField, SelectField, TextAreaField, BooleanField
from wtforms.validators import Email, DataRequired, NumberRange, Length, URL, Optional
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
    submit = SubmitField('Salvar alterações')

