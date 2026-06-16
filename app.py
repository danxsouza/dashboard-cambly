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
            
            # Extrator ultra-robusto de nomes de professores
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

st.sidebar.markdown("---")

st.sidebar.header("🎯 Modo de Foco Intensivo")
opcao_foco = st.sidebar.radio(
    "Escolha um objetivo de estudo:",
    ["Desativado (Ver Tudo)", "⏳ Erros no Passado", "🗺️ Erros de Preposição"]
)

st.sidebar.markdown("---")
st.sidebar.header("📅 Filtros de Aula")

if df_original.empty:
    st.sidebar.warning("Nenhuma aula encontrada na base de dados.")
else:
    modo_visualizacao = st.sidebar.radio("Período de Estudo:", ["Todas as Aulas", "Escolher Data no Calendário"])
    
    # Valores padrão de data para evitar quebras
    data_inicio = df_original['Data Real'].min()
    data_fim = df_original['Data Real'].max()
    
    if modo_visualizacao == "Escolher Data no Calendário" and not df.empty:
        data_padrao = df_original['Data Real'].max()
        data_selecionada = st.sidebar.date_input("Selecione o período:", value=(data_padrao, data_padrao))
        
        if isinstance(data_selecionada, tuple):
            if len(data_selecionada) == 2:
                data_inicio, data_fim = data_selecionada
            elif len(data_selecionada) == 1:
                data_inicio = data_fim = data_selecionada[0]
        else:
            data_inicio = data_fim = data_selecionada

    professores_disponiveis = [p for p in df_original['Professor'].unique().tolist() if p and p != "Sem Nome"]
    professores_disponiveis.sort() 
    professor_selecionado = st.sidebar.selectbox("👨‍🏫 Filtrar por Professor", ["Todos"] + professores_disponiveis)

    # --- CRIAÇÃO DO DATAFRAME ISOLADO PARA CONVERSAÇÃO (TALK TIME) ---
    # Este bloco filtra apenas por Data e Professor, ignorando o Modo de Foco Intensivo
    df_conversacao = df_original.copy()
    if modo_visualizacao == "Escolher Data no Calendário":
        df_conversacao = df_conversacao[(df_conversacao["Data Real"] >= data_inicio) & (df_conversacao["Data Real"] <= data_fim)]
    if professor_selecionado != "Todos":
        df_conversacao = df_conversacao[df_conversacao["Professor"] == professor_selecionado]

    # --- APLICAÇÃO DOS FILTROS NO DATAFRAME DE ERROS PRINCIPAL ---
    if modo_visualizacao == "Escolher Data no Calendário":
        df = df[(df["Data Real"] >= data_inicio) & (df["Data Real"] <= data_fim)]
        
    if opcao_foco == "⏳ Erros no Passado":
        filtro_termo = r'passado|past|was|were|did|\bed\b|irregular'
        df = df[df['Explicação e Dica de Estudo'].str.contains(filtro_termo, case=False, na=False)]
        df_original = df_original[df_original['Explicação e Dica de Estudo'].str.contains(filtro_termo, case=False, na=False)]
    elif opcao_foco == "🗺️ Erros de Preposição":
        filtro_termo = r'preposição|preposition|\bin\b|\bon\b|\bat\b|\bto\b|\bfrom\b|\bfor\b|\bwith\b|regência'
        df = df[df['Explicação e Dica de Estudo'].str.contains(filtro_termo, case=False, na=False)]
        df_original = df_original[df_original['Explicação e Dica de Estudo'].str.contains(filtro_termo, case=False, na=False)]

    if professor_selecionado != "Todos":
        df = df[df["Professor"] == professor_selecionado]

st.write("Acompanhe sua evolução, identifique padrões e escute como os nativos falam.")

if df.empty and df_conversacao.empty:
    st.info("Nenhum registro encontrado para os filtros selecionados.")
else:
    # MÉTRICAS SIMPLIFICADAS (Respeitam o foco ativo)
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total de Erros Encontrados", len(df))
    with col2:
        professores_vistos = ", ".join([p for p in df["Professor"].unique() if p != "Sem Nome"]) if not df.empty else professor_selecionado
        st.metric("Professor(es) das Aulas", professores_vistos if professores_vistos != "Todos" else "Nenhum no foco")

    # --- SEÇÃO: ESTATÍSTICAS DE CONVERSAÇÃO (TALK TIME CORRIGIDO) ---
    st.markdown("---")
    st.subheader("🎙️ Estatísticas de Conversação Estimadas (Talk Time)")
    
    if 'Palavras Aluno' in df_conversacao.columns and 'Palavras Professor' in df_conversacao.columns:
        # Usa o dataframe global da aula para extrair os minutos reais sem duplicar
        df_aulas_unicas = df_conversacao.drop_duplicates(subset=['Arquivo de Origem'])
        
        total_palavras_danilo = pd.to_numeric(df_aulas_unicas['Palavras Aluno'], errors='coerce').fillna(0).sum()
        total_palavras_tutor = pd.to_numeric(df_aulas_unicas['Palavras Professor'], errors='coerce').fillna(0).sum()
        
        if total_palavras_danilo > 0 or total_palavras_tutor > 0:
            minutos_danilo = round(total_palavras_danilo / 140, 1)
            minutos_tutor = round(total_palavras_tutor / 140, 1)
            
            nome_label_prof = f"{professor_selecionado} (Tutor)" if professor_selecionado != "Todos" else "Professor"
            
            col_talk1, col_talk2 = st.columns([1, 2])
            with col_talk1:
                st.metric("Seu Tempo de Fala", f"⏱️ {minutos_danilo} min")
                st.metric(f"Tempo de Fala - {nome_label_prof}", f"⏱️ {minutos_tutor} min")
            with col_talk2:
                dados_pizza = pd.DataFrame({
                    "Quem Falou": ["Danilo (Você)", nome_label_prof],
                    "Minutos": [minutos_danilo, minutos_tutor]
                })
                st.vega_lite_chart(dados_pizza, {
                    'mark': {'type': 'arc', 'innerRadius': 40},
                    'encoding': {
                        'theta': {'field': 'Minutos', 'type': 'quantitative'},
                        'color': {'field': 'Quem Falou', 'type': 'nominal', 'scale': {'range': ['#2b5c8f', '#2ca02c']}}
                    }
                }, width="stretch")
        else:
            st.info("⚠️ Não há contagem de palavras registrada para o período ou professor selecionado.")
    else:
        st.info("💡 As estatísticas aparecerão quando dados em .txt forem integrados na planilha.")

    # --- TOP ERROS RECORRENTES ---
    if not df.empty:
        st.markdown("---")
        if professor_selecionado == "Todos":
            st.subheader("🔥 Top Erros Mais Recorrentes (Foco Ativo)")
            df_top_erros = df_original.copy()
        else:
            st.subheader(f"🔥 Top Erros Mais Recorrentes (com {professor_selecionado})")
            df_top_erros = df_original[df_original['Professor'] == professor_selecionado]
            
        top_n = st.selectbox("Quantidade de erros para exibir no ranking:", [5, 6, 7, 8, 9, 10])
        
        erros_frequentes = df_top_erros['Explicação e Dica de Estudo'].value_counts().reset_index()
        erros_frequentes.columns = ['Explicação', 'Quantidade']
        top_erros = erros_frequentes.head(top_n)
        
        for index, row_top in top_erros.iterrows():
            qtd = row_top['Quantidade']
            exp = row_top['Explicação']
            
            linhas_erro = df_top_erros[df_top_erros['Explicação e Dica de Estudo'] == exp]
            profs_envolvidos = ", ".join([p for p in linhas_erro['Professor'].unique() if p != "Sem Nome"])
            
            icone = "🔥" if qtd > 1 else "⚠️"
            vezes = "vezes" if qtd > 1 else "vez"
            
            titulo_top = f"[{profs_envolvidos}] {icone} {qtd} {vezes} - {exp[:60]}..."
            
            with st.expander(titulo_top):
                st.info(f"**Explicação Completa:** {exp}")
                for _, row_detalhe in linhas_erro.iterrows():
                    frase_errada = row_detalhe['Frase com Erro']
                    frase_correta = row_detalhe['Como Falar Corretamente']
                    professor = row_detalhe['Professor']
                    data_aula = row_detalhe['Data da Aula']
                    
                    texto_url = urllib.parse.quote(frase_correta)
                    link_playphrase = f"https://www.playphrase.me/#/search?q={texto_url}"
                    link_youglish = f"https://pt.youglish.com/pronounce/{texto_url}/english"
                    link_gtranslate = f"https://translate.google.com/?sl=en&tl=pt&text={texto_url}&op=translate"
                    
                    st.markdown(f"- ❌ **Você disse:** {frase_errada} 🏷️ **[Prof: {professor} em {data_aula}]**")
                    st.markdown(f"  ✅ **O certo é:** {frase_correta}")
                    st.markdown(f"  🎧 **Pratique:** [🎬 PlayPhrase]({link_playphrase}) | [🗣️ YouGlish]({link_youglish}) | [🌐 Google Tradutor]({link_gtranslate})")
                    st.write("---")

    # --- HISTÓRICO DE CORREÇÕES ---
    if not df.empty:
        st.markdown("---")
        st.subheader("📚 Histórico de Correções Filtrado")
        
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
            grupos_aula = df_paginado[['Professor', 'Data da Aula']].drop_duplicates()
            
            for _, grupo in grupos_aula.iterrows():
                prof = grupo['Professor']
                if prof == "Sem Nome": continue
                data_aula = grupo['Data da Aula'] 
                
                st.markdown(f"### 👨‍🏫 Aula com {prof} 📅 {data_aula}")
                df_prof = df_paginado[(df_paginado['Professor'] == prof) & (df_paginado['Data da Aula'] == data_aula)]
                
                for index, row in df_prof.iterrows():
                    titulo_expander = f"📖 [{row['Tipo de Erro']}] {row['Frase com Erro']}"
                    with st.expander(titulo_expander):
                        frase_correta = row['Como Falar Corretamente']
                        dica_estudo = row['Explicação e Dica de Estudo']
                        
                        texto_url = urllib.parse.quote(frase_correta)
                        link_playphrase = f"https://www.playphrase.me/#/search?q={texto_url}"
                        link_youglish = f"https://pt.youglish.com/pronounce/{texto_url}/english"
                        link_gtranslate = f"https://translate.google.com/?sl=en&tl=pt&text={texto_url}&op=translate"
                        
                        st.success(f"**Como falar corretamente:** {frase_correta}")
                        st.info(f"**Dica de Estudo:** {dica_estudo}")
                        st.markdown(f"**Pratique:** [🎬 PlayPhrase]({link_playphrase}) | [🗣️ YouGlish]({link_youglish}) | [🌐 Google Tradutor]({link_gtranslate})")
                        
                        chave_sessao = f"exemplos_cal_{index}"
                        if st.button("💡 Gerar 3 exemplos de uso", key=f"btn_cal_{index}"):
                            with st.spinner("Gerando exemplos..."):
                                st.session_state[chave_sessao] = chamar_gemini(frase_correta, dica_estudo)
                        
                        if chave_sessao in st.session_state:
                            st.markdown("---")
                            st.markdown(st.session_state[chave_sessao])
                        st.caption(f"Origem: {row['Arquivo de Origem']}")
        else:
            for index, row in df_paginado.iterrows():
                prof_exibicao = row['Professor'] if row['Professor'] != "Sem Nome" else "Tutor"
                titulo_expander = f"📖 [{row['Tipo de Erro']}] {row['Frase com Erro']}   🏷️ [{prof_exibicao}]"
                with st.expander(titulo_expander):
                    frase_correta = row['Como Falar Corretamente']
                    dica_estudo = row['Explicação e Dica de Estudo']
                    
                    texto_url = urllib.parse.quote(frase_correta)
                    link_playphrase = f"https://www.playphrase.me/#/search?q={texto_url}"
                    link_youglish = f"https://pt.youglish.com/pronounce/{texto_url}/english"
                    link_gtranslate = f"https://translate.google.com/?sl=en&tl=pt&text={texto_url}&op=translate"
                    
                    st.success(f"**Como falar corretamente:** {frase_correta}")
                    st.info(f"**Dica de Estudo:** {dica_estudo}")
                    st.markdown(f"**Pratique:** [🎬 PlayPhrase]({link_playphrase}) | [🗣️ YouGlish]({link_youglish}) | [🌐 Google Tradutor]({link_gtranslate})")
                    
                    chave_sessao = f"exemplos_list_{index}"
                    if st.button("💡 Gerar 3 exemplos de uso", key=f"btn_list_{index}"):
                        with st.spinner("Gerando exemplos..."):
                            st.session_state[chave_sessao] = chamar_gemini(frase_correta, dica_estudo)
                    
                    if chave_sessao in st.session_state:
                        st.markdown("---")
                        st.markdown(st.session_state[chave_sessao])
                    st.caption(f"Data: {row['Data da Aula']} | Origem: {row['Arquivo de Origem']}")

        # --- BOTÕES DE PAGINAÇÃO COMPACTOS ---
        if total_paginas > 1:
            st.markdown("<br>", unsafe_allow_html=True) 
            col_esp1, col_ant, col_pag, col_prox, col_esp2 = st.columns([3.8, 0.8, 1.4, 0.8, 3.8])
            
            with col_ant:
                if st.session_state['pagina_atual'] > 1:
                    if st.button("⏪ Ant", width="stretch"):
                        st.session_state['pagina_atual'] -= 1
                        st.rerun() 
            with col_pag:
                st.markdown(
                    f"<div style='text-align: center; padding: 6px 0px; font-weight: bold; font-size: 14px; background-color: rgba(128,128,128,0.05); border-radius: 4px; border: 1px solid rgba(128,128,128,0.1);'>"
                    f"Pág {st.session_state['pagina_atual']} de {total_paginas}</div>", 
                    unsafe_allow_html=True
                )
            with col_prox:
                if st.session_state['pagina_atual'] < total_paginas:
                    if st.button("Prox ⏩", width="stretch"):
                        st.session_state['pagina_atual'] += 1
                        st.rerun() 
