import os
import re
import sys
import time
import json
import threading
import queue
from pathlib import Path
from flask import Flask, render_template, request, Response, jsonify
from dotenv import load_dotenv

# Importa pyautogui para clicar por coordenadas (apenas no Windows local)
try:
    import pyautogui
    PYAUTOGUI_DISPONIVEL = True
except ImportError:
    PYAUTOGUI_DISPONIVEL = False

load_dotenv()

# NOTA: playwright importado APENAS dentro de run_automation()
# para evitar travamento na inicialização do servidor

# === DETECTA AMBIENTE: cloud vs local ===
IS_CLOUD = os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('RENDER') or os.environ.get('DYNO')
IS_CLOUD = bool(IS_CLOUD)
# SEMPRE abre navegador COM interface gráfica (visível)
HEADLESS = False

if IS_CLOUD:
    print('[INIT] Modo CLOUD detectado - rodando headless', flush=True)
else:
    print(f'[INIT] Modo LOCAL - headless={HEADLESS}', flush=True)

app = Flask(__name__)

# Configurações
SITE_URL = os.getenv('SITE_URL', 'https://protocolo.manaus.am.gov.br/proton/login.asp')
SITE_LOGIN = os.getenv('SITE_LOGIN', '')
SITE_SENHA = os.getenv('SITE_SENHA', '')
# Pasta de destino: se não configurada, usa "downloads" dentro da pasta do projeto
PASTA_ENV = os.getenv('PASTA_DESTINO', '')
if PASTA_ENV:
    PASTA_DESTINO = PASTA_ENV
else:
    PASTA_DESTINO = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')

# Fila de eventos SSE para cada execução
event_queue = queue.Queue()
execution_active = False

def emit(tipo, msg, **kwargs):
    """Envia evento para o frontend via SSE."""
    data = {'tipo': tipo, 'msg': msg, **kwargs}
    event_queue.put(data)


def run_automation(processos):
    """
    Executa a automação completa no Playwright.
    Fluxo do usuário:
      1. Login no SIGED
      2. Clica em "Pesquisa Rápida"
      3. Cola o número do processo e clica Pesquisar
      4. Na tela de dados do processo, clica em "VISUALIZAR"
      5. Na nova aba, clica no símbolo ">>" para baixar
      6. Salva o PDF em D:\\Processos
    """
    from playwright.sync_api import sync_playwright
    global execution_active
    execution_active = True

    # Garante que a pasta de destino existe
    Path(PASTA_DESTINO).mkdir(parents=True, exist_ok=True)

    emit('info', f'📂 Pasta de destino: {PASTA_DESTINO}')
    emit('info', f'🔗 URL do site: {SITE_URL}')
    emit('info', f'📝 Total de processos: {len(processos)}')

    try:
        with sync_playwright() as p:
            # === LANÇA NAVEGADOR ===
            print('[DEBUG] PASSO 0: Abrindo navegador...', flush=True)
            emit('info', '🌐 Abrindo navegador...')
            
            # Usa Chromium padrão (mais compatível) com anti-detecção
            browser = p.chromium.launch(
                headless=HEADLESS,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-infobars',
                    '--window-size=1400,900',
                ]
            )
            print('[DEBUG] Navegador aberto com sucesso!', flush=True)
            emit('info', '   ✅ Navegador aberto!')
            
            context = browser.new_context(
                accept_downloads=True,
                viewport={'width': 1400, 'height': 900},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='pt-BR',
                timezone_id='America/Manaus',
            )
            
            # Script anti-detecção
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                if (window.chrome) window.chrome.runtime = undefined;
                Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
                Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR','pt','en-US','en'] });
                delete window.__PLAYWRIGHT__;
                delete window.__pw_app_loader;
            """)
            
            page = context.new_page()
            print('[DEBUG] PASSO 1: Navegando para URL de login...', flush=True)
            emit('info', '🔑 Acessando página de login...')
            
            try:
                # Timeout maior (120s) pois o site pode estar lento dos EUA
                page.goto(SITE_URL, wait_until='domcontentloaded', timeout=120000)
                print(f'[DEBUG] Página carregada! URL: {page.url}', flush=True)
            except Exception as e:
                print(f'[DEBUG] Erro ao carregar página: {e}', flush=True)
                # Tenta novamente com mais tempo
                try:
                    emit('info', '   🔄 Tentando novamente com mais tempo...')
                    page.goto(SITE_URL, wait_until='domcontentloaded', timeout=120000)
                    print(f'[DEBUG] Página carregada na 2a tentativa! URL: {page.url}', flush=True)
                except Exception as e2:
                    print(f'[DEBUG] Erro na 2a tentativa: {e2}', flush=True)
                    emit('erro', f'❌ Erro ao carregar página: {str(e)[:100]}')
                    time.sleep(30)
                    browser.close()
                    execution_active = False
                    emit('fim', '')
                    return
            
            time.sleep(3)
            
            # ================================================================
            # DEBUG: Verifica se há iframes na página
            # ================================================================
            print('[DEBUG] Verificando iframes...', flush=True)
            try:
                frames = page.frames
                print(f'[DEBUG] Total de frames encontrados: {len(frames)}', flush=True)
                for i, f in enumerate(frames):
                    print(f'[DEBUG] Frame {i}: url={f.url[:80]}', flush=True)
                    emit('info', f'   📋 Frame {i}: {f.url[:80]}')
            except Exception as e:
                print(f'[DEBUG] Erro ao listar frames: {e}', flush=True)
            
            # ================================================================
            # DEBUG: Tenta extrair HTML da página
            # ================================================================
            print('[DEBUG] Extraindo HTML da página...', flush=True)
            try:
                html_preview = page.evaluate("() => document.body ? document.body.innerHTML.substring(0, 3000) : 'SEM BODY'")
                print(f'[DEBUG] HTML preview (3000 chars):', flush=True)
                print(html_preview[:2000], flush=True)
            except Exception as e:
                print(f'[DEBUG] Erro ao extrair HTML: {e}', flush=True)
            
            # ================================================================
            # Tenta encontrar campos em TODOS os frames
            # ================================================================
            print('[DEBUG] Procurando campos de login em todos os frames...', flush=True)
            emit('info', '   🔍 Procurando campos de login...')
            
            cpf_preenchido = False
            senha_preenchida = False
            btn_clicado = False
            
            # Lista de frames para tentar (primeiro o principal, depois iframes)
            all_frames = [page] + page.frames[1:]  # page.frames[0] é o próprio page
            
            for frame_idx, current_frame in enumerate(all_frames):
                frame_name = 'principal' if frame_idx == 0 else f'iframe_{frame_idx}'
                print(f'[DEBUG] Tentando frame {frame_name}: {current_frame.url[:80]}', flush=True)
                
                try:
                    # Tenta encontrar inputs neste frame
                    inputs = current_frame.evaluate("""() => {
                        const all = document.querySelectorAll('input:not([type="hidden"])');
                        const result = [];
                        all.forEach(el => {
                            if (el.offsetParent !== null) {
                                result.push({
                                    type: el.type,
                                    name: el.name,
                                    id: el.id,
                                    placeholder: el.placeholder
                                });
                            }
                        });
                        return JSON.stringify(result);
                    }""")
                    parsed_inputs = json.loads(inputs)
                    print(f'[DEBUG] Frame {frame_name} - inputs visíveis: {len(parsed_inputs)}', flush=True)
                    for inp in parsed_inputs:
                        print(f'[DEBUG]   input type="{inp["type"]}" name="{inp["name"]}" id="{inp["id"]}" placeholder="{inp["placeholder"]}"', flush=True)
                    
                    # Tenta encontrar botões
                    buttons = current_frame.evaluate("""() => {
                        const all = document.querySelectorAll('button, input[type="submit"]');
                        const result = [];
                        all.forEach(el => {
                            if (el.offsetParent !== null) {
                                result.push({
                                    type: el.type || '',
                                    text: (el.innerText || el.value || '').trim().substring(0, 20)
                                });
                            }
                        });
                        return JSON.stringify(result);
                    }""")
                    parsed_buttons = json.loads(buttons)
                    print(f'[DEBUG] Frame {frame_name} - botões visíveis: {len(parsed_buttons)}', flush=True)
                    for btn in parsed_buttons:
                        print(f'[DEBUG]   button type="{btn["type"]}" text="{btn["text"]}"', flush=True)
                    
                except Exception as e:
                    print(f'[DEBUG] Erro ao inspecionar frame {frame_name}: {e}', flush=True)
                    continue
                
                # Se já preencheu tudo, não precisa continuar
                if cpf_preenchido and senha_preenchida and btn_clicado:
                    break
                
                # Tenta preencher CPF neste frame
                if not cpf_preenchido:
                    for selector in [
                        'input[name="cpf"]',
                        'input[id*="cpf"]',
                        'input[placeholder*="cpf" i]',
                        'input[name="txt_login"]',
                        '#txt_login',
                        'input[type="text"]',
                    ]:
                        try:
                            campo = current_frame.locator(selector).first
                            if campo.is_visible(timeout=1000):
                                campo.click()
                                time.sleep(0.2)
                                campo.fill('')
                                time.sleep(0.2)
                                campo.fill(SITE_LOGIN)
                                print(f'[DEBUG] CPF preenchido no frame {frame_name} com seletor: {selector}', flush=True)
                                emit('sucesso', f'   ✅ CPF preenchido ({frame_name})')
                                cpf_preenchido = True
                                break
                        except:
                            continue
                
                # Tenta preencher senha neste frame
                if not senha_preenchida:
                    for selector in [
                        'input[name="senha"]',
                        'input[id*="senha"]',
                        'input[placeholder*="senha" i]',
                        'input[name="txt_senha"]',
                        '#txt_senha',
                        'input[type="password"]',
                    ]:
                        try:
                            campo = current_frame.locator(selector).first
                            if campo.is_visible(timeout=1000):
                                campo.click()
                                time.sleep(0.2)
                                campo.fill('')
                                time.sleep(0.2)
                                campo.fill(SITE_SENHA)
                                print(f'[DEBUG] Senha preenchida no frame {frame_name} com seletor: {selector}', flush=True)
                                emit('sucesso', f'   ✅ Senha preenchida ({frame_name})')
                                senha_preenchida = True
                                break
                        except:
                            continue
                
                # Tenta clicar no botão ENTRAR neste frame
                if not btn_clicado:
                    for texto in ['Entrar', 'ENTRAR', 'entrar', 'Acessar', 'ACESSAR', 'Login', 'LOGIN']:
                        try:
                            btn = current_frame.locator(f'button:has-text("{texto}")').first
                            if btn.is_visible(timeout=500):
                                btn.click()
                                print(f'[DEBUG] Botão "{texto}" clicado no frame {frame_name}', flush=True)
                                emit('sucesso', f'   ✅ Botão "{texto}" clicado!')
                                btn_clicado = True
                                break
                        except:
                            continue
                    
                    if not btn_clicado:
                        try:
                            btn = current_frame.locator('input[type="submit"]').first
                            if btn.is_visible(timeout=500):
                                btn.click()
                                print(f'[DEBUG] input[type="submit"] clicado no frame {frame_name}', flush=True)
                                emit('sucesso', '   ✅ Botão submit clicado!')
                                btn_clicado = True
                        except:
                            pass
            
            # ================================================================
            # FALLBACK: Se não encontrou em nenhum frame, tenta JavaScript
            # ================================================================
            if not cpf_preenchido:
                print('[DEBUG] CPF não encontrado em nenhum frame! Tentando JavaScript...', flush=True)
                emit('info', '   ▶ Tentando preencher CPF via JavaScript...')
                login_escaped = SITE_LOGIN.replace("'", "\\'").replace("\\", "\\\\")
                for f in all_frames:
                    try:
                        result = f.evaluate(f"""
                            (function() {{
                                var campo = document.querySelector('input[name="cpf"]') || 
                                           document.querySelector('input[id*="cpf"]') ||
                                           document.querySelector('input[type="text"]');
                                if (campo) {{
                                    campo.value = '{login_escaped}';
                                    campo.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                    return 'OK';
                                }}
                                return 'NOT_FOUND';
                            }})()
                        """)
                        print(f'[DEBUG] JS CPF result: {result}', flush=True)
                        if result == 'OK':
                            cpf_preenchido = True
                            break
                    except:
                        continue
            
            if not senha_preenchida:
                print('[DEBUG] Senha não encontrada em nenhum frame! Tentando JavaScript...', flush=True)
                emit('info', '   ▶ Tentando preencher senha via JavaScript...')
                senha_escaped = SITE_SENHA.replace("'", "\\'").replace("\\", "\\\\")
                for f in all_frames:
                    try:
                        result = f.evaluate(f"""
                            (function() {{
                                var campo = document.querySelector('input[name="senha"]') ||
                                           document.querySelector('input[id*="senha"]') ||
                                           document.querySelector('input[type="password"]');
                                if (campo) {{
                                    campo.value = '{senha_escaped}';
                                    campo.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                    return 'OK';
                                }}
                                return 'NOT_FOUND';
                            }})()
                        """)
                        print(f'[DEBUG] JS Senha result: {result}', flush=True)
                        if result == 'OK':
                            senha_preenchida = True
                            break
                    except:
                        continue
            
            # ================================================================
            # APÓS PREENCHER OS CAMPOS COM LOCATOR, CLICA NO BOTÃO ENTRAR
            # ================================================================
            print(f'[DEBUG] Verificando se já está logado...', flush=True)
            current_url = page.url
            print(f'[DEBUG] URL atual: {current_url}', flush=True)
            
            if 'login.asp' in current_url.lower():
                # AINDA na página de login - precisa fazer login
                print('[DEBUG] Ainda na página de login. Preenchendo campos...', flush=True)
                
                # Verifica valores ANTES de preencher
                valores_antes = page.evaluate("""() => {
                    var cpf = document.getElementById('txt_login');
                    var senha = document.getElementById('txt_senha');
                    return 'ANTES|CPF=[' + (cpf ? cpf.value : 'N/A') + ']|SENHA=[' + (senha ? senha.value : 'N/A') + ']';
                }""")
                print(f'[DEBUG] {valores_antes}', flush=True)
                
                # Preenche CPF
                emit('info', '   ✏️ Preenchendo CPF...')
                try:
                    campo_cpf = page.locator('#txt_login').first
                    campo_cpf.click(timeout=5000)
                    time.sleep(0.1)
                    campo_cpf.fill('')
                    time.sleep(0.1)
                    login_limpo = re.sub(r'[.\-\s]', '', SITE_LOGIN)
                    campo_cpf.fill(login_limpo)
                    print(f'[DEBUG] CPF preenchido: [{login_limpo}]', flush=True)
                    emit('sucesso', '   ✅ CPF preenchido!')
                except Exception as e:
                    print(f'[DEBUG] Erro CPF: {e}', flush=True)
                
                time.sleep(0.2)
                
                # Preenche Senha
                emit('info', '   ✏️ Preenchendo senha...')
                try:
                    campo_senha = page.locator('#txt_senha').first
                    campo_senha.click(timeout=5000)
                    time.sleep(0.1)
                    campo_senha.fill('')
                    time.sleep(0.1)
                    campo_senha.fill(SITE_SENHA)
                    print(f'[DEBUG] Senha preenchida', flush=True)
                    emit('sucesso', '   ✅ Senha preenchida!')
                except Exception as e:
                    print(f'[DEBUG] Erro senha: {e}', flush=True)
                
                time.sleep(0.3)
                
                # Clica no botão ENTRAR
                emit('info', '   ▶ Clicando ENTRAR...')
                btn_clicou = False
                for texto in ['Entrar', 'ENTRAR', 'entrar']:
                    try:
                        btn = page.locator(f'button:has-text("{texto}")').first
                        if btn.is_visible(timeout=2000):
                            btn.click()
                            print(f'[DEBUG] Botão "{texto}" clicado!', flush=True)
                            emit('sucesso', '   ✅ Botão ENTRAR clicado!')
                            btn_clicou = True
                            break
                    except:
                        continue
                
                if not btn_clicou:
                    print('[DEBUG] Botão não clicou. Tentando fn_entrar()...', flush=True)
                    emit('info', '   ▶ Chamando fn_entrar()...')
                    page.evaluate("if (typeof fn_entrar === 'function') fn_entrar();")
                
                print('[DEBUG] Aguardando login...', flush=True)
                emit('info', '⏳ Aguardando login...')
                time.sleep(5)
                
                # Verifica se a URL mudou
                current_url = page.url
                print(f'[DEBUG] URL após 5s: {current_url}', flush=True)
                
                if 'login.asp' in current_url.lower():
                    print('[DEBUG] Ainda em login.asp, aguardando mais...', flush=True)
                    time.sleep(10)
                    try:
                        page.wait_for_load_state('networkidle', timeout=20000)
                    except:
                        pass
                    current_url = page.url
                    print(f'[DEBUG] URL após 15s: {current_url}', flush=True)
                
                emit('info', f'📍 URL atual: {current_url}')
                
                # Verifica se o login funcionou
                if 'login.asp' in current_url.lower():
                    print('[DEBUG] ❌ LOGIN FALHOU!', flush=True)
                    emit('erro', '❌ Login falhou! Verifique credenciais no .env')
                    try:
                        page.screenshot(path=os.path.join(PASTA_DESTINO, '_erro_login_falhou.png'))
                    except:
                        pass
                    print('[DEBUG] Navegador aberto para inspeção por 5s', flush=True)
                    emit('info', '⚠️ Navegador aberto para inspeção por 5s')
                    time.sleep(5)
                    browser.close()
                    execution_active = False
                    emit('fim', '')
                    return
            else:
                print('[DEBUG] ✅ JÁ ESTÁ LOGADO! Pulando etapa de login.', flush=True)
                emit('sucesso', '✅ Login já realizado!')

            emit('sucesso', '✅ Login realizado com sucesso!')

            # ============================================================
            # PASSO 2: PARA CADA PROCESSO
            # ============================================================
            # ============================================================
            # PASSO 2: DEBUG DA PÁGINA APÓS LOGIN
            # ============================================================
            print('[DEBUG] Aguardando página carregar completamente...', flush=True)
            time.sleep(1)
            try:
                page.wait_for_load_state('networkidle', timeout=20000)
            except:
                pass
            
            # Debug completo da página após login
            print(f'[DEBUG] URL atual: {page.url}', flush=True)
            print(f'[DEBUG] Title: {page.title()}', flush=True)
            
            # Lista TODOS os elementos da página
            try:
                full_html = page.evaluate("() => document.body ? document.body.innerHTML : 'NO BODY'")
                # Salva HTML completo para debug
                with open(os.path.join(PASTA_DESTINO, '_debug_pagina.html'), 'w', encoding='utf-8') as f:
                    f.write(full_html)
                print(f'[DEBUG] HTML completo salvo em {PASTA_DESTINO}', flush=True)
            except Exception as e:
                print(f'[DEBUG] Erro ao salvar HTML: {e}', flush=True)
            
            # Lista TODOS os inputs, inclusive em iframes
            try:
                all_inputs = page.evaluate("""() => {
                    const all = document.querySelectorAll('input');
                    const result = [];
                    all.forEach(el => {
                        result.push({
                            tag: el.tagName,
                            type: el.type,
                            name: el.name,
                            id: el.id,
                            class: (el.className || '').substring(0, 40),
                            placeholder: el.placeholder,
                            value: (el.value || '').substring(0, 30),
                            visible: el.offsetParent !== null,
                            rect: el.getBoundingClientRect() ? JSON.stringify({top: el.getBoundingClientRect().top, left: el.getBoundingClientRect().left}) : ''
                        });
                    });
                    return JSON.stringify(result);
                }""")
                parsed = json.loads(all_inputs)
                print(f'[DEBUG] Total de inputs na página: {len(parsed)}', flush=True)
                for inp in parsed:
                    print(f'[DEBUG]   <{inp["tag"]} type="{inp["type"]}" name="{inp["name"]}" id="{inp["id"]}" placeholder="{inp["placeholder"]}" value="{inp["value"]}" visible={inp["visible"]} rect={inp["rect"]}', flush=True)
            except Exception as e:
                print(f'[DEBUG] Erro listar inputs: {e}', flush=True)
                
            # Lista TODOS os botões
            try:
                all_buttons = page.evaluate("""() => {
                    const all = document.querySelectorAll('button');
                    const result = [];
                    all.forEach(el => {
                        result.push({
                            id: el.id,
                            text: (el.innerText || '').trim().substring(0, 30),
                            visible: el.offsetParent !== null,
                            rect: el.getBoundingClientRect() ? JSON.stringify({top: el.getBoundingClientRect().top, left: el.getBoundingClientRect().left}) : ''
                        });
                    });
                    return JSON.stringify(result);
                }""")
                parsed_btns = json.loads(all_buttons)
                print(f'[DEBUG] Total de botões: {len(parsed_btns)}', flush=True)
                for btn in parsed_btns:
                    print(f'[DEBUG]   button id="{btn["id"]}" text="{btn["text"]}" visible={btn["visible"]} rect={btn["rect"]}', flush=True)
            except Exception as e:
                print(f'[DEBUG] Erro listar botões: {e}', flush=True)

            # ============================================================
            # PASSO 3: PREENCHER CAMPOS DE PESQUISA RÁPIDA E PESQUISAR
            # ============================================================
            for i, processo in enumerate(processos):
                emit('info', f'\n{"="*50}')
                emit('info', f'📋 Processo [{i+1}/{len(processos)}]: {processo}')
                emit('info', f'{"="*50}')
                emit('progresso', '', concluidos=i)

                try:
                    # -------------------------------------------------------
                    # A) Preenche o número do processo no campo "txt_numero_ano"
                    # -------------------------------------------------------
                    emit('info', f'   ✏️ Digitando processo: {processo}')
                    
                    # Parseia o processo em partes: ANO.FIXO.ORGAO.TIPO.SEQUENCIAL
                    # Ex: 2025.18000.19328.0.037608
                    partes = re.split(r'[.\-\s]', processo.strip())
                    print(f'[DEBUG] Processo parseado: {partes}', flush=True)
                    
                    # Mapeia para os campos (pode ter de 3 a 5 partes)
                    ano = partes[0] if len(partes) > 0 else ''
                    fixo = partes[1] if len(partes) > 1 else ''
                    orgao = partes[2] if len(partes) > 2 else ''
                    tipo = partes[3] if len(partes) > 3 else ''
                    sequencial = partes[4] if len(partes) > 4 else ''
                    
                    emit('info', f'   📋 Partes: ano={ano}, fixo={fixo}, orgao={orgao}, tipo={tipo}, seq={sequencial}')
                    
                    # Preenche cada campo via JavaScript
                    result = page.evaluate(f"""
                        (function() {{
                            var r = [];
                            
                            // Campo ANO
                            var campo_ano = document.getElementById('txt_numero_ano');
                            if (campo_ano) {{
                                campo_ano.value = '';
                                campo_ano.value = '{ano}';
                                campo_ano.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                campo_ano.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                r.push('ano=' + campo_ano.value);
                            }}
                            
                            // Campo FIXO
                            var campo_fixo = document.getElementById('txt_numero_fixo');
                            if (campo_fixo) {{
                                campo_fixo.value = '';
                                campo_fixo.value = '{fixo}';
                                campo_fixo.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                campo_fixo.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                r.push('fixo=' + campo_fixo.value);
                            }}
                            
                            // Campo ORGAO
                            var campo_orgao = document.getElementById('txt_numero_orgao');
                            if (campo_orgao) {{
                                campo_orgao.value = '';
                                campo_orgao.value = '{orgao}';
                                campo_orgao.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                campo_orgao.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                r.push('orgao=' + campo_orgao.value);
                            }}
                            
                            // Campo TIPO
                            var campo_tipo = document.getElementById('txt_numero_tipo');
                            if (campo_tipo) {{
                                campo_tipo.value = '';
                                campo_tipo.value = '{tipo}';
                                campo_tipo.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                campo_tipo.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                r.push('tipo=' + campo_tipo.value);
                            }}
                            
                            // Campo SEQUENCIAL
                            var campo_seq = document.getElementById('txt_numero_sequencial');
                            if (campo_seq) {{
                                campo_seq.value = '';
                                campo_seq.value = '{sequencial}';
                                campo_seq.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                campo_seq.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                r.push('seq=' + campo_seq.value);
                            }}
                            
                            return r.join(' | ');
                        }})()
                    """)
                    print(f'[DEBUG] Campos preenchidos: {result}', flush=True)
                    emit('info', f'   📋 {result}')
                    
                    time.sleep(0.5)
                    emit('sucesso', f'   ✅ Processo digitado!')

                    # -------------------------------------------------------
                    # B) Clica no botão "PESQUISAR"
                    # -------------------------------------------------------
                    emit('info', '   🔎 Clicando em PESQUISAR...')
                    time.sleep(0.5)

                    btn_pesquisar = None
                    for sel in [
                        'button:has-text("PESQUISAR")',
                        'button:has-text("Pesquisar")',
                        'button[type="submit"]',
                    ]:
                        try:
                            btn = page.locator(sel).first
                            if btn.is_visible(timeout=2000):
                                btn_pesquisar = btn
                                emit('info', f'   ▶ Botão pesquisar encontrado: {sel}')
                                break
                        except:
                            continue

                    if btn_pesquisar:
                        btn_pesquisar.click(force=True)
                        emit('sucesso', '   ✅ PESQUISAR clicado!')
                    else:
                        emit('info', '   ▶ Botão não encontrado, tentando JS...')
                        page.evaluate("""
                            (function() {
                                var botoes = document.querySelectorAll('button');
                                for (var i = 0; i < botoes.length; i++) {
                                    if (botoes[i].offsetParent !== null && botoes[i].innerText.trim() === 'PESQUISAR') {
                                        botoes[i].click();
                                        return;
                                    }
                                }
                            })()
                        """)

                    time.sleep(3)
                    try:
                        page.wait_for_load_state('networkidle', timeout=15000)
                    except:
                        pass
                    emit('sucesso', '   ✅ Pesquisa realizada!')

                    # -------------------------------------------------------
                    # D) Clica em "VISUALIZAR"
                    # -------------------------------------------------------
                    emit('info', '   👁️ Procurando botão VISUALIZAR...')

                    visualizar = None
                    
                    # Estratégia 1: Usa locator com has-text (mais confiável)
                    try:
                        btn = page.locator('button:has-text("VISUALIZAR")').first
                        if btn.is_visible(timeout=5000):
                            visualizar = btn
                            emit('info', '   ▶ VISUALIZAR encontrado via locator button')
                    except Exception as e:
                        print(f'[DEBUG] Erro locator button: {e}', flush=True)
                    
                    # Estratégia 2: query_selector com seletor CSS
                    if not visualizar:
                        for sel in [
                            'button:has-text("VISUALIZAR")',
                            'a:has-text("VISUALIZAR")',
                            'button[id*="visualiz" i]',
                            'a[id*="visualiz" i]',
                            '[class*="visualizar"]',
                        ]:
                            try:
                                el = page.query_selector(sel)
                                if el and el.is_visible(timeout=2000):
                                    visualizar = el
                                    emit('info', f'   ▶ VISUALIZAR encontrado: {sel}')
                                    break
                            except:
                                continue
                    
                    # Estratégia 3: get_by_text com timeout maior
                    if not visualizar:
                        try:
                            visualizar = page.get_by_text('VISUALIZAR', exact=True).first
                            if visualizar.is_visible(timeout=3000):
                                emit('info', '   ▶ VISUALIZAR encontrado via get_by_text exato')
                        except Exception as e:
                            print(f'[DEBUG] Erro get_by_text exato: {e}', flush=True)
                    
                    if not visualizar:
                        try:
                            visualizar = page.get_by_text(re.compile(r'VISUALIZAR', re.I)).first
                            emit('info', '   ▶ VISUALIZAR encontrado via get_by_text regex')
                        except Exception as e:
                            print(f'[DEBUG] Erro get_by_text regex: {e}', flush=True)

                    # -------------------------------------------------------
                    # E) CLICA EM VISUALIZAR E ESPERA O DOWNLOAD AUTOMÁTICO
                    # -------------------------------------------------------
                    emit('info', '   👁️ Clicando em VISUALIZAR...')
                    download_realizado = False
                    nome_arquivo = f'processo_{processo.replace("/","_").replace("\\","_").replace(".","_")}.pdf'

                    if visualizar:
                        try:
                            # ESTRATÉGIA: Usa expect_download para capturar o arquivo
                            # automaticamente quando o VISUALIZAR for clicado
                            caminho_pdf = os.path.join(PASTA_DESTINO, nome_arquivo)
                            
                            # Remove arquivo antigo se existir
                            if os.path.exists(caminho_pdf):
                                os.remove(caminho_pdf)
                            
                            emit('info', '   💾 Aguardando download iniciar...')
                            
                            # Captura o download quando o VISUALIZAR for clicado
                            with page.expect_download(timeout=60000) as download_info:
                                visualizar.click(force=True)
                            
                            # Download iniciado!
                            download = download_info.value
                            
                            # Salva com o nome desejado
                            download.save_as(caminho_pdf)
                            
                            # Verifica se o arquivo foi salvo
                            if os.path.exists(caminho_pdf):
                                tamanho = os.path.getsize(caminho_pdf)
                                if tamanho > 5000:  # Mínimo 5KB para ser um PDF válido
                                    emit('sucesso', f'   ✅ Download: {nome_arquivo} ({tamanho//1024} KB)')
                                    download_realizado = True
                                    print(f'[DEBUG] Download OK: {caminho_pdf}', flush=True)
                                else:
                                    emit('erro', f'   ❌ Arquivo muito pequeno: {tamanho} bytes')
                            else:
                                emit('erro', '   ❌ Arquivo não foi salvo')
                                
                        except Exception as e:
                            print(f'[DEBUG] Erro no download: {e}', flush=True)
                            emit('erro', f'   ❌ Erro: {str(e)[:100]}')
                            
                            # SOLUÇÃO: Impede nova aba e captura a URL para download direto
                            emit('info', '   🔗 Capturando URL do documento...')
                            download_realizado = False
                            
                            # Configura listener para capturar o download ANTES de clicar
                            try:
                                caminho_pdf = os.path.join(PASTA_DESTINO, nome_arquivo)
                                
                                # Captura a URL e MANTÉM a nova aba aberta
                                url_destino = None
                                nova_aba = None
                                with context.expect_page(timeout=10000) as new_page_info:
                                    visualizar.click(force=True)
                                
                                try:
                                    nova_aba = new_page_info.value
                                    url_destino = nova_aba.url
                                    emit('sucesso', f'   ✅ Documento aberto! {url_destino[:60]}')
                                    emit('info', f'   👉 Uma nova aba abriu no navegador - CLIQUE NO ÍCONE DE DOWNLOAD 📥')
                                    
                                # NÃO fecha a nova aba - deixa ABERTA para o usuário baixar
                                    download_realizado = True
                                    
                                    # Usa PYAUTOGUI para clicar no botão de download (ícone no canto superior direito)
                                    if PYAUTOGUI_DISPONIVEL:
                                        try:
                                            emit('info', f'   🤖 Clicando no botão de download (pyautogui)...')
                                            # Coordenadas do botão de download baseado no print (toolbar Chrome superior direita)
                                            # x=0.972 (97.2% da largura), y=0.110 (11% da altura)
                                            # Para 1920x1080: x≈1867, y≈119
                                            pyautogui.click(0.972, 0.110)
                                            emit('sucesso', f'   ✅ Clique no download realizado!')
                                            time.sleep(3)
                                        except Exception as e:
                                            print(f'[PYAUTOGUI] Erro: {e}', flush=True)
                                            emit('info', f'   ⏳ Aguardando você baixar o PDF (60 segundos)...')
                                    else:
                                        emit('info', f'   ⏳ Aguardando você baixar o PDF (60 segundos)...')
                                    
                                    time.sleep(60)
                                    
                                except Exception as e:
                                    print(f'[DEBUG] Erro ao capturar nova aba: {e}', flush=True)
                                
                                if not download_realizado:
                                    emit('erro', '   ❌ Download não realizado')
                                    
                            except Exception as e:
                                print(f'[DEBUG] Erro ao capturar URL: {e}', flush=True)
                                emit('erro', f'   ❌ Erro: {str(e)[:100]}')
                                
                        except Exception as e:
                            print(f'[DEBUG] Erro geral no fluxo VISUALIZAR: {e}', flush=True)
                            emit('erro', f'   ❌ Erro: {str(e)[:100]}')
                    else:
                        emit('erro', '   ❌ Botão VISUALIZAR não encontrado')
                        page.screenshot(path=os.path.join(PASTA_DESTINO, f'_erro_visualizar_{processo.replace("/","_")}.png'))

                    # Volta para a página principal
                    try:
                        if page and not page.is_closed():
                            page.bring_to_front()
                    except:
                        pass
                    time.sleep(1)

                except Exception as e:
                    emit('erro', f'   ❌ Erro ao processar {processo}: {str(e)[:150]}')
                    # Tenta voltar para a página principal
                    try:
                        if page and not page.is_closed():
                            page.bring_to_front()
                    except:
                        pass
                    continue

            # ============================================================
            # FINALIZA
            # ============================================================
            emit('progresso', '', concluidos=len(processos))
            emit('sucesso', f'\n📊 Automação finalizada! {len(processos)} processo(s) processado(s).')
            emit('info', f'📂 Verifique os arquivos em: {PASTA_DESTINO}')

            time.sleep(2)
            browser.close()
            emit('info', '🛑 Navegador fechado.')

    except Exception as e:
        emit('erro', f'❌ Erro geral na automação: {str(e)[:300]}')

    finally:
        execution_active = False
        emit('fim', '')


# ===== ROTAS FLASK =====

@app.route('/health')
@app.route('/ping')
def health_check():
    """Health check obrigatório para Railway/Render."""
    return 'OK', 200


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/iniciar', methods=['POST'])
def iniciar():
    global execution_active
    data = request.get_json()
    if not data or 'processos' not in data:
        return jsonify({'erro': 'Lista de processos não informada'}), 400

    processos = data['processos']
    if not processos:
        return jsonify({'erro': 'Lista vazia'}), 400

    if execution_active:
        return jsonify({'erro': 'Já existe uma execução em andamento'}), 409

    # Limpa fila de eventos
    while not event_queue.empty():
        try:
            event_queue.get_nowait()
        except queue.Empty:
            break

    # Dispara automação em thread separada
    thread = threading.Thread(target=run_automation, args=(processos,), daemon=True)
    thread.start()

    return jsonify({'status': 'iniciado', 'processos': len(processos)})


@app.route('/progresso')
def progresso():
    def event_stream():
        while True:
            try:
                event = event_queue.get(timeout=30)
                yield f'data: {json.dumps(event)}\n\n'
                if event.get('tipo') == 'fim':
                    break
            except queue.Empty:
                yield f'data: {json.dumps({"tipo": "keepalive"})}\n\n'
                if not execution_active:
                    break

    return Response(
        event_stream(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        }
    )


@app.route('/config')
def config():
    return jsonify({
        'site_url': SITE_URL,
        'pasta_destino': PASTA_DESTINO,
    })


if __name__ == '__main__':
    print('=' * 60)
    print('   AUTOMAÇÃO SIGED - Download de Processos')
    print('=' * 60)
    print(f'   URL: {SITE_URL}')
    print(f'   Destino: {PASTA_DESTINO}')
    print(f'   Login configurado: {"Sim" if SITE_LOGIN else "Não (configure o .env)"}')
    print(f'   Senha configurada: {"Sim" if SITE_SENHA else "Não (configure o .env)"}')
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0' if IS_CLOUD else '127.0.0.1')
    print('=' * 60)
    print(f'   Acesse: http://{host}:{port}')
    print('=' * 60)
    app.run(host=host, port=port, debug=False, threaded=True)
