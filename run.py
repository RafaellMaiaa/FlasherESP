import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

import eventlet
eventlet.monkey_patch()

import os
import webbrowser
from app import create_app, socketio

app = create_app()

def abrir_browser():
    eventlet.sleep(1.5)
    print(">> A abrir o painel no navegador (http://127.0.0.1:5000/)...")
    webbrowser.open_new('http://127.0.0.1:5000/')

if __name__ == '__main__':
    print("==================================================")
    print(" INICIANDO SERVIDOR INDUSTRIAL ESP FLASHER (V6.2)")
    print("==================================================")
    eventlet.spawn(abrir_browser)
    # use_reloader=False evita que o servidor arranque duas vezes no Windows
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=False)