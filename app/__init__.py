import os
import sys
from flask import Flask
from flask_socketio import SocketIO

socketio = SocketIO(async_mode='eventlet', cors_allowed_origins="*")

def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath(os.path.dirname(os.path.dirname(__file__))), relative_path)

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
FIRMWARE_FOLDER = os.path.join(BASE_DIR, 'firmwares')
ETIQUETA_FOLDER = os.path.join(BASE_DIR, 'etiquetas')
PDF_FOLDER = os.path.join(BASE_DIR, 'pdfs')
CSV_FILE = os.path.join(BASE_DIR, 'dispositivos_registados.csv')
PERFIS_FILE = os.path.join(BASE_DIR, 'perfis.json')

def create_app():
    app = Flask(__name__, template_folder=get_resource_path('app/templates'))
    app.config['SECRET_KEY'] = 'FlasherESP_Key_123'
    
    for folder in [FIRMWARE_FOLDER, ETIQUETA_FOLDER, PDF_FOLDER]:
        if not os.path.exists(folder):
            os.makedirs(folder)

    # Injetar variáveis de configuração na app para os módulos usarem
    app.config['FIRMWARE_FOLDER'] = FIRMWARE_FOLDER
    app.config['ETIQUETA_FOLDER'] = ETIQUETA_FOLDER
    app.config['PDF_FOLDER'] = PDF_FOLDER
    app.config['CSV_FILE'] = CSV_FILE
    app.config['PERFIS_FILE'] = PERFIS_FILE

    socketio.init_app(app)

    from app.routes import main_routes
    app.register_blueprint(main_routes)

    # Importa os eventos de socket para serem registados
    from app import sockets

    return app