from flask_wtf import FlaskForm
from wtforms import SelectField, HiddenField, SubmitField
from wtforms.validators import DataRequired

class RelatorioForm(FlaskForm):
    consulta         = SelectField("Consulta",        coerce=int, validators=[DataRequired()])
    conteudo_base64  = HiddenField(validators=[DataRequired()])
    submit           = SubmitField("Salvar Relatório")
