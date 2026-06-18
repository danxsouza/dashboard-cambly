import streamlit as st
import pandas as pd
import json
from google.oauth2.service_account import Credentials
import gspread
import requests
import urllib.parse
from datetime import datetime
import re

# Configuração da página Web
st.set_page_config(page_title="Meu Dashboard de Inglês", layout="wide")
st.title("📊 Análise de Aulas - Cambly")

# --- LEMBRETE: COLOQUE APENAS A URL DO GOOGLE AQUI ---
URL_APPS_SCRIPT = "https://script.google.com/macros/s/AKfycbyPYXxhH0FlZpk6i55x9c7_FtAVV-PxdQ2c2HWHpZPrPbaglS7G6eqaCkpCzT3wyumO/exec" 

# --- INICIALIZAÇÃO DE MEMÓRIA PARA PERMITIR RESET DOS FILTROS ---
if "opcao_foco" not in st.session_state:
    st.session_state["opcao_foco"] = "Desativado (Ver Tudo)"
if "modo_visualizacao" not in st.session_state:
    st.session_state["modo_visualizacao"] = "Todas as Aulas"
if "professor_selecionado" not in st.session_state:
    st.session_state["professor_selecionado"] = "Todos"

@st.cache_data(ttl=60)
def carregar_dados():
    try:
        key_dict = json.loads(st.secrets["gcp_service_account"])
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(key_dict, scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open_by_key("11Cg3acTMwOIZ82L2hn6i5RnV4akuSoAp1u3M-HTxMi0").sheet1
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        if not df.empty:
            df.columns = df.columns.str.strip() 
            df['Data Real'] = pd.to_datetime(df['Data da Aula'], format='%d-%m-%Y', errors='coerce').dt.date
            
            def limpar_nome_professor(arq):
                if pd.isna(arq): return "Sem Nome"
                nome = str(arq).strip()
                nome = re.sub(r'(?i)\.(pdf|txt)$', '', nome).strip() 
                nome = re.sub(r'\s*\(\d+\)$', '', nome).strip()  
                partes = re.split(r'[-_\s]+', nome)
                if partes:
                    p = partes[-1].strip().title()
                    if p.isalpha():
                        return p
                return "Sem Nome"
                
            df['Professor'] = df['Arquivo de Origem'].apply(limpar_nome_professor)
            df = df.sort_values(by="Data Real", ascending=False)
            
        return df
    except Exception as e:
        st.error(f"Ocorreu um erro ao conectar à base de dados: {e}")
        return pd.DataFrame()

def chamar_gemini(frase, dica):
    chave_api = st.secrets["GEMINI_API_KEY"]
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key=" + chave_api
    prompt = f"A frase correta em inglês é: '{frase}'. A dica de estudo foi: '{dica}'. Gere 3 exemplos curtos e práticos em inglês (com a tradução em português) usando essa mesma estrutura ou vocabulário. Responda APENAS com os 3 exemplos em formato de lista."
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        r = requests.post(url, json=payload)
        return r.json()['candidates'][0]['content']['parts'][0]['text']
    except:
        return "Não foi possível gerar os exemplos no momento."

df_original = carregar_dados()
df = df_original.copy() 

# --- SEÇÃO DE AÇÕES DO MENU LATERAL ---
st.sidebar.header("⚙️ Ações")
if st.sidebar.button("🚀 Processar Novos TXTs"):
    with st.spinner("Lendo arquivos TXT e acionando a Inteligência Artificial... Aguarde."):
        try:
            resposta = requests.get(URL_APPS_SCRIPT)
            if "Sucesso" in resposta.text:
                st.sidebar.success("Concluído! Atualizando o dashboard...")
                st.cache_data.clear() 
                st.rerun() 
            else:
                st.sidebar.error("Erro. O Apps Script retornou uma falha.")
        except Exception as e:
            st.sidebar.error(f"Falha ao conectar com o Google: {e}")

if st.sidebar.button("🧹 Limpar Todos os Filtros"):
    st.session_state["opcao_foco"] = "Desativado (Ver Tudo)"
    st.session_state["modo_visualizacao"] = "Todas as Aulas"
    st.session_state["professor_selecionado"] = "Todos"
    if "data_key" in st.session_state:
        del st.session_state["data_key"]  
    st.rerun()

st.sidebar.markdown("---")

st.sidebar.header("🎯 Modo de Foco Intensivo")
opcao_foco = st.sidebar.radio(
    "Escolha um objetivo de estudo:",
    ["Desativado (Ver Tudo)", "⏳ Erros no Passado", "🗺️ Erros de Preposição"],
    key="opcao_foco"
)

st.sidebar.markdown("---")
st.sidebar.header("📅 Filtros de Aula")

if df_original.empty:
    st.sidebar.warning("Nenhuma aula encontrada na base de dados.")
else:
    modo_visualizacao = st.sidebar.radio(
        "Período de Estudo:", 
        ["Todas as Aulas", "Escolher Data no Calendário"],
        key="modo_visualizacao"
    )
    
    data_inicio = df_original['Data Real'].min()
    data_fim = df_original['Data Real'].max()
    
    if modo_visualizacao == "Escolher Data no Calendário" and not df.empty:
        data_padrao = df_original['Data Real'].max()
        data_selecionada = st.sidebar.date_input(
            "Selecione o período:", 
            value=(data_padrao, data_padrao),
            key="data_key"
        )
        
        if isinstance(data_selecionada, tuple):
            if len(data_selecionada) == 2:
                data_inicio, data_fim = data_selecionada
            elif len(data_selecionada) == 1:
                data_inicio = data_fim = data_selecionada[0]
        else:
            data_inicio = data_fim = data_selecionada

    professores_disponiveis = [p for p in df_original['Professor'].unique().tolist() if p and p != "Sem Nome"]
    professores_disponiveis.sort() 
    professor_selecionado = st.sidebar.selectbox(
        "👨‍🏫 Filtrar por Professor", 
        ["Todos"] + professores_disponiveis,
        key="professor_selecionado"
    )

    # DataFrame Isolado para o Talk Time (Mantém as linhas N/A para não perder os minutos de fala)
    df_conversacao = df_original.copy()
    if modo_visualizacao == "Escolher Data no Calendário":
        df_conversacao = df_conversacao[(df_conversacao["Data Real"] >= data_inicio) & (df_conversacao["Data Real"] <= data_fim)]
    if professor_selecionado != "Todos":
        df_conversacao = df_conversacao[df_conversacao["Professor"] == professor_selecionado]

    # Aplicação dos filtros no DataFrame de Erros Principal
    if modo_visualizacao == "Escolher Data no Calendário":
        df = df[(df["Data Real"] >= data_inicio) & (df["Data Real"] <= data_fim)]
        
    if opcao_foco == "⏳ Erros no Passado":
        filtro_termo = r'passado|past|was|were|did|\bed\b|irregular'
        df = df[df['Explicação e Dica de Estudo'].str.contains(filtro_termo, case=False, na=False)]
    elif opcao_foco == "🗺️ Erros de Preposição":
        filtro_termo = r'preposição|preposition|\bin\b|\bon\b|\bat\b|\bto\b|\bfrom\b|\bfor\b|\bwith\b|regência'
        df = df[df['Explicação e Dica de Estudo'].str.contains(filtro_termo, case=False, na=False)]

    if professor_selecionado != "Todos":
        df = df[df["Professor"] == professor_selecionado]

st.write("Acompanhe sua evolução, identifique padrões e escute como os nativos falam.")

if df.empty and df_conversacao.empty:
    st.info("Nenhum registro encontrado para os filtros selecionados.")
else:
    # --- NOVO: FILTRO VISUAL INTELIGENTE ---
    # Remove as linhas fantasmas ("N/A") das listas de erros e chat
    df_visual = df[df['Frase com Erro'].astype(str).str.strip() != 'N/A']

    # Separação dos dados limpos: Áudio vs Chat
    df_chat = df_visual[df_visual['Tipo de Erro'].astype(str).str.contains('💬', na=False) | df_visual['Tipo de Erro'].astype(str).str.contains('Chat', case=False, na=False)]
    df_erros_audio = df_visual[~(df_visual['Tipo de Erro'].astype(str).str.contains('💬', na=False) | df_visual['Tipo de Erro'].astype(str).str.contains('Chat', case=False, na=False))]

    col1, col2 = st.columns(2)
    with col1:
        # Conta apenas os itens reais de estudo
        st.metric("Total de Itens Estudados", len(df_visual))
    with col2:
        professores_vistos = ", ".join([p for p in df["Professor"].unique() if p != "Sem Nome"]) if not df.empty else professor_selecionado
        st.metric("Professor(es)", professores_vistos if professores_vistos != "Todos" else "Nenhum no foco")

    # --- ESTATÍSTICAS DE CONVERSAÇÃO (TALK TIME) ---
    st.markdown("---")
    st.subheader("🎙️ Estatísticas de Conversação Estimadas (Talk Time)")
    
    # O gráfico continua lendo o df_conversacao para garantir que aulas perfeitas somem no tempo
    if 'Palavras Aluno' in df_conversacao.columns and 'Palavras Professor' in df_conversacao.columns
