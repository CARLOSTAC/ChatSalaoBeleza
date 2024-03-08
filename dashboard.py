from flask import Flask, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, Length
from flask_bcrypt import Bcrypt
from flask import current_app

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///seu_banco_de_dados.db'
app.config['SECRET_KEY'] = 'deda190310250272'

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

# Definição de modelos do banco de dados
# Adicione suas classes de modelo aqui

# Definição de formulários


class CadastroForm(FlaskForm):
    nome_salao = StringField('Nome do Salão', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    senha = PasswordField('Senha', validators=[DataRequired(), Length(min=6)])
    submit = SubmitField('Cadastrar')


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    senha = PasswordField('Senha', validators=[DataRequired()])
    submit = SubmitField('Entrar')


@app.route('/')
def home():
    current_app.logger.info('Acessando a página inicial')
    return 'Página Inicial'


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        # Lógica de login do usuário
        flash('Login bem-sucedido!', 'success')
        return redirect(url_for('painel'))
    return render_template('login.html', form=form)


@app.route('/painel')
def painel():
    # Lógica para mostrar o painel do usuário
    return render_template('painel.html')


if __name__ == '__main__':
    app.run(debug=True)
