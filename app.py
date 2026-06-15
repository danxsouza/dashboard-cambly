import streamlit as st
import pandas as pd
import json
from google.oauth2.service_account import Credentials
import gspread
import requests
import urllib.parse # NOVA FERRAMENTA PARA GERAR LINKS

# Configuração da página Web
st.set_page_config(page_title="Meu Dashboard de Inglês", layout="wide")
st.title("📊 Análise de Aulas - Cambly")

# --- LEMBRETE: COLOQUE A SUA URL AQUI NOVAMENTE ---
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
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Ocorreu um erro ao conectar à base de dados: {e}")
        return pd.DataFrame()

df = carregar_dados()

st.sidebar.header("⚙️ Ações")
if st.sidebar.button("🚀 Processar Novos PDFs"):
    with st.spinner("Lendo PDFs e acionando a Inteligência Artificial... Aguarde."):
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

st.sidebar.markdown("---")
st.sidebar.header("Filtros de Aula")

if df.empty:
    st.warning("Ainda não há dados processados para apresentar. Coloque os PDFs no Drive e clique em Processar!")
else:
    datas = df["Data da Aula"].unique()
    data_selecionada = st.sidebar.selectbox("Escolher a data da aula", ["Todas as Aulas"] + list(datas))
    
    if data_selecionada != "Todas as Aulas":
        df = df[df["Data da Aula"] == data_selecionada]
        
    st.write("Acompanhe sua evolução e foque no que mais precisa de atenção.")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total de Erros (Filtro Atual)", len(df))
    with col2:
        if not df.empty:
            erro_comum = df["Tipo de Erro"].mode()[0]
            st.metric("Categoria Mais Frequente", erro_comum)

    st.subheader("Distribuição de Erros")
    contagem_erros = df['Tipo de Erro'].value_counts()
    st.bar_chart(contagem_erros)

    # --- TOP ERROS RECORRENTES ---
    st.markdown("---")
    st.subheader("🔥 Top Erros Mais Recorrentes")
    st.write("Identifique os padrões que mais se repetem. Use o controle abaixo para expandir o ranking de 5 até 10 erros.")
    
    top_n = st.slider("Mostrar top:", min_value=5, max_value=10, value=5)
    
    erros_frequentes = df['Explicação e Dica de Estudo'].value_counts().reset_index()
    erros_frequentes.columns = ['Explicação', 'Quantidade']
    top_erros = erros_frequentes.head(top_n)
    
    for index, row_top in top_erros.iterrows():
        qtd = row_top['Quantidade']
        exp = row_top['Explicação']
        
        # Filtra todas as linhas originais que tem essa explicação
        linhas_erro = df[df['Explicação e Dica de Estudo'] == exp]
        
        icone = "🔥" if qtd > 1 else "⚠️"
        vezes = "vezes" if qtd > 1 else "vez"
        
        with st.expander(f"{icone} {qtd} {vezes} - {exp[:70]}..."):
            st.info(f"**Explicação Completa:** {exp}")
            st.write("**Exemplos onde você cometeu este erro:**")
            
            for _, row_detalhe in linhas_erro.iterrows():
                frase_errada = row_detalhe['Frase com Erro']
                frase_correta = row_detalhe['Como Falar Corretamente']
                
                # Gera os links de busca
                texto_url = urllib.parse.quote(frase_correta)
                link_playphrase = f"https://www.playphrase.me/#/search?q={texto_url}"
                link_youglish = f"https://pt.youglish.com/pronounce/{texto_url}/english"
                
                st.markdown(f"- ❌ **Você disse:** {frase_errada}")
                st.markdown(f"  ✅ **O certo é:** {frase_correta}")
                st.markdown(f"  🎧 **Ouça nativos:** [🎬 PlayPhrase.me]({link_playphrase}) | [🗣️ YouGlish]({link_youglish})")
                st.write("---")

    # --- HISTÓRICO COMPLETO ---
    st.markdown("---")
    st.subheader("📚 Histórico Completo de Correções")
    for index, row in df.iterrows():
        with st.expander(f"📖 {row['Frase com Erro']}"):
            frase_correta = row['Como Falar Corretamente']
            
            # Gera os links de busca
            texto_url = urllib.parse.quote(frase_correta)
            link_playphrase = f"https://www.playphrase.me/#/search?q={texto_url}"
            link_youglish = f"https://pt.youglish.com/pronounce/{texto_url}/english"
            
            st.success(f"**Como falar corretamente:** {frase_correta}")
            st.info(f"**Dica de Estudo:** {row['Explicação e Dica de Estudo']}")
            st.markdown(f"**Ouça nativos falando a versão correta:** [🎬 PlayPhrase.me]({link_playphrase}) | [🗣️ YouGlish]({link_youglish})")
            st.caption(f"Categoria: {row['Tipo de Erro']} | Data: {row['Data da Aula']} | Origem: {row['Arquivo de Origem']}")
