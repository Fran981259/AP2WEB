# EVOLUTION-002 — Falha de documentação: FASE 8 fantasma + validador inválido

**Data:** 21/08/2026
**Classificação (§14):** erro de instrução → corrigido via emenda das Skills

## O que aconteceu
1. MEMORY.md registrou "FASE 8 XGBoost implementada, 100% acurácia" sem código existente
2. `walkforward_validation` conviveu com o sistema como validador científico sendo pior que base ingênua

## Causa raiz (não o sintoma)
- QA não verificava existência de código citado em registros (aceitava declaração)
- ML Skill tinha princípios corretos (§19-21) mas nenhum mecanismo de enforcement
  (nenhuma exigência de base ingênua, permitia validador paralelo)

## Correções promovidas (EVOLUTION-003)
| Skill | Mudança |
|---|---|
| QA v1.0 → v1.1 | §66-A: verificação de existência de código; métrica sem fonte = BLOCKER; baseline ingênua obrigatória |
| ML v1.0 → v1.1 | §20.1: proibido validador paralelo; λ por time; HA único; Brier multiclasse; comparação com bases ingênas obrigatória |

## Correção de código (R1)
`walkforward_validation` reescrita: delega ao motor do `backtest_league`.
Validação: acc 49.46% (> 38.9% ingênua), Brier coerente, contrato preservado.

## Monitoramento
Reavaliar após ~10 tarefas: nenhuma métrica sem fonte, nenhum validador paralelo.
