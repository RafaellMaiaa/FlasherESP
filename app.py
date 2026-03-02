import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

import eventlet
eventlet.monkey_patch()
import os
import sys
import subprocess
import serial
import serial.tools.list_ports
import re
import socket
import csv
import json
from datetime import datetime
import random
import webbrowser
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
from flask_socketio import SocketIO


# --- CONFIGURAÇÃO DE CAMINHOS E PASTAS ---
def get_resource_path(relative_path):
    """Garante que a app encontra as pastas quer esteja em .py ou .exe"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath(os.path.dirname(__file__)), relative_path)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Pastas Auto-Geradas
FIRMWARE_FOLDER = os.path.join(BASE_DIR, 'firmwares')
ETIQUETA_FOLDER = os.path.join(BASE_DIR, 'etiquetas')
PDF_FOLDER = os.path.join(BASE_DIR, 'pdfs')  # NOVA PASTA V6: Manuais
CSV_FILE = os.path.join(BASE_DIR, 'dispositivos_registados.csv')
PERFIS_FILE = os.path.join(BASE_DIR, 'perfis.json')

for folder in [FIRMWARE_FOLDER, ETIQUETA_FOLDER, PDF_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# --- INICIALIZAÇÃO FLASK ---
app = Flask(__name__, template_folder=get_resource_path('templates'))
app.config['SECRET_KEY'] = 'FlasherESP_Key_123'
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

# Variáveis Globais (Estado da App)
serial_port = None
monitor_active = False
buffer_serial = ""

# --- ROTAS WEB BÁSICAS ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/shutdown', methods=['POST'])
def shutdown():
    """Desliga o servidor seguro"""
    os._exit(0)
    return jsonify(sucesso=True)

# --- GESTÃO DE ARQUIVOS (FIRMWARES) ---
@app.route('/listar_ficheiros', methods=['GET'])
def listar_ficheiros():
    files = [f for f in os.listdir(FIRMWARE_FOLDER) if f.endswith('.bin')]
    return jsonify(files)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify(sucesso=False, erro="Nenhum ficheiro")
    file = request.files['file']
    if file and file.filename.endswith('.bin'):
        file.save(os.path.join(FIRMWARE_FOLDER, file.filename))
        return jsonify(sucesso=True)
    return jsonify(sucesso=False)

@app.route('/delete_file', methods=['POST'])
def delete_file():
    filename = request.json.get('filename')
    filepath = os.path.join(FIRMWARE_FOLDER, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    return jsonify(sucesso=True)

# --- GESTÃO DE ARQUIVOS (ETIQUETAS ZPL) ---
@app.route('/listar_etiquetas', methods=['GET'])
def listar_etiquetas():
    extensoes = ('.zpl', '.txt', '.lbl', '.prn', '.nlbl')
    files = [f for f in os.listdir(ETIQUETA_FOLDER) if f.lower().endswith(extensoes)]
    return jsonify(files)

@app.route('/upload_etiqueta', methods=['POST'])
def upload_etiqueta():
    if 'file' not in request.files:
        return jsonify(sucesso=False, erro="Nenhum ficheiro")
    file = request.files['file']
    if file:
        file.save(os.path.join(ETIQUETA_FOLDER, file.filename))
        return jsonify(sucesso=True)
    return jsonify(sucesso=False)

@app.route('/delete_etiqueta', methods=['POST'])
def delete_etiqueta():
    filename = request.json.get('filename')
    filepath = os.path.join(ETIQUETA_FOLDER, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    return jsonify(sucesso=True)

# --- NOVA GESTÃO DE PDFS V6.0 ---
@app.route('/upload_pdf', methods=['POST'])
def upload_pdf():
    if 'file' not in request.files:
        return jsonify(sucesso=False, erro="Nenhum ficheiro")
    file = request.files['file']
    if file and file.filename.lower().endswith('.pdf'):
        file.save(os.path.join(PDF_FOLDER, file.filename))
        return jsonify(sucesso=True)
    return jsonify(sucesso=False, erro="Ficheiro inválido")

@app.route('/download_pdf/<filename>', methods=['GET'])
def download_pdf(filename):
    return send_from_directory(PDF_FOLDER, filename, as_attachment=False)

# --- GESTÃO DE HARDWARE ---
@app.route('/listar_portas', methods=['GET'])
def listar_portas():
    portas = serial.tools.list_ports.comports()
    lista = [{"device": p.device, "description": p.description} for p in portas]
    return jsonify(lista)

# --- PERFIS DE HARDWARE ---
@app.route('/api/perfis', methods=['GET', 'POST'])
def perfis_api():
    if request.method == 'POST':
        with open(PERFIS_FILE, 'w') as f:
            json.dump(request.json, f)
        return jsonify(sucesso=True)
    else:
        if os.path.exists(PERFIS_FILE):
            with open(PERFIS_FILE, 'r') as f:
                return jsonify(json.load(f))
        return jsonify([])

# --- REGISTO CSV (HISTÓRICO DE PRODUÇÃO) ---
def garantir_cabecalho_csv():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Data', 'MAC', 'Serial', 'IMEI', 'CIMI', 'Perfil', 'Firmware'])

@app.route('/guardar_csv_manual', methods=['POST'])
def guardar_csv_manual():
    garantir_cabecalho_csv()
    dados = request.json
    data_atual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Tratamento de MAC (sem dois pontos para base de dados)
    mac_original = dados.get('mac', '')
    mac_limpo = mac_original.replace(':', '').upper() if mac_original else ""

    linha = [
        data_atual,
        mac_limpo,
        dados.get('sn', ''),
        dados.get('imei', ''),
        dados.get('cimi', ''),
        dados.get('perfil', ''),
        dados.get('firmware', 'N/A')
    ]
    with open(CSV_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(linha)
        f.flush()
        os.fsync(f.fileno())
    return jsonify(sucesso=True)

@app.route('/api/logs', methods=['GET'])
def get_logs():
    logs = []
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                logs.append(row)
    return jsonify(logs)

@app.route('/api/export_csv', methods=['GET'])
def export_csv():
    if os.path.exists(CSV_FILE):
        return send_file(CSV_FILE, as_attachment=True, download_name=f"Producao_ESP_{datetime.now().strftime('%Y%m%d')}.csv")
    return "Nenhum histórico encontrado", 404

@app.route('/api/delete_csv', methods=['POST'])
def delete_csv():
    if os.path.exists(CSV_FILE):
        os.remove(CSV_FILE)
    return jsonify(sucesso=True)

# NOVO V6.0: APAGAR LINHA ÚNICA
@app.route('/api/delete_csv_row', methods=['POST'])
def delete_csv_row():
    try:
        index_to_delete = int(request.json.get('index'))
        if os.path.exists(CSV_FILE):
            with open(CSV_FILE, 'r', encoding='utf-8') as f:
                linhas = f.readlines()
            
            # Removemos a linha (+1 porque o índice HTML começa do zero após os cabeçalhos)
            if 0 <= index_to_delete < len(linhas) - 1:
                del linhas[index_to_delete + 1]
            
            with open(CSV_FILE, 'w', encoding='utf-8') as f:
                f.writelines(linhas)
        return jsonify(sucesso=True)
    except Exception as e:
        return jsonify(sucesso=False, erro=str(e))

# --- MOTOR REGEX (EXTRAÇÃO DE DADOS) ---
def extrair_identificadores(texto):
    resultados = {"mac": None, "imei": None, "cimi": None}
    
    # MAC
    match_mac = re.search(r'([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})', texto)
    if match_mac: resultados["mac"] = match_mac.group(0)
    else:
        match_mac_flat = re.search(r'mac:\s*([0-9A-Fa-f]{12})', texto, re.IGNORECASE)
        if match_mac_flat: resultados["mac"] = match_mac_flat.group(1)

    # CIMI
    match_cimi_cmd = re.search(r'AT\+CIMI[\s\S]*?<<\s*(\d{15})', texto)
    if match_cimi_cmd: resultados["cimi"] = match_cimi_cmd.group(1)
    else:
        # Padrão flexível GSM para CIMI
        match_cimi_alt = re.search(r'CIMI.*?(\d{15})', texto, re.IGNORECASE)
        if match_cimi_alt: resultados["cimi"] = match_cimi_alt.group(1)

    # IMEI
    match_imei_cmd = re.search(r'AT\+CGSN[\s\S]*?<<\s*(\d{15})', texto)
    if match_imei_cmd: resultados["imei"] = match_imei_cmd.group(1)
    else:
        # Se falhou CGSN, procura 15 dígitos perdidos (evita CIMI se já encontrado)
        todos_15 = re.findall(r'\b\d{15}\b', texto)
        for cand in todos_15:
            if cand != resultados["cimi"]:
                resultados["imei"] = cand
                break

    return resultados

@app.route('/analisar_buffer', methods=['POST'])
def analisar_buffer():
    global buffer_serial
    dados = extrair_identificadores(buffer_serial)
    return jsonify(dados)

@app.route('/analisar_logs_ficheiro', methods=['POST'])
def analisar_logs_ficheiro():
    if 'file' not in request.files:
        return jsonify(erro="Nenhum ficheiro recebido")
    file = request.files['file']
    try:
        conteudo = file.read().decode('utf-8', errors='ignore')
        dados = extrair_identificadores(conteudo)
        return jsonify(dados)
    except Exception as e:
        return jsonify(erro=str(e))

# --- NOVO MOTOR ZPL (SUPORTE QUANTIDADES V6.0) ---
class ZPLEngine:
    @staticmethod
    def processar_etiqueta(filepath, dicionario_dados):
        with open(filepath, 'rb') as f:
            raw_data = f.read()
            
        if raw_data.startswith(b'PK\x03\x04') or b'<?xml' in raw_data[:50]:
            raise ValueError("O Ficheiro LBL submetido é o projeto fonte. Grave como 'Imprimir para ficheiro' (código RAW).")
            
        try:
            conteudo = raw_data.decode('utf-8')
        except UnicodeDecodeError:
            conteudo = raw_data.decode('iso-8859-1', errors='ignore')

        # Variações avançadas de MAC
        if 'mac' in dicionario_dados and isinstance(dicionario_dados['mac'], str):
            dicionario_dados['mac_clean'] = dicionario_dados['mac'].replace(':', '')
            dicionario_dados['mac_lower'] = dicionario_dados['mac'].lower()

        # Injeção no documento
        for chave, valor in dicionario_dados.items():
            if valor is not None:
                conteudo = conteudo.replace(f'@{chave.upper()}@', str(valor))
                
        return conteudo

    @staticmethod
    def imprimir_rede(zpl_data, ip, porta=9100):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3.0)
            s.connect((ip, porta))
            s.sendall(zpl_data.encode('utf-8'))
            s.close()
            return True, "Enviado com sucesso"
        except Exception as e:
            return False, f"Falha na comunicação TCP: {str(e)}"

@app.route('/api/processar_zpl_v6', methods=['POST'])
def api_processar_zpl_v6():
    dados = request.json
    label_file = dados.get('label_file')
    ip = dados.get('ip_impressora', '').strip()
    quantidade = int(dados.get('quantidade', 1))

    if not label_file:
        return jsonify(sucesso=False, erro="Nenhum ficheiro ZPL especificado.")

    filepath = os.path.join(ETIQUETA_FOLDER, label_file)
    if not os.path.exists(filepath):
        return jsonify(sucesso=False, erro="Ficheiro ZPL não encontrado no servidor.")

    try:
        # 1. Substituir Variáveis normais
        zpl_final = ZPLEngine.processar_etiqueta(filepath, dados)
        
        # 2. Injetar a Quantidade de Etiquetas (^PQ)
        if '^PQ' in zpl_final:
            # Substitui qualquer comando ^PQ existente pelo novo
            zpl_final = re.sub(r'\^PQ\d+', f'^PQ{quantidade}', zpl_final)
        else:
            # Força o ^PQ mesmo antes do comando de fecho ^XZ
            zpl_final = zpl_final.replace('^XZ', f'^PQ{quantidade}\n^XZ')

        # 3. Decidir se Imprime Rede ou Devolve para Download
        if ip:
            sucesso, msg = ZPLEngine.imprimir_rede(zpl_final, ip)
            if sucesso:
                return jsonify(sucesso=True, impresso_direto=True)
            return jsonify(sucesso=False, erro=msg)
        else:
            return jsonify(sucesso=True, impresso_direto=False, zpl=zpl_final)

    except Exception as e:
        return jsonify(sucesso=False, erro=str(e))


# --- SOCKET IO: THREADS DO MONITOR E FLASH ---
def thread_monitor(porta, baud):
    global serial_port, monitor_active, buffer_serial
    buffer_serial = "" # Limpa memória anterior
    try:
        serial_port = serial.Serial(porta, baud, timeout=1)
        socketio.emit('status_monitor', {'ativo': True, 'msg': f"{porta} @ {baud}"})
        
        while monitor_active:
            if serial_port.in_waiting:
                try:
                    linha = serial_port.readline().decode('utf-8', errors='ignore')
                    buffer_serial += linha
                    
                    # Prevenir estouro de memória mantendo apenas os últimos 10000 caracteres
                    if len(buffer_serial) > 10000:
                        buffer_serial = buffer_serial[-10000:]
                        
                    socketio.emit('log_monitor', {'data': linha.strip()})
                    
                    # Leitura Passiva em Tempo Real (Opcional, alimenta o frontend sem forçar)
                    dados = extrair_identificadores(buffer_serial)
                    if any(dados.values()):
                        socketio.emit('dados_capturados', dados)

                except: pass
            eventlet.sleep(0.01)
    except Exception as e:
        socketio.emit('log_monitor', {'data': f"ERRO SERIAL: {str(e)}"})
        monitor_active = False
        socketio.emit('status_monitor', {'ativo': False})
    finally:
        if serial_port and serial_port.is_open:
            serial_port.close()

@socketio.on('iniciar_monitor')
def handle_iniciar_monitor(dados):
    global monitor_active
    monitor_active = True
    eventlet.spawn(thread_monitor, dados['porta'], dados['baud'])

@socketio.on('parar_monitor')
def handle_parar_monitor():
    global monitor_active
    monitor_active = False
    socketio.emit('status_monitor', {'ativo': False})


@socketio.on('iniciar_processo')
def handle_iniciar_processo(dados):
    porta = dados['porta']
    baud = dados['baud']
    ficheiro = dados['ficheiro']
    modo = dados['modo']
    
    comando = [
        sys.executable, '-m', 'esptool',
        '--port', porta,
        '--baud', str(baud),
        '--before', 'default_reset',
        '--after', 'hard_reset'
    ]
    
    if modo == 'flash_limpo':
        caminho_bin = os.path.join(FIRMWARE_FOLDER, ficheiro)
        comando.extend(['write_flash', '-z', '--flash_mode', 'dio', '--flash_freq', 'keep', '0x0', caminho_bin])
    elif modo == 'apenas_limpar':
        comando.append('erase_flash')
        
    eventlet.spawn(executar_esptool, comando)

def executar_esptool(comando):
    try:
        processo = subprocess.Popen(comando, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        for linha in processo.stdout:
            socketio.emit('log_flash', {'data': linha})
            eventlet.sleep(0)
        processo.wait()
        
        if processo.returncode == 0:
            socketio.emit('log_flash', {'data': '\n✅ SUCESSO ABSOLUTO!'})
        else:
            socketio.emit('log_flash', {'data': f'\n❌ ERRO Fatal. Código: {processo.returncode}'})
            
    except Exception as e:
        socketio.emit('log_flash', {'data': f'\n❌ ERRO de Sistema: {str(e)}'})
    finally:
        socketio.emit('fim_processo')


# --- ARRANQUE AUTOMÁTICO ---
def abrir_browser():
    eventlet.sleep(1)
    webbrowser.open_new('http://127.0.0.1:5000/')

if __name__ == '__main__':
    eventlet.spawn(abrir_browser)
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, log_output=False)