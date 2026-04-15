import os
import subprocess
import sys

def run_script(script_name):
    script_path = os.path.join("src", script_name)
    print(f"\n--- Iniciando: {script_name} ---")
    try:
        # Executa o script e redireciona a saída para o terminal atual
        result = subprocess.run([sys.executable, script_path], check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"Erro ao executar {script_name}: {e}")
        return False

def main():
    # Muda o diretório de trabalho para a raiz do projeto (onde este script está)
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # 1. Coleta
    if run_script("coletor.py"):
        # 2. Edição (Curadoria)
        run_script("editor.py")
    
    print("\n--- Processo Finalizado ---")

if __name__ == "__main__":
    main()
