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

@st.cache_data(ttl=3600) 
def buscar_novas_palavras_cambridge():
    url = "https://dictionaryblog.cambridge.org/category/new-words/"
    palavras = []
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resposta = requests.get(url, headers=headers)
        soup = BeautifulSoup(resposta.text, 'html.parser')
        
        artigos = soup.find_all('article', limit=3)
        for artigo in artigos:
            titulo_tag = artigo.find(['h1', 'h2'], class_=['entry-title', 'title'])
            if titulo_tag and titulo_tag.find('a'):
                titulo = titulo_tag.text.strip()
                link = titulo_tag.find('a')['href']
                
                conteudo_tag = artigo.find('div', class_='entry-content')
                resumo = conteudo_tag.text.strip()[:150] + "..." if conteudo_tag else ""
                
                palavras.append({"titulo": titulo, "link": link, "resumo": resumo})
                
        if not palavras:
            links = soup.select('.entry-title a')[:3]
            for a in links:
                palavras.append({"titulo": a.text.strip(), "link": a['href'], "resumo": ""})
                
        return palavras
    except Exception as e:
        return []

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
        data_selecionada = st.sidebar.date_input(
            "Selecione o período (clique no início e depois no fim):", 
            value=(data_padrao, data_padrao)
        )
        
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
                profs_deste_dia = df_original[df_original['Data Real'] == d]['Professor'].unique()
                profs_texto = ", ".join(profs_deste_dia)
                st.sidebar.caption(f"📌 {d.strftime('%d/%m/%Y')} (com {profs_texto})")
        else:
            st.sidebar.caption("Nenhuma aula encontrada neste período.")

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
            erro_comum = df["Tipo de Erro"].mode()[0] if not df["Tipo de Erro"].empty else "N/A"
            st.metric("Categoria Mais Frequente", erro_comum)
        with col3:
            professores_vistos = ", ".join(df["Professor"].unique())
            st.metric("Professor(es)", professores_vistos)

        st.markdown("---")
        st.subheader("🆕 Novas Palavras em Inglês (Cambridge Dictionary)")
        
        novas_palavras = buscar_novas_palavras_cambridge()
        
        if novas_palavras:
            for palavra in novas_palavras:
                st.markdown(f"**[{palavra['titulo']}]({palavra['link']})**")
                if palavra['resumo']:
                    st.caption(f"{palavra['resumo']}")
        else:
            st.info("Não foi possível buscar as novas palavras no momento.")
            
        st.markdown("🔗 **[Acessar a página oficial do Cambridge Dictionary](https://dictionaryblog.cambridge.org/category/new-words/)**")

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
        
        ITENS_POR_PAGINA = 20
        total_linhas = len(df)
        total_paginas = max(1, (total_linhas - 1) // ITENS_POR_PAGINA + 1)
        
        if 'pagina_atual' not in st.session_state:
            st.session_state['pagina_atual'] = 1
            
        if st.session_state['pagina_atual'] > total_paginas:
            st.session_state['pagina_atual'] = 1
            
        inicio = (st.session_state['pagina_atual'] - 1) * ITENS_POR_PAGINA
        fim = inicio + ITENS_POR_PAGINA
        df_paginado = df.iloc[inicio:fim]
        
        st.caption(f"Exibindo itens {inicio + 1} a {min(fim, total_linhas)} de {total_linhas} correções.")

        if modo_visualizacao == "Escolher Data no Calendário" and professor_selecionado == "Todos":
            # --- ATUALIZAÇÃO: AGRUPANDO POR PROFESSOR E DATA ---
            grupos_aula = df_paginado[['Professor', 'Data da Aula']].drop_duplicates()
            
            for _, grupo in grupos_aula.iterrows():
                prof = grupo['Professor']
                data_aula = grupo['Data da Aula']
                
                st.markdown(f"### 👨‍🏫 Aula com {prof} 📅 {data_aula}")
                
                df_prof = df_paginado[(df_paginado['Professor'] == prof) & (df_paginado['Data da Aula'] == data_aula)]
                
                for index, row in df_prof.iterrows():
                    with st.expander(f"📖 {row['Frase com Erro']}"):
                        frase_correta = row['Como Falar Corretamente']
                        dica_estudo = row['Explicação e Dica de Estudo']
                        texto_url = urllib.parse.quote(frase_correta)
                        link_playphrase = f"https://www.playphrase.me/#/search?q={texto_url}"
                        link_youglish = f"https://pt.youglish.com/pronounce/{texto_url}/english"
                        
                        st.success(f"**Como falar corretamente:** {frase_correta}")
                        st.info(f"**Dica de Estudo:** {dica_estudo}")
                        st.markdown(f"**Ouça nativos falando:** [🎬 PlayPhrase.me]({link_playphrase}) | [🗣️ YouGlish]({link_youglish})")
                        
                        chave_sessao = f"exemplos_cal_{index}"
                        if st.button("💡 Gerar 3 exemplos de uso", key=f"btn_cal_{index}"):
                            with st.spinner("Conectando à IA para gerar os exemplos..."):
                                st.session_state[chave_sessao] = chamar_gemini(frase_correta, dica_estudo)
                        
                        if chave_sessao in st.session_state:
                            st.markdown("---")
                            st.markdown(st.session_state[chave_sessao])
                            
                        st.caption(f"Arquivo: {row['Arquivo de Origem']}")
        else:
            for index, row in df_paginado.iterrows():
                titulo_expander = f"📖 {row['Frase com Erro']}   🏷️ [{row['Professor']}]"
                with st.expander(titulo_expander):
                    frase_correta = row['Como Falar Corretamente']
                    dica_estudo = row['Explicação e Dica de Estudo']
                    
                    texto_url = urllib.parse.quote(frase_correta)
                    link_playphrase = f"https://www.playphrase.me/#/search?q={texto_url}"
                    link_youglish = f"https://pt.youglish.com/pronounce/{texto_url}/english"
                    
                    st.success(f"**Como falar corretamente:** {frase_correta}")
                    st.info(f"**Dica de Estudo:** {dica_estudo}")
                    st.markdown(f"**Ouça nativos falando:** [🎬 PlayPhrase.me]({link_playphrase}) | [🗣️ YouGlish]({link_youglish})")
                    
                    chave_sessao = f"exemplos_list_{index}"
                    if st.button("💡 Gerar 3 exemplos de uso", key=f"btn_list_{index}"):
                        with st.spinner("Conectando à IA para gerar os exemplos..."):
                            st.session_state[chave_sessao] = chamar_gemini(frase_correta, dica_estudo)
                    
                    if chave_sessao in st.session_state:
                        st.markdown("---")
                        st.markdown(st.session_state[chave_sessao])
                        
                    st.caption(f"Categoria: {row['Tipo de Erro']} | Data: {row['Data da Aula']} | Origem: {row['Arquivo de Origem']}")

        if total_paginas > 1:
            st.markdown("<br>", unsafe_allow_html=True) 
            col_esp1, col_ant, col_pag, col_prox, col_esp2 = st.columns([1, 1.5, 2, 1.5, 1])
            
            with col_ant:
                if st.session_state['pagina_atual'] > 1:
                    if st.button("⏪ Anterior", use_container_width=True):
                        st.session_state['pagina_atual'] -= 1
                        st.rerun() 
            with col_pag:
                st.markdown(
                    f"<div style='text-align: center; padding: 5px; border-radius: 8px; border: 1px solid rgba(128,128,128,0.3); font-weight: bold; font-size: 16px;'>"
                    f"Página {st.session_state['pagina_atual']} de {total_paginas}</div>", 
                    unsafe_allow_html=True
                )
            with col_prox:
                if st.session_state['pagina_atual'] < total_paginas:
                    if st.button("Próxima ⏩", use_container_width=True):
                        st.session_state['pagina_atual'] += 1
                        st.rerun() 
