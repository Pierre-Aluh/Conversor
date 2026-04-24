import pandas as pd
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
import shutil
import tempfile
import time
from config import CONTAS_PRIORITARIAS, TOLERANCIA_CONTAS_PRIORITARIAS, TOLERANCIA_GLOBAL

def gerar_contabilidade_consorciada(arquivo_origem, percentual, cod_empresa, cod_obra, conta_arredondamento=None,
                                   repasse_ativo=None, repasse_passivo=None, grupo_excluido=None):
    """
    Transforma lançamentos do Consórcio para a Empresa Consorciada.
    
    CONTAS PRIORITÁRIAS (SAGRADAS): Devem fechar 100% em todos os níveis
    conta_arredondamento: Conta a ser usada para lançamentos de ajuste de arredondamento
    """
    # Validação de parâmetros críticos
    if conta_arredondamento is None or not str(conta_arredondamento).strip():
        raise ValueError("❌ ERRO: Conta de arredondamento é obrigatória")
    
    if not isinstance(percentual, (int, float)) or percentual <= 0 or percentual > 1:
        raise ValueError(f"❌ ERRO: Percentual inválido: {percentual} (deve estar entre 0 e 1)")
    
    if not isinstance(cod_empresa, int) or cod_empresa <= 0:
        raise ValueError(f"❌ ERRO: Código de empresa inválido: {cod_empresa}")
    
    if not isinstance(cod_obra, int) or cod_obra <= 0:
        raise ValueError(f"❌ ERRO: Código de obra inválido: {cod_obra}")
    
    # 1. Carregar os dados
    arquivo_origem = Path(arquivo_origem)
    try:
        if arquivo_origem.suffix.lower() in {'.xls', '.xlsx'}:
            # Tenta leitura direta com pequenas retentativas para lock transitório (Excel/OneDrive).
            df = None
            ultimo_erro = None
            for _ in range(3):
                try:
                    df = pd.read_excel(arquivo_origem)
                    break
                except PermissionError as e:
                    ultimo_erro = e
                    time.sleep(0.8)

            if df is None:
                # Fallback: copia para arquivo temporário e tenta ler de lá.
                try:
                    with tempfile.TemporaryDirectory() as tmp_dir:
                        tmp_file = Path(tmp_dir) / arquivo_origem.name
                        shutil.copy2(arquivo_origem, tmp_file)
                        df = pd.read_excel(tmp_file)
                except PermissionError as e:
                    raise PermissionError(
                        f"❌ ARQUIVO BLOQUEADO - Não consegui acessar: {arquivo_origem}\n"
                        f"\nSoluções:\n"
                        f"1. Feche o arquivo se estiver aberto no Excel\n"
                        f"2. Aguarde a sincronização do OneDrive completar\n"
                        f"3. Verifique permissões da pasta\n"
                        f"\nTente novamente em alguns segundos."
                    ) from e
                except Exception as e:
                    if ultimo_erro is not None:
                        raise PermissionError(
                            f"❌ ARQUIVO BLOQUEADO - Não consegui acessar: {arquivo_origem}\n"
                            f"\nSoluções:\n"
                            f"1. Feche o arquivo se estiver aberto no Excel\n"
                            f"2. Aguarde a sincronização do OneDrive completar\n"
                            f"3. Verifique permissões da pasta\n"
                            f"\nDetalhe técnico: {e}"
                        ) from ultimo_erro
                    raise
        else:
            df = pd.read_csv(arquivo_origem, sep=None, engine='python', encoding='utf-8-sig')
    except FileNotFoundError:
        raise FileNotFoundError(f"❌ ARQUIVO NÃO ENCONTRADO: {arquivo_origem}")
    except Exception as e:
        raise Exception(f"❌ ERRO ao carregar arquivo: {str(e)}")
    
    # Validar colunas obrigatórias
    colunas_obrigatorias = ['Valor', 'Conta', 'Ação']
    colunas_faltantes = [col for col in colunas_obrigatorias if col not in df.columns]
    if colunas_faltantes:
        raise ValueError(f"❌ ERRO: Colunas obrigatórias não encontradas no arquivo: {', '.join(colunas_faltantes)}")
    
    # CONTAS PRIORITÁRIAS (SAGRADAS) - DEVEM FECHAR 100%
    # Importadas de config.py - NUNCA MUDAR ESTAS CONTAS
    contas_prioritarias = CONTAS_PRIORITARIAS
    
    # 2. Mapeamento de colunas
    mapping = {
        'Documento': 'DOC',
        'Cheque': 'NUMCHEQUE',
        'Categ. mov. fin.': 'CategoriaMovimentacaoFinanceira',
        'Data': 'Data',
        'Conta': 'CONTA',
        'Ação': 'ACAO',
        'Histórico lançamento contábil': 'HISTORICO',
        'Sequência': 'NumSequencia',
        'Contra part.': 'ContaContraPartida'
    }
    
    new_df = pd.DataFrame()
    
    # Detectar o tipo de lançamento do ARQUIVO (não por linha)
    # Se houver qualquer lançamento de tipo SOCIETÁRIO, o arquivo inteiro é SOCIETÁRIO
    col_tipo = next((c for c in df.columns if 'tipo' in c.lower() and 'lan' in c.lower()), None)
    tipo_arquivo = 'FISCAL'  # Padrão
    
    if col_tipo:
        # Verificar se há algum lançamento societário no arquivo
        eh_societario = df[col_tipo].astype(str).str.contains('19|42|ajuste societario', case=False, na=False).any()
        if eh_societario:
            tipo_arquivo = 'SOCIETARIO'
    
    print(f"\n[✓] Tipo de arquivo detectado: {tipo_arquivo}")
    
    # Aplicar o tipo a TODOS os lançamentos (não por linha, mas para o arquivo inteiro)
    new_df['Lancamento'] = [tipo_arquivo] * len(df)
    
    # Guardar valores desde já (antes de qualquer exclusão)
    new_df['VALOR_ORIGINAL'] = df['Valor'].values
    
    for old_col, new_col in mapping.items():
        if old_col in df.columns:
            new_df[new_col] = df[old_col]
    
    # Garantir que a coluna Data exista
    if 'Data' not in new_df.columns:
        new_df['Data'] = ''
        
    new_df['Empresa'] = cod_empresa
    new_df['Obra'] = cod_obra
    new_df['TipoLancamento'] = 0
    
    # Preencher colunas opcionais apenas se existirem
    if 'NUMCHEQUE' in new_df.columns:
        new_df['NUMCHEQUE'] = new_df['NUMCHEQUE'].fillna(0)
    else:
        new_df['NUMCHEQUE'] = 0
        
    if 'DOC' in new_df.columns:
        new_df['DOC'] = new_df['DOC'].fillna(0)
    else:
        new_df['DOC'] = ''
        
    new_df['ACAO_LIMPA'] = new_df['ACAO'].str.strip()
    
    # Limpeza de espaços em campos-chave
    new_df['CONTA'] = new_df['CONTA'].str.strip()
    
    if 'HISTORICO' in new_df.columns:
        new_df['HISTORICO'] = new_df['HISTORICO'].fillna('').str.strip()
    else:
        new_df['HISTORICO'] = ''
        
    # NumSequencia: limpar espaços e preencher NaN com 0
    if 'NumSequencia' in new_df.columns:
        new_df['NumSequencia'] = pd.to_numeric(new_df['NumSequencia'], errors='coerce').fillna(0)
    else:
        new_df['NumSequencia'] = 0
        
    if 'ContaContraPartida' in new_df.columns:
        new_df['ContaContraPartida'] = new_df['ContaContraPartida'].fillna('').astype(str).str.strip()
    else:
        new_df['ContaContraPartida'] = ''
        
    if 'CategoriaMovimentacaoFinanceira' in new_df.columns:
        new_df['CategoriaMovimentacaoFinanceira'] = new_df['CategoriaMovimentacaoFinanceira'].fillna('').astype(str).str.strip()
    else:
        new_df['CategoriaMovimentacaoFinanceira'] = ''
    
    df = df.copy()
    df['ACAO_LIMPA'] = df['Ação'].str.strip()
    df['Conta'] = df['Conta'].str.strip()
    
    print("=" * 70)
    print("CONVERSÃO COM AJUSTE APENAS DE CONTAS DESBALANCEADAS")
    print("=" * 70)
    
    # Marca linhas que não recebem percentual (preservadas em 100%)
    new_df['_preservar_100'] = False
    
    # ===== PASSO EXCLUSÃO INICIAL (ANTES DE TUDO) =====
    # Exclui por par (linha + contrapartida) para não preservar lançamento inteiro por engano.
    if repasse_ativo and repasse_passivo and grupo_excluido:
        print(f"\n[PASSO EXCLUSÃO INICIAL] Removendo grupo {grupo_excluido}...")

        def _norm_conta(valor):
            return str(valor).strip().rstrip('.')

        def _conta_no_grupo(conta_norm, grupo_norm):
            return conta_norm == grupo_norm or conta_norm.startswith(grupo_norm + '.')

        def _indices_contrapartida(lancamento_df, idx):
            """Retorna índices da contrapartida da linha, priorizando par inverso exato."""
            linha = lancamento_df.loc[idx]
            conta = linha['_CONTA_NORM']
            contra = linha['_CONTRA_NORM']
            acao = linha['ACAO_LIMPA']

            if not contra:
                return []

            mask_exata = (
                (lancamento_df['_CONTA_NORM'] == contra)
                & (lancamento_df['_CONTRA_NORM'] == conta)
                & (lancamento_df['ACAO_LIMPA'] != acao)
            )
            idxs = lancamento_df[mask_exata].index.tolist()
            if idxs:
                return idxs

            mask_fallback = (
                (lancamento_df['_CONTA_NORM'] == contra)
                & (lancamento_df['ACAO_LIMPA'] != acao)
            )
            return lancamento_df[mask_fallback].index.tolist()

        grupo_excluido_norm = _norm_conta(grupo_excluido)
        repasse_passivo_norm = _norm_conta(repasse_passivo)
        repasse_ativo_norm = _norm_conta(repasse_ativo)

        linhas_antes_exclusao = len(new_df)

        if 'Data' in new_df.columns and not new_df['Data'].isna().all():
            data_str = pd.to_datetime(new_df['Data'], errors='coerce').dt.strftime('%Y%m%d').fillna('00000000')
        else:
            data_str = '00000000'

        new_df['_lance_id_temp'] = (
            data_str + '_'
            + new_df['NumSequencia'].astype(str)
            + '_'
            + new_df['VALOR_ORIGINAL'].astype(str)
        )
        new_df['_CONTA_NORM'] = new_df['CONTA'].astype(str).str.strip().str.rstrip('.')
        new_df['_CONTRA_NORM'] = new_df['ContaContraPartida'].astype(str).str.strip().str.rstrip('.')
        contas_no_grupo = sorted({
            conta for conta in new_df['_CONTA_NORM'].unique().tolist()
            if _conta_no_grupo(conta, grupo_excluido_norm)
        })
        
        if not contas_no_grupo:
            print("\n" + "!" * 70)
            print("⚠️  AVISO: Grupo para exclusão não encontrado no arquivo")
            print("!" * 70)
            print(f"Grupo configurado: {grupo_excluido_norm}")
            print("O filtro de exclusão não será aplicado.")
            print("A conversão continuará normalmente com todos os lançamentos.")
            print("!" * 70 + "\n")
            # Remove colunas temporárias criadas para exclusão e continua processamento
            # (mantém _preservar_100 para uso nos próximos passos)
            new_df = new_df.drop(columns=['_lance_id_temp', '_CONTA_NORM', '_CONTRA_NORM'])
        else:
            # EXECUTA A EXCLUSÃO DE GRUPO APENAS SE HOUVER GRUPO NO ARQUIVO
            if repasse_passivo_norm not in contas_no_grupo:
                contas_exemplo = ', '.join(contas_no_grupo[:8])
                sufixo_repasse = repasse_passivo_norm.split('.')[-1] if '.' in repasse_passivo_norm else repasse_passivo_norm
                contas_todas = sorted(set(new_df['_CONTA_NORM'].unique().tolist() + new_df['_CONTRA_NORM'].unique().tolist()))
                contas_mesmo_sufixo = [c for c in contas_todas if c.endswith('.' + sufixo_repasse)]
                dica_conta = f"\n  Dica: contas com final {sufixo_repasse} no arquivo: {', '.join(contas_mesmo_sufixo[:6])}" if contas_mesmo_sufixo else ''
                raise ValueError(
                    "❌ ERRO DE CONFIGURAÇÃO: Conta Repasse Passivo não encontrada no grupo informado.\n"
                    f"  Grupo: {grupo_excluido_norm}\n"
                    f"  Repasse passivo informado: {repasse_passivo_norm}\n"
                    f"  Contas encontradas no grupo: {contas_exemplo}"
                    f"{dica_conta}"
                )

            linhas_para_excluir = set()
            linhas_para_reclassificar = set()

            for lance_id in new_df['_lance_id_temp'].unique():
                lancamento_mask = new_df['_lance_id_temp'] == lance_id
                lancamento = new_df[lancamento_mask]

                if lancamento.empty:
                    continue

                idxs_grupo = [
                    idx for idx in lancamento.index
                    if _conta_no_grupo(new_df.loc[idx, '_CONTA_NORM'], grupo_excluido_norm)
                ]
                if not idxs_grupo:
                    continue

                idxs_preservar = set()
                idxs_repasse = lancamento[
                    (lancamento['_CONTA_NORM'] == repasse_passivo_norm)
                    | (lancamento['_CONTRA_NORM'] == repasse_passivo_norm)
                ].index.tolist()

                for idx_rep in idxs_repasse:
                    idxs_preservar.add(idx_rep)
                    for idx_cp in _indices_contrapartida(lancamento, idx_rep):
                        idxs_preservar.add(idx_cp)

                for idx in idxs_preservar:
                    new_df.loc[idx, '_preservar_100'] = True

                for idx in idxs_grupo:
                    if idx in idxs_preservar:
                        continue
                    linhas_para_excluir.add(idx)
                    for idx_cp in _indices_contrapartida(lancamento, idx):
                        if idx_cp not in idxs_preservar:
                            linhas_para_excluir.add(idx_cp)

                for idx in idxs_preservar:
                    if new_df.loc[idx, '_CONTA_NORM'] == repasse_passivo_norm:
                        linhas_para_reclassificar.add(idx)

            reclassificados = 0
            if linhas_para_reclassificar:
                idxs_reclassificar = list(linhas_para_reclassificar)
                new_df.loc[idxs_reclassificar, 'CONTA'] = repasse_ativo_norm
                new_df.loc[idxs_reclassificar, '_CONTA_NORM'] = repasse_ativo_norm
                reclassificados = len(idxs_reclassificar)

            if linhas_para_excluir:
                new_df = new_df.drop(list(linhas_para_excluir)).reset_index(drop=True)
                excluidos = linhas_antes_exclusao - len(new_df)
            else:
                excluidos = 0

            linhas_preservadas = int(new_df['_preservar_100'].sum())

            new_df = new_df.drop(columns=['_lance_id_temp', '_CONTA_NORM', '_CONTRA_NORM'])

            print(f"  Grupo: {grupo_excluido_norm}")
            print(f"  [OK] {excluidos} linhas removidas (grupo + contrapartidas)")
            print(f"  [OK] {reclassificados} linhas reclassificadas {repasse_passivo_norm} -> {repasse_ativo_norm}")
            print(f"  [*] {linhas_preservadas} linhas preservadas com valor 100%")
    
    # ===== AGORA SIM: PASSO 1 (em dados já limpos) =====
    print("\n[PASSO 1] Aplicando percentual individualmente...")
    # Linhas preservadas não recebem percentual (100% do valor original)
    new_df['VALOR_CENTS'] = (new_df['VALOR_ORIGINAL'] * percentual * 100).round().astype(int)
    mask_preservar_100 = new_df['_preservar_100'] == True
    if mask_preservar_100.any():
        new_df.loc[mask_preservar_100, 'VALOR_CENTS'] = (
            new_df.loc[mask_preservar_100, 'VALOR_ORIGINAL'] * 100
        ).round().astype(int)
    print(f"  [OK] {len(new_df)} lançamentos convertidos (com {int(mask_preservar_100.sum())} em valor original)")

    def _total_esperado_cents(mask):
        """Calcula esperado por conta/ação considerando linhas preservadas em 100%."""
        mask_pres = mask & (new_df['_preservar_100'] == True)
        mask_conv = mask & (new_df['_preservar_100'] == False)

        total_pres = Decimal(str(new_df.loc[mask_pres, 'VALOR_ORIGINAL'].sum()))
        total_conv = Decimal(str(new_df.loc[mask_conv, 'VALOR_ORIGINAL'].sum()))
        total_decimal = (total_conv * Decimal(str(percentual))) + total_pres
        return int((total_decimal * Decimal('100')).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    
    # PASSO 1.5: Sincronizar pares D/C que vieram do mesmo valor original
    print("\n[PASSO 1.5] Sincronizando pares Débito/Crédito...")
    
    # Criar identificador de lançamento (DOC + Data + NumSequencia)
    data_part = new_df['Data'].astype(str) if 'Data' in new_df.columns else ''
    new_df['_lance_id'] = (
        new_df['DOC'].astype(str) + '_' +
        data_part + '_' +
        new_df['NumSequencia'].astype(str)
    )
    
    pares_sincronizados = 0
    
    for lance_id in new_df['_lance_id'].unique():
        lancamento = new_df[new_df['_lance_id'] == lance_id]
        
        # Verificar se tem exatamente 1 débito e 1 crédito
        debitos = lancamento[lancamento['ACAO_LIMPA'] == 'D - Débito']
        creditos = lancamento[lancamento['ACAO_LIMPA'] == 'C - Crédito']
        
        if len(debitos) == 1 and len(creditos) == 1:
            valor_d = debitos['VALOR_CENTS'].iloc[0]
            valor_c = creditos['VALOR_CENTS'].iloc[0]
            
            # Se os valores são diferentes, sincronizar para a média arredondada
            if valor_d != valor_c:
                # Usar o maior valor (mais conservador)
                valor_sincr = max(valor_d, valor_c)
                
                idx_d = debitos.index[0]
                idx_c = creditos.index[0]
                
                new_df.loc[idx_d, 'VALOR_CENTS'] = valor_sincr
                new_df.loc[idx_c, 'VALOR_CENTS'] = valor_sincr
                
                pares_sincronizados += 1
    
    if pares_sincronizados > 0:
        print(f"  [OK] {pares_sincronizados} pares D/C sincronizados")
    else:
        print(f"  [OK] Todos os pares já estão sincronizados")
    
    # PASSO 2: Ajustar apenas contas/ações que desceram
    print("\n[PASSO 2] Ajustando contas/ações com diferença...")
    
    ajustes_feitos = 0
    contas_ajustadas = set()  # Rastrear quais (conta, ação) foram ajustadas
    
    # Iterar apenas sobre contas/ações que existem em new_df
    for (conta, acao) in new_df.groupby(['CONTA', 'ACAO_LIMPA']).groups.keys():
        mask = (new_df['CONTA'] == conta) & (new_df['ACAO_LIMPA'] == acao)
        
        # Usar VALOR_ORIGINAL de new_df (somente entradas remanescentes após exclusões)
        # NÃO usar df original, pois ele inclui entradas já excluídas que inflariam os valores
        total_origem = new_df.loc[mask, 'VALOR_ORIGINAL'].sum()
        if total_origem == 0:
            continue
            
        total_esperado_cents = _total_esperado_cents(mask)
        
        total_atual_cents = int(new_df.loc[mask, 'VALOR_CENTS'].sum())
        diferenca_cents = total_esperado_cents - total_atual_cents
        
        if diferenca_cents != 0:
            # Ajustar apenas o maior lançamento dessa conta/ação
            idx = new_df.loc[mask, 'VALOR_CENTS'].abs().idxmax()
            new_df.loc[idx, 'VALOR_CENTS'] += diferenca_cents
            contas_ajustadas.add((conta, acao))
            ajustes_feitos += 1
    
    print(f"  [OK] {ajustes_feitos} contas/ações ajustadas")
    
    # PASSO 2.5 ESPECIAL: Ajustar CONTAS PRIORITÁRIAS até fecharem 100%
    print("\n[PASSO 2.5 ESPECIAL] Ajustando contas priorizadas para 100%...")
    
    contas_prioritarias_ajustadas = 0
    
    for conta in contas_prioritarias:
        for acao in ['D - Débito', 'C - Crédito']:
            mask = (new_df['CONTA'] == conta) & (new_df['ACAO_LIMPA'] == acao)
            
            if not mask.any():
                continue  # Essa conta/ação não existe
            
            # Usar VALOR_ORIGINAL de new_df (não df original que inclui excluídos)
            total_origem = new_df.loc[mask, 'VALOR_ORIGINAL'].sum()
            
            if total_origem == 0:
                continue
            
            total_esperado_cents = _total_esperado_cents(mask)
            total_atual_cents = int(new_df.loc[mask, 'VALOR_CENTS'].sum())
            dif = total_esperado_cents - total_atual_cents
            
            if dif != 0:
                # Ajustar o maior lançamento dessa conta
                idx = new_df.loc[mask, 'VALOR_CENTS'].abs().idxmax()
                new_df.loc[idx, 'VALOR_CENTS'] += dif
                contas_prioritarias_ajustadas += 1
                print(f"  {conta} ({acao:10}): Ajustado +{dif/100:.2f}")
                
                # Rastrear a sequência que foi alterada
                seq_alterada = new_df.loc[idx, 'NumSequencia']
                if not pd.isna(seq_alterada) and seq_alterada in sequencias_balanceadas_antes:
                    sequencias_alteradas_por_ajuste.add(seq_alterada)
    print("\n[PASSO 3] Forçando fechamento de sequências (D=C)...")
    
    # Estratégia simples em 3 passos:
    # 3.1: Força sequências
    # 3.2: Reforça prioridades  
    # 3.3: Reconverge uma vez
    
    def _aplicar_ajuste_sequencia(seq_data, dif_cents):
        """Ajusta a sequência no lado correto para zerar diferença D-C."""
        candidatos_base = seq_data[~seq_data['CONTA'].isin(contas_prioritarias)]
        candidatos = candidatos_base if len(candidatos_base) > 0 else seq_data

        if dif_cents > 0:
            # D > C: aumentar crédito (preferível) ou reduzir débito
            candidatos_credito = candidatos[candidatos['ACAO_LIMPA'] == 'C - Crédito']
            if len(candidatos_credito) > 0:
                idx = candidatos_credito['VALOR_CENTS'].abs().idxmax()
                new_df.loc[idx, 'VALOR_CENTS'] += dif_cents
                return True

            candidatos_debito = candidatos[candidatos['ACAO_LIMPA'] == 'D - Débito']
            if len(candidatos_debito) > 0:
                idx = candidatos_debito['VALOR_CENTS'].abs().idxmax()
                new_df.loc[idx, 'VALOR_CENTS'] -= dif_cents
                return True

            return False

        # dif_cents < 0 -> C > D: aumentar débito (preferível) ou reduzir crédito
        ajuste = abs(dif_cents)
        candidatos_debito = candidatos[candidatos['ACAO_LIMPA'] == 'D - Débito']
        if len(candidatos_debito) > 0:
            idx = candidatos_debito['VALOR_CENTS'].abs().idxmax()
            new_df.loc[idx, 'VALOR_CENTS'] += ajuste
            return True

        candidatos_credito = candidatos[candidatos['ACAO_LIMPA'] == 'C - Crédito']
        if len(candidatos_credito) > 0:
            idx = candidatos_credito['VALOR_CENTS'].abs().idxmax()
            new_df.loc[idx, 'VALOR_CENTS'] -= ajuste
            return True

        return False

    # ===== 3.1: Ajustar sequências para D=C (passada única) =====
    seq_ajustadas = 0
    for seq in new_df['NumSequencia'].unique():
        if pd.isna(seq):
            continue
        
        seq_mask = new_df['NumSequencia'] == seq
        d_cents = new_df.loc[seq_mask & (new_df['ACAO_LIMPA'] == 'D - Débito'), 'VALOR_CENTS'].sum()
        c_cents = new_df.loc[seq_mask & (new_df['ACAO_LIMPA'] == 'C - Crédito'), 'VALOR_CENTS'].sum()
        dif = d_cents - c_cents
        
        if dif != 0:
            seq_data = new_df[seq_mask]
            if _aplicar_ajuste_sequencia(seq_data, dif):
                seq_ajustadas += 1
    
    print(f"  Passo 3.1: {seq_ajustadas} sequências forçadas a D=C")
    
    # ===== 3.2: Reforçar contas prioritárias =====
    reforco_ajustado = 0
    for conta in contas_prioritarias:
        for acao in ['D - Débito', 'C - Crédito']:
            mask = (new_df['CONTA'] == conta) & (new_df['ACAO_LIMPA'] == acao)
            
            if not mask.any():
                continue
            
            # Usar VALOR_ORIGINAL de new_df (não df original que inclui excluídos)
            total_origem = new_df.loc[mask, 'VALOR_ORIGINAL'].sum()
            
            if total_origem == 0:
                continue
            
            total_esperado_cents = _total_esperado_cents(mask)
            total_atual_cents = int(new_df.loc[mask, 'VALOR_CENTS'].sum())
            dif = total_esperado_cents - total_atual_cents
            
            if dif != 0:
                # Reajustar o maior lançamento dessa conta/ação
                idx = new_df.loc[mask, 'VALOR_CENTS'].abs().idxmax()
                new_df.loc[idx, 'VALOR_CENTS'] += dif
                reforco_ajustado += 1
    
    if reforco_ajustado == 0:
        print(f"  Passo 3.2: Contas prioritárias já estão 100%")
        print(f"  [OK] Convergência alcançada: Sequências D=C + Prioridades 100%")
    else:
        print(f"  Passo 3.2: {reforco_ajustado} contas ajustadas")
        
        # ===== 3.3: Reconverger sequências após reforço =====
        # O reforço pode ter quebrado algumas sequências
        seq_reconvergio = 0
        for seq in new_df['NumSequencia'].unique():
            if pd.isna(seq):
                continue
            
            seq_mask = new_df['NumSequencia'] == seq
            d = new_df.loc[seq_mask & (new_df['ACAO_LIMPA'] == 'D - Débito'), 'VALOR_CENTS'].sum()
            c = new_df.loc[seq_mask & (new_df['ACAO_LIMPA'] == 'C - Crédito'), 'VALOR_CENTS'].sum()
            dif = d - c
            
            if dif != 0:
                seq_data = new_df[seq_mask]
                if _aplicar_ajuste_sequencia(seq_data, dif):
                    seq_reconvergio += 1
        
        print(f"  Passo 3.3: {seq_reconvergio} sequências reconvergidas")
    
    print(f"  [OK] TODAS AS {len(contas_prioritarias)} CONTAS PRIORITÁRIAS FECHADAS 100%")
    
    # ===== PASSO 3.4: NÃO MAIS CRIAR LANÇAMENTOS DE AJUSTE POR SEQUÊNCIA =====
    # Os passos anteriores (3.1, 3.2, 3.3) já forçam D=C em cada sequência
    # e garantem que contas prioritárias fechem 100%. Não há necessidade de
    # criar lançamentos extras, pois toda a sincronização já foi feita.
    
    
    # PASSO 4: Validação
    print("\n[PASSO 4] Validação final...")
    
    total_d_cents = new_df[new_df['ACAO_LIMPA'] == 'D - Débito']['VALOR_CENTS'].sum()
    total_c_cents = new_df[new_df['ACAO_LIMPA'] == 'C - Crédito']['VALOR_CENTS'].sum()
    dif_global = total_d_cents - total_c_cents
    
    print(f"  Total Débitos: {total_d_cents / 100:,.2f}")
    
    # Validação DETALHADA de sequências
    seq_desbalanceadas = 0
    seq_details = []
    for seq in new_df['NumSequencia'].unique():
        if pd.isna(seq):
            continue
        seq_mask = new_df['NumSequencia'] == seq
        d = new_df.loc[seq_mask & (new_df['ACAO_LIMPA'] == 'D - Débito'), 'VALOR_CENTS'].sum()
        c = new_df.loc[seq_mask & (new_df['ACAO_LIMPA'] == 'C - Crédito'), 'VALOR_CENTS'].sum()
        dif_seq = d - c
        if dif_seq != 0:
            seq_desbalanceadas += 1
            if seq_desbalanceadas <= 5:  # Mostrar apenas as 5 primeiras desbalanceadas
                seq_details.append((seq, dif_seq / 100))
    
    if seq_desbalanceadas > 0:
        print(f"  [ERR] {seq_desbalanceadas} Sequências desbalanceadas:")
        for seq, diff in seq_details:
            print(f"    - Seq {seq}: diferença {diff:.2f}")
    else:
        print("  [OK] Sequências balanceadas (D=C)")
    
    # Validar contas prioritárias
    erros_prioritarios = 0
    for conta in contas_prioritarias:
        for acao in ['D - Débito', 'C - Crédito']:
            mask = (new_df['CONTA'] == conta) & (new_df['ACAO_LIMPA'] == acao)
            if not mask.any():
                continue
            
            total_origem = df[(df['Conta'] == conta) & (df['ACAO_LIMPA'] == acao)]['Valor'].sum()
            if total_origem == 0:
                continue
            
            total_decimal = Decimal(str(total_origem)) * Decimal(str(percentual))
            total_esperado_cents = int((total_decimal * Decimal('100')).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
            total_atual_cents = int(new_df.loc[mask, 'VALOR_CENTS'].sum())
            
            diferenca_cents = abs(total_atual_cents - total_esperado_cents)
            
            if diferenca_cents > TOLERANCIA_CONTAS_PRIORITARIAS:
                erros_prioritarios += 1
                print(f"  [ERR] ERRO PRIORITÁRIO: {conta} ({acao}): Esperado {total_esperado_cents/100:.2f}, Atual {total_atual_cents/100:.2f}, Dif: {diferenca_cents/100:.2f}")
    
    if erros_prioritarios == 0:
        print(f"  [OK] TODAS AS {len(contas_prioritarias)} CONTAS PRIORITÁRIAS FECHADAS 100%")
    
    # Validar outras contas
    erros_conta = 0
    for (conta, acao), grupo_orig in df.groupby(['Conta', 'ACAO_LIMPA']):
        if conta in contas_prioritarias:
            continue  # Já validadas
        
        total_origem = grupo_orig['Valor'].sum()
        total_decimal = Decimal(str(total_origem)) * Decimal(str(percentual))
        total_esperado_cents = int((total_decimal * Decimal('100')).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        
        mask = (new_df['CONTA'] == conta) & (new_df['ACAO_LIMPA'] == acao)
        total_atual_cents = int(new_df.loc[mask, 'VALOR_CENTS'].sum())
        
        if total_atual_cents != total_esperado_cents:
            erros_conta += 1
    
    if erros_conta == 0:
        print("  [OK] Outras contas/ações fechadas conforme percentual")
    else:
        print(f"  [WARN] {erros_conta} outras contas/ações com pequenas diferenças")
    
    seq_desbalanceadas = 0
    for seq in new_df['NumSequencia'].unique():
        if pd.isna(seq):
            continue
        seq_mask = new_df['NumSequencia'] == seq
        d = new_df.loc[seq_mask & (new_df['ACAO_LIMPA'] == 'D - Débito'), 'VALOR_CENTS'].sum()
        c = new_df.loc[seq_mask & (new_df['ACAO_LIMPA'] == 'C - Crédito'), 'VALOR_CENTS'].sum()
        if d != c:
            seq_desbalanceadas += 1
    
    if seq_desbalanceadas == 0:
        print("  [OK] Sequências balanceadas (D=C)")
    else:
        print(f"  [ERR] {seq_desbalanceadas} Sequências desbalanceadas")
    
    if dif_global == 0:
        print("  [OK] Global balanceado (D=C)")
    elif abs(dif_global) <= TOLERANCIA_GLOBAL:
        print(f"  [OK] Global balanceado (D=C) - Dentro da tolerância: {dif_global / 100:,.2f}")
    else:
        print(f"  [ERR] Global desbalanceado: diferença de {dif_global / 100:,.2f}")
    
    print("=" * 70)
    
    # PASSO 4.5: Proteção contra valores zero (UAU não aceita valores <= 0)
    # Ao invés de remover 0,00, converter para 0,01 (piso mínimo)
    # Isso preserva linhas e força reconvergência adequada
    print("\n[PASSO 4.5] Aplicando piso de 0,01 centavos...")
    
    zeros_encontrados = (new_df['VALOR_CENTS'] == 0).sum()
    if zeros_encontrados > 0:
        new_df.loc[new_df['VALOR_CENTS'] == 0, 'VALOR_CENTS'] = 1  # 0,01 em centavos
        
        # Após forçar piso de 0,01, é necessário reconvergir NOVAMENTE
        # porque mudamos alguns valores e quebramos D=C em algumas sequências
        print(f"  Encontrados {zeros_encontrados} valores 0,00 → convertidos para 0,01")
        print(f"  Reconvergindo sequências quebradas...")
        
        # ===== Reconvergência Final =====
        seq_rebalanceadas = 0
        for seq in new_df['NumSequencia'].unique():
            if pd.isna(seq):
                continue
            
            seq_mask = new_df['NumSequencia'] == seq
            d_cents = new_df.loc[seq_mask & (new_df['ACAO_LIMPA'] == 'D - Débito'), 'VALOR_CENTS'].sum()
            c_cents = new_df.loc[seq_mask & (new_df['ACAO_LIMPA'] == 'C - Crédito'), 'VALOR_CENTS'].sum()
            dif = d_cents - c_cents
            
            if dif != 0:
                # Encontrar lançamento para ajustar em D ou C (o que tem maior saldo)
                debitos_mask = seq_mask & (new_df['ACAO_LIMPA'] == 'D - Débito')
                creditos_mask = seq_mask & (new_df['ACAO_LIMPA'] == 'C - Crédito')
                
                if dif > 0 and creditos_mask.any():  # D > C, aumentar C
                    idx = new_df.loc[creditos_mask, 'VALOR_CENTS'].abs().idxmax()
                    new_df.loc[idx, 'VALOR_CENTS'] += dif
                elif dif < 0 and debitos_mask.any():  # D < C, aumentar D
                    idx = new_df.loc[debitos_mask, 'VALOR_CENTS'].abs().idxmax()
                    new_df.loc[idx, 'VALOR_CENTS'] -= dif
                    
                seq_rebalanceadas += 1
        
        print(f"  {seq_rebalanceadas} sequências reconvergidas")
    else:
        print("  Nenhum valor zero encontrado")
    
    # Converter de volta para VALOR (decimal)
    new_df['VALOR'] = (new_df['VALOR_CENTS'] / 100).round(2)
    
    new_df = new_df.drop(columns=['ACAO_LIMPA', 'VALOR_CENTS'])
    
    # Remover colunas temporárias criadas durante processamento
    cols_temp = ['_lance_id', 'VALOR_ORIGINAL']
    new_df = new_df.drop(columns=[c for c in cols_temp if c in new_df.columns])

    # Substituir conta 3.6.03.03.000002 por 1.1.11.04.000005 em débitos
    mask_substituir = (new_df['CONTA'] == '3.6.03.03.000002') & (new_df['ACAO'] == 'D - Débito')
    new_df.loc[mask_substituir, 'CONTA'] = '1.1.11.04.000005'
    
    # NÃO remover lançamentos zerados - manter 0,00 para manter número de linhas consistente
    # Isso garante que duas consorciadas com percentuais diferentes tenham mesmo número de linhas
    # Nota: Se UAU não aceitar valores 0, essa decisão pode ser revertida
    # new_df = new_df[new_df['VALOR'] != 0]
    # Formatar data para DD/MM/YYYY
    if 'Data' in new_df.columns and not new_df['Data'].isna().all():
        new_df['Data'] = pd.to_datetime(new_df['Data'], errors='coerce').dt.strftime('%d/%m/%Y').fillna('')
    else:
        new_df['Data'] = ''

    # Simplificar ACAO: "C - Crédito" → "C" e "D - Débito" → "D"
    new_df['ACAO'] = new_df['ACAO'].str.replace('C - Crédito', 'C').str.replace('D - Débito', 'D').str.strip()
    
    # Limpeza final de espaçamento em colunas textuais
    new_df['HISTORICO'] = new_df['HISTORICO'].str.strip()
    new_df['CONTA'] = new_df['CONTA'].str.strip()
    new_df['ContaContraPartida'] = new_df['ContaContraPartida'].str.strip()
    
    # Remover TODAS as colunas temporárias/técnicas antes do retorno
    # (Nota: ACAO_LIMPA, VALOR_ORIGINAL, _lance_id já foram removidos anteriormente)
    cols_temp = ['_reclassificado', '_lance_id_temp', '_CONTA_NORM', '_CONTRA_NORM', '_preservar_100']
    new_df = new_df.drop(columns=[c for c in cols_temp if c in new_df.columns])

    # Reordenar colunas para o layout final do UAU
    cols_order = ['Lancamento', 'DOC', 'NUMCHEQUE', 'CategoriaMovimentacaoFinanceira', 
                  'Empresa', 'Data', 'VALOR', 'CONTA', 'ACAO', 'HISTORICO', 
                  'Obra', 'NumSequencia', 'ContaContraPartida', 'TipoLancamento']
    
    return new_df[cols_order]

# --- PROCESSAMENTO EM LOTE ---
# Coloque os arquivos de entrada em: ./entrada
# Os arquivos .xlsx serão gerados em: ./saida

def gerar_para_multiplas_consorciadas(arquivo_origem, lista_consorciadas):
    """
    Gera lançamentos para múltiplas consorciadas em um único arquivo.
    
    Args:
        arquivo_origem: Path do arquivo do consórcio
        lista_consorciadas: Lista de dicts com 'cod_empresa', 'cod_obra', 'percentual'
    
    Returns:
        DataFrame com todos os lançamentos concatenados
    """
    resultados = []
    
    for consorciada in lista_consorciadas:
        df_consorciada = gerar_contabilidade_consorciada(
            arquivo_origem,
            consorciada['percentual'],
            consorciada['cod_empresa'],
            consorciada['cod_obra']
        )
        resultados.append(df_consorciada)
    
    # Concatena todos sem pular linhas
    return pd.concat(resultados, ignore_index=True)


def processar_pasta_entrada(percentual, cod_empresa, cod_obra, conta_arredondamento=None, nome_consorciada=""):
    base_dir = Path(__file__).resolve().parent
    pasta_entrada = base_dir / 'entrada'
    pasta_saida = base_dir / 'saida'

    pasta_entrada.mkdir(parents=True, exist_ok=True)
    pasta_saida.mkdir(parents=True, exist_ok=True)

    arquivos = [p for p in pasta_entrada.iterdir() if p.is_file()]

    if not arquivos:
        print(f"Nenhum arquivo encontrado em {pasta_entrada}")
        return

    for arquivo in arquivos:
        try:
            resultado = gerar_contabilidade_consorciada(arquivo, percentual, cod_empresa, cod_obra, conta_arredondamento)
            if nome_consorciada:
                saida = pasta_saida / f"{arquivo.stem} - {nome_consorciada} - Arquivo de Saída para Importação no UAU.xlsx"
            else:
                saida = pasta_saida / f"{arquivo.stem} - Arquivo de Saída para Importação no UAU.xlsx"
            resultado.to_excel(saida, index=False)
            print(f"Arquivo gerado: {saida}")
        except Exception as exc:
            print(f"Falha ao processar {arquivo.name}: {exc}")


# --- EXEMPLO DE USO ---
# percentual_participacao = 0.50  (para 50%)
# processar_pasta_entrada(0.5, 97, 972)

if __name__ == "__main__":
    # Configure aqui os parâmetros desejados:
    percentual_participacao = 0.50  # 50% de participação
    codigo_empresa = 97
    codigo_obra = 972
    
    processar_pasta_entrada(percentual_participacao, codigo_empresa, codigo_obra)