import streamlit as st
import pandas as pd
import json
from google.oauth2.service_account import Credentials
import gspread
import requests
import urllib.parse
from datetime import datetime

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

df = carregar_dados()
df_original = df.copy() 

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
st.sidebar.header("📅 Filtros de Aula")

if df.empty:
    st.warning("Ainda não há dados processados para apresentar. Coloque os PDFs no Drive e clique em Processar!")
else:
    modo_visualizacao = st.sidebar.radio("Período de Estudo:", ["Todas as Aulas", "Escolher Data no Calendário"])
    
    if modo_visualizacao == "Escolher Data no Calendário":
        data_padrao = df['Data Real'].max()
        
        # --- ATUALIZAÇÃO: CALENDÁRIO COM INTERVALO DE DATAS (RANGE) ---
        data_selecionada = st.sidebar.date_input(
            "Selecione o período (clique no início e depois no fim):", 
            value=(data_padrao, data_padrao) # Valor padrão é o dia mais recente
        )
        
        # O Streamlit retorna uma tupla com 1 ou 2 valores dependendo de como o usuário clica
        if isinstance(data_selecionada, tuple):
            if len(data_selecionada) == 2:
                data_inicio, data_fim = data_selecionada
            elif len(data_selecionada) == 1:
                data_inicio = data_fim = data_selecionada[0]
            else:
                data_inicio = data_fim = data_padrao
        else:
            data_inicio = data_fim = data_selecionada
        
        st.sidebar.caption(f"💡 **Aulas registradas entre {data_inicio.strftime('%d/%m/%Y')} e {data_fim.strftime('%d/%m/%Y')}:**")
        
        dias_com_aula = df_original['Data Real'].unique()
        dias_no_periodo = sorted([d for d in dias_com_aula if data_inicio <= d <= data_fim], reverse=True)
        
        if dias_no_periodo:
            for d in dias_no_periodo:
                st.sidebar.caption(f"📌 {d.strftime('%d/%m/%Y')}")
        else:
            st.sidebar.caption("Nenhuma aula encontrada neste período.")

        # Filtra o dataframe usando o intervalo de datas
        df = df[(df["Data Real"] >= data_inicio) & (df["Data Real"] <= data_fim)]
    
    st.sidebar.markdown("---")
    
    professores_disponiveis = df['Professor'].unique().tolist()
    professor_selecionado = st.sidebar.selectbox("👨‍🏫 Filtrar por Professor", ["Todos"] + professores_disponiveis)
    
    if professor_selecionado != "Todos":
        df = df[df["Professor"] == professor_selecionado]

    st.write("Acompanhe sua evolução, identifique padrões e escute como os nativos falam.")
    
    if df.empty:
        st.info("Nenhum erro encontrado para os filtros selecionados (Data/Professor).")
    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total de Erros (Filtro)", len(df))
        with col2:
            erro_comum = df["Tipo de Erro"].mode()[0]
            st.metric("Categoria Mais Frequente", erro_comum)
        with col3:
            professores_vistos = ", ".join(df["Professor"].unique())
            st.metric("Professor(es)", professores_vistos)

        st.subheader("Distribuição de Erros")
        contagem_erros = df['Tipo de Erro'].value_counts()
        st.bar_chart(contagem_erros)

        st.markdown("---")
        st.subheader("🔥 Top Erros Mais Recorrentes")
        
        top_n = st.selectbox("Quantidade de erros para exibir no ranking:", [5, 6, 7, 8, 9, 10])
        
        erros_frequentes = df['Explicação e Dica de Estudo'].value_counts().reset_index()
        erros_frequentes.columns = ['Explicação', 'Quantidade']
        top_erros = erros_frequentes.head(top_n)
        
        for index, row_top in top_erros.iterrows():
            qtd = row_top['Quantidade']
            exp = row_top['Explicação']
            
            linhas_erro = df[df['Explicação e Dica de Estudo'] == exp]
            profs_envolvidos = ", ".join(linhas_erro['Professor'].unique())
            
            icone = "🔥" if qtd > 1 else "⚠️"
            vezes = "vezes" if qtd > 1 else "vez"
            
            titulo_top = f"[{profs_envolvidos}] {icone} {qtd} {vezes} - {exp[:60]}..."
            
            with st.expander(titulo_top):
                st.info(f"**Explicação Completa:** {exp}")
                st.write("**Exemplos onde você cometeu este erro:**")
                
                for _, row_detalhe in linhas_erro.iterrows():
                    frase_errada = row_detalhe['Frase com Erro']
                    frase_correta = row_detalhe['Como Falar Corretamente']
                    professor = row_detalhe['Professor']
                    
                    texto_url = urllib.parse.quote(frase_correta)
                    link_playphrase = f"https://www.playphrase.me/#/search?q={texto_url}"
                    link_youglish = f"https://pt.youglish.com/pronounce/{texto_url}/english"
                    
                    st.markdown(f"- ❌ **Você disse:** {frase_errada} 🏷️ **[Prof: {professor}]**")
                    st.markdown(f"  ✅ **O certo é:** {frase_correta}")
                    st.markdown(f"  🎧 **Ouça nativos:** [🎬 PlayPhrase.me]({link_playphrase}) | [🗣️ YouGlish]({link_youglish})")
                    st.write("---")

        st.markdown("---")
        st.subheader("📚 Histórico Completo de Correções")
        
        if modo_visualizacao == "Escolher Data no Calend
