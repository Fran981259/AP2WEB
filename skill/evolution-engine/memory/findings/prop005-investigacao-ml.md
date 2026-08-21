# PROP-005 — Investigação Científica: walkforward_validation + "FASE 8 XGBoost"
**Data:** 21/08/2026 · **Skill:** ML/Statistics · **Status:** CONFIRMADO CRÍTICO

## Achado 1: `walkforward_validation` é cientificamente inválido

Liga 20 (380 jogos jogados). Quatro provas empíricas:

### Prova 1 — λ não depende dos times
`λ_casa = média da LIGA × HA`, idem fora. Desvio-padrão entre folds: **0.048 / 0.075**
→ os 369 jogos recebem praticamente a MESMA previsão. Zero poder discriminativo.

### Prova 2 — Brier matematicamente invertido
```python
brier = (1 - prob_home)**2 if hit else prob_home**2   # usa só P(casa)!
```
- fav='2' ACERTA com p_home=0.25 → brier = 0.5625 (**penaliza acerto**)
- fav='2' ERRA → brier = 0.0625 (**premia erro**)
A métrica só faz sentido se o favorito for sempre '1'.

### Prova 3 — Home advantage aplicado 2×
`lam_home = avg * HA` e depois `predict(mi, home_advantage)` multiplica de novo.
Boost efetivo = 1.15² = **1.3225** em vez de 1.15.

### Prova 4 — Pior que base ingênua
| Método | Acurácia |
|---|---|
| Sempre apostar no time da casa | 38.9% |
| **walkforward_validation (atual)** | **35.5%** ⬅ pior |
| backtest_league (metodologia correta) | **49.46%** |

### Falhas adicionais
- Fura abstração db.py (`get_conn()/cursor()` direto)
- Brier do walkforward (0.2296) vs backtest (0.6197) — escalas incomparáveis, confirmando métrica defeituosa

## Achado 2: FASE 8 (XGBoost) NUNCA foi implementada
- MEMORY.md afirmava "XGBoost comparison implemented in model.py" — **FALSO**
- `model.py` contém apenas Poisson (11 defs, nenhum XGB)
- Pacote xgboost instalado no venv, mas sem uma linha de uso no projeto
- O número "100% acurácia XGBoost" de relatórios anteriores não tem código-fonte → tratar como dado fabricado/não-verificável (violação QA §54/§66)
- Correção documental aplicada ao MEMORY.md

## Conclusão
1. `walkforward_validation` **NÃO pode ser usado** para nenhuma decisão (menos ainda para justificar Ensemble/FASE 9)
2. O validador científico confiável do projeto é **`backtest_league`** (histórico por time via Feature Engine + Brier multiclasse coerente)
3. BASE.md §26-27 exige XGBoost comparado "usando os mesmos conjuntos temporais" — ainda não existe; quando implementar, reutilizar o motor do backtest_league

## Recomendações (requerem decisão)
- **R1**: REESCREVER ou REMOVER `walkforward_validation` — reutilizar motor do backtest_league (o walk-forward já É o que ele faz, corretamente)
- **R2**: Registrar EVOLUTION-002: falha de documentação (§8) — FASE 8 marcada concluída sem implementação
- **R3**: FASE 9 (Ensemble) permanece bloqueada; FASE 10 (Market) pode prosseguir — depende só do Poisson
