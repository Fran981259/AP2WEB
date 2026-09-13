# Protocolo de avaliacao cientifica

## Regra de comunicacao

Nenhuma metrica de desempenho, calibracao ou recomendacao de mercado e publicada como validada sem executar este protocolo sobre um snapshot versionado. Antes disso, o produto deve apresentar o recurso como experimental e apenas informativo.

## Dados e corte temporal

1. Registrar hash/snapshot, ligas, fontes, periodo e horario de extracao.
2. Ordenar todas as partidas pelo horario de inicio; nunca usar dados posteriores ao instante da previsao.
3. Reservar um holdout final congelado, nao consultado durante selecao de features, hiperparametros ou limiares.
4. Aplicar validacao walk-forward somente no periodo anterior ao holdout.

## Comparacao e metricas

1. Comparar contra bases explicitas: frequencia da liga e Poisson simples.
2. Medir log loss, Brier multiclass, RPS e calibracao por classe para 1X2; reportar tamanho amostral e intervalos bootstrap.
3. Separar desempenho por liga, temporada e faixa de confianca; resultados agregados nao substituem estratos com baixa amostra.
4. Para mercados, tratar odds como dado temporal: registrar timestamp, fonte e fechamento. Nao inferir valor sem odds disponiveis antes do kickoff.

## Promocao

Uma versao so pode sair de experimental quando supera a baseline no walk-forward e no holdout congelado, sem degradacao material de calibracao, e quando o relatorio reproduzivel e os artefatos do modelo foram arquivados. Caso contrario, manter o rotulo experimental e nao comunicar expectativa de retorno.
