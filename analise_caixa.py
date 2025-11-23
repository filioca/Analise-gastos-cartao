import pandas as pd
import numpy as np
from google.colab import files
import io
from dateutil.relativedelta import relativedelta

# ==========================================
# 1. UPLOAD
# ==========================================
print("⬇️ CLIQUE NO BOTÃO E ENVIE O ARQUIVO 'Fechamento Mensal 2025.xlsx':")
uploaded = files.upload()
nome_arquivo = next(iter(uploaded))

# ==========================================
# 2. LEITURA E PADRONIZAÇÃO
# ==========================================
try:
    xls = pd.ExcelFile(io.BytesIO(uploaded[nome_arquivo]))
    aba_out = [aba for aba in xls.sheet_names if 'out' in aba.lower()][0]
    aba_nov = [aba for aba in xls.sheet_names if 'nov' in aba.lower()][0]
    
    df_out = pd.read_excel(xls, sheet_name=aba_out)
    df_nov = pd.read_excel(xls, sheet_name=aba_nov)
    
    # Padronizar nomes
    if 'Pagamento' in df_out.columns: df_out = df_out.rename(columns={'Pagamento': 'Via'})
    if 'Pagamento' in df_nov.columns: df_nov = df_nov.rename(columns={'Pagamento': 'Via'})
    
    # Padronizar parcelas
    for col in df_out.columns:
        if 'parcela' in col.lower(): df_out = df_out.rename(columns={col: 'Parcelas'})
    for col in df_nov.columns:
        if 'parcela' in col.lower(): df_nov = df_nov.rename(columns={col: 'Parcelas'})

    if 'Parcelas' not in df_out.columns: df_out['Parcelas'] = 1
    if 'Parcelas' not in df_nov.columns: df_nov['Parcelas'] = 1

    cols = ['Data', 'Título', 'Via', 'Valor Final', 'Parcelas']
    df_out = df_out[[c for c in cols if c in df_out.columns]]
    df_nov = df_nov[[c for c in cols if c in df_nov.columns]]
    
    # Reset index é CRUCIAL aqui para garantir IDs únicos
    df_total = pd.concat([df_out, df_nov]).reset_index(drop=True)
    
    # Limpeza
    df_total['Data'] = pd.to_datetime(df_total['Data'], errors='coerce')
    df_total['Data'] = df_total['Data'].apply(lambda x: x.replace(year=2025) if (not pd.isnull(x) and x.year == 2011) else x)
    df_total['Título'] = df_total['Título'].astype(str).str.strip()
    df_total['Parcelas'] = pd.to_numeric(df_total['Parcelas'], errors='coerce').fillna(1).astype(int)

except Exception as e:
    print(f"❌ Erro crítico: {e}")

# ==========================================
# 3. AUDITORIA INTERATIVA (VISUAL AJUSTADO)
# ==========================================
print("\n" + "="*60)
print("🕵️‍♂️ PASSO 1: AUDITORIA INTELIGENTE")
print("="*60)

duplicatas = df_total[df_total.duplicated(subset=['Data', 'Valor Final'], keep=False)]
indices_excluidos = []

if len(duplicatas) > 0:
    grupos_conflito = duplicatas.groupby(['Data', 'Valor Final'])
    
    for (data, valor), grupo in grupos_conflito:
        if len([i for i in grupo.index if i not in indices_excluidos]) < 2: continue
        
        print(f"\n⚠️ CONFLITO EM {data.strftime('%d/%m/%Y')} | VALOR: R$ {valor}")
        print("   Registros encontrados:")
        print(grupo[['Título', 'Via']].to_markdown())
        
        print("\n   Quer excluir UMA das entradas duplicadas e manter a outra? (s/n):")
        decisao = input("   👉 ")
        
        if decisao.lower() == 's':
            id_vitima = grupo.index[-1]
            indices_excluidos.append(id_vitima)
            print(f"   ❌ OK. Removido o item ID {id_vitima}. O outro foi mantido.")
        else:
            print("   ✅ OK. Mantidas todas as entradas.")

    df_limpo = df_total.drop(indices_excluidos).reset_index(drop=True)
    print(f"\n🏁 Auditoria finalizada. {len(indices_excluidos)} itens removidos.")

else:
    df_limpo = df_total
    print("✅ Nenhuma duplicata encontrada.")

# ==========================================
# 4. PROCESSAMENTO DE PARCELAS
# ==========================================
print("\n⚙️ Processando parcelamentos...")

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

# ==========================================
# 5. CÁLCULO DE FATURA
# ==========================================
def definir_fatura(data):
    if pd.isnull(data): return "Data Inválida"
    if data.day >= 23:
        return (data + pd.DateOffset(months=1)).strftime('%Y-%m')
    else:
        return data.strftime('%Y-%m')

df_final['Mes_Fatura'] = df_final['Data'].apply(definir_fatura)
df_final = df_final.sort_values(by=['Mes_Fatura', 'Data'])

# Filtra só crédito
df_credito_final = df_final[df_final['Via'].astype(str).str.contains("Crédito", case=False, na=False)].copy()

# ==========================================
# 6. RELATÓRIO MENSAL EM TELA
# ==========================================
faturas = sorted(df_credito_final['Mes_Fatura'].unique())

print("\n" + "="*80)
print("📊 FLUXO DE CAIXA REAL - CARTÃO DE CRÉDITO")
print("="*80)

for fatura in faturas:
    df_fatura = df_credito_final[df_credito_final['Mes_Fatura'] == fatura]
    total = df_fatura['Valor Final'].sum()
    
    if abs(total) > 0.01:
        print(f"\n📅 FATURA VENCIMENTO: {fatura}")
        print(f"💰 TOTAL A PAGAR: R$ {total:,.2f}")
        print("-" * 80)
        display_df = df_fatura[['Data', 'Título', 'Valor Final']].copy()
        display_df['Data'] = display_df['Data'].dt.strftime('%d/%m/%Y')
        display_df['Valor Final'] = display_df['Valor Final'].apply(lambda x: f"R$ {x:,.2f}")
        print(display_df.to_markdown(index=False))
        print("\n")

# ==========================================
# 7. ANÁLISE ABC (CORRIGIDA E AGRUPADA)
# ==========================================
print("\n" + "#"*80)
print("🏆 ANÁLISE ABC INTELIGENTE (AGRUPADA POR FORNECEDOR)")
print("#"*80)

# Função para limpar e agrupar nomes similares
def padronizar_nome_abc(nome):
    nome_limpo = nome.lower()
    
    # 1. Remove indicação de parcela " (1/8)"
    if '(' in nome_limpo and '/' in nome_limpo:
        nome_limpo = nome_limpo.split('(')[0].strip()
        
    # 2. Agrupamentos Lógicos
    if 'multibar' in nome_limpo: return 'MULTIBAR (Fornecedor)'
    if 'açougue' in nome_limpo: return 'AÇOUGUE / PROTEÍNA'
    if 'supermercado' in nome_limpo or 'mercado' in nome_limpo or 'compra' in nome_limpo: return 'SUPERMERCADO / INSUMOS'
    if 'construçao' in nome_limpo or 'construção' in nome_limpo: return 'MANUTENÇÃO / OBRA'
    if 'embalagen' in nome_limpo: return 'EMBALAGENS'
    
    # Se não cair em nenhuma regra, retorna o nome original maiúsculo
    return nome_limpo.upper()

# Cria coluna temporária para agrupamento
df_credito_final['Categoria_ABC'] = df_credito_final['Título'].apply(padronizar_nome_abc)

# Agrupa pela CATEGORIA, não mais pelo título sujo
df_abc = df_credito_final.groupby('Categoria_ABC')['Valor Final'].sum().reset_index()

# Valores absolutos para cálculo
df_abc['Valor Absoluto'] = df_abc['Valor Final'].abs()
df_abc = df_abc.sort_values(by='Valor Absoluto', ascending=False)

# Cálculos Estatísticos
total_gasto = df_abc['Valor Absoluto'].sum()
df_abc['% do Total'] = (df_abc['Valor Absoluto'] / total_gasto) * 100
df_abc['% Acumulado'] = df_abc['% do Total'].cumsum()

# Definição das Classes
def definir_classe(p):
    if p <= 80: return 'A (Vital - 80% do Custo)'
    elif p <= 95: return 'B (Médio Impacto)'
    else: return 'C (Baixo Impacto)'

df_abc['Classe'] = df_abc['% Acumulado'].apply(definir_classe)

# Formatação
df_exibir_abc = df_abc[['Classe', 'Categoria_ABC', 'Valor Final', '% do Total']].copy()
df_exibir_abc['Valor Final'] = df_exibir_abc['Valor Final'].apply(lambda x: f"R$ {x:,.2f}")
df_exibir_abc['% do Total'] = df_exibir_abc['% do Total'].apply(lambda x: f"{x:.1f}%")
df_exibir_abc.columns = ['Classe', 'Fornecedor Agrupado', 'Valor Total', '% Impacto']

print(f"\n💰 GASTO TOTAL ANALISADO NO CARTÃO: R$ {total_gasto:,.2f}\n")
print(df_exibir_abc.to_markdown(index=False))
print("\n💡 NOTA: 'Supermercado/Insumos' agrupa: 'Compra', 'NF Supermercado' e 'Cupom Mercado'.")
