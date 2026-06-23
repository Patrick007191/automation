"""Script para verificar se o Playwright esta instalado."""
import sys

try:
    from playwright.sync_api import sync_playwright
    print("OK")
    sys.exit(0)
except ImportError:
    print("FALHOU")
    sys.exit(1)