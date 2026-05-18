#!/usr/bin/env python3
"""
Script para fazer commit e merge das mudanças UI/UX
"""

import subprocess
import os
import sys

def run_git_command(cmd, cwd=None):
    """Executa comando git e retorna output"""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            shell=False
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return -1, "", str(e)

def main():
    worktree_path = r'c:\Users\rafar\Desktop\testing\FlasherESP.worktrees\agents-app-ui-improvement-and-consistency'
    main_worktree = r'c:\Users\rafar\Desktop\testing\FlasherESP'
    
    print("=" * 60)
    print("  MERGE: UI/UX Improvements to Main")
    print("=" * 60)
    print()
    
    # 1. Verificar status
    print("[1/4] Verificando status do repositório...")
    code, stdout, stderr = run_git_command(['git', 'status', '--short'], cwd=worktree_path)
    
    if code != 0:
        print(f"Erro: {stderr}")
        return 1
    
    if stdout:
        print(f"Mudanças não commitadas detectadas:\n{stdout}\n")
        
        # 2. Stage all changes
        print("[2/4] Fazendo stage de todas as mudanças...")
        code, _, stderr = run_git_command(['git', 'add', '-A'], cwd=worktree_path)
        
        if code != 0:
            print(f"Erro ao fazer stage: {stderr}")
            return 1
        
        # 3. Get branch name
        print("[3/4] Obtendo nome da branch...")
        code, branch, stderr = run_git_command(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=worktree_path)
        
        if code != 0:
            print(f"Erro ao obter branch: {stderr}")
            return 1
        
        print(f"Branch atual: {branch}")
        
        # 4. Commit
        print("[4/4] Commitando mudanças...")
        commit_msg = "UI/UX improvements: standardize components and layout"
        commit_body = """Standardized all panels with consistent HTML structure and CSS classes:
- Added reusable CSS components (.panel-title, .label-section, .btn-action-primary, etc)
- Refactored 7 panels (flash, offline, perfis, arquivos, etiquetas, logs, definicoes)
- Improved spacing, typography, and color consistency
- Maintained theme colors and animations
- Updated modal styling to match new standards

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"""
        
        code, stdout, stderr = run_git_command(
            ['git', 'commit', '-m', commit_msg, '-m', commit_body],
            cwd=worktree_path
        )
        
        if code != 0:
            print(f"Erro ao commitear: {stderr}")
            return 1
        
        print(f"Commit criado:\n{stdout}\n")
    else:
        print("Nenhuma mudança para commitear.\n")
    
    # 5. Merge para main
    print("=" * 60)
    print("  Iniciando MERGE para main branch")
    print("=" * 60)
    print()
    
    # Get branch name
    code, branch, _ = run_git_command(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=worktree_path)
    
    if code != 0:
        print("Erro ao obter branch")
        return 1
    
    print(f"[MERGE] Topic branch: {branch}")
    print(f"[MERGE] Target: main (em {main_worktree})")
    print()
    
    # Fazer merge
    code, stdout, stderr = run_git_command(['git', 'merge', branch], cwd=main_worktree)
    
    if code != 0:
        if 'conflict' in stderr.lower():
            print(f"Conflitos detectados:\n{stderr}")
            print("\nResolve os conflitos manualmente e tenta novamente.")
            return 1
        else:
            print(f"Erro ao fazer merge: {stderr}")
            return 1
    
    print(f"Merge completado:\n{stdout}\n")
    
    # 6. Validar
    print("=" * 60)
    print("  Validando Merge")
    print("=" * 60)
    print()
    
    # Check if clean
    code, stdout, _ = run_git_command(['git', 'status', '--porcelain'], cwd=main_worktree)
    
    if stdout:
        print(f"Atenção: Main worktree não está limpo:\n{stdout}")
    else:
        print("✓ Main worktree está limpo")
    
    # Check log
    code, stdout, _ = run_git_command(['git', 'log', '--oneline', '-5'], cwd=main_worktree)
    print(f"\nÚltimos commits em main:\n{stdout}")
    
    print("\n" + "=" * 60)
    print("  MERGE COMPLETO COM SUCESSO!")
    print("=" * 60)
    print()
    print("✓ Todas as mudanças foram mergeadas para main")
    print("✓ A branch UI improvements foi integrada")
    print()
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
