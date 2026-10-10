import os
from pathlib import Path
import re

import streamlit as st
from dotenv import load_dotenv
import google.generativeai as genai

# Leitura opcional de PDF e DOCX
try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

try:
    from docx import Document
except ImportError:
    Document = None

# -------------------------------------------------------------------
# Configuração
# -------------------------------------------------------------------
PASTA_PROJETO = Path(__file__).resolve().parent
ARQUIVO_ENV = PASTA_PROJETO / ".env"
load_dotenv(dotenv_path=ARQUIVO_ENV, override=False)

st.set_page_config(
    page_title="OrientAção IA",
    page_icon="🧭",
    layout="wide",
)

MODOS = [
    "Orientação profissional",
    "Análise de competências",
    "Plano de carreira",
    "Currículo profissional",
    "Análise de vaga",
    "Simulação de entrevista",
    "Comportamento e Postura Profissional",
    "📊 Gerar Apresentação de Slides (Projeto)",
]

SYSTEM_PROMPT = """
Você é o OrientAção IA, um assistente de orientação profissional, desenvolvimento
de carreira, empregabilidade e mentoria comportamental no Brasil. 
Responda em português brasileiro, com tom acolhedor, profissional, prático e respeitoso.

REGRAS DE CONFIABILIDADE E MENTORIA:
- Use apenas os dados que a pessoa forneceu como fatos sobre ela.
- Diferencie claramente "informado pela pessoa", "possibilidade a confirmar".
- Se os dados forem insuficientes, faça até 3 perguntas objetivas. 
- MENTORIA COMPORTAMENTAL: Ao avaliar conflitos ou postura, utilize princípios de Inteligência Emocional.
- CORREÇÃO DE POSTURA: Identifique atitudes que sabotam o ambiente de trabalho. Explique o impacto negativo.
- Seja honesto e direto ao apontar erros comportamentais do usuário, mas de forma construtiva.
- Use Markdown simples e legível. Não gere HTML.
- Evite recomendações genéricas.
"""

def limpar_resposta(texto: str) -> str:
    texto = re.sub(r"(?i)<br\s*/?>", "\n", texto)
    texto = re.sub(r"<[^>]+>", "", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()

def extrair_curriculo(arquivo) -> tuple[str, str | None]:
    if arquivo is None:
        return "", None
    nome = arquivo.name.lower()
    try:
        if nome.endswith(".txt"):
            conteudo = arquivo.getvalue()
            for encoding in ("utf-8", "latin-1"):
                try:
                    return conteudo.decode(encoding).strip(), None
                except UnicodeDecodeError:
                    continue
            return "", "Não consegui ler o arquivo TXT."
        
        if nome.endswith(".pdf"):
            if PdfReader is None:
                return "", "Para ler PDF, instale: pip install pypdf"
            reader = PdfReader(arquivo)
            partes = []
            for pagina in reader.pages:
                texto_pagina = pagina.extract_text()
                if texto_pagina:
                    partes.append(texto_pagina)
            texto = "\n".join(partes).strip()
            if not texto:
                return "", "Não encontrei texto selecionável nesse PDF."
            return texto, None
        
        if nome.endswith(".docx"):
            if Document is None:
                return "", "Para ler DOCX, instale: pip install python-docx"
            documento = Document(arquivo)
            partes = []
            for p in documento.paragraphs:
                if p.text.strip():
                    partes.append(p.text)
            
            for tabela in documento.tables:
                for linha in tabela.rows:
                    celulas_texto = []
                    for celula in linha.cells:
                        celulas_texto.append(celula.text.strip())
                    separador = " | "
                    linha_formatada = separador.join(celulas_texto)
                    partes.append(linha_formatada)
                    
            texto_final = "\n".join(partes).strip()
            if not texto_final:
                return "", "O arquivo DOCX parece estar vazio."
            return texto_final, None
            
        return "", "Formato não reconhecido. Use PDF, DOCX ou TXT."
    except Exception as exc:
        return "", f"Erro ao ler arquivo: {type(exc).__name__}"

def parece_analise_de_curriculo(mensagem: str) -> bool:
    texto = mensagem.lower()
    termos = (
        "analise meu curriculo", "analisa meu curriculo", "analisar meu curriculo",
        "revisar meu curriculo", "revise meu curriculo", "corrigir meu curriculo",
        "avalie meu curriculo", "avaliar meu curriculo", "melhore meu curriculo"
    )
    normalizado = (
        texto.replace("á", "a").replace("à", "a").replace("ã", "a")
        .replace("â", "a").replace("é", "e").replace("ê", "e")
        .replace("í", "i").replace("ó", "o").replace("õ", "o")
    )
    return any(termo in normalizado for termo in termos)

# -------------------------------------------------------------------
# Interface
# -------------------------------------------------------------------
st.title("🧭 OrientAção IA")
st.caption("Orientação profissional, carreira, empregabilidade e postura com Inteligência Artificial.")

with st.sidebar:
    st.header("Seu perfil profissional")
    with st.form("form_perfil"):
        experiencia = st.text_area("Experiência", placeholder="Ex: manutenção, atendimento...", height=90)
        formacao = st.text_area("Formação", placeholder="Ex: cursos, certificações...", height=75)
        competencias = st.text_area("Competências", placeholder="Ex: elétrica, hidráulica, Excel...", height=75)
        objetivo = st.text_input("Objetivo", placeholder="Ex: promoção, recolocação")
        salario = st.text_input("Salário desejado (opcional)")
        disponibilidade = st.text_input("Disponibilidade (opcional)")
        salvar_perfil = st.form_submit_button("💾 Salvar perfil", use_container_width=True)

    if salvar_perfil:
        st.session_state.perfil = {
            "Experiência": experiencia.strip(),
            "Formação e cursos": formacao.strip(),
            "Competências informadas": competencias.strip(),
            "Objetivo profissional": objetivo.strip(),
            "Salário desejado": salario.strip(),
            "Disponibilidade": disponibilidade.strip(),
        }
        st.success("Perfil atualizado com sucesso!")

    st.divider()
    modo = st.selectbox("Ferramenta", MODOS, index=0)
    
    if st.button("🗑️ Limpar conversa", use_container_width=True):
        st.session_state.mensagens_gemini = []
        st.session_state.mensagens_exibicao = []
        st.rerun()

if "perfil" not in st.session_state:
    st.session_state.perfil = {}
if "mensagens_gemini" not in st.session_state:
    st.session_state.mensagens_gemini = []
if "mensagens_exibicao" not in st.session_state:
    st.session_state.mensagens_exibicao = []
if "curriculo_texto" not in st.session_state:
    st.session_state.curriculo_texto = ""

perfil = st.session_state.perfil
perfil_formatado = "\n".join(f"- {chave}: {valor if valor else 'Não informado'}" for chave, valor in perfil.items())

# Se o usuário escolheu o modo especial de Slides
if modo == "📊 Gerar Apresentação de Slides (Projeto)":
    st.subheader("📊 Gerador de Apresentação Executiva do Projeto")
    st.write("Esta ferramenta compila a arquitetura, o propósito e os diferenciais do **OrientAção IA** em uma apresentação de slides profissional em HTML para você entregar e apresentar para a sua professora.")
    
    if st.button("🚀 Gerar Apresentação do Projeto Agora", use_container_width=True):
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            st.error("⚠️ Chave `GEMINI_API_KEY` não encontrada no arquivo `.env`.")
        else:
            with st.spinner("Compilando dados do projeto e gerando os slides..."):
                try:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel('gemini-3.1-flash-lite')
                    
                    prompt_slides = """
                    Gere estritamente um documento HTML completo e válido, iniciando exatamente com <!DOCTYPE html> e terminando com </html>.
                    Não inclua nenhuma explicação fora do código.
                    O conteúdo deve ser um pitch deck executivo sobre o software "OrientAção IA" com os seguintes slides:
                    1. Capa: OrientAção IA - Plataforma de Carreira e Postura.
                    2. O Problema: Dificuldade de recolocação e falhas de soft skills.
                    3. A Solução: Mentoria por IA (Google Gemini) focada em inteligência emocional e planos de carreira.
                    4. Arquitetura: Python, Streamlit, API do Google Gemini, suporte a PDF/DOCX.
                    5. Diferenciais: Confiabilidade de dados e mentoria comportamental.
                    Use um design moderno com estilos CSS embutidos (fundo claro, cartões brancos e cores corporativas).
                    """
                    
                    response = model.generate_content(prompt_slides)
                    html_resultado = limpar_resposta(response.text)
                    
                    html_resultado = re.sub(r"^```html\s*", "", html_resultado, flags=re.IGNORECASE)
                    html_resultado = re.sub(r"^```\s*", "", html_resultado)
                    html_resultado = re.sub(r"\s*```$", "", html_resultado)
                    
                    st.success("✨ Apresentação do projeto gerada com sucesso!")
                    st.download_button(
                        label="📥 Baixar Apresentação em HTML (Abrir no Navegador para Apresentar)",
                        data=html_resultado,
                        file_name="apresentacao_orientacao_ia.html",
                        mime="text/html",
                        use_container_width=True
                    )
                    
                    with st.expander("Pré-visualizar código HTML"):
                        st.code(html_resultado, language="html")
                        
                except Exception as exc:
                    st.error(f"Erro ao gerar slides: {exc}")

else:
    curriculo_texto = ""
    if modo == "Currículo profissional":
        st.subheader("📄 Seu currículo")
        arquivo_curriculo = st.file_uploader("Anexar currículo (PDF, DOCX ou TXT)", type=["pdf", "docx", "txt"])
        if arquivo_curriculo is not None:
            texto_extraido, erro = extrair_curriculo(arquivo_curriculo)
            if erro:
                st.warning(erro)
            elif texto_extraido:
                st.session_state.curriculo_texto = texto_extraido
                st.success("Currículo carregado.")
        texto_colado = st.text_area("Ou cole o texto aqui", value=st.session_state.curriculo_texto, height=180)
        if texto_colado.strip():
            st.session_state.curriculo_texto = texto_colado.strip()
        curriculo_texto = st.session_state.curriculo_texto

    for msg in st.session_state.mensagens_exibicao:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    mensagem_usuario = st.chat_input("Escreva sua pergunta ou relate uma situação...")

    if mensagem_usuario:
        st.session_state.mensagens_exibicao.append({"role": "user", "content": mensagem_usuario})
        with st.chat_message("user"):
            st.markdown(mensagem_usuario)

        resposta_local = None

        if modo == "Currículo profissional" and parece_analise_de_curriculo(mensagem_usuario) and not curriculo_texto.strip():
            resposta_local = "Para eu analisar seu currículo, anexe o arquivo acima ou cole o texto na caixa."

        if resposta_local:
            st.session_state.mensagens_exibicao.append({"role": "assistant", "content": resposta_local})
            with st.chat_message("assistant"):
                st.markdown(resposta_local)
        else:
            api_key = os.getenv("GEMINI_API_KEY", "").strip()
            if not api_key:
                resposta = "⚠️ Chave `GEMINI_API_KEY` não encontrada no arquivo `.env`."
                st.session_state.mensagens_exibicao.append({"role": "assistant", "content": resposta})
                with st.chat_message("assistant"):
                    st.markdown(resposta)
            else:
                contexto = f"MODO: {modo}\n\nPERFIL DO USUÁRIO:\n{perfil_formatado}\n\nCURRÍCULO:\n{curriculo_texto}\n"
                
                instrucoes_modo = {
                    "Orientação profissional": "Ajude a pessoa a definir próximos passos com base nos dados.",
                    "Análise de competências": "Separe competências informadas das que precisam ser confirmadas.",
                    "Plano de carreira": "Crie um plano prático com etapas e prazos.",
                    "Currículo profissional": "Analise ou edite apenas com base no texto enviado.",
                    "Análise de vaga": "Se o texto da vaga não foi fornecido, peça para colar a descrição.",
                    "Simulação de entrevista": "Faça uma pergunta por vez e dê feedback.",
                    "Comportamento e Postura Profissional": "Avalie sob a ótica da inteligência emocional. Aponte atitudes ruins e ensine a agir de forma mais madura e construtiva no trabalho."
                }[modo]

                prompt_completo = f"{SYSTEM_PROMPT}\n\n{contexto}\n\nINSTRUÇÕES:\n{instrucoes_modo}\n\nPergunta/Situação do usuário: {mensagem_usuario}"

                with st.chat_message("assistant"):
                    with st.spinner("Preparando análise com Google Gemini..."):
                        try:
                            genai.configure(api_key=api_key)
                            model = genai.GenerativeModel('gemini-3.1-flash-lite') 
                            
                            if not st.session_state.mensagens_gemini:
                                chat = model.start_chat(history=[])
                            else:
                                chat = model.start_chat(history=st.session_state.mensagens_gemini)

                            response = chat.send_message(prompt_completo)
                            resposta = limpar_resposta(response.text)
                            
                            st.session_state.mensagens_gemini = chat.history

                        except Exception as exc:
                            resposta = f"❌ **Erro:** `{type(exc).__name__}: {str(exc)}`"
                    
                    st.markdown(resposta)
                st.session_state.mensagens_exibicao.append({"role": "assistant", "content": resposta})
