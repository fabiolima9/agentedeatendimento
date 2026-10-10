import os
from dotenv import load_dotenv
from groq import Groq
import streamlit as st

# Carrega as variáveis do arquivo .env
load_dotenv()

# Configuração da página do Streamlit
st.set_page_config(page_title="Agente de Atendimento", page_icon="🤖")

st.title("🤖 Agente de Atendimento")
st.write("Digite sua dúvida abaixo para conversar com o assistente.")

# Inicializa o cliente do Groq puxando a chave automaticamente do ambiente (.env)
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Caixa de texto na tela do navegador
pergunta = st.text_input("Digite sua pergunta:")

# Botão para enviar
if st.button("Enviar"):
    if pergunta:
        with st.spinner("Pensando..."):
            try:
                # Chamada para a API do Groq usando o modelo GPT-OSS 120B
                chat_completion = client.chat.completions.create(
                    messages=[
                        {"role": "user", "content": pergunta}
                    ],
                    model="openai/gpt-oss-120b",
                )
                
                # Exibe a resposta na tela
                resposta = chat_completion.choices[0].message.content
                st.success("Resposta:")
                st.write(resposta)
                
            except Exception as e:
                st.error(f"Ocorreu um erro: {e}")
    else:
        st.warning("Por favor, digite uma pergunta antes de enviar.")