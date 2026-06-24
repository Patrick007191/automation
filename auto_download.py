"""
Módulo para baixar PDF usando o Playwright (download nativo).
Funciona em cloud/headless - sem dependência de GUI.
"""
import os
import time
import re
from pathlib import Path


def baixar_pdf(aba, pasta_destino, nome_arquivo):
    """
    Baixa o PDF da aba atual usando o sistema de download nativo do Playwright.
    
    Args:
        aba: Página do Playwright (a aba do visualizador)
        pasta_destino: Pasta onde salvar o PDF
        nome_arquivo: Nome desejado para o arquivo
    
    Returns:
        (sucesso: bool, caminho_arquivo: str ou None)
    """
    Path(pasta_destino).mkdir(parents=True, exist_ok=True)
    caminho_completo = str(Path(pasta_destino) / nome_arquivo)
    
    print(f'[DOWNLOAD] Iniciando download para: {caminho_completo}')
    
    try:
        # ESTRATÉGIA 1: Print do título e URL pra debug
        try:
            print(f'[DOWNLOAD] URL atual: {aba.url[:100]}')
            print(f'[DOWNLOAD] Título: {aba.title()[:100]}')
        except:
            pass
        
        # ESTRATÉGIA 2: Capturar download com expect_download
        print('[DOWNLOAD] Tentando capturar download automático...')
        resultado = _capturar_download_automatico(aba, pasta_destino, nome_arquivo)
        if resultado[0]:
            return resultado
        
        # ESTRATÉGIA 3: Tirar screenshot e salvar HTML como fallback
        print('[DOWNLOAD] Salvando página como HTML (fallback)...')
        html_path = caminho_completo.replace('.pdf', '.html')
        try:
            conteudo = aba.content()
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(conteudo)
            print(f'[DOWNLOAD] ✅ Página salva como HTML: {html_path}')
            return True, html_path
        except Exception as e:
            print(f'[DOWNLOAD] Erro ao salvar HTML: {e}')
        
        return False, None
        
    except Exception as e:
        print(f'[DOWNLOAD] Erro geral: {e}')
        return False, None


def _capturar_download_automatico(aba, pasta_destino, nome_arquivo):
    """
    Tenta capturar download que ocorre automaticamente ao carregar página
    ou ao clicar em botões de download.
    """
    caminho = str(Path(pasta_destino) / nome_arquivo)
    
    # 1. Tenta com expect_download esperando 10 segundos
    try:
        with aba.expect_download(timeout=10000) as download_info:
            # Tenta clicar em links/botões de download
            clicou = aba.evaluate("""() => {
                const elementos = document.querySelectorAll('a, button, input, img, span');
                let clicou = false;
                for (const el of elementos) {
                    const texto = (el.innerText || el.title || el.alt || el.className || '').toLowerCase();
                    if (texto.includes('download') || texto.includes('baixar') || 
                        texto.includes('salvar') || texto.includes('save') ||
                        texto.includes('pdf') || texto.includes('>>') ||
                        texto.includes('▼') || texto.includes('↓')) {
                        if (el.offsetParent !== null) {
                            el.click();
                            clicou = true;
                            break;
                        }
                    }
                }
                return clicou;
            }""")
            if not clicou:
                # Tenta Ctrl+S
                aba.keyboard.press('Control+s')
            time.sleep(3)
        
        download = download_info.value
        download.save_as(caminho)
        print(f'[DOWNLOAD] ✅ Download capturado com expect_download!')
        return True, caminho
    except Exception as e:
        print(f'[DOWNLOAD] expect_download não capturou nada: {str(e)[:80]}')
    
    # 2. Tenta navegar para URL do PDF diretamente
    try:
        url_pdf = aba.evaluate("""() => {
            // Procura src/url do PDF em embed, iframe, object
            const embed = document.querySelector('embed[type="application/pdf"]');
            if (embed && embed.src) return embed.src;
            const iframe = document.querySelector('iframe');
            if (iframe && iframe.src && iframe.src.includes('.pdf')) return iframe.src;
            const obj = document.querySelector('object[type="application/pdf"]');
            if (obj && obj.data) return obj.data;
            // Procura qualquer link que leva a PDF
            const links = document.querySelectorAll('a[href*=".pdf"], a[download]');
            for (const a of links) {
                if (a.href) return a.href;
            }
            return null;
        }""")
        
        if url_pdf:
            print(f'[DOWNLOAD] URL do PDF encontrada: {url_pdf[:80]}...')
            # Tenta baixar via navegação direta
            with aba.expect_download(timeout=30000) as download_info:
                aba.goto(url_pdf, wait_until='domcontentloaded', timeout=20000)
            download = download_info.value
            # Salva com o nome correto
            donwload_path = str(Path(pasta_destino) / nome_arquivo)
            download.save_as(donwload_path)
            print(f'[DOWNLOAD] ✅ PDF baixado via URL direta!')
            return True, donwload_path
    except Exception as e:
        print(f'[DOWNLOAD] URL direta falhou: {str(e)[:80]}')
    
    # 3. Tenta clicar em ">>" ou botão de expandir
    try:
        for _ in range(3):
            clicou = aba.evaluate("""() => {
                const elementos = document.querySelectorAll('button, a, span, img');
                for (const el of elementos) {
                    const texto = (el.innerText || el.title || el.alt || '').trim();
                    const cls = (el.className || '').toLowerCase();
                    if (texto === '>>' || texto === '»' || cls.includes('expan') || 
                        cls.includes('download') || cls.includes('baixar')) {
                        if (el.offsetParent !== null) {
                            el.click();
                            return true;
                        }
                    }
                }
                return false;
            }""")
            if clicou:
                print(f'[DOWNLOAD] Clicou em elemento de expansão/download')
                time.sleep(2)
            else:
                break
        
        # Após clicar, verifica se apareceu botão de download
        with aba.expect_download(timeout=8000) as download_info:
            aba.evaluate("""() => {
                const links = document.querySelectorAll('a');
                for (const a of links) {
                    if (a.href && (a.href.includes('.pdf') || a.hasAttribute('download'))) {
                        a.click();
                        return;
                    }
                }
            }""")
            time.sleep(2)
        
        download = download_info.value
        download.save_as(caminho)
        print(f'[DOWNLOAD] ✅ Download capturado após cliques!')
        return True, caminho
    except Exception as e:
        print(f'[DOWNLOAD] Cliques não geraram download: {str(e)[:80]}')
    
    return False, None


def _verificar_download(pasta_destino, nome_arquivo):
    """
    Verifica se o arquivo foi realmente baixado na pasta de destino.
    """
    caminho_esperado = str(Path(pasta_destino) / nome_arquivo)
    
    # Aguarda até 30s para o arquivo aparecer
    tempo_inicio = time.time()
    while time.time() - tempo_inicio < 30:
        if os.path.exists(caminho_esperado):
            tamanho = os.path.getsize(caminho_esperado)
            if tamanho > 1024:  # Mínimo 1KB
                print(f'[DOWNLOAD] ✅ Sucesso! Arquivo: {nome_arquivo} ({tamanho/1024:.1f} KB)')
                return True, caminho_esperado
            else:
                print(f'[DOWNLOAD] ⚠️ Arquivo muito pequeno: {tamanho} bytes')
        
        # Verifica se há PDFs na pasta
        pdfs = list(Path(pasta_destino).glob('*.pdf'))
        if pdfs:
            pdf_recente = max(pdfs, key=os.path.getmtime)
            tempo_arquivo = time.time() - os.path.getmtime(str(pdf_recente))
            if tempo_arquivo < 15 and pdf_recente.stat().st_size > 1024:
                # Renomeia para o nome desejado se for diferente
                if str(pdf_recente) != caminho_esperado:
                    os.rename(str(pdf_recente), caminho_esperado)
                tamanho = os.path.getsize(caminho_esperado)
                print(f'[DOWNLOAD] ✅ PDF existente: {pdf_recente.name} → renomeado para {nome_arquivo} ({tamanho/1024:.1f} KB)')
                return True, caminho_esperado
        
        time.sleep(1)
    
    print(f'[DOWNLOAD] ❌ Arquivo não encontrado após 30s: {nome_arquivo}')
    return False, None


# Mantém compatibilidade com código antigo
def baixar_pdf_da_aba(pasta_destino, nome_arquivo, aba=None):
    """Wrapper para compatibilidade."""
    if aba is None:
        print(f'[DOWNLOAD] ⚠️ Função antiga chamada sem fornecer a aba!')
        return False, None
    return baixar_pdf(aba, pasta_destino, nome_arquivo)


if __name__ == '__main__':
    print('Módulo de download via Playwright carregado.')
    print('Use: from auto_download import baixar_pdf')