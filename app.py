import os
import sys
import subprocess
import threading
import webbrowser
import time
import serial # Requer: pip install pyserial
import serial.tools.list_ports
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit

def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

app = Flask(__name__, 
            template_folder=get_resource_path("templates"),
            static_folder=get_resource_path("static"))

app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
PASTA_FIRMWARES = 'firmwares'

# --- VARIÁVEIS GLOBAIS PARA O MONITOR SERIAL ---
serial_conn = None
monitor_running = False
monitor_thread = None

if not os.path.exists(PASTA_FIRMWARES):
    os.makedirs(PASTA_FIRMWARES)

# --- ROTAS PADRÃO ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files: return jsonify({'erro': 'Sem ficheiro'}), 400
    file = request.files['file']
    if file.filename == '' or not file.filename.endswith('.bin'):
        return jsonify({'erro': 'Apenas .bin'}), 400
    file.save(os.path.join(PASTA_FIRMWARES, file.filename))
    return jsonify({'sucesso': True})

@app.route('/delete_file', methods=['POST'])
def delete_file():
    try:
        os.remove(os.path.join(PASTA_FIRMWARES, request.json.get('filename')))
        return jsonify({'sucesso': True})
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@app.route('/listar_portas')
def listar_portas():
    return jsonify([{'device': p.device, 'description': p.description} for p in serial.tools.list_ports.comports()])

@app.route('/listar_ficheiros')
def listar_ficheiros():
    return jsonify([f for f in os.listdir(PASTA_FIRMWARES) if f.endswith('.bin')])

# --- MOTOR DE FLASH (Instalação) ---
def correr_comando(cmd_list):
    try:
        processo = subprocess.Popen(
            cmd_list, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, universal_newlines=True, shell=False 
        )
        for linha in iter(processo.stdout.readline, ''):
            if linha:
                socketio.emit('log_flash', {'data': linha.rstrip()})
        processo.wait()
    except Exception as e:
        socketio.emit('log_flash', {'data': f"ERRO CRÍTICO: {str(e)}"})
    finally:
        socketio.emit('fim_processo')

@socketio.on('iniciar_processo')
def handle_processo(dados):
    # SEGURANÇA: Se o monitor serial estiver ligado, desliga-o antes de flashar!
    fechar_monitor_serial() 
    time.sleep(0.5) # Dá tempo à porta para libertar

    porta = dados['porta']
    baud = dados['baud']
    ficheiro = dados['ficheiro']
    modo = dados['modo']
    caminho = os.path.abspath(os.path.join(PASTA_FIRMWARES, ficheiro)) if ficheiro else ""

    if modo == 'flash_limpo':
        cmd = [
            sys.executable, "-m", "esptool", "--port", porta, "--baud", baud,
            "--before", "default_reset", "--after", "hard_reset",
            "write_flash", "--erase-all", "-z", "--flash_mode", "dio", "0x0", caminho
        ]
        threading.Thread(target=correr_comando, args=(cmd,)).start()
    
    elif modo == 'apenas_limpar':
        cmd = [sys.executable, "-m", "esptool", "--port", porta, "--before", "default_reset", "erase_flash"]
        threading.Thread(target=correr_comando, args=(cmd,)).start()

# --- MOTOR DE MONITOR SERIAL (Tera Term Style) ---
def ler_porta_serial():
    global serial_conn, monitor_running
    while monitor_running and serial_conn and serial_conn.is_open:
        try:
            if serial_conn.in_waiting > 0:
                # Lê a linha e descodifica (ignora erros de caracteres estranhos)
                linha = serial_conn.readline().decode('utf-8', errors='ignore').strip()
                if linha:
                    socketio.emit('log_monitor', {'data': linha})
            else:
                time.sleep(0.01) # Evita uso excessivo de CPU
        except Exception as e:
            socketio.emit('log_monitor', {'data': f"[ERRO LEITURA]: {str(e)}"})
            break

@socketio.on('iniciar_monitor')
def abrir_monitor_serial(dados):
    global serial_conn, monitor_running, monitor_thread
    porta = dados['porta']
    baud = int(dados['baud']) # Monitor geralmente usa 115200

    # Fecha se já estiver aberto
    fechar_monitor_serial()

    try:
        serial_conn = serial.Serial(porta, baud, timeout=1)
        monitor_running = True
        monitor_thread = threading.Thread(target=ler_porta_serial)
        monitor_thread.daemon = True
        monitor_thread.start()
        socketio.emit('status_monitor', {'ativo': True, 'msg': f"Conectado a {porta} ({baud})"})
    except Exception as e:
        socketio.emit('status_monitor', {'ativo': False, 'msg': f"Erro ao conectar: {str(e)}"})

@socketio.on('parar_monitor')
def parar_monitor_wrapper():
    fechar_monitor_serial()
    socketio.emit('status_monitor', {'ativo': False, 'msg': "Desconectado."})

def fechar_monitor_serial():
    global serial_conn, monitor_running
    monitor_running = False
    if serial_conn and serial_conn.is_open:
        try:
            serial_conn.close()
        except:
            pass
    serial_conn = None

if __name__ == '__main__':
    url = "http://127.0.0.1:5000"
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    print(f"--- SERVIDOR PRONTO: {url} ---")
    socketio.run(app, debug=False, port=5000, use_reloader=False)