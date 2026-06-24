"""
Modulo de download usando Selenium (interface grafica).
Clica no icone de download/pasta no canto superior direito.
"""
import os
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager


def baixar_pdf(url, pasta_destino, nome_arquivo, cookies=None, headers=None):
    """Baixa PDF usando Selenium com interface grafica."""
    Path(pasta_destino).mkdir(parents=True, exist_ok=True)
    caminho_final = os.path.join(pasta_destino, nome_arquivo)
    
    chrome_options = Options()
    chrome_options.add_argument('--start-maximized')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    prefs = {
        "download.default_directory": str(Path(pasta_destino).absolute()),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    driver = None
    try:
        print('[SELENIUM] Abrindo navegador...', flush=True)
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        print(f'[SELENIUM] Acessando: {url[:80]}', flush=True)
        driver.get(url)
        time.sleep(5)
        
        if cookies:
            for name, value in cookies.items():
                try:
                    driver.add_cookie({'name': name, 'value': value, 'path': '/'})
                except:
                    pass
            driver.refresh()
            time.sleep(3)
        
        print('[SELENIUM] Procurando icone de download...', flush=True)
        
        # Screenshot para debug
        try:
            driver.save_screenshot(os.path.join(pasta_destino, '_debug_tela.png'))
            print(f'[SELENIUM] Screenshot salvo', flush=True)
        except:
            pass
        
        icone_encontrado = False
        
        # Estrategia 1: PROCURA ICONE DE DONWLOAD DO CHROME PDF VIEWER
        print('[SELENIUM] Procurando icone de download do PDF...', flush=True)
        
        # METODO PRINCIPAL: Usa Ctrl+S (atalho universal para salvar)
        # Funciona em qualquer visualizador de PDF do Chrome
        from selenium.webdriver.common.action_chains import ActionChains
        from selenium.webdriver.common.keys import Keys
        
        try:
            print('[SELENIUM] Usando Ctrl+S para salvar PDF...', flush=True)
            
            # Garante que a janela do Chrome está em foco
            driver.switch_to.window(driver.current_window_handle)
            
            # Clica no body para garantir foco
            body = driver.find_element(By.TAG_NAME, 'body')
            body.click()
            time.sleep(1)
            
            # Usa ActionChains para enviar Ctrl+S
            actions = ActionChains(driver)
            actions.key_down(Keys.CONTROL).send_keys('s').key_up(Keys.CONTROL).perform()
            
            print('[SELENIUM] Ctrl+S enviado!', flush=True)
            icone_encontrado = True
            time.sleep(2)
            
            # Tenta aceitar o diálogo de salvar (se aparecer)
            try:
                # Espera um pouco pelo diálogo
                time.sleep(1)
                
                # Tenta encontrar o campo de nome do arquivo e alterar
                from selenium.webdriver.support.ui import WebDriverWait
                from selenium.webdriver.support import expected_conditions as EC
                
                # Espera o diálogo aparecer (máximo 5s)
                try:
                    WebDriverWait(driver, 5).until(EC.alert_is_present())
                    alert = driver.switch_to.alert
                    # Alerta de download - aceita
                    alert.accept()
                    print('[SELENIUM] Alerta aceito', flush=True)
                except:
                    pass
            except:
                pass
            
        except Exception as e:
            print(f'[SELENIUM] Erro Ctrl+S: {e}', flush=True)
            icone_encontrado = False
        
        # FALLBACK: Se Ctrl+S não funcionar, tenta clicar no ícone
        if not icone_encontrado:
            print('[SELENIUM] Tentando clicar no icone...', flush=True)
            try:
                icones = driver.find_elements(By.CSS_SELECTOR, 'cr-icon-button, [role="button"]')
                for idx, botao in enumerate(icones):
                    try:
                        loc = botao.location
                        y = loc.get('y', 0)
                        x = loc.get('x', 0)
                        
                        if y < 150 and x > 800:
                            print(f'[SELENIUM] Clicando botao {idx}', flush=True)
                            botao.click()
                            icone_encontrado = True
                            time.sleep(3)
                            break
                    except:
                        pass
            except Exception as e:
                print(f'[SELENIUM] Erro fallback: {e}', flush=True)
        
        # Estrategia 2: Procura links/botoes na regiao superior
        if not icone_encontrado:
            print('[SELENIUM] Verificando links/botoes...', flush=True)
            try:
                elementos = driver.find_elements(By.XPATH, '//a | //button')
                for idx, el in enumerate(elementos):
                    loc = el.location
                    y = loc.get('y', 0)
                    x = loc.get('x', 0)
                    texto = (el.text or el.get_attribute('title') or '')[:30]
                    
                    if y < 150 and x > 300:
                        try:
                            el.click()
                            icone_encontrado = True
                            print(f'[SELENIUM] Clicou no elemento {idx}: {texto}', flush=True)
                            time.sleep(3)
                            break
                        except:
                            pass
            except Exception as e:
                print(f'[SELENIUM] Erro estrategia 2: {e}', flush=True)
        
        # Estrategia 3: JavaScript - primeiro elemento clicavel na regiao
        if not icone_encontrado:
            print('[SELENIUM] Tentando JavaScript...', flush=True)
            try:
                resultado = driver.execute_script("""
                    const elementos = document.querySelectorAll('*');
                    for (const el of elementos) {
                        if (el.children.length === 0) {
                            const rect = el.getBoundingClientRect();
                            if (rect.top >= 0 && rect.top < 150 && rect.left > 300 && rect.width > 5) {
                                el.click();
                                return true;
                            }
                        }
                    }
                    return false;
                """)
                
                if resultado:
                    print('[SELENIUM] Clicou via JavaScript', flush=True)
                    icone_encontrado = True
                    time.sleep(3)
            except Exception as e:
                print(f'[SELENIUM] Erro JS: {e}', flush=True)
        
        if icone_encontrado:
            print('[SELENIUM] Aguardando download...', flush=True)
            time.sleep(5)
            
            # Verifica pastas de download
            pastas = [pasta_destino, os.path.join(os.path.expanduser('~'), 'Downloads')]
            
            for pasta in pastas:
                if os.path.exists(pasta):
                    arquivos = list(Path(pasta).glob('*.pdf'))
                    if arquivos:
                        arquivo_recente = max(arquivos, key=os.path.getmtime)
                        tempo_mod = time.time() - os.path.getmtime(str(arquivo_recente))
                        if tempo_mod < 60:
                            tamanho = os.path.getsize(str(arquivo_recente))
                            if tamanho > 5000:
                                if str(arquivo_recente) != caminho_final:
                                    import shutil
                                    shutil.move(str(arquivo_recente), caminho_final)
                                print(f'[SELENIUM] Download OK: {caminho_final} ({tamanho} bytes)', flush=True)
                                return True, caminho_final, tamanho
        
        print('[SELENIUM] Download nao confirmado', flush=True)
        return False, caminho_final, 0
        
    except Exception as e:
        print(f'[SELENIUM] Erro: {e}', flush=True)
        return False, caminho_final, 0
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass


if __name__ == '__main__':
    print('Modulo Selenium carregado.')