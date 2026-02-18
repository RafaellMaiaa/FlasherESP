import os
import sys
import threading
import webbrowser
import time
import json
import csv
import serial
import serial.tools.list_ports
import subprocess
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import esptool

# --- CONFIGURAÇÃO DE CAMINHOS ---
def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

app = Flask(__name__, 
            template_folder=get_resource_path("templates"),
            static_folder=get_resource_path("static"))

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Caminhos Absolutos (Para não perder ficheiros no Windows)
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PASTA_FIRMWARES = os.path.join(BASE_DIR, 'firmwares')
FICHEIRO_PERFIS = os.path.join(BASE_DIR, 'perfis.json')
FICHEIRO_CSV = os.path.join(BASE_DIR, 'dispositivos_registados.csv')

# --- VARIÁVEIS GLOBAIS (Correção do NameError) ---
serial_conn = None
monitor_running = False

if not os.path.exists(PASTA_FIRMWARES):
    os.makedirs(PASTA_FIRMWARES)

# --- CORREÇÃO AUTOMÁTICA DO CSV ---
def verificar_csv():
    """Verifica e repara o cabeçalho do CSV se for antigo"""
    if os.path.exists(FICHEIRO_CSV):
        try:
            with open(FICHEIRO_CSV, 'r', encoding='utf-8') as f:
                header = f.readline().strip().split(',')
            
            # Se faltar a coluna Serial, vamos recriar o ficheiro
            if "Serial" not in header:
                print("Atualizando formato do CSV...")
                with open(FICHEIRO_CSV, 'r', encoding='utf-8') as f:
                    rows = list(csv.reader(f))
                
                with open(FICHEIRO_CSV, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Data', 'MAC', 'Serial', 'IMEI', 'Firmware'])
                    # Migra dados antigos
                    for row in rows[1:]:
                        if len(row) >= 4:
                            # Tenta gerar serial do MAC antigo
                            mac = row[1]
                            serial_num = mac.replace(':', '').upper()
                            writer.writerow([row[0], mac, serial_num, row[2], row[3]])
        except: pass

verificar_csv() # Executa ao arrancar

# --- CLASSE DE OUTPUT ---
class SocketOutput:
    def __init__(self, event_name):
        self.event_name = event_name
        self.encoding = 'utf-8'
    def write(self, text):
        if text:
            socketio.emit(self.event_name, {'data': text.strip()})
            try:
                if sys.__stdout__: sys.__stdout__.write(text)
            except: pass
    def flush(self): pass
    def isatty(self): return False

# --- DADOS ---
def carregar_perfis():
    if not os.path.exists(FICHEIRO_PERFIS): return []
    try:
        with open(FICHEIRO_PERFIS, 'r', encoding='utf-8') as f: return json.load(f)
    except: return []

def guardar_perfis(perfis):
    with open(FICHEIRO_PERFIS, 'w', encoding='utf-8') as f: json.dump(perfis, f, indent=4)

def registar_dispositivo(mac, imei, serial_num, firmware):
    header = ['Data', 'MAC', 'Serial', 'IMEI', 'Firmware']
    existe = os.path.exists(FICHEIRO_CSV)
    try:
        with open(FICHEIRO_CSV, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not existe: writer.writerow(header)
            writer.writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                mac, serial_num, imei, firmware
            ])
            f.flush()
            os.fsync(f.fileno())
    except Exception as e:
        print(f"Erro CSV: {e}")

# --- ROTAS ---
@app.route('/')
def index(): return render_template('index.html')

@app.route('/shutdown', methods=['POST'])
def shutdown():
    fechar_monitor_serial()
    def kill(): time.sleep(1); os._exit(0)
    threading.Thread(target=kill).start()
    return jsonify({'status': 'ok'})

@app.route('/listar_portas')
def listar_portas():
    return jsonify([{'device': p.device, 'description': p.description} for p in serial.tools.list_ports.comports()])

@app.route('/listar_ficheiros')
def listar_ficheiros():
    return jsonify([f for f in os.listdir(PASTA_FIRMWARES) if f.endswith('.bin')])

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files['file']
    file.save(os.path.join(PASTA_FIRMWARES, file.filename))
    return jsonify({'sucesso': True})

@app.route('/delete_file', methods=['POST'])
def delete_file():
    try:
        os.remove(os.path.join(PASTA_FIRMWARES, request.json.get('filename')))
        return jsonify({'sucesso': True})
    except: return jsonify({'erro': 'Erro'}), 500

@app.route('/api/perfis', methods=['GET', 'POST'])
def api_perfis():
    if request.method == 'POST':
        guardar_perfis(request.json)
        return jsonify({"status": "ok"})
    return jsonify(carregar_perfis())

@app.route('/api/logs')
def api_logs():
    if not os.path.exists(FICHEIRO_CSV): return jsonify([])
    try:
        with open(FICHEIRO_CSV, 'r', encoding='utf-8') as f:
            return jsonify(list(csv.DictReader(f)))
    except: return jsonify([])

# --- MOTOR DE FLASH INTELIGENTE ---
def executar_flash(porta, baud, ficheiro, modo):
    stdout_old = sys.stdout
    sys.stdout = SocketOutput('log_flash')
    
    mac_detectado = "N/A"
    imei_detectado = "N/A"
    serial_detectado = "N/A"
    
    # 1. Tentar ler IMEI (Apenas se for instalar)
    if modo == 'flash_limpo':
        socketio.emit('log_flash', {'data': "🔍 A verificar Modem GSM..."})
        try:
            # Tenta conectar a 115200 para ler info AT
            with serial.Serial(porta, 115200, timeout=0.5) as s:
                s.write(b"AT+GSN\r\n")
                time.sleep(0.2)
                resp = s.read_all().decode(errors='ignore')
                for line in resp.split('\n'):
                    line = line.strip()
                    if line.isdigit() and len(line) >= 15:
                        imei_detectado = line
                        socketio.emit('log_flash', {'data': f"✅ IMEI: {imei_detectado}"})
                        break
        except: pass
    
    time.sleep(0.5) # Pausa para libertar porta

    caminho = os.path.join(PASTA_FIRMWARES, ficheiro) if ficheiro else ""
    
    # Argumentos do Esptool (V5.1.0)
    args = [sys.executable, '-m', 'esptool', '--port', porta, '--baud', str(baud), 
            '--before', 'default-reset', '--after', 'hard-reset']
    
    if modo == 'flash_limpo':
        args.extend(['write-flash', '--erase-all', '-z', '--flash-mode', 'dio', '0x0', caminho])
    elif modo == 'apenas_limpar':
        args.append('erase-flash')

    sucesso = False
    try:
        # Iniciamos o processo de flash
        processo = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        
        # Lemos o output linha a linha ENQUANTO acontece
        for linha in iter(processo.stdout.readline, ''):
            clean_line = linha.strip()
            if clean_line:
                socketio.emit('log_flash', {'data': clean_line})
                
                # --- CAPTURA DE MAC EM TEMPO REAL ---
                # O esptool imprime "MAC: xx:xx..." durante a conexão
                if "MAC:" in clean_line:
                    try:
                        parts = clean_line.split("MAC:")
                        if len(parts) > 1:
                            mac_raw = parts[1].strip()
                            # Validação básica
                            if mac_raw.count(':') == 5:
                                mac_detectado = mac_raw
                                serial_detectado = mac_raw.replace(':', '').upper()
                                socketio.emit('log_flash', {'data': f"✅ MAC Capturado: {mac_detectado}"})
                                socketio.emit('log_flash', {'data': f"✅ Serial Gerado: {serial_detectado}"})
                    except: pass
        
        processo.wait()
        if processo.returncode == 0: sucesso = True
            
    except Exception as e:
        socketio.emit('log_flash', {'data': f"❌ ERRO CRÍTICO: {str(e)}"})
    finally:
        sys.stdout = stdout_old
        
        # --- GRAVAÇÃO NO CSV ---
        if sucesso and modo == 'flash_limpo':
            registar_dispositivo(mac_detectado, imei_detectado, serial_detectado, ficheiro)
            socketio.emit('log_flash', {'data': "💾 DADOS GUARDADOS NO CSV!"})
            
        socketio.emit('fim_processo')

@socketio.on('iniciar_processo')
def handle_processo(dados):
    fechar_monitor_serial()
    time.sleep(0.5)
    threading.Thread(target=executar_flash, args=(dados['porta'], int(dados['baud']), dados['ficheiro'], dados['modo'])).start()

# --- MONITOR SERIAL ---
def ler_porta_serial():
    global serial_conn, monitor_running
    while monitor_running and serial_conn and serial_conn.is_open:
        try:
            if serial_conn.in_waiting > 0:
                line = serial_conn.readline().decode('utf-8', errors='ignore').strip()
                if line: socketio.emit('log_monitor', {'data': line})
            else: time.sleep(0.01)
        except: break

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
    if serial_conn: 
        try: serial_conn.close() 
        except: pass
    serial_conn = None

if __name__ == '__main__':
    threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    socketio.run(app, debug=False, port=5000, use_reloader=False, allow_unsafe_werkzeug=True)