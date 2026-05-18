#!/usr/bin/env python3
"""
Script de Teste Automatizado - ESP Flasher UI/UX Improvements
Valida se todas as mudanças foram aplicadas corretamente
"""

import os
import re
from pathlib import Path

# Cores para output
VERDE = '\033[92m'
VERMELHO = '\033[91m'
AMARELO = '\033[93m'
AZUL = '\033[94m'
RESET = '\033[0m'

def print_test(passed, name, details=""):
    """Imprime resultado do teste"""
    symbol = f"{VERDE}✓{RESET}" if passed else f"{VERMELHO}✗{RESET}"
    status = f"{VERDE}PASS{RESET}" if passed else f"{VERMELHO}FAIL{RESET}"
    print(f"{symbol} [{status}] {name}")
    if details:
        print(f"    → {details}")

def test_css_classes(css_file):
    """Testa se todas as classes CSS novas existem"""
    print(f"\n{AZUL}=== TESTES CSS ==={RESET}")
    
    with open(css_file, 'r', encoding='utf-8') as f:
        css_content = f.read()
    
    required_classes = [
        '.panel-title',
        '.label-section',
        '.card-header-label',
        '.card-description',
        '.input-group-section',
        '.divider-section',
        '.btn-action-primary',
        '.btn-action-secondary',
        '.info-box',
        '.badge-status',
        '.panel-row',
        '.card-flex-col'
    ]
    
    tests_passed = 0
    for cls in required_classes:
        exists = cls in css_content
        print_test(exists, f"Classe CSS '{cls}'", 
                  "Encontrada" if exists else "NÃO ENCONTRADA")
        if exists:
            tests_passed += 1
    
    return tests_passed, len(required_classes)

def test_html_panels(templates_dir):
    """Testa se todos os painéis usam novos padrões"""
    print(f"\n{AZUL}=== TESTES HTML PAINÉIS ==={RESET}")
    
    panels = [
        'flash.html',
        'offline.html',
        'perfis.html',
        'arquivos.html',
        'etiquetas.html',
        'logs.html',
        'definicoes.html'
    ]
    
    tests_passed = 0
    total_tests = 0
    
    for panel in panels:
        panel_path = os.path.join(templates_dir, 'panels', panel)
        
        if not os.path.exists(panel_path):
            print_test(False, f"Painel {panel}", "Ficheiro não encontrado")
            total_tests += 1
            continue
        
        with open(panel_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Verifica padrões
        has_panel_title = 'class="panel-title"' in content or '.panel-title' in content
        has_custom_card = 'class="custom-card' in content
        has_label_section = '.label-section' in content or 'label-section' in content
        
        all_ok = has_panel_title and has_custom_card and has_label_section
        
        print_test(all_ok, f"Painel {panel}", 
                  f"panel-title:{has_panel_title}, custom-card:{has_custom_card}, label-section:{has_label_section}")
        
        if all_ok:
            tests_passed += 1
        total_tests += 1
    
    return tests_passed, total_tests

def test_no_emojis(templates_dir, css_file):
    """Valida que não há emojis no código"""
    print(f"\n{AZUL}=== TESTES SEM EMOJIS ==={RESET}")
    
    # Padrão de emojis Unicode
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # faces
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "]+",
        flags=re.UNICODE
    )
    
    files_to_check = [css_file]
    
    # Adiciona todos os painéis
    panels_dir = os.path.join(templates_dir, 'panels')
    if os.path.exists(panels_dir):
        files_to_check.extend([
            os.path.join(panels_dir, f) for f in os.listdir(panels_dir) 
            if f.endswith('.html')
        ])
    
    tests_passed = 0
    for filepath in files_to_check:
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            emojis = emoji_pattern.findall(content)
            no_emojis = len(emojis) == 0
            
            filename = os.path.basename(filepath)
            print_test(no_emojis, f"Sem emojis em {filename}", 
                      f"Encontrados: {len(emojis)}" if emojis else "OK")
            
            if no_emojis:
                tests_passed += 1
    
    return tests_passed, len(files_to_check)

def test_colors_maintained(css_file):
    """Valida se cores foram mantidas"""
    print(f"\n{AZUL}=== TESTES CORES ==={RESET}")
    
    with open(css_file, 'r', encoding='utf-8') as f:
        css_content = f.read()
    
    colors = {
        '--bg-main: #09090b': 'Background principal',
        '--accent: #0ea5e9': 'Accent azul',
        '--warning: #fbbf24': 'Warning amarelo',
        '--danger: #f87171': 'Danger vermelho'
    }
    
    tests_passed = 0
    for color_def, name in colors.items():
        exists = color_def in css_content
        print_test(exists, f"Cor mantida: {name}", 
                  color_def if exists else "NÃO ENCONTRADA")
        if exists:
            tests_passed += 1
    
    return tests_passed, len(colors)

def main():
    """Executa todos os testes"""
    base_dir = r'c:\Users\rafar\Desktop\testing\FlasherESP.worktrees\agents-app-ui-improvement-and-consistency'
    css_file = os.path.join(base_dir, 'app', 'static', 'css', 'style.css')
    templates_dir = os.path.join(base_dir, 'app', 'templates')
    
    print(f"\n{AMARELO}")
    print("=" * 60)
    print("  TESTE AUTOMATIZADO - ESP FLASHER UI/UX IMPROVEMENTS")
    print("=" * 60)
    print(f"{RESET}")
    
    total_pass = 0
    total_tests = 0
    
    # Teste 1: CSS Classes
    p, t = test_css_classes(css_file)
    total_pass += p
    total_tests += t
    
    # Teste 2: HTML Painéis
    p, t = test_html_panels(templates_dir)
    total_pass += p
    total_tests += t
    
    # Teste 3: Sem Emojis
    p, t = test_no_emojis(templates_dir, css_file)
    total_pass += p
    total_tests += t
    
    # Teste 4: Cores Mantidas
    p, t = test_colors_maintained(css_file)
    total_pass += p
    total_tests += t
    
    # Resumo
    print(f"\n{AMARELO}")
    print("=" * 60)
    print(f"RESULTADO FINAL: {VERDE}{total_pass}/{total_tests}{RESET} testes PASSADOS")
    print("=" * 60)
    print(f"{RESET}")
    
    if total_pass == total_tests:
        print(f"{VERDE}✓ TODOS OS TESTES PASSARAM! App pronta para usar.{RESET}\n")
        return 0
    else:
        print(f"{VERMELHO}✗ {total_tests - total_pass} teste(s) falharam.{RESET}\n")
        return 1

if __name__ == '__main__':
    exit(main())
