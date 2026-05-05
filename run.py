import os
import sys
os.environ['EVENTLET_HUB'] = 'selects'
import eventlet
eventlet.monkey_patch()

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

if getattr(sys, 'frozen', False):
    sys.path.insert(0, sys._MEIPASS)
else:
    sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import webbrowser
from app import create_app, socketio

aplicacao = create_app()

def abrir_browser():
    eventlet.sleep(1.5)
    webbrowser.open_new('http://127.0.0.1:5000/')

if __name__ == '__main__':
    print("==================================================")
    print(" INICIANDO SERVIDOR INDUSTRIAL ESP FLASHER (V6.2)")
    print("==================================================")
    eventlet.spawn(abrir_browser)
    socketio.run(aplicacao, host='0.0.0.0', port=5000, debug=False, use_reloader=False)
