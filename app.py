import streamlit as st
import pandas as pd
import json
from google.oauth2.service_account import Credentials
import gspread

# Configuração da página Web
st.set_page_config(page_title="O Meu Dashboard de Inglês", layout="wide")
st.title("📊 Análise de Aulas - Cambly")

# Função para ligar de forma segura ao Google Drive
@st.cache_data(ttl=600)
def carregar_dados():
    try:
        # A chave de acesso será lida a partir dos segredos do site
        key_dict = json.loads(st.secrets["gcp_service_account"])
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(key_dict, scopes=scopes)
        client = gspread.authorize(creds)
        
        # ID da folha de cálculo criada anteriormente
        sheet = client.open_by_key("11Cg3acTMwOIZ82L2hn6i5RnV4akuSoAp1u3M-HTxMi0").sheet1
        data = sheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Ocorreu um erro ao ligar à base de dados: {e}")
        return pd.DataFrame()

df = carregar_dados()

if df.empty:
    st.warning("Ainda não há dados processados para apresentar. Lê os teus PDFs primeiro!")
else:
    # Menu lateral com filtros
    st.sidebar.header("Filtros de Aula")
    
    datas = df["Data da Aula"].unique()
    data_selecionada = st.sidebar.selectbox("Escolher a data da aula", ["Todas as Aulas"] + list(datas))
    
    if data_selecionada != "Todas as Aulas":
        df = df[df["Data da Aula"] == data_selecionada]
        
    st.write("Acompanha a tua evolução e deteta os padrões dos teus erros mais frequentes.")
    
    # Cartões de Resumo no topo
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total de Erros (Filtro Atual)", len(df))
    with col2:
        if not df.empty:
            erro_comum = df["Tipo de Erro"].mode()[0]
            st.metric("Categoria Mais Frequente", erro_comum)

    # Gráfico de barras simples
    st.subheader("Distribuição de Erros")
    contagem_erros = df['Tipo de Erro'].value_counts()
    st.bar_chart(contagem_erros)

    # Tabela elegante de correções
    st.subheader("Detalhe das Frases a Corrigir")
    for index, row in df.iterrows():
        # Cria uma secção que se expande ao clicar
        with st.expander(f"⚠️ {row['Frase com Erro']}"):
            st.success(f"**Como falar corretamente:** {row['Como Falar Corretamente']}")
            st.info(f"**Dica de Estudo:** {row['Explicação e Dica de Estudo']}")
            st.caption(f"Categoria: {row['Tipo de Erro']} | Data: {row['Data da Aula']} | Origem: {row['Arquivo de Origem']}")
