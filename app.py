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
            
            # Ordena os dados do mais recente para o mais antigo
            df = df.sort_values(by="Data Real", ascending=False)
            
        return df
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
st.sidebar.header("📅 Filtros de Aula")

if df.empty:
    st.warning("Ainda não há dados processados para apresentar. Coloque os PDFs no Drive e clique em Processar!")
else:
    modo_visualizacao = st.sidebar.radio("Período de Estudo:", ["Todas as Aulas", "Escolher Aula Específica"])
    
    if modo_visualizacao == "Escolher Aula Específica":
        
        # --- NOVA LÓGICA: LISTA INTELIGENTE DE DATAS ---
        # Agrupa para não repetir o mesmo dia, mantendo a ordem da data mais recente
        dias_com_aula = df.groupby('Data Real', sort=False)['Professor'].unique().reset_index()
        
        opcoes_dropdown = []
        mapa_datas = {}
        
        for index, row in dias_com_aula.iterrows():
            data_formatada = row['Data Real'].strftime("%d/%m/%Y")
            profs = ", ".join(row['Professor'])
            texto_opcao = f"📅 {data_formatada} (com {profs})"
            opcoes_dropdown.append(texto_opcao)
            mapa_datas[texto_opcao] = row['Data Real'] # Salva a data real no fundo para o filtro funcionar
            
        opcao_selecionada = st.sidebar.selectbox("Selecione a data disponível:", opcoes_dropdown)
        data_selecionada = mapa_datas[opcao_selecionada]
        df = df[df["Data Real"] == data_selecionada]
    
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
            
            linhas_erro = df[df['Explicação e Dica de Estudo'] == exp]
            
            icone = "🔥" if qtd > 1 else "⚠️"
            vezes = "vezes" if qtd > 1 else "vez"
            
            with st.expander(f"{icone} {qtd} {vezes} - {exp[:70]}..."):
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

        # --- HISTÓRICO COMPLETO ---
        st.markdown("---")
        st.subheader("📚 Histórico Completo de Correções")
        for index, row in df.iterrows():
            titulo_expander = f"📖 {row['Frase com Erro']}   🏷️ [👨‍🏫 {row['Professor']}]"
            with st.expander(titulo_expander):
                frase_correta = row['Como Falar Corretamente']
                
                texto_url = urllib.parse.quote(frase_correta)
                link_playphrase = f"https://www.playphrase.me/#/search?q={texto_url}"
                link_youglish = f"https://pt.youglish.com/pronounce/{texto_url}/english"
                
                st.success(f"**Como falar corretamente:** {frase_correta}")
                st.info(f"**Dica de Estudo:** {row['Explicação e Dica de Estudo']}")
                st.markdown(f"**Ouça nativos falando a versão correta:** [🎬 PlayPhrase.me]({link_playphrase}) | [🗣️ YouGlish]({link_youglish})")
                st.caption(f"Categoria: {row['Tipo de Erro']} | Data: {row['Data da Aula']} | Origem: {row['Arquivo de Origem']}")
