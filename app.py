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
    
    data_inicio = df_original['Data Real'].dropna().min()
    data_fim = df_original['Data Real'].dropna().max()
    
    if modo_visualizacao == "Escolher Data no Calendário" and not df.empty:
        data_padrao = df_original['Data Real'].dropna().max()
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

    # --- APLICAÇÃO CRÍTICA DE FILTROS: CALENDÁRIO + PROFESSOR ---
    df_conversacao = df_original.copy()
    
    # 1. Filtro de Data (Isolado e Absoluto)
    if modo_visualizacao == "Escolher Data no Calendário":
        df_conversacao = df_conversacao[(df_conversacao["Data Real"] >= data_inicio) & (df_conversacao["Data Real"] <= data_fim)]
        
    # 2. Filtro de Professor (Isolado e Absoluto)
    if professor_selecionado != "Todos":
        df_conversacao = df_conversacao[df_conversacao["Professor"] == professor_selecionado]

    # --- NOVO: RESUMO CRONOLÓGICO DA AGENDA NO MENU LATERAL ---
    if modo_visualizacao == "Escolher Data no Calendário" and not df_conversacao.empty:
        st.sidebar.markdown("---")
        st.sidebar.markdown("🗓️ **Resumo de Aulas no Período:**")
        
        # Pega as datas e professores, remove duplicatas (caso tenha arquivo de áudio e chat no mesmo dia) e ordena pela data (do mais antigo pro mais novo)
        aulas_unicas = df_conversacao[['Data Real', 'Professor']].drop_duplicates().sort_values(by='Data Real', ascending=True)
        dias_pt = {0: 'Seg', 1: 'Ter', 2: 'Qua', 3: 'Qui', 4: 'Sex', 5: 'Sáb', 6: 'Dom'}
        
        for _, row in aulas_unicas.iterrows():
            data_obj = row['Data Real']
            prof = row['Professor']
            if prof != "Sem Nome":
                dia_str = dias_pt[data_obj.weekday()]
                data_str = data_obj.strftime("%d/%m/%Y")
                st.sidebar.markdown(f"- `{data_str} ({dia_str})` - **{prof}**")

    # --- APLICAÇÃO DOS FILTROS NO DATAFRAME DE ERROS PRINCIPAL ---
    if modo_visualizacao == "Escolher Data no Calendário":
        df = df[(df["Data Real"] >= data_inicio) & (df["Data Real"] <= data_fim)]
        
    if opcao_foco == "⏳ Erros no Passado":
        filtro_termo = r'passado|past|was|were|did|\bed\b|irregular'
        df = df[df['Explicação e Dica de Estudo'].astype(str).str.contains(filtro_termo, case=False, na=False)]
    elif opcao_foco == "🗺️ Erros de Preposição":
        filtro_termo = r'preposição|preposition|\bin\b|\bon\b|\bat\b|\bto\b|\bfrom\b|\bfor\b|\bwith\b|regência'
        df = df[df['Explicação e Dica de Estudo'].astype(str).str.contains(filtro_termo, case=False, na=False)]

    if professor_selecionado != "Todos":
        df = df[df["Professor"] == professor_selecionado]

st.write("Acompanhe sua evolução, identifique padrões e escute como os nativos falam.")

if df.empty and df_conversacao.empty:
    st.info("Nenhum registro encontrado para os filtros selecionados.")
else:
    # Remove as linhas fantasmas ("N/A") das listas de erros e chat
    df_visual = df[df['Frase com Erro'].astype(str).str.strip() != 'N/A']

    # Separação dos dados limpos: Áudio vs Chat
    df_chat = df_visual[df_visual['Tipo de Erro'].astype(str).str.contains('💬', na=False) | df_visual['Tipo de Erro'].astype(str).str.contains('Chat', case=False, na=False)]
    df_erros_audio = df_visual[~(df_visual['Tipo de Erro'].astype(str).str.contains('💬', na=False) | df_visual['Tipo de Erro'].astype(str).str.contains('Chat', case=False, na=False))]

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total de Itens Estudados", len(df_visual))
    with col2:
        professores_vistos = ", ".join([p for p in df_conversacao["Professor"].unique() if p != "Sem Nome"]) if not df_conversacao.empty else professor_selecionado
        st.metric("Professor(es) no Período", professores_vistos if professores_vistos != "Todos" else "Nenhum no foco")

    # --- ESTATÍSTICAS DE CONVERSAÇÃO (TALK TIME) COM GRÁFICO DINÂMICO E BLINDADO ---
    st.markdown("---")
    st.subheader("🎙️ Estatísticas de Conversação Estimadas (Talk Time)")
    
    if 'Palavras Aluno' in df_conversacao.columns and 'Palavras Professor' in df_conversacao.columns:
        # Uso do .copy() garante que o fatiamento seja profundo, limpando a memória de dados anteriores
        df_aulas_reais = df_conversacao[~df_conversacao['Arquivo de Origem'].astype(str).str.contains('-chat-', case=False, na=False)]
        df_aulas_unicas = df_aulas_reais.drop_duplicates(subset=['Arquivo de Origem']).copy()
        
        # Converte as colunas para números de forma segura
        df_aulas_unicas['Palavras Aluno'] = pd.to_numeric(df_aulas_unicas['Palavras Aluno'], errors='coerce').fillna(0)
        df_aulas_unicas['Palavras Professor'] = pd.to_numeric(df_aulas_unicas['Palavras Professor'], errors='coerce').fillna(0)
        
        total_palavras_danilo = df_aulas_unicas['Palavras Aluno'].sum()
        total_palavras_tutor = df_aulas_unicas['Palavras Professor'].sum()
        
        if total_palavras_danilo > 0 or total_palavras_tutor > 0:
            total_palavras_geral = total_palavras_danilo + total_palavras_tutor
            
            perc_danilo = round((total_palavras_danilo / total_palavras_geral) * 100, 1)
            perc_tutor = round((total_palavras_tutor / total_palavras_geral) * 100, 1)
            
            minutos_danilo = round(total_palavras_danilo / 140, 1)
            horas_danilo = round(minutos_danilo / 60, 1)
            
            minutos_tutor = round(total_palavras_tutor / 140, 1)
            horas_tutor = round(minutos_tutor / 60, 1)
            
            nome_label_prof = f"{professor_selecionado} (Tutor)" if professor_selecionado != "Todos" else "Professor(es)"
            
            # --- CONSTRUÇÃO DO GRÁFICO DE PIZZA ---
            dados_para_pizza = []
            dados_para_pizza.append({"Quem Falou": f"Danilo ({perc_danilo}%)", "Minutos": minutos_danilo})
            
            if professor_selecionado == "Todos":
                # Se for todos, quebra o gráfico criando uma fatia por professor que deu aula no período
                professores_agrupados = df_aulas_unicas.groupby('Professor')['Palavras Professor'].sum()
                for prof_nome, qtd_palavras in professores_agrupados.items():
                    if qtd_palavras > 0:
                        min_prof = round(qtd_palavras / 140, 1)
                        perc_prof = round((qtd_palavras / total_palavras_geral) * 100, 1)
                        dados_para_pizza.append({"Quem Falou": f"{prof_nome} ({perc_prof}%)", "Minutos": min_prof})
            else:
                # Se for um específico, exibe apenas ele
                dados_para_pizza.append({"Quem Falou": f"{nome_label_prof} ({perc_tutor}%)", "Minutos": minutos_tutor})
                
            df_pizza = pd.DataFrame(dados_para_pizza)
            
            col_talk1, col_talk2 = st.columns([1, 2])
            with col_talk1:
                st.metric(
                    label="Seu Tempo de Fala", 
                    value=f"⏱️ {horas_danilo}h ({minutos_danilo} min)", 
                    delta=f"🗣️ {int(total_palavras_danilo)} palavras | {perc_danilo}% do tempo", 
                    delta_color="off"
                )
                st.metric(
                    label=f"Tempo de Fala - {nome_label_prof}", 
                    value=f"⏱️ {horas_tutor}h ({minutos_tutor} min)", 
                    delta=f"🗣️ {int(total_palavras_tutor)} palavras | {perc_tutor}% do tempo", 
                    delta_color="off"
                )
            with col_talk2:
                # A chave invisível 'description' OBRIGA o Streamlit a destruir e redesenhar o gráfico
                st.vega_lite_chart(df_pizza, {
                    'description': f"Pizza_TalkTime_{professor_selecionado}_{data_inicio}_{data_fim}",
                    'mark': {'type': 'arc', 'innerRadius': 40, 'tooltip': True},
                    'encoding': {
                        'theta': {'field': 'Minutos', 'type': 'quantitative'},
                        'color': {
                            'field': 'Quem Falou', 
                            'type': 'nominal', 
                            'scale': {'range': ['#2b5c8f', '#2ca02c', '#ff7f0e', '#d62728', '#9467bd', '#8c564b']}
                        }
                    }
                }, width="stretch")
        else:
            st.info("🎙️ Selecione um período com arquivos de transcrição de áudio para ver o gráfico de Talk Time.")
    else:
        st.info("💡 As estatísticas aparecerão quando dados em .txt forem integrados na planilha.")

    # --- TOP ERROS RECORRENTES ---
    if not df_erros_audio.empty:
        st.markdown("---")
        st.subheader("🔥 Top Erros Mais Recorrentes (Apenas Áudio)")
        
        erros_frequentes = df_erros_audio['Explicação e Dica de Estudo'].value_counts().reset_index()
        erros_frequentes.columns = ['Explicação', 'Quantidade']
        erros_frequentes = erros_frequentes[erros_frequentes['Quantidade'] > 1]
        
        if not erros_frequentes.empty:
            top_n = st.selectbox("Quantidade de erros para exibir no ranking:", [5, 6, 7, 8, 9, 10])
            top_erros = erros_frequentes.head(top_n)
            
            for index, row_top in top_erros.iterrows():
                qtd = row_top['Quantidade']
                exp = row_top['Explicação']
                
                linhas_erro = df_erros_audio[df_erros_audio['Explicação e Dica de Estudo'] == exp]
                profs_envolvidos = ", ".join([p for p in linhas_erro['Professor'].unique() if p != "Sem Nome"])
                
                titulo_top = f"[{profs_envolvidos}] 🔥 {qtd} vezes - {exp[:60]}..."
                
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
                        
                        st.markdown(f"- ❌ **Você disse:** {frase_errada} 🏷️ **[Prof: {professor} em {data_aula}]**")
                        st.markdown(f"  ✅ **O certo é:** {frase_correta}")
                        st.markdown(f"  🎧 **Pratique:** [🎬 PlayPhrase]({link_playphrase}) | [🗣️ YouGlish]({link_youglish})")
                        st.write("---")

    # --- BLOCO EXCLUSIVO PARA O CHAT DO PROFESSOR ---
    if professor_selecionado != "Todos":
        if not df_chat.empty:
            st.markdown("---")
            st.subheader(f"💬 Notas e Vocabulário do Chat ({professor_selecionado})")
            
            for index, row in df_chat.iterrows():
                termo_chat = row['Frase com Erro']
                significado_chat = row['Como Falar Corretamente']
                dica_chat = row['Explicação e Dica de Estudo']
                
                texto_url_chat = urllib.parse.quote(termo_chat)
                link_playphrase_chat = f"https://www.playphrase.me/#/search?q={texto_url_chat}"
                link_youglish_chat = f"https://pt.youglish.com/pronounce/{texto_url_chat}/english"
                
                titulo_chat_expander = f"💬 [Chat] {termo_chat}"
                
                with st.expander(titulo_chat_expander):
                    st.success(f"**Definição / Tradução:** {significado_chat}")
                    st.info(f"**Explicação e Exemplos Iniciais:**\n{dica_chat}")
                    st.markdown(f"**Pratique o termo do chat:** [🎬 PlayPhrase]({link_playphrase_chat}) | [🗣️ YouGlish]({link_youglish_chat})")
                    
                    chave_sessao_chat = f"exemplos_chat_{index}"
                    if st.button("💡 Gerar mais 3 exemplos de uso", key=f"btn_chat_{index}"):
                        with st.spinner("Conectando ao Gemini..."):
                            st.session_state[chave_sessao_chat] = chamar_gemini(termo_chat, dica_chat)
                            
                    if chave_sessao_chat in st.session_state:
                        st.markdown("---")
                        st.markdown(st.session_state[chave_sessao_chat])
                        
                    st.caption(f"📅 Aula do dia: {row['Data da Aula']} | Origem: {row['Arquivo de Origem']}")
        else:
            st.markdown("---")
            st.subheader(f"💬 Notas e Vocabulário do Chat ({professor_selecionado})")
            st.info(f"Nenhum vocabulário relevante registrado no chat com {professor_selecionado} neste período.")

    # --- HISTÓRICO DE CORREÇÕES (APENAS ÁUDIO) ---
    if not df_erros_audio.empty:
        st.markdown("---")
        st.subheader("📚 Histórico de Correções de Áudio Filtrado")
        
        ITENS_POR_PAGINA = 20
        total_linhas = len(df_erros_audio)
        total_paginas = max(1, (total_linhas - 1) // ITENS_POR_PAGINA + 1)
        
        if 'pagina_atual' not in st.session_state:
            st.session_state['pagina_atual'] = 1
            
        if st.session_state['pagina_atual'] > total_paginas:
            st.session_state['pagina_atual'] = 1
            
        inicio = (st.session_state['pagina_atual'] - 1) * ITENS_POR_PAGINA
        fim = inicio + ITENS_POR_PAGINA
        df_paginado = df_erros_audio.iloc[inicio:fim]
        
        st.caption(f"Exibindo erros de fala {inicio + 1} a {min(fim, total_linhas)} de {total_linhas}.")

        if modo_visualizacao == "Escolher Data no Calendário" and professor_selecionado == "Todos":
            grupos_aula = df_paginado[['Professor', 'Data da Aula']].drop_duplicates()
            
            for _, group in grupos_aula.iterrows():
                prof = group['Professor']
                if prof == "Sem Nome": continue
                data_aula = group['Data da Aula'] 
                
                st.markdown(f"### 👨‍🏫 Aula com {prof} 📅 {data_aula}")
                df_prof = df_paginado[(df_paginado['Professor'] == prof) & (df_paginado['Data da Aula'] == data_aula)]
                
                for index, row in df_prof.iterrows():
                    tipo_erro = row['Tipo de Erro']
                    titulo_expander = f"📖 [{tipo_erro}] {row['Frase com Erro']}"
                    with st.expander(titulo_expander):
                        frase_correta = row['Como Falar Corretamente']
                        dica_estudo = row['Explicação e Dica de Estudo']
                        
                        texto_url = urllib.parse.quote(frase_correta)
                        link_playphrase = f"https://www.playphrase.me/#/search?q={texto_url}"
                        link_youglish = f"https://pt.youglish.com/pronounce/{texto_url}/english"
                        
                        st.success(f"**Como falar corretamente:** {frase_correta}")
                        st.info(f"**Explicação:**\n{dica_estudo}")
                        st.markdown(f"**Pratique:** [🎬 PlayPhrase]({link_playphrase}) | [🗣️ YouGlish]({link_youglish})")
                        
                        chave_sessao = f"exemplos_cal_{index}"
                        if st.button("💡 Gerar 3 exemplos de uso", key=f"btn_cal_{index}"):
                            with st.spinner("Gerando exemplos..."):
                                st.session_state[chave_sessao] = chamar_gemini(frase_correta, dica_estudo)
                        
                        if chave_sessao in st.session_state:
                            st.markdown("---")
                            st.markdown(st.session_state[chave_sessao])
        else:
            for index, row in df_paginado.iterrows():
                prof_exibicao = row['Professor'] if row['Professor'] != "Sem Nome" else "Tutor"
                tipo_erro = row['Tipo de Erro']
                titulo_expander = f"📖 [{tipo_erro}] {row['Frase com Erro']}   🏷️ [{prof_exibicao}]"
                with st.expander(titulo_expander):
                    frase_correta = row['Como Falar Corretamente']
                    dica_estudo = row['Explicação e Dica de Estudo']
                    
                    texto_url = urllib.parse.quote(frase_correta)
                    link_playphrase = f"https://www.playphrase.me/#/search?q={texto_url}"
                    link_youglish = f"https://pt.youglish.com/pronounce/{texto_url}/english"
                    
                    st.success(f"**Como falar corretamente:** {frase_correta}")
                    st.info(f"**Explicação:**\n{dica_estudo}")
                    st.markdown(f"**Pratique:** [🎬 PlayPhrase]({link_playphrase}) | [🗣️ YouGlish]({link_youglish})")
                    
                    chave_sessao = f"exemplos_list_{index}"
                    if st.button("💡 Gerar 3 exemplos de uso", key=f"btn_list_{index}"):
                        with st.spinner("Gerando exemplos..."):
                            st.session_state[chave_sessao] = chamar_gemini(frase_correta, dica_estudo)
                    
                    if chave_sessao in st.session_state:
                        st.markdown("---")
                        st.markdown(st.session_state[chave_sessao])
                    st.caption(f"Data: {row['Data da Aula']} | Origem: {row['Arquivo de Origem']}")

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
    else:
        st.markdown("---")
        st.subheader("📚 Histórico de Correções de Áudio Filtrado")
        st.success(f"🎉 Excelente! A aula com {professor_selecionado} não teve nenhum erro gramatical grave registrado pela IA.")
