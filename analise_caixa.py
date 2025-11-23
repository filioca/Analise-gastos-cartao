import streamlit as st
import pandas as pd
import numpy as np
from dateutil.relativedelta import relativedelta
import io

# ==========================================
# CONFIGURAÇÃO DA PÁGINA
# ==========================================
st.set_page_config(page_title="Gestão Financeira Restaurante", layout="wide")

st.title("👨‍🍳 Painel Financeiro Inteligente")
st.info("ℹ️ Instrução: Clique no botão **'Browse files'** abaixo para selecionar sua planilha.")
st.markdown("---")

# ==========================================
# GESTÃO DE ESTADO (MEMÓRIA DO APP)
# ==========================================
if 'indices_excluidos' not in st.session_state:
    st.session_state.indices_excluidos = set()
if 'conflitos_resolvidos' not in st.session_state:
    st.session_state.conflitos_resolvidos = set()

# ==========================================
# 1. UPLOAD DO ARQUIVO
# ==========================================
uploaded_file = st.file_uploader("Clique para selecionar o arquivo 'Fechamento Mensal 2025.xlsx'", type=['xlsx'])

if uploaded_file is not None:
    try:
        xls = pd.ExcelFile(uploaded_file)
        
        try:
            aba_out = [aba for aba in xls.sheet_names if 'out' in aba.lower()][0]
            aba_nov = [aba for aba in xls.sheet_names if 'nov' in aba.lower()][0]
        except:
            st.error("❌ Erro: Não encontrei as abas 'Outubro' ou 'Novembro' no arquivo.")
            st.stop()
            
        df_out = pd.read_excel(xls, sheet_name=aba_out)
        df_nov = pd.read_excel(xls, sheet_name=aba_nov)
        
        # Padronização
        if 'Pagamento' in df_out.columns: df_out = df_out.rename(columns={'Pagamento': 'Via'})
        if 'Pagamento' in df_nov.columns: df_nov = df_nov.rename(columns={'Pagamento': 'Via'})
        
        for col in df_out.columns:
            if 'parcela' in col.lower(): df_out = df_out.rename(columns={col: 'Parcelas'})
        for col in df_nov.columns:
            if 'parcela' in col.lower(): df_nov = df_nov.rename(columns={col: 'Parcelas'})

        if 'Parcelas' not in df_out.columns: df_out['Parcelas'] = 1
        if 'Parcelas' not in df_nov.columns: df_nov['Parcelas'] = 1

        cols = ['Data', 'Título', 'Via', 'Valor Final', 'Parcelas']
        # Verifica colunas existentes
        cols_out = [c for c in cols if c in df_out.columns]
        cols_nov = [c for c in cols if c in df_nov.columns]
        
        df_out = df_out[cols_out]
        df_nov = df_nov[cols_nov]
        
        df_total = pd.concat([df_out, df_nov]).reset_index(drop=True)
        
        # Limpeza
        df_total['Data'] = pd.to_datetime(df_total['Data'], errors='coerce')
        df_total['Data'] = df_total['Data'].apply(lambda x: x.replace(year=2025) if (not pd.isnull(x) and x.year == 2011) else x)
        df_total['Título'] = df_total['Título'].astype(str).str.strip()
        df_total['Parcelas'] = pd.to_numeric(df_total['Parcelas'], errors='coerce').fillna(1).astype(int)

        # ==========================================
        # 2. AUDITORIA INTERATIVA
        # ==========================================
        st.subheader("🕵️‍♂️ Auditoria de Duplicatas")
        
        duplicatas = df_total[df_total.duplicated(subset=['Data', 'Valor Final'], keep=False)]
        
        conflitos_pendentes = False
        
        if len(duplicatas) > 0:
            grupos = duplicatas.groupby(['Data', 'Valor Final'])
            
            for (data, valor), grupo in grupos:
                chave = f"{data}_{valor}"
                
                if chave in st.session_state.conflitos_resolvidos:
                    continue
                
                itens_ativos = [i for i in grupo.index if i not in st.session_state.indices_excluidos]
                if len(itens_ativos) < 2:
                    continue
                
                conflitos_pendentes = True
                
                with st.container():
                    st.warning(f"⚠️ **Duplicata Encontrada:** {data.strftime('%d/%m/%Y')} | Valor: R$ {valor}")
                    st.write("O sistema encontrou estes registros idênticos:")
                    st.dataframe(grupo.loc[itens_ativos, ['Título', 'Via']])
                    
                    col1, col2 = st.columns(2)
                    
                    if col1.button("❌ Excluir uma das cópias", key=f"del_{chave}"):
                        id_vitima = itens_ativos[-1]
                        st.session_state.indices_excluidos.add(id_vitima)
                        st.session_state.conflitos_resolvidos.add(chave)
                        st.rerun()
                        
                    if col2.button("✅ Não, são compras diferentes", key=f"keep_{chave}"):
                        st.session_state.conflitos_resolvidos.add(chave)
                        st.rerun()

        if not conflitos_pendentes:
            if len(duplicatas) > 0:
                st.success("✅ Auditoria finalizada! Todas as duplicatas foram resolvidas.")
            else:
                st.info("✅ Nenhuma duplicata encontrada.")
            
            # ==========================================
            # 3. PROCESSAMENTO FINANCEIRO
            # ==========================================
            df_limpo = df_total.drop(list(st.session_state.indices_excluidos)).reset_index(drop=True)
            
            novas_linhas = []
            for idx, row in df_limpo.iterrows():
                eh_credito = "Crédito" in str(row['Via'])
                n_parcelas = row['Parcelas']
                
                if eh_credito and n_parcelas > 1:
                    valor_parcela = row['Valor Final'] / n_parcelas
                    data_original = row['Data']
                    for i in range(n_parcelas):
                        nova_data = data_original + relativedelta(months=i)
                        nova_linha = row.copy()
                        nova_linha['Data'] = nova_data
                        nova_linha['Valor Final'] = valor_parcela
                        nova_linha['Título'] = f"{row['Título']} ({i+1}/{n_parcelas})"
                        nova_linha['Parcelas'] = 1 
                        novas_linhas.append(nova_linha)
                else:
                    novas_linhas.append(row)
            
            df_final = pd.DataFrame(novas_linhas)
            
            def definir_fatura(data):
                if pd.isnull(data): return "Data Inválida"
                if data.day >= 23:
                    return (data + pd.DateOffset(months=1)).strftime('%Y-%m')
                else:
                    return data.strftime('%Y-%m')

            df_final['Mes_Fatura'] = df_final['Data'].apply(definir_fatura)
            df_final = df_final.sort_values(by=['Mes_Fatura', 'Data'])
            
            df_credito = df_final[df_final['Via'].astype(str).str.contains("Crédito", case=False, na=False)]
            
            # ==========================================
            # 4. EXIBIÇÃO: FLUXO DE CAIXA
            # ==========================================
            st.markdown("---")
            st.header("📊 Fluxo de Caixa Real")
            
            faturas = sorted(df_credito['Mes_Fatura'].unique())
            tabs = st.tabs(faturas)
            
            for i, fatura in enumerate(faturas):
                with tabs[i]:
                    df_fat = df_credito[df_credito['Mes_Fatura'] == fatura]
                    total = df_fat['Valor Final'].sum()
                    
                    st.metric(label=f"Total a Pagar ({fatura})", value=f"R$ {total:,.2f}")
                    
                    display_df = df_fat[['Data', 'Título', 'Valor Final']].copy()
                    display_df['Data'] = display_df['Data'].dt.strftime('%d/%m/%Y')
                    display_df['Valor Final'] = display_df['Valor Final'].apply(lambda x: f"R$ {x:,.2f}")
                    st.dataframe(display_df, use_container_width=True)

            # ==========================================
            # 5. ANÁLISE ABC (AGRUPADA E CORRIGIDA)
            # ==========================================
            st.markdown("---")
            st.header("🏆 Análise ABC (Agrupada)")
            st.caption("Aqui vemos quem são os fornecedores que mais impactam seu caixa.")
            
            # Agrupador Inteligente (Mesma lógica do código Python anterior)
            def padronizar_nome_abc(nome):
                nome_limpo = nome.lower()
                # 1. Remove parcelas
                if '(' in nome_limpo and '/' in nome_limpo:
                    nome_limpo = nome_limpo.split('(')[0].strip()
                
                # 2. Agrupamentos
                if 'multibar' in nome_limpo: return 'MULTIBAR (Fornecedor)'
                if 'açougue' in nome_limpo: return 'AÇOUGUE / PROTEÍNA'
                if 'supermercado' in nome_limpo or 'mercado' in nome_limpo or 'compra' in nome_limpo: return 'SUPERMERCADO / INSUMOS'
                if 'construçao' in nome_limpo or 'construção' in nome_limpo: return 'MANUTENÇÃO / OBRA'
                if 'embalagen' in nome_limpo: return 'EMBALAGENS'
                
                return nome_limpo.upper()

            df_credito['Categoria_ABC'] = df_credito['Título'].apply(padronizar_nome_abc)
            
            # Agrupa pela Categoria Limpa
            df_abc = df_credito.groupby('Categoria_ABC')['Valor Final'].sum().reset_index()
            
            df_abc['Valor Absoluto'] = df_abc['Valor Final'].abs()
            df_abc = df_abc.sort_values(by='Valor Absoluto', ascending=False)
            
            total_gasto = df_abc['Valor Absoluto'].sum()
            df_abc['% do Total'] = (df_abc['Valor Absoluto'] / total_gasto) * 100
            df_abc['% Acumulado'] = df_abc['% do Total'].cumsum()
            
            def definir_classe(p):
                if p <= 80: return 'A (Vital)'
                elif p <= 95: return 'B (Médio)'
                else: return 'C (Baixo)'
            
            df_abc['Classe'] = df_abc['% Acumulado'].apply(definir_classe)
            
            col1, col2 = st.columns([2, 1])
            with col1:
                st.dataframe(
                    df_abc[['Classe', 'Categoria_ABC', 'Valor Final', '% do Total']].style.format({
                        'Valor Final': 'R$ {:,.2f}',
                        '% do Total': '{:.1f}%'
                    }),
                    use_container_width=True
                )
            with col2:
                st.info(f"**Total Analisado:** R$ {total_gasto:,.2f}")
                st.success("💡 Dica: Os itens da Classe A (Vital) representam 80% do seu custo. Foque neles!")
                
    except Exception as e:
        st.error(f"Erro ao processar arquivo: {e}")

else:
    st.info("Aguardando arquivo...")
