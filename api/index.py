import os
import sys

# Adiciona o diretório raiz ao PYTHONPATH para permitir importar server.py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import app

