# MEMORY — AP2WEB

> Memória de trabalho do projeto. Sempre que voltarmos a trabalhar, ler este
> arquivo para saber onde paramos. Manter atualizado ao final de cada sessão.

## Última sessão (22/08/2026)

### ✅ Otimização do Sistema — 31 ligas calibradas
- **MIN_SAMPLES** reduzido de 30 → 20 (permite ligas com menos jogos)
- **Grid de parâmetros**: 6×3×3 = 54 combinações/lia (HA: 1.05–1.30, Win: 5–15, Feat: xg/goals/blend)
- **Calibração completa**: 31 ligas otimizadas em 223s (4 workers paralelos)
- **3 ligas novas calibradas**: National League (73), México (79), Paraguai Clausura (9)
- **28 ligas existentes recalibradas** com grid ampliado

### ✅ Monitor de Evolução — 31 ligas rastreadas
- `LEAGUES_TO_TRACK` expandido de 5 → 31 ligas (todas com ≥30 jogos)
- Cada snapshot roda `backtest_league()` para cada liga (~3.6s total)
- Coluna **Evolução** adicionada ao frontend: % mudança desde primeira medição
- Backend: `_evolution_pct()` calcula first vs current para acc/brier/logloss

### ✅ Bugs corrigidos no Evolution Monitor
- **Bug 1**: `regression_suite` sempre "changed" — endpoint sobrescrevia valor do baseline
- **Bug 2**: LogLoss = 1.0 em todas as ligas — `backtest_league()` não calculava logloss
- **Fixes**: `learning.py` agora retorna logloss real; `main.py` preserva baseline

### ✅ Dados exportados
- **CSV**: `export/ap2web_matches.csv` — 6.066 jogos jogados, 66 colunas
- **Ligas XLSX**: `update de ligas/ligas_sofascore.xlsx` — 161 ligas (57 confirmadas + 104 aproximadas)

### ✅ Sync Massivo Concluído (madrugada 22/08)
- **Banco final**: 56 ligas · 1.257 times · 5.955→6.066 jogos jogados
- Força bruta com backoff: MLS, Chile, Suécia, Paraguai, Eredivisie, Portugal, Dinamarca, Egito, J1, China×2, Inglaterra, LaLiga, Bundesliga, Bélgica, Estônia, México, Coreia, Suíça, Equador + copas
- **PENDENTE**: Colômbia (11539) e Peru (406) — bloqueio SofaScore 403

---

## Status Atual do Projeto

### 📊 Base de Dados
- **56 ligas** sincronizadas no banco
- **6.066 jogos jogados** · **~9.600 agendados**
- **83% dos jogos com xG** (5.081/6.066)
- **31 ligas calibradas** (otimizadas com grid 6×3×3)
- Schema: `leagues`, `teams`, `matches`, `predictions`, `league_models`, `users`

### 🧠 Motor de Previsão
- **Modelo**: Poisson V2 (produção) — vence XGBoost em 5/5 ligas
- **Calibração**: 31 ligas com parâmetros otimizados (HA, window, feature)
- **Walk-forward**: backtest honesto sem data leakage
- **Comparação**: XGBoost real (12 features) vs Poisson — Poisson vence em Brier/LogLoss
- **Ensemble**: bloqueado (XGBoost não supera Poisson)

### 📈 Monitor de Evolução
- **31 ligas rastreadas** (todas com ≥30 jogos)
- **Baseline**: regressão=PASS, logloss real (1.005–1.091)
- **Evolução**: % mudança desde primeira medição (acc/brier)
- **Histórico**: append-only em `evolution_history.jsonl`
- **Tempo**: ~3.6s por snapshot

### 🏪 Market Engine (FASE 10)
- `market.py`: fair odds, market odds (vig 4%), EV, kelly_full, value_bets
- Endpoints: `/api/market/{match_id}`, `/api/market/league/{league_id}`

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

### ✅ FASE 5 — Poisson Baseline V2
- Matriz de Poisson, normalização 1X2=1, fair odds, tipagens completas

### ✅ FASE 6 — Evaluation Engine
- `brier_score`, `log_loss`, `model_version`, `predicted_at` em predictions
- Funções: `_brier_score()`, `_log_loss()`, `_result_of_pick_v2()`

### ✅ FASE 7 — Walk-forward Validation
- `backtest_league()`: walk-forward honesto, curva de aprendizado
- `calibrate_league()`: grid search (HA×window×feature)

### ✅ FASE 8 — XGBoost Real (refeita)
- `xgb_engine.py`: 12 features, walk-forward temporal
- Resultado: Poisson vence em Brier/LogLoss em 5/5 ligas
- **Ensemble bloqueado** — Poisson permanece modelo de produção

### ✅ FASE 10 — Market Engine
- `market.py`: fair/market odds, EV, kelly_full, value_bets
- Endpoints validados

### ⏳ FASE 9 — Ensemble
- **BLOQUEADA**: XGBoost não supera Poisson
- Retomar apenas com evidência nova (ex: FEATURE-001)

### ⏳ FASE 11 — Risk Engine
- **PRÓXIMA**: Kelly fracionado, limites, exposição
- Base já existe em `market.py` (kelly_full)

---

## Próximos Passos

### 🎯 Imediatos
- [ ] **Re-sincronizar Colômbia (11539) e Peru (406)** — bloqueio SofaScore
- [ ] **FASE 11 Risk Engine** — Kelly fracionado, limites de exposição

### 📋 Backlog
- [ ] **FEATURE-001**: fator de colocação/tabela no modelo
- [ ] **Mais dados**: sincronizar ligas faltantes do `lista de ligas.xlsx`
- [ ] **Features extras**: rest_days, posição na tabela
- [ ] **Calibração automática**: recalibrar quando novos jogos chegam
- [ ] **Expor avaliação contínua** usando predictions em tempo real
- [ ] **FASE 12**: Agent Runtime (após todas as científicas)

---

## Stack & Arquitetura

- **Backend**: FastAPI + SQLite/Postgres (db.py dual-engine)
- **Frontend**: React + Vite (dev `:5173`, build em `frontend/dist/`)
- **Motor**: Poisson V2 (produção) + XGBoost (comparação)
- **Fonte**: Sofascore API
- **DB**: SQLite local / Postgres via `DATABASE_URL`

## Comandos

```bash
cd ~/Documents/AP2WEB
./start.sh          # sobe backend + frontend
./stop.sh           # para tudo
nohup setsid ./start.sh > /tmp/ap2web.log 2>&1 &
```

- Backend log: `backend.log` · Frontend log: `frontend.log`
- Backend `:8000`, frontend `:5173` (Vite proxy `/api` → `:8000`)

## Deploy

- **Git**: repo `https://github.com/Fran981259/AP2WEB`. Push em `main` → deploy no Render.
- **Produção**: https://ap2web.onrender.com (Docker, plano free — disco efêmero)
- Endpoint de saúde: `GET /api/health`

## Estrutura Relevante

- `backend/app/leagues_config.py` — 57 ligas do Sofascore
- `backend/app/sofascore_data.py` — sync, 28 métricas
- `backend/app/feature_engine.py` — features unificadas (FASE 3)
- `backend/app/learning.py` — calibração/backtest (FASE 7)
- `backend/app/xgb_engine.py` — XGBoost comparison (FASE 8)
- `backend/app/market.py` — Market Engine (FASE 10)
- `backend/app/evolution_tracker.py` — Monitor de evolução
- `backend/app/prediction.py` — previsões Poisson
- `backend/app/history.py` — previsões salvas + resolução (FASE 6)
- `backend/app/main.py` — endpoints
- `backend/app/db.py` — schema dual-engine (SQLite/Postgres)
- `frontend/src/App.jsx` — UI 6 abas
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
- **Poisson V2 é modelo de produção** — XGBoost perde em Brier/LogLoss
- **Regras ML v1.1 §20.1**: sem paralelo validator, per-team λ, single HA, multiclass Brier
- **QA v1.1 §66-A**: code existence verification obrigatória; métrica sem fonte = BLOCKER
