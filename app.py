import os
import sys
import threading
import webbrowser
import time
import json
import csv
import re
import socket
import serial
import serial.tools.list_ports
import random
from datetime import datetime
from flask import Flask, render_template, jsonify, request, send_file
from flask_socketio import SocketIO, emit
import esptool

# --- CONFIGURAÇÃO DE CAMINHOS ---
def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'): return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, template_folder=get_resource_path("templates"), static_folder=get_resource_path("static"))
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

PASTA_FIRMWARES = os.path.join(BASE_DIR, 'firmwares')
PASTA_ETIQUETAS = os.path.join(BASE_DIR, 'etiquetas')
FICHEIRO_PERFIS = os.path.join(BASE_DIR, 'perfis.json')
FICHEIRO_CSV = os.path.join(BASE_DIR, 'dispositivos_registados.csv')

serial_conn, monitor_running, buffer_serial = None, False, ""
dados_sessao = {"mac": "N/A", "imei": "N/A", "serial": "N/A", "cimi": "N/A"}

for pasta in [PASTA_FIRMWARES, PASTA_ETIQUETAS]:
    if not os.path.exists(pasta): os.makedirs(pasta)

# =====================================================================
# MÓDULO: GESTOR ZPL (Modularização)
# =====================================================================
class MotorZPL:
    def __init__(self, pasta_templates):
        self.pasta = pasta_templates

    def listar_templates(self):
        # Aceita zpl, txt, lbl e nlbl
        return [f for f in os.listdir(self.pasta) if f.endswith(('.zpl', '.txt', '.lbl', '.nlbl', '.prn'))]

    def gerar_codigo(self, nome_template, dicionario_dados):
        caminho = os.path.join(self.pasta, nome_template)
        if not os.path.exists(caminho):
            raise FileNotFoundError(f"Template {nome_template} não encontrado.")
        
        with open(caminho, 'rb') as f:
            raw_data = f.read()
            
        if len(raw_data) == 0:
            raise ValueError("O template base está vazio.")
            
        # Proteção contra ficheiros binários do ZebraDesigner (.nlbl original)
        if raw_data.startswith(b'PK\x03\x04') or b'<?xml' in raw_data[:50]:
            raise ValueError("AVISO: Carregou o ficheiro de projeto do ZebraDesigner. Tem de usar a opção 'Imprimir para Ficheiro' no ZebraDesigner para gerar o código de máquina, e carregar esse ficheiro!")
            
        try: conteudo = raw_data.decode('utf-8')
        except UnicodeDecodeError: conteudo = raw_data.decode('iso-8859-1', errors='ignore')
        
        # --- NOVO: Criar versão do MAC limpo e MAC minúsculo ---
        if 'mac' in dicionario_dados and isinstance(dicionario_dados['mac'], str):
            dicionario_dados['mac_clean'] = dicionario_dados['mac'].replace(':', '')
            dicionario_dados['mac_lower'] = dicionario_dados['mac'].lower()
        
        # Injeção modular de variáveis
        for chave, valor in dicionario_dados.items():
            if valor is not None:
                conteudo = conteudo.replace(f'@{chave.upper()}@', str(valor))
            
        return conteudo

    def imprimir_rede(self, zpl_data, ip, porta=9100):
        """Envia o código ZPL cru diretamente para a porta TCP da impressora Zebra"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(3)
                s.connect((ip, porta))
                s.sendall(zpl_data.encode('utf-8'))
            return True, "Enviado com sucesso para a impressora."
        except Exception as e:
            return False, f"Falha na comunicação TCP: {str(e)}"

# Instanciar o motor
motor_zpl = MotorZPL(PASTA_ETIQUETAS)
# =====================================================================

# --- CSV AUTOMÁTICO ---
def verificar_csv():
    if os.path.exists(FICHEIRO_CSV):
        try:
            with open(FICHEIRO_CSV, 'r', encoding='utf-8') as f:
                header = f.readline().strip().split(',')
            if "CIMI" not in header:
                with open(FICHEIRO_CSV, 'r', encoding='utf-8') as f: rows = list(csv.reader(f))
                with open(FICHEIRO_CSV, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Data', 'MAC', 'Serial', 'IMEI', 'CIMI', 'Firmware'])
                    for row in rows[1:]:
                        if len(row) >= 5: writer.writerow([row[0], row[1], row[2], row[3], 'N/A', row[4]])
                        elif len(row) == 4: writer.writerow([row[0], row[1], row[1].replace(':',''), row[2], 'N/A', row[3]])
        except: pass
    else:
        with open(FICHEIRO_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Data', 'MAC', 'Serial', 'IMEI', 'CIMI', 'Firmware'])
verificar_csv()

# --- CLASSE DE LOGS ---
class SocketOutput:
    def __init__(self, event_name):
        self.event_name = event_name
        self.encoding = 'utf-8'
    
    def write(self, text):
        global dados_sessao
        if text:
            socketio.emit(self.event_name, {'data': text.strip()})
            try:
                if sys.__stdout__: sys.__stdout__.write(text)
            except: pass
            if "MAC: " in text:
                try:
                    parts = text.split("MAC: ")
                    if len(parts) > 1:
                        mac_raw = parts[1].strip().split(' ')[0]
                        if mac_raw.count(':') == 5:
                            dados_sessao["mac"] = mac_raw.upper()
                            socketio.emit('dados_capturados', dados_sessao)
                except: pass
    def flush(self): pass
    def isatty(self): return False

def extrair_parametros_log(texto):
    d = {"mac": "", "imei": "", "sn": "", "cimi": ""}
    m_cimi_cmd = re.search(r'AT\+CIMI[\s\S]*?<<\s*(\d{15})', texto, re.IGNORECASE)
    m_cimi_log = re.search(r'CIMI[:\s=]*(\d{15})', texto, re.IGNORECASE)
    if m_cimi_cmd: d["cimi"] = m_cimi_cmd.group(1)
    elif m_cimi_log: d["cimi"] = m_cimi_log.group(1)

    m_imei_log = re.search(r'imei:\s*(\d{15})', texto, re.IGNORECASE)
    m_imei_cmd = re.search(r'AT\+CGSN[\s\S]*?<<\s*(\d{15})', texto, re.IGNORECASE)
    if m_imei_log: d["imei"] = m_imei_log.group(1)
    elif m_imei_cmd: d["imei"] = m_imei_cmd.group(1)
    
    m_mac_std = re.search(r'([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})', texto)
    m_mac_flat = re.search(r'mac:\s*([0-9A-Fa-f]{12})', texto, re.IGNORECASE)
    
    if m_mac_std:
        d["mac"] = m_mac_std.group(0).upper()
    elif m_mac_flat:
        flat = m_mac_flat.group(1).upper()
        d["mac"] = ':'.join(flat[i:i+2] for i in range(0, 12, 2))
        
    if not d["imei"]:
        todos_15 = re.findall(r'\b\d{15}\b', texto)
        for val in todos_15:
            if val != d["cimi"]: d["imei"] = val; break
            
    # SN Aleatório caso encontre identificadores
    if d["mac"] or d["imei"] or d["cimi"]:
        d["sn"] = str(random.randint(1000000000, 9999999999))
        
    return d

# --- ROTAS PRINCIPAIS ---
@app.route('/')
def index(): return render_template('index.html')

@app.route('/analisar_buffer', methods=['POST'])
def analisar_buffer():
    global buffer_serial
    return jsonify(extrair_parametros_log(buffer_serial))

@app.route('/analisar_logs_ficheiro', methods=['POST'])
def analisar_logs_ficheiro():
    if 'file' not in request.files: return jsonify({'erro': 'Nenhum ficheiro'}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({'erro': 'Ficheiro sem nome'}), 400
    try: return jsonify(extrair_parametros_log(file.read().decode('utf-8', errors='ignore')))
    except Exception as e: return jsonify({'erro': str(e)}), 500

@app.route('/guardar_csv_manual', methods=['POST'])
def guardar_csv_manual():
    d = request.json
    registar_dispositivo(d.get('mac', ''), d.get('imei', ''), d.get('sn', ''), d.get('cimi', ''), "Manual/Monitor")
    return jsonify({'sucesso': True})

# --- ROTAS DE GESTÃO DE ETIQUETAS E ZPL ---
@app.route('/listar_etiquetas')
def listar_etiquetas():
    return jsonify(motor_zpl.listar_templates())

@app.route('/upload_etiqueta', methods=['POST'])
def upload_etiqueta():
    f = request.files['file']
    f.save(os.path.join(PASTA_ETIQUETAS, f.filename))
    return jsonify({'sucesso': True})

@app.route('/delete_etiqueta', methods=['POST'])
def delete_etiqueta():
    try: os.remove(os.path.join(PASTA_ETIQUETAS, request.json.get('filename'))); return jsonify({'sucesso': True})
    except Exception as e: return jsonify({'erro': str(e)}), 500

@app.route('/api/processar_zpl', methods=['POST'])
def processar_zpl():
    """Usa o Motor ZPL para gerar e (opcionalmente) imprimir via Rede"""
    dados = request.json
    label_file = dados.get('label_file')
    ip_impressora = dados.get('ip_impressora', '').strip()

    if not label_file: return jsonify({'erro': 'Nenhum modelo ativo.'}), 400

    try:
        # 1. Gerar o código via MotorZPL
        zpl_final = motor_zpl.gerar_codigo(label_file, dados)
        impresso = False
        msg_impressao = ""
        
        # 2. Imprimir via Rede se existir IP
        if ip_impressora:
            sucesso, msg = motor_zpl.imprimir_rede(zpl_final, ip_impressora)
            impresso = sucesso
            msg_impressao = msg
            if not sucesso:
                return jsonify({'erro': msg}), 500

        extensao = label_file.split('.')[-1]
        sn_file = dados.get('sn') or dados.get('imei') or "GERADO"
        
        return jsonify({
            'sucesso': True, 
            'zpl': zpl_final, 
            'impresso_direto': impresso,
            'mensagem': msg_impressao,
            'extensao': extensao,
            'filename': f"Etiqueta_{sn_file}.{extensao}"
        })
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

# --- ROTAS GERAIS ---
@app.route('/api/export_csv')
def export_csv():
    if os.path.exists(FICHEIRO_CSV): return send_file(FICHEIRO_CSV, as_attachment=True, download_name=f"Logs_Producao_{datetime.now().strftime('%Y%m%d_%H%M')}.csv")
    return "Ficheiro CSV não encontrado", 404

@app.route('/api/delete_csv', methods=['POST'])
def delete_csv():
    if os.path.exists(FICHEIRO_CSV): os.remove(FICHEIRO_CSV); verificar_csv()
    return jsonify({'sucesso': True})

@app.route('/api/logs')
def api_logs():
    if not os.path.exists(FICHEIRO_CSV): return jsonify([])
    try:
        with open(FICHEIRO_CSV, 'r', encoding='utf-8') as f: return jsonify(list(csv.DictReader(f)))
    except: return jsonify([])

@app.route('/listar_portas')
def listar_portas(): return jsonify([{'device': p.device, 'description': p.description} for p in serial.tools.list_ports.comports()])
@app.route('/listar_ficheiros')
def listar_ficheiros(): return jsonify([f for f in os.listdir(PASTA_FIRMWARES) if f.endswith('.bin')])
@app.route('/upload', methods=['POST'])
def upload(): request.files['file'].save(os.path.join(PASTA_FIRMWARES, request.files['file'].filename)); return jsonify({'sucesso': True})
@app.route('/delete_file', methods=['POST'])
def delete_file(): os.remove(os.path.join(PASTA_FIRMWARES, request.json.get('filename'))); return jsonify({'sucesso': True})
@app.route('/api/perfis', methods=['GET', 'POST'])
def api_perfis():
    if request.method == 'POST': guardar_perfis(request.json); return jsonify({"status": "ok"})
    return jsonify(carregar_perfis())
@app.route('/shutdown', methods=['POST'])
def shutdown(): fechar_monitor_serial(); threading.Thread(target=lambda: (time.sleep(1), os._exit(0))).start(); return jsonify({'status': 'ok'})

def carregar_perfis():
    if not os.path.exists(FICHEIRO_PERFIS): return []
    try: return json.load(open(FICHEIRO_PERFIS))
    except: return []
def guardar_perfis(p): json.dump(p, open(FICHEIRO_PERFIS,'w'), indent=4)

def registar_dispositivo(mac, imei, serial_num, cimi, firmware):
    ex = os.path.exists(FICHEIRO_CSV)
    try:
        # Tira os dois pontos (:) do MAC apenas para guardar no CSV
        mac_csv = mac.replace(':', '') if isinstance(mac, str) else mac
        
        with open(FICHEIRO_CSV, 'a', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            if not ex: w.writerow(['Data', 'MAC', 'Serial', 'IMEI', 'CIMI', 'Firmware'])
            w.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), mac_csv, serial_num, imei, cimi, firmware])
            f.flush(); os.fsync(f.fileno())
    except: pass

def executar_flash(porta, baud, ficheiro, modo):
    global dados_sessao
    dados_sessao = {"mac": "N/A", "imei": "N/A", "serial": str(random.randint(1000000000, 9999999999)), "cimi": "N/A"}
    old_stdout = sys.stdout
    sys.stdout, sys.stderr = SocketOutput('log_flash'), SocketOutput('log_flash')
    
    if modo == 'flash_limpo':
        socketio.emit('log_flash', {'data': "🔍 A sondar IMEI (GSM)..."})
        try:
            with serial.Serial(porta, 115200, timeout=0.5) as s:
                s.write(b"AT+GSN\r\n")
                time.sleep(0.3)
                r = s.read_all().decode(errors='ignore')
                for l in r.split('\n'):
                    l = l.strip()
                    if l.isdigit() and len(l) >= 15: dados_sessao["imei"] = l; socketio.emit('dados_capturados', dados_sessao); break
        except: pass
    
    time.sleep(0.5)
    caminho = os.path.join(PASTA_FIRMWARES, ficheiro) if ficheiro else ""
    args = ['--port', porta, '--baud', str(baud), '--before', 'default-reset', '--after', 'hard-reset']
    if modo == 'flash_limpo': args.extend(['write-flash', '--erase-all', '-z', '--flash-mode', 'dio', '0x0', caminho])
    elif modo == 'apenas_limpar': args.append('erase-flash')

    sucesso = False
    try: esptool.main(args); sucesso = True; socketio.emit('log_flash', {'data': "🏆 SUCESSO."})
    except SystemExit as e:
        if e.code == 0: sucesso = True; socketio.emit('log_flash', {'data': "🏆 SUCESSO."})
        else: socketio.emit('log_flash', {'data': f"❌ ERRO: {e.code}"})
    except Exception as e: socketio.emit('log_flash', {'data': f"❌ CRÍTICO: {str(e)}"})
    finally:
        sys.stdout, sys.stderr = old_stdout, sys.__stderr__
        if sucesso and modo == 'flash_limpo':
            registar_dispositivo(dados_sessao['mac'], dados_sessao['imei'], dados_sessao['serial'], dados_sessao['cimi'], ficheiro)
            socketio.emit('log_flash', {'data': "💾 Registado no CSV."})
        socketio.emit('fim_processo')

@socketio.on('iniciar_processo')
def handle_processo(dados):
    fechar_monitor_serial(); time.sleep(0.5)
    threading.Thread(target=executar_flash, args=(dados['porta'], int(dados['baud']), dados['ficheiro'], dados['modo'])).start()

def ler_porta_serial():
    global serial_conn, monitor_running, buffer_serial
    buffer_serial = ""
    while monitor_running and serial_conn and serial_conn.is_open:
        try:
            if serial_conn.in_waiting > 0:
                l = serial_conn.readline().decode('utf-8', errors='ignore')
                buffer_serial += l
                if len(buffer_serial) > 10000: buffer_serial = buffer_serial[-10000:]
                socketio.emit('log_monitor', {'data': l.strip()})
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
    except Exception as e: socketio.emit('status_monitor', {'ativo': False, 'msg': str(e)})

@socketio.on('parar_monitor')
def stop_monitor(): fechar_monitor_serial(); socketio.emit('status_monitor', {'ativo': False, 'msg': 'Desconectado'})

def fechar_monitor_serial():
    global serial_conn, monitor_running
    monitor_running = False
    if serial_conn: 
        try: serial_conn.close()
        except: pass
    serial_conn = None

if __name__ == '__main__':
    url = "http://127.0.0.1:5000"
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    print(f"--- SERVIDOR PRONTO: {url} ---")
    socketio.run(app, debug=False, port=5000, use_reloader=False, allow_unsafe_werkzeug=True)