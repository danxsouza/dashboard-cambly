import streamlit as st
import pandas as pd
import json
from google.oauth2.service_account import Credentials
import gspread
import requests
import urllib.parse
from datetime import datetime
from bs4 import BeautifulSoup

# Configuração da página Web
st.set_page_config(page_title="Meu Dashboard de Inglês", layout="wide")
st.title("📊 Análise de Aulas - Cambly")

# --- LEMBRETE: COLOQUE APENAS A URL DO GOOGLE AQUI ---
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
            df['Professor'] = df['Arquivo de Origem'].str.extract(r'\d{2}-\d{2}-\d{4}-([^\.]+)\.pdf', expand=False)
            df['Professor'] = df['Professor'].str.title().fillna("Sem Nome")
            df = df.sort_values(by="Data Real", ascending=False)
            
        return df
    except Exception as e:
        st.error(f"Ocorreu um erro ao conectar à base de dados: {e}")
        return pd.DataFrame()

# ... [Mantenha aqui as funções buscar_novas_palavras_cambridge e chamar_gemini como estavam] ...

df = carregar_dados()
df_original = df.copy() 

# ... [Mantenha a lógica dos filtros laterais] ...

# --- ATUALIZAÇÃO NO TOP ERROS ---
        st.markdown("---")
        st.subheader("🔥 Top Erros Mais Recorrentes (Global)")
        st.write("Aqui estão os erros que mais se repetem em todo o seu histórico, comparando todos os professores.")
        
        top_n = st.selectbox("Quantidade de erros para exibir:", [5, 6, 7, 8, 9, 10])
        
        # AGORA USA O 'df_original' PARA COMPARAR TODOS OS PROFESSORES
        erros_frequentes = df_original['Explicação e Dica de Estudo'].value_counts().reset_index()
        erros_frequentes.columns = ['Explicação', 'Quantidade']
        top_erros = erros_frequentes.head(top_n)
        
        for index, row_top in top_erros.iterrows():
            qtd = row_top['Quantidade']
            exp = row_top['Explicação']
            
            # Busca todas as ocorrências na base original
            linhas_erro = df_original[df_original['Explicação e Dica de Estudo'] == exp]
            profs_envolvidos = ", ".join(linhas_erro['Professor'].unique())
            
            icone = "🔥" if qtd > 1 else "⚠️"
            vezes = "vezes" if qtd > 1 else "vez"
            
            titulo_top = f"[{profs_envolvidos}] {icone} {qtd} {vezes} - {exp[:60]}..."
            
            with st.expander(titulo_top):
                st.info(f"**Explicação Completa:** {exp}")
                st.write("**Onde você cometeu este erro (Histórico Geral):**")
                
                # Exibe exemplos do erro (limitado a 3 para não ficar gigante)
                for _, row_detalhe in linhas_erro.head(3).iterrows():
                    frase_errada = row_detalhe['Frase com Erro']
                    frase_correta = row_detalhe['Como Falar Corretamente']
                    professor = row_detalhe['Professor']
                    data = row_detalhe['Data da Aula']
                    
                    st.markdown(f"- ❌ **Você disse:** {frase_errada} 🏷️ **[Prof: {professor} em {data}]**")
                    st.markdown(f"  ✅ **O certo é:** {frase_correta}")
                    st.write("---")

# ... [Mantenha o Histórico Completo como estava] ...