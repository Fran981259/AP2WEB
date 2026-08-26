# MEMORY — AP2WEB

> Memória de trabalho do projeto. Sempre que voltarmos a trabalhar, ler este
> arquivo para saber onde paramos. Manter atualizado ao final de cada sessão.

## Última sessão (26/08/2026)

### ✅ Propostas Otimizadas (FASE 12b)
- **Problema**: 1X2 estava 26.1% (pior que aleatório 33%), GOLS 5.2%
- **Causa**: propostas geradas para todos os jogos sem filtro de confiança
- **Solução**: thresholds mínimos por tipo (1X2≥55%, GOLS≥65%, BTTS≥58%, PLACAR≥8%)
- **Resultado**: 1X2→54.7%, GOLS→72.2%, BTTS→58.8%, PLACAR→15.2%
- **Mudanças**: `model.py:proposals()` + `backtest_engine.py:_backtest_detailed()`

### ✅ Auditoria Técnica Completa (Skill Sports Analytics)
- **§4.1 Integridade Temporal**: 3 bugs de leakage em `prediction.py:_build()` — CORRIGIDOS
  - Bug 1 (ALTA): `_compare()` sem `as_of_timestamp` → linhas 231-232
  - Bug 2 (MÉDIA): `_recent_form()` sem `as_of_timestamp` → linha 240
  - Bug 3 (MÉDIA): `_h2h()` sem `as_of_timestamp` → linha 242
- **§4.2 Grafos/Espacial**: Sem SoS, sem rede de confrontos (parcial)
- **§4.3 Calibração**: Poisson + Brier/LogLoss corretos (9/10)
- **§4.4 Desempenho**: P2 (LRU cache) e P3 (connection pool) — CORRIGIDOS

### ✅ Auditoria Matemática (Skill Advanced Algebra Engine)
- **Poisson PMF**: 100% real — fórmula padrão
- **Score matrix**: 100% real — produto de Poissons
- **Dixon-Coles**: IMPLEMENTADO — fator τ para placares baixos
- **Bayesian updating**: IMPLEMENTADO — Gamma-Poisson conjugate priors
- **XGBoost**: Real mas features fracas (12 variáveis básicas)
- **Kelly/EV**: 100% real
- **Fake**: Cantos λ×5.2 e propostas if/else (heurísticas)

### ✅ Dixon-Coles Implementado
- **`model.py`**: `dixon_coles_tau(i, j, lam_home, lam_away, rho)` + `build_matrix(rho)` + `predict(rho)`
- **Correção τ**: ajusta P(0-0), P(1-0), P(0-1), P(1-1) com fator `1 + ρ×Δ`
- **Grid search**: 6 valores de ρ `[0, -0.05, -0.10, -0.13, -0.15, -0.20]`
- **Total combos por liga**: 3×3×6×6 = 324 (antes: 54)
- **Calibração**: 31 ligas recalibradas com ρ otimizado

### ✅ Bayesian Updating Implementado
- **`bayesian.py`**: `BayesianEngine`, `TeamBayesianState`
- **Prior**: Gamma(α=1.3, β=5.0) — média ~1.3 gols/jogo
- **Update**: `α += gols, β += 1` por jogo observado
- **Reports**: média posterior, desvio padrão, intervalo de credibilidade 95%
- **Status**: Pronto para uso, não integrado ao prediction path (opt-in)

### ✅ Calibração Dixon-Coles Resultados
- **10 de 31 ligas** melhoraram com ρ ≠ 0
- **21 ligas** mantiveram ρ=0 (Poisson puro melhor)
- **Destaques**: Premier League ρ=-0.20, Serie A ρ=-0.20, Bundesliga ρ=-0.20
- **Melhoria média**: Brier +0.005 nas ligas onde Dixon-Coles ajuda

### ✅ Correções de Performance
- **P2**: LRU cache (2048) em `compute_team_stats` via tuple-hash
- **P3**: `psycopg_pool.ConnectionPool` (min=2, max=10) para Postgres
- **P3**: Shutdown hook fecha pool em `main.py`

---

## Status Atual do Projeto

### 📊 Base de Dados
- **57 ligas** sincronizadas no banco
- **6.066+ jogos jogados** · **~5.000+ agendados**
- **83% dos jogos com xG**
- **31 ligas calibradas** (com Dixon-Coles ρ otimizado)
- Schema: `leagues`, `teams`, `matches`, `predictions`, `league_models`, `users`
- **Últimas syncs** (26/08/2026): MLS(90), Premier League(18), Serie A(20), Ligue 1(23), Bundesliga(24), Argentina LP(65)

### 🧠 Motor de Previsão
- **Modelo**: Poisson V3 (Dixon-Coles) — ρ calibrado por liga
- **Calibração**: 31 ligas, 324 combos (feature×window×HA×ρ)
- **Walk-forward**: backtest honesto sem data leakage
- **Comparação**: XGBoost real (12 features) vs Poisson — Poisson vence
- **Ensemble**: bloqueado (XGBoost não supera Poisson)

### 📈 Monitor de Evolução
- **31 ligas rastreadas** (todas com ≥30 jogos)
- **Baseline**: regressão=PASS, logloss real (1.005–1.091)
- **Evolução**: % mudança desde primeira medição (acc/brier)
- **Histórico**: append-only em `evolution_history.jsonl`

### 🏪 Market Engine (FASE 10)
- `market.py`: fair odds, market odds (vig 4%), EV, kelly_full, value_bets
- Endpoints: `/api/market/{match_id}`, `/api/market/league/{league_id}`

### 🛡️ Risk Engine (FASE 11)
- `risk.py`: Kelly fracionado, limites de exposição, score de confiança
- Endpoints: `/api/risk/{match_id}`, `/api/risk/league/{league_id}`, `/api/risk/portfolio`
- Configuração: kelly_fraction, bankroll, max_stake_pct, max_exposure_pct, max_daily_pct
- Score A/B/C/D baseado em edge + probabilidade + kelly
- Frontend: painel interativo no PredictionView

### 🔬 Bayesian Engine (NOVO)
- `bayesian.py`: Gamma-Poisson conjugate priors para team strength
- `BayesianEngine`: update por jogo, lambdas bayesianos, credible intervals
- `build_bayesian_engine_from_history()`: popula engine a partir do DB
- **Status**: Pronto para uso, não integrado ao prediction path ainda

### 🔬 Backtest Engine (FASE 12)
- **`backtest_engine.py`**: ciclo contínuo de backtest, CV temporal e meta-learning
- **3 componentes**: TemporalCV (K-fold temporal), MetaLearner (Bayesian opt), BacktestLoop (background)
- **MetaLearner**: scikit-optimize (gp_minimize) para sugerir hiperparâmetros
- **Persistência**: `data/meta_learner.json`, `data/backtest_state.json`, `data/backtest_history.jsonl`
- **Reconstrução**: se meta_learner.json sumir, reconstrói a partir do history.jsonl
- **Endpoints**: `/api/backtest/start|stop|status|run|cv/{id}|history|meta|summary`
- **Frontend**: aba "🔬 Backtest Engine" com controle de loop, resultados, CV e meta-learning
- **Dependencies**: `scikit-optimize==0.10.2` adicionado ao requirements.txt
- **Status**: Rodando, processou 44 ligas em 7 ciclos, 48 registros no meta-learner
- **Bug fix**: `temporal_cv` retornava sem `n_folds` — corrigido

### 🎯 Propostas Otimizadas (FASE 12b)
- **Thresholds de confiança**: só gera proposta se favorito >= 55% (antes: gerava para todos)
- **Filtragem**: backtest_engine filtra por confiança mínima por tipo
- **Removido**: Cantos (lambda*5.2 era fake)
- **Resultados MLS (antes → depois)**:
  - 1X2: 26.1% → **54.7%** (+28.6%)
  - GOLS: 5.2% → **72.2%** (+67.0%)
  - BTTS: 60.4% → **58.8%** (menos propostas, mais seletivo)
  - PLACAR: 12% → **15.2%** (+3.2%)
  - Total propostas: 2073 → **366** (-82%)
- **Lógica**: só conta proposta se `fav_prob >= 0.55` E `conf >= threshold`

### 🏗️ Infraestrutura
- **systemd services**: `ap2web-backend.service` + `ap2web-frontend.service`
- **Linger ativo**: `loginctl enable-linger razuk` — serviços sobem no boot
- **Persiste mesmo com terminal fechado**
- **Comandos**: `systemctl --user [start|stop|restart|status] ap2web-backend`

### 🔐 Segurança
- **Senha tester**: `tester`/`abc12345`
- **Admin**: `AdminSecure2024!`
- **Token GitHub**: revocado

---

## FASES IMPLEMENTADAS (BASE.md)

### ✅ FASE 1 — Data Integrity with kickoff_datetime
- Coluna `kickoff_datetime TEXT` (UTC ISO 8601) na tabela `matches`
- Índices: `idx_matches_kickoff`, `idx_matches_league`, `idx_matches_date`, `idx_matches_status`

### ✅ FASE 2 — Sync Correctness
- Lógica `_upsert_match`: scheduled → played → stats collection
- 56 ligas sincronizadas

### ✅ FASE 3 — Feature Engine Unification
- `feature_engine.py`: **única fonte** gf/ga/xg/xga/window/blend
- `learning.py` e `prediction.py` importam de `feature_engine`

### ✅ FASE 4 — As-of Prediction (Data Leakage Prevention)
- `as_of_timestamp` em 7 funções e 3 endpoints
- **Todas as queries usam `date(m.kickoff_datetime) < date(?)`**
- **CORRIGIDO**: `_build()` agora propaga `as_of_timestamp` para `_compare`, `_recent_form`, `_h2h`

### ✅ FASE 5 — Poisson Baseline V2 → V3 (Dixon-Coles)
- Matriz de Poisson + Dixon-Coles τ factor
- `dixon_coles_tau()`: correção para P(0-0), P(1-0), P(0-1), P(1-1)
- `build_matrix(rho)`: normalização pós-tau
- `predict(rho)`: parâmetro ρ configurável por liga
- **ρ calibrado por liga**: 10/31 ligas com ρ ≠ 0

### ✅ FASE 6 — Evaluation Engine
- `brier_score`, `log_loss`, `model_version`, `predicted_at` em predictions
- Funções: `_brier_score()`, `_log_loss()`, `_result_of_pick_v2()`

### ✅ FASE 7 — Walk-forward Validation + Dixon-Coles
- `backtest_league(rho)`: walk-forward com Dixon-Coles
- `calibrate_league()`: grid search (HA×window×feature×ρ) — 324 combos
- `RHO_GRID`: [0, -0.05, -0.10, -0.13, -0.15, -0.20]
- DB schema: coluna `rho` em `league_models` (auto-migração)

### ✅ FASE 8 — XGBoost Real (refeita)
- `xgb_engine.py`: 12 features, walk-forward temporal
- Resultado: Poisson vence em Brier/LogLoss em 5/5 ligas
- **Ensemble bloqueado** — Poisson permanece modelo de produção

### ✅ FASE 10 — Market Engine
- `market.py`: fair/market odds, EV, kelly_full, value_bets
- Endpoints validados

### ✅ FASE 11 — Risk Engine
- `risk.py`: Kelly fracionado (1/8 a full), limites de exposição, score de confiança (A/B/C/D)
- Endpoints: `/api/risk/{match_id}`, `/api/risk/league/{league_id}`, `/api/risk/portfolio`
- Frontend: painel interativo no PredictionView com Kelly configurável e banca
- Guardrails: max stake 5%, max exposição/jogo 15%, max diário 25%

### ⏳ FASE 9 — Ensemble
- **BLOQUEADA**: XGBoost não supera Poisson
- Retomar apenas com evidência nova (ex: FEATURE-001)

### ✅ FASE 12 — Backtest Engine
- `backtest_engine.py`: ciclo contínuo de backtest e meta-learning
- **TemporalCV**: cross-validation temporal K-fold (zero leakage)
- **MetaLearner**: Bayesian optimization via scikit-optimize (gp_minimize)
- **BacktestLoop**: thread de background com ciclo completo (configurável)
- **Persistência**: meta_learner.json, backtest_state.json, backtest_history.jsonl
- **Reconstrução**: meta-learner reconstrói do history.jsonl se arquivo sumir
- **Endpoints**: `/api/backtest/start|stop|status|run|cv/{id}|history|meta`
- **Frontend**: aba "🔬 Backtest Engine" com controle de loop, resultados, CV e meta-learning
- **Bug fix**: temporal_cv retornava sem n_folds em early return — corrigido

---

## Próximos Passos

### 🎯 Imediatos
- [ ] **Rodar backtest nas ligas 18, 20, 23, 24, 65** — dados já sincronizados
- [ ] **Integrar Bayesian Engine ao prediction path** — usar lambdas bayesianos em vez de médias

### 📋 Backlog
- [ ] **FEATURE-001**: fator de colocação/tabela no modelo
- [ ] **Mais dados**: sincronizar ligas faltantes do `lista de ligas.xlsx`
- [ ] **Features extras**: rest_days, posição na tabela
- [ ] **Expor avaliação contínua** usando predictions em tempo real
- [ ] **FASE 13**: Agent Runtime (após todas as científicas)

---

## Stack & Arquitetura

- **Backend**: FastAPI + SQLite/Postgres (db.py dual-engine + pool)
- **Frontend**: React + Vite (dev `:5173`, build em `frontend/dist/`)
- **Motor**: Poisson V3 (Dixon-Coles) + XGBoost (comparação)
- **Backtest Engine**: TemporalCV + MetaLearner (Bayesian opt) + BacktestLoop (background)
- **Bayesian**: Gamma-Poisson conjugate priors (opt-in)
- **Fonte**: Sofascore API
- **DB**: SQLite local / Postgres via `DATABASE_URL` (connection pool)

## Comandos

```bash
cd ~/Documents/AP2WEB
./start.sh          # sobe backend + frontend (legacy)
./stop.sh           # para tudo

# systemd (persiste com terminal fechado)
systemctl --user [start|stop|restart|status] ap2web-backend
systemctl --user [start|stop|restart|status] ap2web-frontend
journalctl --user -u ap2web-backend -f    # ver logs
```

- Backend log: `backend.log` · Frontend log: `frontend.log`
- Backend `:8000`, frontend `:5173` (Vite proxy `/api` → `:8000`)
- **systemd services**: `~/.config/systemd/user/ap2web-*.service`
- **Linger**: `loginctl enable-linger razuk` (serviços sobem no boot)

## Deploy

- **Git**: repo `https://github.com/Fran981259/AP2WEB`. Push em `main` → deploy no Render.
- **Produção**: https://ap2web.onrender.com (Docker, plano free — disco efêmero)
- Endpoint de saúde: `GET /api/health`

## Estrutura Relevante

- `backend/app/leagues_config.py` — 57 ligas do Sofascore
- `backend/app/sofascore_data.py` — sync, 28 métricas
- `backend/app/feature_engine.py` — features unificadas + LRU cache
- `backend/app/learning.py` — calibração/backtest com Dixon-Coles
- `backend/app/model.py` — Poisson V3 com Dixon-Coles τ
- `backend/app/bayesian.py` — Bayesian Engine (Gamma-Poisson)
- `backend/app/xgb_engine.py` — XGBoost comparison (FASE 8)
- `backend/app/market.py` — Market Engine (FASE 10)
- `backend/app/risk.py` — Risk Engine (FASE 11)
- `backend/app/backtest_engine.py` — Backtest Engine (FASE 12)
- `backend/app/evolution_tracker.py` — Monitor de evolução
- `backend/app/prediction.py` — previsões Poisson/Dixon-Coles
- `backend/app/history.py` — previsões salvas + resolução (FASE 6)
- `backend/app/main.py` — endpoints + shutdown hook
- `backend/app/db.py` — schema dual-engine + connection pool
- `frontend/src/App.jsx` — UI 7 abas + Risk Panel
- `frontend/src/styles.css` — Theme v2.0 "Midnight Sapphire"
- `export/ap2web_matches.csv` — 6.066 jogos jogados
- `update de ligas/ligas_sofascore.xlsx` — 161 ligas

## Notas técnicas / pegadinhas

- **httpx.Client não é thread-safe**: cada thread cria o seu próprio client
- **Rate limit Sofascore**: após ~5-13 ligas bloqueia; cooldown ~20min; silêncio total destrava
- **soccerdata só existe no `.venv`** (`backend/.venv/bin/python`)
- **Bash tool tem timeout 120s** — scripts longos com `setsid -f`
- `MIN_SAMPLES=20`: ligas com <20 previsões são puladas na calibração
- Botões "disfuncionais" no frontend = cache → hard refresh (Ctrl+Shift+R)
- **FASE 4 + FASE 7**: prevenção completa de data leakage
- **Poisson V3 é modelo de produção** — Dixon-Coles ρ calibrado por liga
- **Regras ML v1.1 §20.1**: sem paralelo validator, per-team λ, single HA, multiclass Brier
- **QA v1.1 §66-A**: code existence verification obrigatória; métrica sem fonte = BLOCKER
- **Dixon-Coles**: 10/31 ligas com ρ ≠ 0; melhoria média Brier +0.005
- **Bayesian Engine**: pronto mas não integrado — opt-in via `bayesian.py`
- **LRU cache**: `compute_team_stats` cacheado com tuple-hash (2048 entradas)
- **Connection pool**: `psycopg_pool` para Postgres (min=2, max=10)
