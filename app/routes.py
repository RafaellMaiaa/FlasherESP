import os
import csv
import json
import serial.tools.list_ports
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, send_file, send_from_directory, current_app, session
from werkzeug.utils import secure_filename
from app.core.utils import guardar_registo_csv, extrair_identificadores, ZPLEngine
import re

main_routes = Blueprint('main_routes', __name__)

# ==========================================
# ROTAS DE AUTENTICAÇÃO (CORREÇÃO VULN 1)
# ==========================================
@main_routes.route('/api/login', methods=['POST'])
def login():
    senha = request.json.get('password')
    # A password agora é validada no backend!
    if senha == "admin123":
        session['is_admin'] = True
        return jsonify(sucesso=True)
    return jsonify(sucesso=False, erro="Senha incorreta")

@main_routes.route('/api/logout', methods=['POST'])
def logout():
    session.pop('is_admin', None)
    return jsonify(sucesso=True)

# ==========================================
# ROTAS GERAIS E GESTÃO DE FICHEIROS
# ==========================================
@main_routes.route('/')
def index():
    return render_template('index.html')

@main_routes.route('/shutdown', methods=['POST'])
def shutdown():
    os._exit(0)
    return jsonify(sucesso=True)

@main_routes.route('/listar_ficheiros', methods=['GET'])
def listar_ficheiros():
    files = [f for f in os.listdir(current_app.config['FIRMWARE_FOLDER']) if f.endswith('.bin')]
    return jsonify(files)

# CORREÇÃO VULN 2: SECURE_FILENAME NOS UPLOADS
@main_routes.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files: return jsonify(sucesso=False, erro="Nenhum ficheiro")
    file = request.files['file']
    if file and file.filename.endswith('.bin'):
        nome_seguro = secure_filename(file.filename)
        file.save(os.path.join(current_app.config['FIRMWARE_FOLDER'], nome_seguro))
        return jsonify(sucesso=True)
    return jsonify(sucesso=False)

@main_routes.route('/delete_file', methods=['POST'])
def delete_file():
    filename = secure_filename(request.json.get('filename', ''))
    filepath = os.path.join(current_app.config['FIRMWARE_FOLDER'], filename)
    if os.path.exists(filepath): os.remove(filepath)
    return jsonify(sucesso=True)

@main_routes.route('/listar_etiquetas', methods=['GET'])
def listar_etiquetas():
    extensoes = ('.zpl', '.txt', '.lbl', '.prn', '.nlbl')
    files = [f for f in os.listdir(current_app.config['ETIQUETA_FOLDER']) if f.lower().endswith(extensoes)]
    return jsonify(files)

@main_routes.route('/upload_etiqueta', methods=['POST'])
def upload_etiqueta():
    if 'file' not in request.files: return jsonify(sucesso=False, erro="Nenhum ficheiro")
    file = request.files['file']
    if file:
        nome_seguro = secure_filename(file.filename)
        file.save(os.path.join(current_app.config['ETIQUETA_FOLDER'], nome_seguro))
        return jsonify(sucesso=True)
    return jsonify(sucesso=False)

@main_routes.route('/delete_etiqueta', methods=['POST'])
def delete_etiqueta():
    filename = secure_filename(request.json.get('filename', ''))
    filepath = os.path.join(current_app.config['ETIQUETA_FOLDER'], filename)
    if os.path.exists(filepath): os.remove(filepath)
    return jsonify(sucesso=True)

@main_routes.route('/upload_pdf', methods=['POST'])
def upload_pdf():
    if 'file' not in request.files: return jsonify(sucesso=False, erro="Nenhum ficheiro")
    file = request.files['file']
    if file and file.filename.lower().endswith('.pdf'):
        nome_seguro = secure_filename(file.filename)
        file.save(os.path.join(current_app.config['PDF_FOLDER'], nome_seguro))
        return jsonify(sucesso=True)
    return jsonify(sucesso=False, erro="Ficheiro inválido")

@main_routes.route('/download_pdf/<filename>', methods=['GET'])
def download_pdf(filename):
    nome_seguro = secure_filename(filename)
    return send_from_directory(current_app.config['PDF_FOLDER'], nome_seguro, as_attachment=False)

# ==========================================
# ROTAS RESTANTES
# ==========================================
@main_routes.route('/listar_portas', methods=['GET'])
def listar_portas():
    portas = serial.tools.list_ports.comports()
    lista = [{"device": p.device, "description": p.description} for p in portas]
    return jsonify(lista)

@main_routes.route('/api/perfis', methods=['GET', 'POST'])
def perfis_api():
    if request.method == 'POST':
        with open(current_app.config['PERFIS_FILE'], 'w', encoding='utf-8') as f:
            json.dump(request.json, f)
        return jsonify(sucesso=True)
    else:
        if os.path.exists(current_app.config['PERFIS_FILE']) and os.path.getsize(current_app.config['PERFIS_FILE']) > 0:
            try:
                with open(current_app.config['PERFIS_FILE'], 'r', encoding='utf-8') as f:
                    return jsonify(json.load(f))
            except json.JSONDecodeError:
                return jsonify([])
        return jsonify([])

@main_routes.route('/guardar_csv_manual', methods=['POST'])
def guardar_csv_manual_route():
    guardar_registo_csv(current_app.config['CSV_FILE'], request.json)
    return jsonify(sucesso=True)

@main_routes.route('/api/logs', methods=['GET'])
def get_logs():
    logs = []
    if os.path.exists(current_app.config['CSV_FILE']):
        with open(current_app.config['CSV_FILE'], 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader: logs.append(row)
    return jsonify(logs)

@main_routes.route('/api/export_csv', methods=['GET'])
def export_csv():
    if os.path.exists(current_app.config['CSV_FILE']):
        return send_file(current_app.config['CSV_FILE'], as_attachment=True, download_name=f"Producao_{datetime.now().strftime('%Y%m%d')}.csv")
    return "Nenhum histórico encontrado", 404

@main_routes.route('/api/delete_csv', methods=['POST'])
def delete_csv():
    if os.path.exists(current_app.config['CSV_FILE']): os.remove(current_app.config['CSV_FILE'])
    return jsonify(sucesso=True)

@main_routes.route('/api/delete_csv_row', methods=['POST'])
def delete_csv_row():
    try:
        index_to_delete = int(request.json.get('index'))
        if os.path.exists(current_app.config['CSV_FILE']):
            with open(current_app.config['CSV_FILE'], 'r', encoding='utf-8') as f:
                linhas = f.readlines()
            if 0 <= index_to_delete < len(linhas) - 1:
                del linhas[index_to_delete + 1]
            with open(current_app.config['CSV_FILE'], 'w', encoding='utf-8') as f:
                f.writelines(linhas)
        return jsonify(sucesso=True)
    except Exception as e:
        return jsonify(sucesso=False, erro=str(e))

@main_routes.route('/analisar_logs_ficheiro', methods=['POST'])
def analisar_logs_ficheiro():
    if 'file' not in request.files: return jsonify(erro="Nenhum ficheiro recebido")
    file = request.files['file']
    try:
        conteudo = file.read().decode('utf-8', errors='ignore')
        dados = extrair_identificadores(conteudo)
        return jsonify(dados)
    except Exception as e:
        return jsonify(erro=str(e))

@main_routes.route('/api/processar_zpl_v6', methods=['POST'])
def api_processar_zpl_v6():
    dados = request.json
    label_file = dados.get('label_file')
    ip = dados.get('ip_impressora', '').strip()
    quantidade = int(dados.get('quantidade', 1))

    if not label_file: return jsonify(sucesso=False, erro="Nenhum ficheiro ZPL especificado.")
    
    # Proteção Path Traversal
    label_file = secure_filename(label_file)
    filepath = os.path.join(current_app.config['ETIQUETA_FOLDER'], label_file)
    if not os.path.exists(filepath): return jsonify(sucesso=False, erro="Ficheiro ZPL não encontrado.")

    try:
        zpl_final = ZPLEngine.processar_etiqueta(filepath, dados)
        if '^PQ' in zpl_final:
            zpl_final = re.sub(r'\^PQ\d+', f'^PQ{quantidade}', zpl_final)
        else:
            zpl_final = zpl_final.replace('^XZ', f'^PQ{quantidade}\n^XZ')

        if ip:
            sucesso, msg = ZPLEngine.imprimir_rede(zpl_final, ip)
            if sucesso: return jsonify(sucesso=True, impresso_direto=True)
            return jsonify(sucesso=False, erro=msg)
        else:
            return jsonify(sucesso=True, impresso_direto=False, zpl=zpl_final)
    except Exception as e:
        return jsonify(sucesso=False, erro=str(e))
