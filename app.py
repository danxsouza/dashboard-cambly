import streamlit as st
import pandas as pd
import json
from google.oauth2.service_account import Credentials
import gspread
import requests
import urllib.parse
from datetime import datetime
from bs4 import BeautifulSoup

# Configuração da página
st.set_page_config(page_title="Dashboard de Inglês", layout="wide")
st.title("📊 Análise de Aulas - Cambly")

# --- CONFIGURAÇÃO ---
URL_APPS_SCRIPT = "https://script.google.com/macros/s/AKfycbyPYXxhH0FlZpk6i55x9c7_FtAVV-PxdQ2c2HWHpZPrPbaglS7G6eqaCkpCzT3wyumO/exec" 

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
            df['Data Real'] = pd.to_datetime(df['Data da Aula'], format='%d-%m-%Y', errors='coerce').dt.date
            df['Professor'] = df['Arquivo de Origem'].str.extract(r'\d{2}-\d{2}-\d{4}-([^\.]+)\.pdf', expand=False).str.title().fillna("Sem Nome")
            df = df.sort_values(by="Data Real", ascending=False)
        return df
    except Exception:
        return pd.DataFrame()

def chamar_gemini(frase, dica):
    try:
        chave_api = st.secrets["GEMINI_API_KEY"]
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={chave_api}"
        prompt = f"Frase correta: '{frase}'. Dica: '{dica}'. Gere 3 exemplos práticos (PT/EN). Responda apenas em lista."
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        r = requests.post(url, json=payload)
        return r.json()['candidates'][0]['content']['parts'][0]['text']
    except:
        return "Erro ao conectar com IA."

# --- CARREGAMENTO INICIAL E CRIAÇÃO DA BASE GLOBAL ---
df_original = carregar_dados() 
df = df_original.copy() # Criamos a cópia de trabalho aqui

if df.empty:
    st.warning("Sem dados processados. Suba seus PDFs!")
else:
    # FILTROS
    modo = st.sidebar.radio("Período:", ["Todas as Aulas", "Escolher Data no Calendário"])
    if modo == "Escolher Data no Calendário":
        periodo = st.sidebar.date_input("Intervalo:", value=(df['Data Real'].min(), df['Data Real'].max()))
        if len(periodo) == 2:
            df = df[(df['Data Real'] >= periodo[0]) & (df['Data Real'] <= periodo[1])]
    
    prof_sel = st.sidebar.selectbox("👨‍🏫 Professor", ["Todos"] + df_original['Professor'].unique().tolist())
    if prof_sel != "Todos":
        df = df[df['Professor'] == prof_sel]

    # TOP ERROS (GLOBAL)
    st.subheader("🔥 Top Erros Mais Recorrentes (Base Global)")
    top_n = st.selectbox("Quantidade de erros para exibir:", [5, 6, 7, 8, 9, 10])
    
    # Agora df_original existe e é usado aqui
    frequencia = df_original['Explicação e Dica de Estudo'].value_counts().head(top_n)
    
    for exp, qtd in frequencia.items():
        linhas = df_original[df_original['Explicação e Dica de Estudo'] == exp]
        with st.expander(f"{qtd} vezes - {exp[:60]}..."):
            st.info(exp)
            for _, r in linhas.head(2).iterrows():
                st.write(f"- ❌ {r['Frase com Erro']} [Prof: {r['Professor']} em {r['Data da Aula']}]")

    # HISTÓRICO PAGINADO
    st.markdown("---")
    st.subheader("📚 Histórico de Correções")
    
    ITENS = 20
    total = len(df)
    paginas = max(1, (total - 1) // ITENS + 1)
    
    if 'page' not in st.session_state: st.session_state.page = 1
    
    df_paginado = df.iloc[(st.session_state.page-1)*ITENS : st.session_state.page*ITENS]
    
    for (prof, data), grupo in df_paginado.groupby(['Professor', 'Data da Aula'], sort=False):
        st.markdown(f"### 👨‍🏫 Aula com {prof} 📅 {data}")
        for i, row in grupo.iterrows():
            with st.expander(f"📖 {row['Frase com Erro']} 🏷️ [{row['Professor']}]"):
                st.success(row['Como Falar Corretamente'])
                st.info(row['Explicação e Dica de Estudo'])
                if st.button("💡 Gerar 3 exemplos", key=f"ex_{i}"):
                    st.write(chamar_gemini(row['Como Falar Corretamente'], row['Explicação e Dica de Estudo']))

    # BOTÕES DE PAGINAÇÃO
    cols = st.columns([1, 2, 1])
    if st.session_state.page > 1 and cols[0].button("⏪ Anterior"):
        st.session_state.page -= 1
        st.rerun()
    cols[1].markdown(f"**Pág {st.session_state.page} de {paginas}**")
    if st.session_state.page < paginas and cols[2].button("Próxima ⏩"):
        st.session_state.page += 1
        st.rerun()
