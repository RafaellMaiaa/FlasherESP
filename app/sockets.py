import os
import sys
import serial
import subprocess
import eventlet
from flask import current_app
from app import socketio
from app.core.utils import extrair_identificadores

# Isolamento de Estado (Evita Globals Soltos)
hardware_state = {
    "serial_port": None,
    "monitor_active": False,
    "buffer_serial": ""
}

def thread_monitor(porta, baud):
    hardware_state["buffer_serial"] = "" 
    try:
        hardware_state["serial_port"] = serial.Serial(porta, baud, timeout=1)
        socketio.emit('status_monitor', {'ativo': True, 'msg': f"{porta} @ {baud}"})
        
        while hardware_state["monitor_active"]:
            if hardware_state["serial_port"].in_waiting:
                try:
                    linha = hardware_state["serial_port"].readline().decode('utf-8', errors='ignore')
                    hardware_state["buffer_serial"] += linha
                    
                    if len(hardware_state["buffer_serial"]) > 10000:
                        hardware_state["buffer_serial"] = hardware_state["buffer_serial"][-10000:]
                        
                    socketio.emit('log_monitor', {'data': linha.strip()})
                    
                    dados = extrair_identificadores(hardware_state["buffer_serial"])
                    if any(dados.values()):
                        socketio.emit('dados_capturados', dados)

                except: pass
            eventlet.sleep(0.01)
    except Exception as e:
        socketio.emit('log_monitor', {'data': f"ERRO SERIAL: {str(e)}"})
        hardware_state["monitor_active"] = False
        socketio.emit('status_monitor', {'ativo': False})
    finally:
        if hardware_state["serial_port"] and hardware_state["serial_port"].is_open:
            hardware_state["serial_port"].close()

@socketio.on('iniciar_monitor')
def handle_iniciar_monitor(dados):
    hardware_state["monitor_active"] = True
    eventlet.spawn(thread_monitor, dados['porta'], dados['baud'])

@socketio.on('parar_monitor')
def handle_parar_monitor():
    hardware_state["monitor_active"] = False
    socketio.emit('status_monitor', {'ativo': False})

# O Frontend força o pedido de leitura do buffer atual
@socketio.on('analisar_buffer_socket')
def handle_analisar_buffer():
    dados = extrair_identificadores(hardware_state["buffer_serial"])
    socketio.emit('dados_capturados', dados)

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

@socketio.on('iniciar_processo')
def handle_iniciar_processo(dados):
    app_context = current_app._get_current_object()
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
        caminho_bin = os.path.join(app_context.config['FIRMWARE_FOLDER'], ficheiro)
        comando.extend(['write_flash', '-z', '--flash_mode', 'dio', '--flash_freq', 'keep', '0x0', caminho_bin])
    elif modo == 'apenas_limpar':
        comando.append('erase_flash')
        
    eventlet.spawn(executar_esptool, comando)