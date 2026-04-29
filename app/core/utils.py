import os
import re
import csv
import json
import socket
from datetime import datetime

def garantir_cabecalho_csv(csv_file):
    if not os.path.exists(csv_file):
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Data', 'MAC', 'Serial', 'IMEI', 'CIMI', 'Perfil', 'Firmware'])

def guardar_registo_csv(csv_file, dados):
    garantir_cabecalho_csv(csv_file)
    data_atual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
    with open(csv_file, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(linha)
        f.flush()
        os.fsync(f.fileno())

def extrair_identificadores(texto):
    resultados = {"mac": None, "imei": None, "cimi": None}
    
    match_mac = re.search(r'([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})', texto)
    if match_mac: resultados["mac"] = match_mac.group(0)
    else:
        match_mac_flat = re.search(r'mac:\s*([0-9A-Fa-f]{12})', texto, re.IGNORECASE)
        if match_mac_flat: resultados["mac"] = match_mac_flat.group(1)

    match_cimi_cmd = re.search(r'AT\+CIMI[\s\S]*?<<\s*(\d{15})', texto)
    if match_cimi_cmd: resultados["cimi"] = match_cimi_cmd.group(1)
    else:
        match_cimi_alt = re.search(r'CIMI.*?(\d{15})', texto, re.IGNORECASE)
        if match_cimi_alt: resultados["cimi"] = match_cimi_alt.group(1)

    match_imei_cmd = re.search(r'AT\+CGSN[\s\S]*?<<\s*(\d{15})', texto)
    if match_imei_cmd: resultados["imei"] = match_imei_cmd.group(1)
    else:
        todos_15 = re.findall(r'\b\d{15}\b', texto)
        for cand in todos_15:
            if cand != resultados["cimi"]:
                resultados["imei"] = cand
                break
    return resultados

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

        if 'mac' in dicionario_dados and isinstance(dicionario_dados['mac'], str):
            dicionario_dados['mac_clean'] = dicionario_dados['mac'].replace(':', '')
            dicionario_dados['mac_lower'] = dicionario_dados['mac'].lower()

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