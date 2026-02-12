import os
import sys
import threading
import webbrowser
import time
import serial
import serial.tools.list_ports
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import esptool # Importação nativa para evitar loops de janelas

# Configuração de caminhos para PyInstaller
def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

app = Flask(__name__, 
            template_folder=get_resource_path("templates"),
            static_folder=get_resource_path("static"))

app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
# async_mode='threading' é obrigatório para compatibilidade Windows
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
PASTA_FIRMWARES = 'firmwares'

# --- VARIÁVEIS GLOBAIS ---
serial_conn = None
monitor_running = False

if not os.path.exists(PASTA_FIRMWARES):
    os.makedirs(PASTA_FIRMWARES)

# --- CLASSE DE CAPTURA DE LOGS (CORREÇÃO ERRO NONETYPE) ---
class SocketOutput:
    def __init__(self, event_name):
        self.event_name = event_name
        self.encoding = 'utf-8' # Esptool precisa desta propriedade
    
    def write(self, text):
        if text:
            # Envia para o navegador
            socketio.emit(self.event_name, {'data': text.strip()})
            # Tenta escrever no sistema se possível (debug)
            try:
                if sys.__stdout__: sys.__stdout__.write(text)
            except: pass

    def flush(self):
        try:
            if sys.__stdout__: sys.__stdout__.flush()
        except: pass
    
    def isatty(self):
        return False # Diz ao esptool que não é um terminal real

# --- ROTAS ---
@app.route('/')
def index():
    return render_template('index.html')

# Rota para matar o processo e fechar a app
@app.route('/shutdown', methods=['POST'])
def shutdown():
    print(">>> A RECEBER SINAL DE ENCERRAMENTO...")
    fechar_monitor_serial()
    
    def kill_server():
        time.sleep(1)
        os._exit(0) # Mata o processo Python/EXE imediatamente
        
    threading.Thread(target=kill_server).start()
    return jsonify({'status': 'A encerrar...'})

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files: return jsonify({'erro': 'Erro'}), 400
    file = request.files['file']
    if file.filename.endswith('.bin'):
        file.save(os.path.join(PASTA_FIRMWARES, file.filename))
        return jsonify({'sucesso': True})
    return jsonify({'erro': 'Inválido'}), 400

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

# --- MOTOR DE FLASH (NATIVO E SEGURO) ---
def executar_esptool_interno(args):
    # Salva o stdout/stderr original (que pode ser None no .exe)
    stdout_old = sys.stdout
    stderr_old = sys.stderr
    
    # Redireciona tudo para a nossa classe WebSocket
    sys.stdout = SocketOutput('log_flash')
    sys.stderr = SocketOutput('log_flash')
    
    try:
        esptool.main(args)
        socketio.emit('log_flash', {'data': ">>> SUCESSO: Operação terminada."})
    except SystemExit as e:
        # Esptool usa sys.exit(), capturamos para não fechar o programa
        if e.code != 0:
            socketio.emit('log_flash', {'data': f">>> ERRO: Código {e.code}"})
    except Exception as e:
        socketio.emit('log_flash', {'data': f">>> ERRO CRÍTICO: {str(e)}"})
    finally:
        # Restaura o sistema
        sys.stdout = stdout_old
        sys.stderr = stderr_old
        socketio.emit('fim_processo')

@socketio.on('iniciar_processo')
def handle_processo(dados):
    fechar_monitor_serial()
    time.sleep(0.2)

    porta = dados['porta']
    baud = dados['baud']
    ficheiro = dados['ficheiro']
    modo = dados['modo']
    caminho = os.path.abspath(os.path.join(PASTA_FIRMWARES, ficheiro)) if ficheiro else ""

    # ARGUMENTOS CORRIGIDOS PARA V5.1.0 (Hífens em vez de underscores)
    args = ['--port', porta, '--baud', baud]
    args.extend(['--before', 'default-reset', '--after', 'hard-reset']) 

    if modo == 'flash_limpo':
        # write-flash e flags com hífens
        args.extend(['write-flash', '--erase-all', '-z', '--flash-mode', 'dio', '0x0', caminho])
    elif modo == 'apenas_limpar':
        args.append('erase-flash') 

    # Executa numa thread separada
    threading.Thread(target=executar_esptool_interno, args=(args,)).start()

# --- MONITOR SERIAL ---
def ler_porta_serial():
    global serial_conn, monitor_running
    while monitor_running and serial_conn and serial_conn.is_open:
        try:
            if serial_conn.in_waiting > 0:
                line = serial_conn.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    socketio.emit('log_monitor', {'data': line})
            else:
                time.sleep(0.01)
        except:
            break

@socketio.on('iniciar_monitor')
def start_monitor(data):
    global serial_conn, monitor_running
    fechar_monitor_serial()
    try:
        serial_conn = serial.Serial(data['porta'], int(data['baud']), timeout=1)
        monitor_running = True
        threading.Thread(target=ler_porta_serial, daemon=True).start()
        socketio.emit('status_monitor', {'ativo': True, 'msg': 'Conectado'})
    except Exception as e:
        socketio.emit('status_monitor', {'ativo': False, 'msg': str(e)})

@socketio.on('parar_monitor')
def stop_monitor():
    fechar_monitor_serial()
    socketio.emit('status_monitor', {'ativo': False, 'msg': 'Desconectado'})

def fechar_monitor_serial():
    global serial_conn, monitor_running
    monitor_running = False
    if serial_conn and serial_conn.is_open:
        try:
            serial_conn.close()
        except: pass
    serial_conn = None

if __name__ == '__main__':
    url = "http://127.0.0.1:5000"
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    # allow_unsafe_werkzeug=True é OBRIGATÓRIO para funcionar no .exe
    socketio.run(app, debug=False, port=5000, use_reloader=False, allow_unsafe_werkzeug=True)