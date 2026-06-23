"""
Arquivo de entrada para deploy em cloud.
Importa o app Flask de app.py e expõe para o servidor.
"""
import sys
import os

# Garante que o diretório raiz está no path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Importa o app do Flask do módulo app
from app import app

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    app.run(host=host, port=port, debug=False, threaded=True)