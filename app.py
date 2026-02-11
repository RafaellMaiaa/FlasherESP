import os
import sys
import subprocess
import threading
import serial.tools.list_ports
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
socketio = SocketIO(app)
PASTA_FIRMWARES = 'firmwares'

if not os.path.exists(PASTA_FIRMWARES):
    os.makedirs(PASTA_FIRMWARES)

# --- ROTAS WEB ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files: return jsonify({'erro': 'Erro no envio'}), 400
    file = request.files['file']
    if file.filename == '' or not file.filename.endswith('.bin'):
        return jsonify({'erro': 'Apenas ficheiros .bin'}), 400
    file.save(os.path.join(PASTA_FIRMWARES, file.filename))
    return jsonify({'sucesso': True})

@app.route('/delete_file', methods=['POST'])
def delete_file():
    dados = request.json
    try:
        os.remove(os.path.join(PASTA_FIRMWARES, dados.get('filename')))
        return jsonify({'sucesso': True})
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@app.route('/listar_portas')
def listar_portas():
    portas_detalhadas = []
    for p in serial.tools.list_ports.comports():
        info = { 'device': p.device, 'description': p.description }
        portas_detalhadas.append(info)
    return jsonify(portas_detalhadas)

@app.route('/listar_ficheiros')
def listar_ficheiros():
    return jsonify([f for f in os.listdir(PASTA_FIRMWARES) if f.endswith('.bin')])

# --- MOTOR DE EXECUÇÃO ---
def correr_comando(cmd_list):
    try:
        processo = subprocess.Popen(
            cmd_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        for linha in processo.stdout:
            socketio.emit('log', {'data': linha})
        processo.wait()
        return processo.returncode
    except Exception as e:
        socketio.emit('log', {'data': f"ERRO: {str(e)}\n"})
        return -1

def sequencia_flash_completa(porta, baud, caminho_ficheiro):
    socketio.emit('log', {'data': '\n>>> A INICIAR INSTALAÇÃO (Reset Automático) <<<\n'})
    
    # Sintaxe atualizada para esptool v5.1.0
    cmd_flash = [
        sys.executable, "-m", "esptool",
        "--port", porta,
        "--baud", baud,
        "--before", "default-reset",
        "--after", "hard-reset",
        "write-flash",
        "--flash-mode", "dio", 
        "0x0", caminho_ficheiro
    ]
    
    if correr_comando(cmd_flash) == 0:
        socketio.emit('log', {'data': '\n✅ SUCESSO! O ESP foi reiniciado.\n'})
        socketio.emit('fim_processo', {'sucesso': True})
    else:
        socketio.emit('log', {'data': '\n❌ FALHA NA CONEXÃO. Se persistir, usa 115200 baud ou segura o botão BOOT.\n'})
        socketio.emit('fim_processo', {'sucesso': False})

@socketio.on('iniciar_processo')
def handle_processo(dados):
    porta = dados['porta']
    baud = dados['baud']
    ficheiro = dados['ficheiro']
    modo = dados['modo']
    caminho = os.path.join(PASTA_FIRMWARES, ficheiro) if ficheiro else None

    if modo == 'apenas_limpar':
        socketio.emit('log', {'data': f'>>> A FORMATAR MEMÓRIA EM {porta}...\n'})
        cmd = [
            sys.executable, "-m", "esptool", 
            "--port", porta, 
            "--before", "default-reset", 
            "--after", "hard-reset",
            "erase-flash"
        ]
        threading.Thread(target=lambda: (correr_comando(cmd), socketio.emit('fim_processo', {'sucesso': True}))).start()
    
    elif modo == 'flash_limpo':
        threading.Thread(target=sequencia_flash_completa, args=(porta, baud, caminho)).start()

if __name__ == '__main__':
    socketio.run(app, debug=True)