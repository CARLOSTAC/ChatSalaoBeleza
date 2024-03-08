import threading
import time
import googleapiclient
import pytz
import requests
from flask import Flask, request, jsonify
from json import dumps
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from pytz import timezone
from dateutil.parser import parse
from googleapiclient.errors import HttpError
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, Length
from flask_bcrypt import Bcrypt
from flask import render_template, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask import Flask, render_template


app = Flask(__name__)
login_manager = LoginManager(app)
# Define a rota de login que será usada para redirecionar os usuários não autenticados
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Usuario, int(user_id))


app.config['SECRET_KEY'] = '\xd1\x0f\x03z\xa1/\xda)\xe2\xab_E\xd8\xa9D\x97'
bcrypt = Bcrypt(app)

# Configura a URI do banco de dados para usar o SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.sqlite'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Cria uma instância do SQLAlchemy
db = SQLAlchemy(app)


class Profissional(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    especialidade = db.Column(db.String(100))
    contato = db.Column(db.String(100))

    # Relacionamento: Um profissional pode oferecer vários serviços
    servicos = db.relationship('Servico', backref='profissional', lazy=True)


class Servico(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    preco = db.Column(db.Float, nullable=False)

    # Chave estrangeira para associar cada serviço a um profissional
    profissional_id = db.Column(db.Integer, db.ForeignKey(
        'profissional.id'), nullable=False)


class Usuario(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    nome_salao = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha_hash = db.Column(db.String(128))

    # Adicione mais campos conforme necessário, como endereço, telefone, etc.

    # Relacionamento (opcional): Se cada salão tiver seus próprios profissionais, você pode querer adicionar um relacionamento aqui
    # profissionais = db.relationship('Profissional', backref='usuario', lazy=True)


class CadastroForm(FlaskForm):
    nome_salao = StringField('Nome do Salão', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    senha = PasswordField('Senha', validators=[DataRequired(), Length(min=6)])
    submit = SubmitField('Cadastrar')


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    senha = PasswordField('Senha', validators=[DataRequired()])
    submit = SubmitField('Entrar')


class ChatState:
    def __init__(self, user_id, bot_instance):
        self.send_response_func = None
        # New variable to track if the last message was a success message
        self.last_message_success = False
        self.reset_bot_state()
        self.last_interaction_time = time.time()
        self.inactivity_timer = threading.Timer(60, self.handle_inactivity)
        self.inactivity_timer.start()
        self.date_page = 0
        self.client_phone_number = None

        self.bot_instance = bot_instance
        self.professional_phone_numbers = {}
        self.user_states = {}
        self.professional_indices = {}
        self.user_id = user_id
        self.state = "INITIAL"
        self.name = None
        self.selected_option = None
        self.selected_service = None
        self.preferred_professional = None
        self.current_date_page = 0
        self.selected_date = None
        self.selected_time = None
        self.professionals = ['Carlos', 'Pedro',
                              'Marina', 'Sofia']  # Adicione esta linha
        self.available_dates = [datetime.now() + timedelta(days=i)
                                for i in range(1, 8)]
        self.available_times = []
        self.day_map = {
            "Monday": "Segunda",
            "Tuesday": "Terça",
            "Wednesday": "Quarta",
            "Thursday": "Quinta",
            "Friday": "Sexta",
            "Saturday": "Sábado",
            "Sunday": "Domingo"
        }
        self.service_names = {
            '1': 'Corte de cabelo masculino',
            '2': 'Corte de cabelo feminino',
            '3': 'Escova',
            '4': 'Tintura',
            '5': 'Hidratação',
            '6': 'Pé e Mão',
            '7': 'Depilação',
            '8': 'Manicure',
            '9': 'Pedicure'
        }
        self.professional_phone_numbers = {
            'Carlos': '+5511934903137',
            'Pedro': '+5511934903137',
            'Marina': '+5511934903137',
            'Sofia': '+5511934903137'
        }
        self.service_to_professionals = {
            '1': ['Carlos', 'Pedro'],
            '2': ['Marina', 'Sofia'],
            '3': ['Sofia', 'Marina'],
            '4': ['Pedro', 'Marina'],
            '5': ['Sofia', 'Carlos'],
            '6': ['Marina', 'Marina'],
            '7': ['Sofia', 'Pedro'],
            '8': ['Sofia'],
            '9': ['Sofia', 'Marina']
        }
        self.service_to_price = {
            "1": "R$ 40,00",
            "2": "R$ 50,00",
            "3": "a partir de R$ 40,00",
            "4": "a partir de R$ 90,00",
            "5": "a partir de R$ 60,00",
            "6": "R$ 60,00",
            "7": "a partir de R$ 40,00",
            "8": "R$ 35,00",
            "9": "R$ 40,00"
        }

        try:
            self.credentials = Credentials.from_service_account_file(
                'C:/Users/Carlos/Downloads/salaobeleza-398119-96aece8e0cc2.json',
                scopes=['https://www.googleapis.com/auth/calendar']
            )
            self.calendar_service = build(
                'calendar', 'v3', credentials=self.credentials)
        except Exception as e:
            print(f"Erro ao criar o serviço do Google Calendar: {e}")
        self.professional_calendar_ids = {
            'Carlos': '3ae628c17db2c46e7858a9b616935d4585aee8df0e8757e3d574b6bf841838e6@group.calendar.google.com',
            'Pedro': '194ff6d5f8d41c77b3119d6a6bc3db0a41ebdb190ecdc220321f465a093701a2@group.calendar.google.com',
            'Marina': '1fc611f22448020d2dfb455ea825975001424773fcf9f4335e09468d6e3cd1aa@group.calendar.google.com',
            'Sofia': 'bfa7e529b102453b1f9c8b6d090a1c1a8d3f8ca59e50b518025ba6c30a4b6d17@group.calendar.google.com'
        }

    def reset_bot_state(self):
        self.state = "INITIAL"

    def send_inactivity_message(self):
        self.send_response_func(
            "Nossa conversa foi encerrada por falta de interação, se precisar iniciar uma nova conversa é só chamar tá? 😘")

    def fetch_tomorrows_events_from_google_calendar(service, calendar_id='primary'):
        try:
            # Configurar o fuso horário e as datas
            tz = pytz.timezone('America/Sao_Paulo')
            now = datetime.now(tz)
            midnight = tz.localize(datetime.combine(
                now.date(), datetime.min.time())) + timedelta(days=1)
            next_midnight = midnight + timedelta(days=1)

            # Buscar eventos
            events_result = service.events().list(calendarId=calendar_id,
                                                  timeMin=midnight.isoformat(),
                                                  timeMax=next_midnight.isoformat(),
                                                  singleEvents=True,
                                                  orderBy='startTime').execute()
            return events_result.get('items', [])
        except HttpError as error:
            print(f"Erro ao buscar eventos: {error}")

            def extract_phone_number_from_event(event):
                description = event.get('description', '')
                # Extrair o número de telefone aqui. Este é um exemplo simples.
                # Você pode precisar ajustar este código para corresponder ao seu formato específico.
                return description.split('Telefone:')[1].split('\n')[0].strip() if 'Telefone:' in description else None

            return []

    def handle_inactivity(self):
        current_time = time.time()
        if current_time - self.last_interaction_time >= 60:

            # Primeiro, envie a mensagem de inatividade
            if self.send_response_func is not None:
                if not self.last_message_success:
                    self.send_response_func(
                        "Nossa conversa foi encerrada por falta de interação, se precisar iniciar uma nova conversa é só chamar tá? 😘"
                    )

            # Em seguida, resete o estado do bot
            if self.reset_bot_state is not None:
                self.reset_bot_state()

    def send_daily_reminders(self):
        # Set the time range for tomorrow
        tz = pytz.timezone('America/Sao_Paulo')
        now = datetime.now(tz)
        midnight = tz.localize(datetime.combine(
            now.date(), datetime.min.time())) + timedelta(days=1)
        next_midnight = midnight + timedelta(days=1)

        # Fetch events from Google Calendar
        events_result = self.calendar_service.events().list(calendarId='primary', timeMin=midnight.isoformat(),
                                                            timeMax=next_midnight.isoformat(), singleEvents=True,
                                                            orderBy='startTime').execute()
        events = events_result.get('items', [])

        for event in events:
            start_time_iso = event['start'].get('dateTime')
            start_time = parse(start_time_iso).strftime(
                '%H:%M')  # Convert to HH:MM format
            # Use a default value if summary is not available
            summary = event.get('summary', "Compromisso")

            # Supondo que você armazenou o número de telefone do cliente na descrição
            client_phone_number = self.client_phone_number

            reminder_message = f"Olá, você tem um compromisso '{
                summary}' agendado para amanhã às {start_time}."
            self.send_message_to_phone(client_phone_number, reminder_message)

    def fetch_available_times(self, professional, selected_date=None):
        print(f"Debug: fetch_available_times chamado com profissional = {
              professional} e data = {selected_date}")

        local_tz = timezone('America/Sao_Paulo')
        calendar_id = self.professional_calendar_ids.get(professional)

        work_days = ['tuesday', 'wednesday', 'thursday', 'friday', 'saturday']
        work_start_time = 9  # 09:00
        work_end_time = 20  # 20:00

        if selected_date is None:
            date_obj = datetime.now() + timedelta(days=1)
        else:
            date_obj = datetime.strptime(selected_date, '%d/%m/%Y')
            weekday = date_obj.strftime('%A').lower()

        # Verificar se a data selecionada é domingo ou segunda
        if date_obj.weekday() in [6, 0]:  # 0 para segunda, 6 para domingo
            print("Data é domingo ou segunda, retornando")
            return

        # Configuração dos horários de trabalho
        work_start_time = 9  # 09:00
        work_end_time = 20  # 20:00

        # Verificar se a data selecionada é uma data passada
        today = datetime.now(local_tz).date()
        if selected_date and date_obj.date() < today:
            return

        # Configurando timeMin e timeMax
        start_time_str = local_tz.localize(
            date_obj.replace(hour=0, minute=0, second=0)).isoformat()
        end_time_str = local_tz.localize(date_obj.replace(
            hour=23, minute=59, second=59)).isoformat()

        try:
            events_result = self.calendar_service.events().list(
                calendarId=calendar_id,
                timeMin=start_time_str,
                timeMax=end_time_str,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
        except googleapiclient.errors.HttpError as error:
            print(f"Detalhes do erro: {error.resp.status}, {
                  error.resp.reason}, {error.content.decode('utf-8')}")
            return

        events = events_result.get('items', [])

        self.available_times = []
        for hour in range(work_start_time, work_end_time):
            slot_start = local_tz.localize(
                date_obj.replace(hour=hour, minute=0)).isoformat()
            slot_end = local_tz.localize(date_obj.replace(
                hour=hour + 1, minute=0)).isoformat()

            if datetime.now(local_tz).isoformat() > slot_start:
                continue

            if any(event['start']['dateTime'] <= slot_start < event['end']['dateTime'] for event in events):
                continue

            self.available_times.append(f"{hour:02}:00")

        return

    def book_appointment(self):
        cleaned_phone_number = self.client_phone_number[2:]
        appointment_successful = False
        print("Debug: Antes de obter calendar_id")
        calendar_id = self.professional_calendar_ids.get(
            self.preferred_professional)
        print(f"Debug: calendar_id obtido: {calendar_id}")
        if calendar_id:
            event_date = datetime.strptime(self.selected_date, '%d/%m/%Y')
            event_time = datetime.strptime(self.selected_time, '%H:%M')
            start_time = event_date.replace(
                hour=event_time.hour, minute=event_time.minute)
            print("Debug: Antes de criar o evento")
            # assumindo que cada compromisso dura 1 hora
            end_time = start_time + timedelta(hours=1)
            service_name = self.service_names.get(
                self.selected_service, "Serviço desconhecido")
            event = {
                'summary': f'Agendamento para {self.name}',
                'description': f'Serviço: {self.selected_service_name}\nTelefone: {cleaned_phone_number}',
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': 'America/Sao_Paulo',
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': 'America/Sao_Paulo',
                },
            }

            print("Debug: Depois de criar o evento")
            try:
                print("Debug: Tentando inserir o evento no Google Calendar")
                self.calendar_service.events().insert(
                    calendarId=calendar_id, body=event).execute()
                print("Debug: Evento inserido com sucesso no Google Calendar")
                appointment_successful = True  # Atualize a variável aqui
            except Exception as e:
                print(f"An error occurred: {e}")
                import traceback
                traceback.print_exc()
            print(f"Debug: Valor de appointment_successful = {
                  appointment_successful}")

            if appointment_successful:
                professional_message = (
                    f"Olá, {
                        self.preferred_professional}. Você teve uma reserva de horário na sua agenda.\n"
                    f"Segue as informações:\n"
                    f"Cliente: {self.name}\n"
                    # Utilize cleaned_phone_number aqui
                    f"Celular: {cleaned_phone_number}\n"
                    f"Serviço: {self.selected_service_name}\n"
                    f"Dia: {self.selected_date}\n"
                    f"Hs: {self.selected_time}\n"
                )
                phone_number = self.professional_phone_numbers.get(
                    self.preferred_professional, None)
                if phone_number:
                    self.send_message_to_phone(
                        phone_number, professional_message)

            return appointment_successful

    def send_message_to_phone(self, phone, message):
        self.bot_instance.send_message(phone, message)

    def reset_booking_details(self):
        self.selected_service = None
        self.preferred_professional = None
        self.selected_date = None
        self.selected_time = None

    def get_available_dates(self, page=0):
        local_tz = timezone('America/Sao_Paulo')
        today = datetime.now(local_tz)
        available_dates = []
        start_day = page * 7  # Inicie a partir do dia que corresponde à página atual
        # Verificar nos próximos 14 dias a partir do dia de início
        for i in range(start_day, start_day + 14):
            date = today + timedelta(days=i)
            # Excluindo Domingo (0) e Segunda (6)
            if date.weekday() not in [0, 6]:
                available_dates.append(date)
        return available_dates[:7]

    def check_availability(self, professional, start_time, end_time):
        calendar_id = self.professional_calendar_ids.get(professional)
        if calendar_id:
            events_result = self.calendar_service.events().list(
                calendarId=calendar_id,
                timeMin=start_time,
                timeMax=end_time,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            events = events_result.get('items', [])
            return len(events) == 0

    def process_user_message(self, message, send_response_func):
        # Atualiza o tempo da última interação
        self.last_interaction_time = time.time()
        self.inactivity_timer.cancel()  # Cancela o timer de inatividade anterior
        self.inactivity_timer = threading.Timer(
            60, self.handle_inactivity)  # Cria um novo timer de inatividade
        self.inactivity_timer.start()  # Inicia o novo timer de inatividad
        self.send_response_func = send_response_func
        print(f"Current state: {self.state}, Received message: {message}")

        if self.state == "INITIAL":
            self.state = "ASKING_NAME"
            send_response_func(
                "Olá! Bem-vinda a \nNikita Beleza & Cia. \nQual é o seu nome?")
        elif self.state == "ASKING_NAME":
            self.name = message.strip()
            self.state = "ASKING_SERVICE"
            send_response_func(f"Olá {self.name}, \nDigite o número da opção abaixo:\n\n"
                               "1 - Para Marcar horário.\n"
                               "2 - Para Cancelar horário.\n"
                               "3 - Falar conosco.")
        elif self.state == "ASKING_SERVICE":
            self.selected_option = message.strip()
            if self.selected_option == "1":
                self.state = "ASKING_TYPE_OF_SERVICE"
                send_response_func("Digite o *NÚMERO* da opção do serviço que deseja:\n\n"
                                   "1- Corte Masculino\n"
                                   "2- Corte Feminino\n"
                                   "3- Escova\n"
                                   "4- Tintura\n"
                                   "5- Hidratação\n"
                                   "6- Pé e Mão\n"
                                   "7- Depilação\n"
                                   "8- Manicure\n"
                                   "9- Pedicure")
            elif self.selected_option == "2":
                # Logic for canceling appointment
                pass
            elif self.selected_option == "3":
                send_response_func(
                    "Toque no número abaixo para falar conosco:\n+55 11 9349-03137")
                self.state = "INITIAL"
            else:
                send_response_func(
                    "Opção inválida. Por favor, tente novamente.")

        elif self.state == "ASKING_TYPE_OF_SERVICE":
            self.selected_service = message.strip()
            self.selected_service_name = self.service_names.get(
                self.selected_service, "Serviço desconhecido")

            price = self.service_to_price.get(
                self.selected_service, "Preço não disponível")

            send_response_func(f"Você escolheu o serviço {
                               self.selected_service_name} o valor desse serviço é *{price}*.")

            self.available_professionals_for_service = self.service_to_professionals.get(
                self.selected_service, [])
            self.professional_indices = {
                i + 1: p for i, p in enumerate(self.available_professionals_for_service)}

            if self.available_professionals_for_service:
                self.state = "ASKING_WHICH_PROFESSIONAL"

                professionals_str = "\n".join(
                    [f"{i + 1} - {p}" for i, p in enumerate(self.available_professionals_for_service)])

                send_response_func(
                    f"Digite o número do profissional abaixo que está disponível para o seu serviço:\n\n{professionals_str}")
            else:
                send_response_func(
                    "Desculpe, não temos profissionais disponíveis para o serviço selecionado.")

        elif self.state == "ASKING_WHICH_PROFESSIONAL":
            self.preferred_professional = self.professional_indices[int(
                message.strip())]
            self.fetch_available_times(self.preferred_professional,
                                       self.selected_date)  # Atualizar horários disponíveis aqui
            self.state = "ASKING_DATE"
            # Chame a função get_available_dates para obter as datas disponíveis
            self.available_dates = self.get_available_dates()
            date_str = "\n".join([f"{i + 1} = {d.strftime('%d/%m/%Y')} >{
                                 self.day_map[d.strftime('%A')]}" for i, d in enumerate(self.available_dates)])
            send_response_func(f"Digite o número referente ao dia da sua escolha:\n\n{
                               date_str}\n8= Ver mais datas")

        elif self.state == "ASKING_DATE":
            if message.strip() == "8":
                self.date_page += 1  # Incrementar o contador de página
                self.available_dates = self.get_available_dates(
                    self.date_page)  # Obter a próxima página de datas
                date_str = "\n".join([f"{i + 1} = {d.strftime('%d/%m/%Y')} >{
                                     self.day_map[d.strftime('%A')]}" for i, d in enumerate(self.available_dates)])

                send_response_func(f"Digite o número referente ao dia da sua escolha:\n\n{
                                   date_str}\n8= Ver mais datas")
                return
            else:
                # Converte para índice baseado em zero
                selected_date_index = int(message.strip()) - 1
                self.selected_date = self.available_dates[selected_date_index].strftime(
                    '%d/%m/%Y')
                # Adicione esta linha para depuração
                print(f"Debug: Data selecionada = {self.selected_date}")

                # Buscar horários disponíveis para o profissional e a data escolhida
                self.fetch_available_times(
                    self.preferred_professional, self.selected_date)
                print(f"Debug: Horários disponíveis = {self.available_times}")

                self.state = "ASKING_TIME"
                # Verifique se há horários disponíveis antes de prosseguir
                if self.available_times:
                    time_str = "\n".join(
                        [f"{i + 1} = {t}" for i, t in enumerate(self.available_times)])
                    send_response_func(
                        f"Digite o número referente ao horário desejado entre as opções abaixo:\n{time_str}")
                else:
                    send_response_func(
                        "Desculpe, não há horários disponíveis para esta data. Por favor, escolha outra data.")

        elif self.state == "ASKING_TIME":
            print(f"Debug: Current state is {self.state}")  # Adicione este log

            # Converte para índice baseado em zero
            selected_time_index = int(message.strip()) - 1
            self.selected_time = self.available_times[selected_time_index]
            self.state = "CONFIRMATION"

            send_response_func(f"Você selecionou o dia {self.selected_date} às {self.selected_time} "
                               f"com o profissional {
                                   self.preferred_professional}. Deseja confirmar?\n"
                               "Digite 1 para *Sim*\n"
                               "Digite 2 para *Não*")

        elif self.state == "CONFIRMATION":
            print(f"Debug: Current state is {self.state}")  # Adicione este log

            if message.strip() == '1':
                self.state = "CONFIRMED"
                if self.book_appointment():
                    # Adicione este log
                    print("Debug: appointment_successful is True")

                    send_response_func(f"{self.name}, seu agendamento com o profissional {self.preferred_professional} "
                                       f"está confirmado para {self.selected_date} às {
                                           self.selected_time} "
                                       f"para realizar o serviço {
                                           self.selected_service_name}.\n"
                                       "Agradecemos a preferência.")
                    # Mova para o novo estado após a confirmação
                    self.state = "ASKING_ANOTHER_APPOINTMENT"
                    send_response_func(
                        "Deseja agendar mais algum horário?\nDigite 1 para Sim\nDigite 2 para Não")
                else:
                    # Adicione este log
                    print("Debug: appointment_successful is False")

                    send_response_func(
                        f"Desculpe, algo deu errado ao tentar marcar o seu compromisso. Tente novamente.")
            elif message.strip() == '2':
                self.state = "ASKING_REBOOK"  # Novo estado
                send_response_func(
                    f"Certo {
                        self.name}, cancelei o agendamento. Você deseja fazer um novo agendamento?\n"
                    "Digite 1 para Sim\n"
                    "Digite 2 para Não")
        elif self.state == "ASKING_ANOTHER_APPOINTMENT":
            if message.strip() == '1':
                self.state = "ASKING_TYPE_OF_SERVICE"
                send_response_func("Digite o NÚMERO da opção do serviço que deseja:\n"
                                   "1- Corte Masculino\n"
                                   "2- Corte Feminino\n"
                                   "3- Escova\n"
                                   "4- Tintura\n"
                                   "5- Hidratação\n"
                                   "6- Pé e Mão\n"
                                   "7- Depilação\n"
                                   "8- Manicure\n"
                                   "9- Pedicure")
            elif message.strip() == '2':
                self.state = "INITIAL"  # Resetar o estado para o inicial
                send_response_func(
                    "Estamos te esperando ansiosamente na(s) data(s) agendada(s) 🥰\n\nNikita Beleza & Cia\nAv.Paulo Gartner, 380 Jd: Florida, São Paulo_SP ")
                send_response_func(
                    "Caso queira utilizar o Wase para chegar ate o salão, basta clicar abaixo.\n\nhttps://waze.com/ul/h6gy9zt18z ")
                self.last_message_success = True  # Set the last message as a success message

        elif self.state == "ASKING_REBOOK":
            if message.strip() == '1':
                self.state = "ASKING_SERVICE"  # Voltar para a seleção de serviço
                send_response_func(f"Olá {self.name}, \nDigite o número da opção abaixo:\n\n"
                                   "1 - Para Marcar horário.\n"
                                   "2 - Para Cancelar horário.\n"
                                   "3 - Falar conosco.")
            elif message.strip() == '2':
                self.state = "INITIAL"  # Resetar o estado para o inicial
                send_response_func(
                    "Seu agendamento foi cancelado, quando quiser marcar um horário é só me chamar 🥰")


class WhatsAppBot:
    instance = None

    @staticmethod
    def getInstance():
        if WhatsAppBot.instance is None:
            WhatsAppBot.instance = WhatsAppBot()
        return WhatsAppBot.instance

    def __init__(self):
        if not WhatsAppBot.instance:
            self.chat_states = {}
            WhatsAppBot.instance = self

    # ...
    def handle_message(self, json_data):
        if 'data' in json_data and 'wook' in json_data['data'] and json_data['data']['wook'] == 'RECEIVE_MESSAGE':
            if not json_data['data']['fromMe']:
                remote_jid = json_data['data']['from']
                text = json_data['data']['content'].strip()

                # Extrai o número de telefone do remetente
                incoming_phone_number = remote_jid.split('@')[0]

                # Obtém o estado atual do chat ou cria um novo
                chat_state = self.chat_states.get(
                    remote_jid, ChatState(remote_jid, self))

                # Atualiza o número de telefone no estado do chat
                chat_state.client_phone_number = incoming_phone_number

                # Salva o estado atualizado do chat
                self.chat_states[remote_jid] = chat_state

                chat_state.process_user_message(
                    text, lambda message: self.send_message(remote_jid, message))

    def send_message(self, remote_jid, message):
        print("Sending message:", message)

        url = 'https://cluster.apigratis.com/api/v2/whatsapp/sendText'

        payload = {
            "number": remote_jid,
            "text": message,
            "time_typing": 1
        }

        headers = {
            'Content-Type': 'application/json',
            'DeviceToken': 'adeef5f2-59fc-44fe-9fae-81bed984374f',
            'Authorization': 'Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwczovL3BsYXRhZm9ybWEuYXBpYnJhc2lsLmNvbS5ici9hdXRoL2xvZ2luIiwiaWF0IjoxNjg3OTY2MDQwLCJleHAiOjE3MTk1MDIwNDAsIm5iZiI6MTY4Nzk2NjA0MCwianRpIjoiNEZNVlRFQTNKS1QxaVY4USIsInN1YiI6IjM3MTciLCJwcnYiOiIyM2JkNWM4OTQ5ZjYwMGFkYjM5ZTcwMWM0MDA4NzJkYjdhNTk3NmY3In0.1ygrZavUYeL3oisczugaVtjMI38rFTbRQU8wFe61THo'}

        print("Mensagem enviada:", message)
        print("Before sending API request")
        response = requests.post(url, data=dumps(payload), headers=headers)
        print("After sending API request")
        info_message = response.json()
        print("API response:", info_message)


@app.route('/', methods=['POST'])
def webhook():
    json_data = request.get_json()
    bot = WhatsAppBot.getInstance()
    bot.handle_message(json_data)
    return ''


@app.route('/', methods=['GET', 'POST'])
@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    form = CadastroForm()
    if form.validate_on_submit():
        senha_hash = bcrypt.generate_password_hash(
            form.senha.data).decode('utf-8')
        usuario = Usuario(nome_salao=form.nome_salao.data,
                          email=form.email.data, senha_hash=senha_hash)
        db.session.add(usuario)
        db.session.commit()
        flash('Conta criada com sucesso! Agora você pode fazer login.', 'success')
        return redirect(url_for('login'))
    return render_template('cadastro.html', title='Cadastro', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        usuario = Usuario.query.filter_by(email=form.email.data).first()
        if usuario and bcrypt.check_password_hash(usuario.senha_hash, form.senha.data):
            login_user(usuario)
            flash('Você entrou com sucesso!', 'success')
            return redirect(url_for('painel'))
        else:
            flash('Falha no login. Verifique o email e a senha', 'danger')
    return render_template('login.html', title='Login', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))


@app.route('/painel')
@login_required
def painel():
    profissionais = Profissional.query.all()
    return render_template('painel.html', title='Painel do Usuário', profissionais=profissionais)


@app.route('/add-professional', methods=['POST'])
def add_profissional():
    nome = request.form.get('professionalName')
    servicos = request.form.getlist('services[]')
    precos = request.form.getlist('prices[]')

    novo_profissional = Profissional(nome=nome)
    db.session.add(novo_profissional)

    for servico_nome, preco in zip(servicos, precos):
        novo_servico = Servico(
            nome=servico_nome, preco=preco, profissional=novo_profissional)
        db.session.add(novo_servico)

    db.session.commit()

    return redirect(url_for('painel'))


@app.route('/editar-profissional/<int:id>', methods=['GET', 'POST'])
def editar_profissional(id):
    profissional = Profissional.query.get_or_404(id)
    if request.method == 'POST':
        # Atualizar os dados do profissional
        return redirect(url_for('painel'))
    return render_template('editar_profissional.html', profissional=profissional)


@app.route('/excluir-profissional/<int:id>')
def excluir_profissional(id):
    profissional = Profissional.query.get_or_404(id)
    db.session.delete(profissional)
    db.session.commit()
    return redirect(url_for('painel'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
