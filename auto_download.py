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
        # Estratégia 1: Tentar baixar via link direto do PDF
        # Em muitos sistemas, o visualizador de PDF tem um link direto
        download_realizado = _tentar_download_direto(aba, pasta_destino, nome_arquivo)
        if download_realizado:
            # Renomear para o nome desejado se necessário
            return _verificar_download(pasta_destino, nome_arquivo)
        
        # Estratégia 2: esperar um download automático iniciado pela página
        print('[DOWNLOAD] Tentando aguardar download automático...')
        download_realizado = _aguardar_download_automatico(aba, pasta_destino, nome_arquivo)
        if download_realizado:
            return _verificar_download(pasta_destino, nome_arquivo)
        
        # Estratégia 3: Abrir o PDF e salvar como (Ctrl+S via keyboard)
        # Nota: em modo headless, Ctrl+S não funciona. Mas tenta mesmo assim.
        print('[DOWNLOAD] Tentando Ctrl+S via página (headless-friendly)...')
        _tentar_ctrl_s(aba, pasta_destino, nome_arquivo)
        return _verificar_download(pasta_destino, nome_arquivo)
        
    except Exception as e:
        print(f'[DOWNLOAD] Erro: {e}')
        return False, None


def _tentar_download_direto(aba, pasta_destino, nome_arquivo):
    """
    Tenta encontrar um link direto para o PDF na página e baixá-lo.
    Muitos visualizadores carregam o PDF via <embed>, <iframe>, ou <object>.
    """
    try:
        print('[DOWNLOAD] Procurando fonte do PDF na página...')
        
        # Tenta extrair a URL do PDF
        url_pdf = aba.evaluate("""() => {
            // Procura em embed
            var embed = document.querySelector('embed[type="application/pdf"]');
            if (embed && embed.src) return embed.src;
            
            // Procura em iframe
            var iframe = document.querySelector('iframe[src*=".pdf"]');
            if (iframe && iframe.src) return iframe.src;
            
            // Procura em object
            var obj = document.querySelector('object[type="application/pdf"]');
            if (obj && obj.data) return obj.data;
            
            // Procura links de download
            var links = document.querySelectorAll('a[href*=".pdf"], a[download]');
            for (var i = 0; i < links.length; i++) {
                if (links[i].href) return links[i].href;
            }
            
            return null;
        }""")
        
        if url_pdf:
            print(f'[DOWNLOAD] URL do PDF encontrada: {url_pdf[:100]}...')
            caminho = str(Path(pasta_destino) / nome_arquivo)
            
            # Usa o contexto de download do Playwright para baixar
            with aba.expect_download(timeout=30000) as download_info:
                # Navega diretamente para a URL do PDF para forçar download
                aba.goto(url_pdf, wait_until='domcontentloaded', timeout=15000)
            
            download = download_info.value
            download.save_as(caminho)
            print(f'[DOWNLOAD] ✅ PDF baixado via link direto!')
            return True
    except Exception as e:
        print(f'[DOWNLOAD] Falha ao tentar download direto: {e}')
    
    return False


def _aguardar_download_automatico(aba, pasta_destino, nome_arquivo):
    """
    Aguarda um download automático que possa ser iniciado pela página.
    """
    try:
        print('[DOWNLOAD] Aguardando possível download automático...')
        caminho = str(Path(pasta_destino) / nome_arquivo)
        
        # Configura listener de download antes de qualquer ação
        with aba.expect_download(timeout=20000) as download_info:
            # Tenta clicar em botão de download se existir
            botoes = aba.evaluate("""() => {
                var botoes = document.querySelectorAll('button, a');
                var encontrados = [];
                botoes.forEach(function(b) {
                    var texto = (b.innerText || b.title || '').toLowerCase();
                    if (texto.includes('download') || texto.includes('baixar') ||
                        texto.includes('salvar') || texto.includes('save') ||
                        texto.includes('pdf')) {
                        var rect = b.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {
                            encontrados.push(b.outerHTML.substring(0, 100));
                        }
                    }
                });
                return JSON.stringify(encontrados);
            }""")
            print(f'[DOWNLOAD] Botões de download encontrados: {botoes[:200]}')
            
            # Espera um pouco para ver se inicia automaticamente
            time.sleep(5)
        
        download = download_info.value
        download.save_as(caminho)
        print(f'[DOWNLOAD] ✅ Download automático capturado!')
        return True
    except Exception as e:
        print(f'[DOWNLOAD] Nenhum download automático detectado: {e}')
    
    return False


def _tentar_ctrl_s(aba, pasta_destino, nome_arquivo):
    """
    Tenta acionar o download via atalho do teclado.
    Em modo headless, isso pode não funcionar, mas não custa tentar.
    """
    try:
        # Tenta teclas de atalho via page.keyboard
        caminho = str(Path(pasta_destino) / nome_arquivo)
        
        # Tenta Ctrl+S (atalho de salvar)
        aba.keyboard.press('Control+s')
        time.sleep(2)
        
        # Se não funcionou, tenta baixar o HTML da página como fallback
        # (alguns visualizadores embutem o PDF no HTML)
        print('[DOWNLOAD] Tentando extrair conteúdo da página como HTML...')
        conteudo = aba.content()
        if conteudo:
            html_path = caminho.replace('.pdf', '.html')
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(conteudo)
            print(f'[DOWNLOAD] Página salva como HTML: {html_path}')
            return True
    except Exception as e:
        print(f'[DOWNLOAD] Ctrl+S falhou: {e}')
    
    return False


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


# Mantém compatibilidade com código antigo (wrapper)
def baixar_pdf_da_aba(pasta_destino, nome_arquivo, aba=None):
    """
    Wrapper para compatibilidade com código antigo.
    Se `aba` não for fornecida, retorna False (precisa da aba para funcionar).
    """
    if aba is None:
        print(f'[DOWNLOAD] ⚠️ Função antiga chamada sem fornecer a aba!')
        return False, None
    return baixar_pdf(aba, pasta_destino, nome_arquivo)


if __name__ == '__main__':
    # Teste
    print('Módulo de download via Playwright carregado.')
    print('Use: from auto_download import baixar_pdf')