import os, re, time, json, threading, queue, string, sys
from pathlib import Path
from flask import Flask, render_template, request, Response, jsonify
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

SITE_URL = os.getenv('SITE_URL', 'https://protocolo.manaus.am.gov.br/proton/login.asp')
SITE_LOGIN = os.getenv('SITE_LOGIN', '')
SITE_SENHA = os.getenv('SITE_SENHA', '')

# Detecta ambiente: cloud ou local
IS_CLOUD = bool(os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('RENDER') or os.environ.get('DYNO'))
if not IS_CLOUD and not sys.platform.startswith('win'):
    IS_CLOUD = True
HEADLESS = os.environ.get('HEADLESS', 'true' if IS_CLOUD else 'false').lower() == 'true'

print(f'[INIT] Modo: {"CLOUD" if IS_CLOUD else "LOCAL"} - headless={HEADLESS}', flush=True)

# Detecta automaticamente HD externo (apenas Windows local)
PASTA_DESTINO = None
if sys.platform.startswith('win'):
    for letra in string.ascii_uppercase:
        if letra == 'C':
            continue
        caminho = f"{letra}:\\"
        if os.path.exists(caminho):
            pasta = f"{letra}:\\Processos_SIGED"
            try:
                os.makedirs(pasta, exist_ok=True)
                PASTA_DESTINO = pasta
                print(f'[INIT] HD detectado em {letra}:\\', flush=True)
                break
            except:
                pass

if not PASTA_DESTINO:
    PASTA_DESTINO = os.getenv('PASTA_DESTINO', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads'))
    print(f'[INIT] Usando pasta: {PASTA_DESTINO}', flush=True)

event_queue = queue.Queue()
execution_active = False

def emit(tipo, msg, **kwargs):
    event_queue.put({'tipo': tipo, 'msg': msg, **kwargs})

def run_automation(processos):
    from playwright.sync_api import sync_playwright
    
    global execution_active
    execution_active = True
    Path(PASTA_DESTINO).mkdir(parents=True, exist_ok=True)

    emit('info', f'📂 Pasta: {PASTA_DESTINO}')
    emit('info', f'📝 Total: {len(processos)} processo(s)')

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=HEADLESS, args=['--disable-blink-features=AutomationControlled', '--no-sandbox'])
            context = browser.new_context(viewport={'width': 1400, 'height': 900}, user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36', locale='pt-BR', timezone_id='America/Manaus')
            page = context.new_page()

            emit('info', '🔑 Acessando site...')
            page.goto(SITE_URL, wait_until='domcontentloaded', timeout=120000)
            time.sleep(2)

            emit('info', '   🔍 Fazendo login...')
            page.locator('#txt_login').first.fill(SITE_LOGIN)
            page.locator('#txt_senha').first.fill(SITE_SENHA)
            time.sleep(0.3)
            for texto in ['Entrar', 'ENTRAR']:
                try:
                    btn = page.locator(f'button:has-text("{texto}")').first
                    if btn.is_visible(timeout=1000):
                        btn.click()
                        break
                except:
                    continue
            time.sleep(5)
            emit('sucesso', '✅ Login realizado!')

            for i, processo in enumerate(processos):
                emit('info', f'\n📋 Processo [{i+1}/{len(processos)}]: {processo}')
                emit('progresso', '', concluidos=i)

                try:
                    partes = re.split(r'[.\-\s]', processo.strip())
                    vals = [partes[0] if len(partes)>0 else '', partes[1] if len(partes)>1 else '', partes[2] if len(partes)>2 else '', partes[3] if len(partes)>3 else '', partes[4] if len(partes)>4 else '']
                    page.evaluate(f"""
                        (function() {{
                            var ids = ['txt_numero_ano','txt_numero_fixo','txt_numero_orgao','txt_numero_tipo','txt_numero_sequencial'];
                            var vals = {json.dumps(vals)};
                            for(var i=0;i<ids.length;i++){{ var el=document.getElementById(ids[i]); if(el){{ el.value=vals[i]; el.dispatchEvent(new Event('input',{{bubbles:true}})); }} }}
                        }})()
                    """)
                    time.sleep(0.3)
                    emit('sucesso', '   ✅ Processo digitado!')

                    emit('info', '   🔎 Pesquisando...')
                    for texto in ['PESQUISAR', 'Pesquisar']:
                        try:
                            btn = page.locator(f'button:has-text("{texto}")').first
                            if btn.is_visible(timeout=1000):
                                btn.click(force=True)
                                break
                        except:
                            continue
                    time.sleep(3)
                    try:
                        page.wait_for_load_state('networkidle', timeout=10000)
                    except:
                        pass
                    emit('sucesso', '   ✅ Pesquisa realizada!')

                    # Procura VISUALIZAR
                    emit('info', '   👁️ Procurando VISUALIZAR...')
                    visualizar = None
                    for sel in ['button:has-text("VISUALIZAR")', 'a:has-text("VISUALIZAR")']:
                        try:
                            el = page.locator(sel).first
                            if el.is_visible(timeout=2000):
                                visualizar = el
                                break
                        except:
                            continue
                    if not visualizar:
                        for frame in page.frames:
                            try:
                                vis = frame.get_by_text('VISUALIZAR', exact=True).first
                                if vis.is_visible(timeout=1000):
                                    visualizar = vis
                                    break
                            except:
                                continue
                    if not visualizar:
                        emit('erro', '   ❌ VISUALIZAR nao encontrado')
                        continue
                    emit('sucesso', '   ✅ VISUALIZAR encontrado!')

                    # Abre o documento e baixa via PDF.js
                    try:
                        with context.expect_page(timeout=8000) as pg:
                            visualizar.click(force=True)
                        nova_aba = pg.value
                        nova_aba.wait_for_load_state('networkidle', timeout=15000)
                        emit('info', f'   🌐 URL: {nova_aba.url[:80]}')

                        # Encontra o frame do PDF.js viewer
                        viewer_frame = None
                        for frame in nova_aba.frames:
                            if 'viewer.html' in frame.url:
                                viewer_frame = frame
                                emit('info', f'   ✅ Frame PDF.js encontrado')
                        
                        download_ok = False
                        processo_limpo = processo.replace('/','_').replace('\\','_').replace('.','_')
                        nome_pdf = f"{processo_limpo}.pdf"
                        caminho_pdf = os.path.join(PASTA_DESTINO, nome_pdf)

                        # ESTRATEGIA 1: Extrair URL real do PDF via JavaScript
                        if viewer_frame and not download_ok:
                            try:
                                pdf_url = viewer_frame.evaluate("() => { try { return PDFViewerApplication.url; } catch(e) { return null; } }")
                                if pdf_url:
                                    emit('sucesso', f'   📄 PDF URL: {pdf_url[:80]}')
                                    import requests
                                    session = requests.Session()
                                    for c in context.cookies():
                                        session.cookies.set(c['name'], c['value'])
                                    r = session.get(pdf_url, headers={'User-Agent': 'Mozilla/5.0', 'Referer': nova_aba.url}, timeout=60)
                                    if len(r.content) > 10000:
                                        with open(caminho_pdf, 'wb') as f:
                                            f.write(r.content)
                                        emit('sucesso', f'   ✅ PDF salvo! ({len(r.content)//1024} KB)')
                                        download_ok = True
                                    else:
                                        emit('erro', f'   ❌ Arquivo pequeno: {len(r.content)} bytes')
                            except Exception as e:
                                emit('info', f'   ⚠️ JS: {str(e)[:40]}')

                        # ESTRATEGIA 2: Clicar no botao #download
                        if viewer_frame and not download_ok:
                            try:
                                emit('info', '   🔘 Clicando #download...')
                                time.sleep(2)
                                with nova_aba.expect_download(timeout=30000) as dl:
                                    viewer_frame.locator('#download').click()
                                dl.value.save_as(caminho_pdf)
                                if os.path.getsize(caminho_pdf) > 5000:
                                    emit('sucesso', f'   ✅ Download! ({os.path.getsize(caminho_pdf)//1024} KB)')
                                    download_ok = True
                            except Exception as e:
                                emit('info', f'   ⚠️ #download: {str(e)[:60]}')

                        # ESTRATEGIA 3: Monitorar requisicoes de rede
                        if not download_ok:
                            try:
                                emit('info', '   📡 Monitorando rede...')
                                pdf_urls = []
                                def capturar(response):
                                    if '.pdf' in response.url.lower():
                                        pdf_urls.append(response.url)
                                nova_aba.on('response', capturar)
                                time.sleep(4)
                                if pdf_urls:
                                    import requests
                                    session = requests.Session()
                                    for c in context.cookies():
                                        session.cookies.set(c['name'], c['value'])
                                    r = session.get(pdf_urls[0], timeout=60)
                                    if len(r.content) > 10000:
                                        with open(caminho_pdf, 'wb') as f:
                                            f.write(r.content)
                                        emit('sucesso', f'   ✅ PDF ({len(r.content)//1024} KB)')
                                        download_ok = True
                            except Exception as e:
                                emit('info', f'   ⚠️ Rede: {str(e)[:40]}')

                        if not download_ok:
                            emit('erro', '   ❌ Download falhou')
                        
                        nova_aba.close()
                    except Exception as e:
                        emit('info', f'   ⚠️ Erro: {str(e)[:60]}')

                    try:
                        page.go_back()
                        time.sleep(2)
                    except:
                        pass

                except Exception as e:
                    emit('erro', f'   ❌ Erro: {str(e)[:80]}')
                    continue

            emit('progresso', '', concluidos=len(processos))
            emit('sucesso', f'\n📊 Finalizado! {len(processos)} processo(s).')
            browser.close()

    except Exception as e:
        emit('erro', f'❌ Erro: {str(e)[:150]}')
    finally:
        execution_active = False
        emit('fim', '')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/iniciar', methods=['POST'])
def iniciar():
    global execution_active
    data = request.get_json()
    if not data or not data.get('processos'):
        return jsonify({'erro': 'Lista vazia'}), 400
    if execution_active:
        return jsonify({'erro': 'Em andamento'}), 409
    while not event_queue.empty():
        try: event_queue.get_nowait()
        except: break
    threading.Thread(target=run_automation, args=(data['processos'],), daemon=True).start()
    return jsonify({'status': 'ok', 'processos': len(data['processos'])})

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
    return Response(event_stream(), mimetype='text/event-stream')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)