# FEATURE-001 — Fator de colocação/tabela no modelo

**Status:** 🟨 *backlog* — registrado, não implementado
**Registrado:** 21/08/2026 (sessão XGBoost Engine)
**Decisão preliminar:** implementar **ao final** dos módulos (post-FASE 10), para não bloquear o pipeline de validação já estável

## Justificativa observada
- A intuição é válida: um time melhor colocado vs pior colocado carrega signal mesurável
- Gap detectado: verificação no código confirma **nenhuma feature de colocação/classificação/tabela** existe
  em Poisson (`feature_engine`/`prediction`) nem no XGBoost (`xgb_engine.FEATURES`)
- XGBoost `ppg` (pontos nos últimos 10 jogos) é prima distante, mas captura *forma recente*, não posição acumulada

## Coisitá existente (não descartar)
- Forma deslizante + xG + fator mando já capturam parcialmente "time forte"
- Colocação acumulada é quase consequência → risco de redundância
- Respeita a disciplina as_of (FASE 4): posição calculada até `kickoff_datetime` é **leakage-safe**

## Plano de implementação (quando aprovado)
1. Adicionar no `xgb_engine.build_dataset` dois features: `posição_acumulada_h/a`, `pontos_acumulados_h/a` (cumulativo até o jogo, janela as_of)
2. Avaliar via `compare_models` (walk-forward idêntico §20.1) → ganho em **Brier/LogLoss**
3. Critério de aceitação (BASE.md §27): melhora métrica > mínimo detectável
4. Não retroceder se não houver ganho científico
