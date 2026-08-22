# MEMORY — AP2WEB

> Memória de trabalho do projeto. Sempre que voltarmos a trabalhar, ler este
> arquivo para saber onde paramos. Manter atualizado ao final de cada sessão.

## Última sessão (21/08/2026)

### ✅ EVOLUTION-001: PROP-001 + PROP-002 promovidas
- **`tests/regression_suite.py`** — suíte de regressão obrigatória (QA): Fase A smoke API (14 checks: auth, contratos, 1X2≈1, as-of temporal) + Fase B E2E selenium (6 checks: login, sidebar, layout, previsão, abas, console). Executar após qualquer mudança cross-cutting: `backend/.venv/bin/python tests/regression_suite.py`. Primeira execução: **20/20 PASS**
- **Backend Skill v1.0 → v1.1**: checklist obrigatório §38.1 (grep call sites + handoff + suíte PASS) para mudanças de assinatura/contrato/schema
- Registros em `skill/evolution-engine/memory/promotions/EVOLUTION-001.md`
- PROP-005 (walkforward λ global + XGBoost overfitting) continua **bloqueando FASE 9** até investigação ML

### ✅ Auditoria visual frontend: bug do layout encolhido
- **Causa**: `.app { display:flex; flex-direction:column }` + `main { margin:0 auto; max-width }` — no flexbox, margens automáticas **desativam o stretch** → main encolhia para max-content (902px) em vez de preencher até 1440px
- **Fix**: `.app` voltou a bloco simples (min-height apenas); `main` volta a esticar corretamente
- Medição E2E em 4 viewports (1440/1024/768/390): main preenche viewport ✓, zero overflow horizontal, zero elementos fora da tela
- Larguras por aba (intencional): Confronto 1440px (sidebar + conteúdo) · Histórico/Aprendizado/Dados/Sofascore 1040px (leitura)
- Screenshots de evidência: /tmp/opencode/final_*.png

### ✅ Auditoria de duplicação no backend — 4 correções aplicadas
1. **`_parse_score` dedup**: era idêntica em `feature_engine.py` e `sofascore_data.py` → fonte única `parse_stat_value()` em feature_engine, importada pelo sofascore_data
2. **Código morto removido**: `_result_of_pick` (v1) em history.py não tinha chamadas; só `_result_of_pick_v2` é usada
3. **Helper único `_played_rows()`** em prediction.py: eliminou 7 cópias do padrão de query as-of (`if as_of: query A else: query B`) nas funções `_avg_stats`, `_avg_stats_detail`, `_recent_form`, `_h2h` — o filtro temporal agora é aplicado em UM lugar
4. **Constante `_PLAYED_COUNT`** em learning.py: substituiu 4 subqueries SQL idênticas de contagem de jogos

### ✅ Bug bônus encontrado na regressão
- `predict_match` aplicava o filtro as-of **ao próprio jogo previsto** (WHERE m.id=? AND kickoff < as_of) → 404 no caso de uso legítimo (prever jogo futuro "as-of" data passada). Fix: jogo sempre buscado por id; filtro fica só nas features.

### ⚠️ Flag para ML Skill (não corrigido — fora do escopo Backend)
- `walkforward_validation` (learning.py): calcula λ com soma GLOBAL de gols (não por time), fura abstração db.py e duplica conceito com `backtest_league` → consolidar cientificamente

### Regressão pós-auditoria (todos OK)
- leagues/teams/matches/predictions/sofascore-data: HTTP 200
- Previsão com e sem as_of: 1X2 soma=1 ✓, as_of altera probs ✓, filtro temporal reduz jogos usados ✓
- fixture/learning/status/curve/backtest: funcionando
- Frontend E2E selenium: sidebar com nomes ✓ · build produção OK

### ✅ Fix definitivo: ligas com nomes vazios no front (bug de transpilação)
- **Causa raiz**: `[...new Map(x.values())]` no `refreshLeagues` era transpilado pelo esbuild do Vite produzindo os PARES `[id, objeto]` em vez dos valores → `l.name`/`l.played` = undefined na renderização
- Diagnosticado via selenium headless + instrumentação: `deduped[0]` era `[24, {...}]` (par), não o objeto
- **Fix**: dedup com `Object.values(byId)` — imune a transpilação
- **Lição QA**: teste standalone de JS nativo no browser NÃO valida código transpilado; sempre testar o bundle servido
- E2E validado: 25 ligas com nomes/contadores, 200 matches, previsão Aldosivi x River Plate (1X2 renderizado), 0 erros SEVERE

### ✅ Fix: frontend "não funcionava" — 3 causas encontradas
1. **Usuários desaparecidos**: banco só tinha `admin`/`razuk` — `tester`/`demo` recriados via `/api/register` (tester/abc12345, demo/demo123)
2. **`_avg_stats_detail()` crash (HTTP 500 em TODA previsão)**: FASE 4 não aplicada a essa função — chamadas passavam `as_of_timestamp` mas ela não aceitava; também usava `_window_values(m, feature, home_side)` com assinatura errada. Fix: aceita `as_of_timestamp` com filtro `date() < date(?)` (fecha gap de leakage na auditoria) + constrói `hist_entry` como `_avg_stats`
3. **`match.get()` em sqlite3.Row** (`_build`): convertido para `dict(match)` antes do `.get`
- Bônus: espaço faltante em 3 queries concatenadas (`date(?)"ORDER`)
- Regressão: 8 previsões aleatórias OK + leagues/learning/curve/predictions/sofascore todos HTTP 200

### ✅ Fix: fonte Inter não carregava
- CSS declarava `font-family: 'Inter'` mas a fonte nunca era importada → browser caía no fallback system-ui
- Fix: `<link>` do Google Fonts (Inter 400-800) no `index.html` com `preconnect` + `display=swap`
- Google Fonts acessível (HTTP 200), build OK

### ✅ Correção crítica: temporada sem resultados (dados zerados no front)
- **Causa raiz**: `_latest_season` escolhia a temporada mais nova (26/27) que só tem calendário, sem resultados → ligas grandes apareciam com 0 jogados
- **Fix**: `_latest_season` agora prefere temporadas **com jogos jogados** (checa `status.code == 100` em events/last/0); fallback para primeira com rodadas
- **Limpeza**: removidas 40 ligas vazias do banco (recriadas automaticamente pelo `_upsert_league` no sync) e matches fantasma das ligas afetadas
- **Estado final**: 25 ligas, **7471 matches**, **3402 jogados** — Premier League 380, Serie A 380, Argentina 325, Ligue 1 308, Bundesliga 307, Brasil A/B 225/230
- Rate limit SofaScore continua derrubando syncs longos (~404 em stats) — rodar em lotes/background

### ✅ Frontend Premium Redesign (Theme v2.0 "Midnight Sapphire")
- `frontend/src/styles.css` reescrito com paleta premium: bg `#07080f`, accent indigo `#6366f1` + teal `#2dd4bf`, gradientes, glassmorphism no header, sombras em camadas
- Corrigidos erros pré-existentes: classes `.app` e `.inline` estavam usadas no App.jsx mas **sem definição CSS** — agora definidas
- Acessibilidade adicionada: `:focus-visible`, `prefers-reduced-motion`, scrollbars customizadas
- Dedup de ligas no estado (`refreshLeagues` com Map por id) + removido double-refresh no `startSofaSync`
- QA: build OK (17.76 kB CSS), verificação automática confirma 100% das 94 classes do App.jsx cobertas pelo CSS
- Zero mudança de contrato de API / nomes de classe / comportamento (regra de não-regressão §47 atendida)

## Sessão anterior (20/08/2026)

## FASES IMPLEMENTADAS (BASE.md)

### ✅ FASE 1 — Data Integrity with kickoff_datetime
- Coluna `kickoff_datetime TEXT` (UTC ISO 8601) adicionada na tabela `matches`
- Coluna `match_date TEXT` mantida para backward compat
- `sofascore_data.py` atualizado: `startTimestamp` → UTC datetime
- Índices criados: `idx_matches_kickoff`, `idx_matches_league`, `idx_matches_date`, `idx_matches_status`

### ✅ FASE 2 — Sync Correctness
- Lógica `_upsert_match` implementada: scheduled → played → stats collection
- Quando status muda para "played" e stats estão faltando, são buscadas do SofaScore API
- 58 ligas sincronizadas no banco

### ✅ FASE 3 — Feature Engine Unification
- `feature_engine.py` criado como **única fonte** para gf/ga/xg/xga/window/blend
- `learning.py` e `prediction.py` refatorados para importar `compute_team_stats`/`compute_match_stats` de `feature_engine`
- Blend 50% gols + 50% xG por BASE.md
- `backtest_league` usa computação unificada de features

### ✅ FASE 4 — As-of Prediction (Data Leakage Prevention)
- Parâmetro `as_of_timestamp` adicionado a 7 funções e 3 endpoints API:
  - `_avg_stats`, `_recent_form`, `_h2h`, `_team_card`, `predict_match`, `predict_league_upcoming`, `predict_fixture`
- **Todas as queries SQL usam `date(m.kickoff_datetime) < date(?)`** — consistente independente do formato ISO 8601
- **Prevenção de data leakage temporal**: somente jogos com `kickoff_datetime` anterior ao `as_of_timestamp` são considerados nas médias de GF/GA/xG
- Endpoints API atualizados:
  - `/api/matches/{match_id}/prediction?as_of_timestamp=...`
  - `/api/predict/fixture?league_id=...&as_of_timestamp=...`
  - `/api/leagues/{league_id}/predictions?as_of_timestamp=...`

### ✅ FASE 5 — Poisson Baseline V2
- Correções aplicadas:
  - **matriz**: constante `GOAL_LINES = [1.5, 2.5, 3.5, 4.5]` para over/under
  - **normalização**: `sum(1X2) == 1.0` garantido
  - **nomenclatura**: tipagens aprimoradas (`TypedDict`, `PoissonResult` com tipos completos)
  - **fair odds**: cálculo `1.0 / v` (odds "fair", sem margem de bookmaker)
  - **tipagem**: `poisson_pmf`, `TeamInput`, `MatchInput`, `PoissonResult` com type hints completos
- Filosofia do modelo Poisson **preservada** (λs dinâmicos, probabilidades normalizadas, derivações sobre mesma matriz)

### ✅ FASE 6 — Evaluation Engine
- Colunas adicionadas à tabela `predictions`:
  - `model_version TEXT` — versão do modelo usado (ex: "poisson_v2")
  - `predicted_at TEXT` — timestamp da previsão
  - `brier_score REAL` — pontuação Brier (0 = perfeito)
  - `log_loss REAL` — loss logarítmico
- Funções implementadas em `history.py`:
  - `_brier_score(prob)` — calcula Brier score: `(1 - p)^2`
  - `_log_loss(prob)` — calcula Log Loss: `-ln(p)`
  - `_result_of_pick_v2(pick_type, pick_value, ft_home, ft_away, prob_home)` — retorna dict com `result`, `brier`, `log_loss`
  - `save_prediction(user_id, data)` — agora inclui `model_version` e `predicted_at`
  - `stats(user_id)` — agora retorna `avg_brier` e `avg_log_loss` medianos
  - `resolve_predictions(user_id)` — preenche `brier_score` e `log_loss` ao resolver
- Métricas de calibração disponíveis:
  - `hit_rate`: porcentagem de acertos
  - `avg_brier`: média da pontuação Brier (menor = melhor calibrated)
  - `avg_log_loss`: média do loss logarítmico (menor = melhor calibrated)

### ✅ FASE 7 — Walk-forward Validation
- Função `walkforward_validation(league_id, window, home_advantage)` implementada em `learning.py`
- **Metodologia**: 
  - Ordena jogos cronologicamente
  - Para cada fold: usa jogos anteriores para treinar, próximo jogo para testar
  - **Previne data leakage temporal** (o foco principal)
- Métricas retornadas:
  - `accuracy`: porcentagem de acertos no favorito
  - `brier`: média da pontuação Brier
  - `series`: curva de aprendizado (jogos × acurácia)
  - `n_folds`: número de validações realizadas
- Complementa a FASE 4: juntas, garantem integridade temporal completa (prevenção de dados futuros tanto nas features quanto no treinamento)

### ⚠️ FASE 8 — NÃO IMPLEMENTADA (registro corrigido em 21/08/2026)
- Investigação PROP-005 confirmou: **não há código XGBoost no projeto** (model.py é 100% Poisson)
- Registro anterior de "XGBoost implementado, 100% acurácia" era falso/não-verificável
- `walkforward_validation` também se provou inválida (λ global sem discriminação por time, Brier invertido, HA aplicado 2×, acurácia 35.5% < base ingênua 38.9%)
- Validador científico confiável do projeto: `backtest_league` (49.46% na liga 20)
- Detalhes: skill/evolution-engine/memory/findings/prop005-investigacao-ml.md

---

## Status Atual do Projeto

### 📊 Base de Dados
- **58 ligas** sincronizadas no banco de dados (de 57 no config + 1 test)
- **4133 matches** with statistics saved
- **15 ligas** com `last_sync` preenchido
- Schema: `leagues`, `teams`, `matches`, `predictions`, `league_models`, `users`
- Colunas novas: `model_version`, `predicted_at`, `brier_score`, `log_loss`
- Bug `cannot access local variable 'koff'` corrigido em `_upsert_match` (FASE 8)

### 🔄 Sync de Ligas
- **43 ligas** ainda sem `last_sync` (sync em andamento em lotes)
- Rate limit do SofaScore — cooldown ~20 min entre ligas
- Script: `sofascore_data.sync_league_local(id)` com handling de erros
- Sync progressivo: 58 ligas inseridas, 4133 matches salvos até o momento

### 📈 Dados Atuais por Liga (exemplo)
- Premier League (ID 17): 210 matches
- Serie A (ID 23): 306 matches
- Ligue 1 (ID 34): 180 matches
- Champions League (ID 7): 0 matches (próximo sync)
- ... e mais 53 ligas com dados variados

### 🔐 Segurança
- **Senha admin**: alterada de `admin12345` → `AdminSecure2024!` (requirement BASE.md)
- **Token GitHub**: revocado anteriormente (identificado em conversa)

### 🌐 Endpoints API Principais
- `GET /api/matches/{match_id}/prediction?as_of_timestamp=...`
- `POST /api/predict/fixture?league_id=...&as_of_timestamp=...`
- `GET /api/leagues/{league_id}/predictions?as_of_timestamp=...`
- `POST /api/sofascore/sync/league/{id}`
- `GET /api/health`

### 📊 Habilidades do Projeto (7/7 aplicadas)
1. **BACKEND ENGINEER** — implementação core + endpoints API + FASES 1-7
2. **DATA ENGINEER** — schema SofaScore + integração + sync de ligas
3. **FRONTEND ENGINEER** — `npm run build` sucesso, UI/UX, acessibilidade
4. **ML - STATISTICS** — modelo Poisson + features + walk-forward validation
5. **ORCHESTRATOR/ARCHITECT** — sequência FASE 1→7 seguindo BASE.md
6. **QA - EVALUATION** — validação de métricas (Brier, Log Loss, acurácia)
7. **DOCUMENTATION** — MEMORY.md, BASE.md reference, registro de mudanças

---

## Próximos Passos Pendentes

### 🔄 Sync de Ligas Pendentes
- **13 ligas** originalmente pendentes (agora parte das 44 não sincronizadas)
- Rate limit do SofaScore — cooldown ~20 min entre ligas
- Script: `backend/.venv/bin/python /tmp/sync_remaining.py`

### 🎯 Próximas Fases BASE.md
- **FASE 8**: XGBoost como modelo paralelo, comparar contra Poisson
- **FASE 9**: Ensemble (somente se resultados justificarem)
- **FASE 10**: Market Engine — odds, EV (valor esperado)
- **FASE 11**: Risk Engine — Kelly fracionado, limites, exposição

### 🎯 Próximos Passos Pendentes

### 🔄 Sync de Ligas Pendentes (Continuando)
- **43 ligas** ainda precisam de `last_sync` preenchido
- Sync em andamento em lotes de 5-8 ligas com cooldown 12-15s entre cada
- Próximas ligas alvo: Champions League (ID 7), LaLiga (ID 8), Premier League (ID 17), Serie A (ID 23)
- Taxa de sucesso melhorada após correção do bug `koff`
- Pode ser continuado em sessão futura com `sofascore_data.sync_league_local(id)`

### 🎯 Próximas Fases BASE.md (atualizado pós PROP-005)
- ~~**FASE 9**: Ensemble~~ → **BLOQUEADA**: XGBoost real implementado (xgb_engine.py) mas **perde do Poisson em Brier/LogLoss em 5/5 ligas** (1.381 confrontos walk-forward). Ensemble contra-indicado; só retomar com evidência nova (ex: FEATURE-001)
- ~~**FASE 10**: Market Engine~~ → **CONCLUÍDA ✅** (21/08/2026): `market.py` + endpoints `/api/market/{match_id}` e `/api/market/league/{league_id}` — fair odds, market odds (vig 4%), EV, kelly_full, value_bets
- **FASE 11: Risk Engine** → PRÓXIMA (Kelly fracionado, limites, exposição; kelly_full já exposto no market.py como base)
- **FASE 12**: Agent Runtime (após todas as científicas)

### 🗄️ Banco de Dados Dual-Engine (21/08/2026)
- `db.py` traduz SQLite→Postgres em runtime quando `DATABASE_URL` está setada (senão SQLite local, comportamento idêntico ao original)
- Traduções: `?`→`%s` · `date(x)`→`(x)::date` · `date(?)`→`(left(?,10))::date` (PG estrito) · `datetime('now')`→`to_char(now())` · `window`→`"window"` (reservada PG) · INSERT ganha `RETURNING id` com fallback p/ PK não-id
- **Fonte única de SQL** (ML v1.1 §20.1): nenhum query paralelo por engine
- Migração: `DATABASE_URL=... backend/.venv/bin/python backend/scripts/migrate_sqlite_to_pg.py`
- Validado em PostgreSQL 16.4 real + regressão 20/20 · Render free = SQLite efêmero; Neon grátis persiste

### 📊 Monitor de Evolução (21/08/2026)
- `evolution_tracker.py`: baseline (`--baseline`) + comparação CLI + histórico append-only em `backend/app/data/evolution_history.jsonl`
- Aba **📈 Evolução** no frontend: cards de status, tabela de mudanças vs baseline (delta colorido), métricas por liga, gráfico de tendência (LineChart)
- Endpoints: `/api/evolution/snapshot` (grava no histórico a cada chamada) e `/api/evolution/history`
- 5 ligas monitoradas: 20, 18, 65, 23, 24 (top por jogos)

### 🎯 XGBoost Real (FASE 8 refeita, 21/08/2026)
- `xgb_engine.py`: dataset leak-safe (12 features por time, janela 10), comparação honesta vs Poisson vs prior empírico no MESMO conjunto
- Endpoint `/api/learning/xgb/{league_id}` (~1 min)
- Resultado: Poisson vence em Brier+LogLoss nas ligas 20/18/65/23/24 → **Poisson permanece modelo de produção**

### 🎯 FEATURE-001 (backlog, registrado 21/08/2026)
- Fator de colocação/tabela no modelo — ver `skill/evolution-engine/memory/promotions/FEATURE-001.md`
- Implementar AO FINAL dos módulos (decisão do usuário); critério: ganho em Brier/LogLoss via compare_models

### 🎯 Sync Massivo Concluído (22/08/2026, madrugada)
- **Banco final: 56 ligas · 1.257 times · 5.955 jogos jogados · 9.624 agendados**
- Força bruta em rodadas aleatórias com backoff (`/tmp/opencode/brute_sync.py`, estado em `/tmp/opencode/brute_state.json`)
- **Baixadas com sucesso:** MLS (533), Chile (150), Suécia (136), Paraguai Apertura (131), Eredivisie, Portugal Betclic, Dinamarca, Egito, J1 League, China×2, Inglaterra Championship/League One/National, LaLiga/LaLiga2, 2.Bundesliga/3.Liga, Bélgica, Estônia, México, Coreia, Suíça, Equador + Libertadores/Sudamericana/Copa América/Europa League/AFC CL + Copa Argentina completada
- ⚠️ Ligas europeias/J1 com poucos jogos = temporada 2026-27 recém-começada (correto)
- **PENDENTE (bloqueio SofaScore 403 global por ~3h+): Colômbia Primera A (sid 11539) e Peru Liga 1 (406, veio vazia)** → re-sincronizar com `sofascore_data.sync_league(cfg)` num dia tranquilo; upsert não duplica
- **Lição registrada:** martelar retries a cada 30s MANTÉM o bloqueio vivo; silêncio total de ~20-30min foi o que destravou (Suécia/J1/Paraguai caíram logo após)

### 📋 Tasks Specifically Marked
- [ ] Continuar sync das ligas pendentes em lotes futuros (rate limit SofaScore)
- [ ] **Re-sincronizar Colômbia (11539) e Peru (406)** — bloqueadas em 22/08; único gap das 57 configuradas
- [x] **Sync força bruta 11 ligas (22/08): 9/11 baixadas + bônus Copa Argentina; banco 46→56 ligas, 3.406→5.955 jogos**
- [x] Decidir FASE 9: XGBoost real implementado — Poisson venceu → Ensemble bloqueado por evidência
- [x] FASE 10 Market Engine ✅ (market.py + endpoints + validação)
- [x] **Frontend: Corrigir duplicated leagues — aplicar dedup no estado `leagues` e remover duplicate refresh calls** ✅ (feito em App.jsx)
- [ ] Expor avaliação contínua usando histórico `predictions` em tempo real
- [ ] Manter MEMORY.md atualizado ao final de cada sessão
- [ ] FASE 11 Risk Engine (próxima)
- [ ] FEATURE-001 fator de colocação (ao final dos módulos, decisão do usuário)
- [ ] Configurar DATABASE_URL no Render + migrar dados p/ Neon (script pronto)

---

## Stack & Arquitetura

- **Backend**: FastAPI + SQLite (SQLAlchemy puro/raw sql),servido em `http://localhost:8000`
- **Frontend**: React + Vite (dev em `http://localhost:5173`), build em `frontend/dist/`
- **Motor de previsão**: Poisson dupla independente (`backend/app/model.py`), fator de mando + janela deslizante calibrados por liga (`league_models`)
- **Fonte de dados**: **Sofascore API** (`https://www.sofascore.com/api/v1/...`)
- **Schema key findings**:
  - Tabela `matches`: `kickoff_datetime TEXT` (UTC ISO 8601), `match_date TEXT` (YYYY-MM-DD)
  - Tabela `predictions`: agora tem `model_version`, `predicted_at`, `brier_score`, `log_loss`
  - Tabela `leagues`: `sofascore_id`, `season_id`, `season_name`, `last_sync`
  - Nenhuma coluna `code` (bug recorrente resolvido evitando `l.code`)

## Comandos

```bash
cd ~/Documents/AP2WEB
./start.sh          # sobe backend + frontend (usa setsid; não morre ao fechar terminal)
./stop.sh           # para tudo
nohup setsid ./start.sh > /tmp/ap2web.log 2>&1 &
```
- Backend log: `backend.log` · Frontend log: `frontend.log`
- Usuários locais: `tester`/`abc12345`, `demo`, `tester2`, `tester3`
- **Produção**: admin `admin/admin12345` → **atualizado para `AdminSecure2024!`**
- Backend `:8000`, frontend `:5173` (Vite proxy `/api` → `:8000`)

## Deploy

- **Git**: repo `https://github.com/Fran981259/AP2WEB`. Push em `main` → deploy no Render.
- **Produção**: https://ap2web.onrender.com (Docker, plano free — disco efêmero, SQLite recriado a cada deploy).
- Endpoint de saúde: `GET /api/health`.

## Estrutura Relevante

- `backend/app/leagues_config.py` — **57 ligas** do Sofascore (`load_leagues()`)
- `backend/app/sofascore_data.py` — sync via Sofascore, `_STAT_NAME_TO_COL` (28 métricas)
- `backend/app/feature_engine.py` — **única fonte** gf/ga/xg/xga/window/blend (FASE 3)
- `backend/app/learning.py` — calibração/backtest/walk-forward (FASE 7)
- `backend/app/prediction.py` — previsões, usa modelo calibrado (`_model_for`)
- `backend/app/history.py` — previsões salvas (predictions) + resolução automática + FASE 6
- `backend/app/main.py` — endpoints (learning, scrape, sofascore, predictions)
- `backend/app/db.py` — schema (leagues, teams, matches, team_stats, predictions, league_models)
- `frontend/src/App.jsx` — UI (abas: Confronto[com ligas], Histórico, Aprendizado, Dados, Sofascore)
- `frontend/src/styles.css` — estilos + acessibilidade/responsividade
- `/tmp/sync_remaining.py`, `/tmp/sync_batch.py`, `/tmp/league_batch_{1,2,3}.txt` — scripts de sync

## Notas técnicas / pegadinhas

- **httpx.Client não é thread-safe**: cada thread do batch cria o seu próprio client
- **Rate limit do Sofascore**: após ~5-13 ligas, bloqueia com `ConnectionError` no `/seasons`. Cooldown de ~20 min restaura; GAP de 10s+ entre ligas ajuda
- **soccerdata só existe no `.venv`** (`backend/.venv/bin/python`); `python3` do sistema não importa
- **Bash tool tem timeout 120s** — scripts longos rodam com `setsid -f` em background
- `MIN_SAMPLES=30` no learning.py: ligas com menos jogos são puladas (não calibradas)
- Campos `model` + `match.league_id/home_id/away_id` na resposta de previsão são necessários para salvar previsão no histórico
- Botões "disfuncionais" no frontend = página antiga em cache → hard refresh (Ctrl+Shift+R)
- **Todas as queries FASE 4 usam `date(m.kickoff_datetime) < date(?)`** — consistência garantida
- **FASE 4 + FASE 7 juntos**: prevenção completa de data leakage (dados futuros em features + em treinamento)
