# AP2WEB — Motor de Previsão Esportiva

Aplicação web (React + FastAPI) que raspa dados do **Soccerstats.com**, guarda em **SQLite** próprio e gera previsões com **modelo Poisson duplo** (λ casa/fora → matriz de placares → 1X2, Over/Under, BTTS, placar exato e propostas).

> A planilha AP 2.0 foi usada **apenas como referência de conhecimento** (núcleo: λ = ataque × defesa adversária; estratégias de proposta). Não há importação da planilha — os dados vêm da raspagem.

## Arquitetura

```
backend/                  FastAPI (Python 3.12)
  app/
    main.py               API: /api/register, /api/login, /api/scrape/..., /api/prediction
    auth.py               JWT (login/senha, cadastro de usuários)
    db.py                 SQLite: users, leagues, teams, matches, team_stats, scrape_runs
    scraper.py            Scraper Soccerstats (httpx HTTP/2 → passa no Cloudflare)
    model.py              Motor Poisson (conhecimento da AP 2.0)
    prediction.py         Une banco + motor → previsões por partida
frontend/                 React + Vite (painel com login, raspagem, previsões)
```

## Como rodar

```bash
# 1. backend
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000

# 2. frontend
cd frontend
npm install
npm run dev            # http://localhost:5173
```

Acesse `http://localhost:5173`, cadastre um usuário e use as abas.

## Deploy no Render (https://app.theprostatereview.com)

O app roda em **um único container Docker** (API + frontend compilado) no plano gratuito do Render, com banco SQLite persistido em disco.

### 1. Suba o código para o GitHub
```bash
cd ~/Documents/AP2WEB
git init && git add -A && git commit -m "AP2WEB"
# crie um repositório no GitHub e:
git remote add origin https://github.com/SEU_USUARIO/AP2WEB.git
git push -u origin main
```

### 2. Crie o serviço no Render
1. Acesse https://dashboard.render.com → **New** → **Blueprint** (usa o `render.yaml` já pronto)
2. Conecte o repositório GitHub
3. Render cria o serviço **ap2web** (Docker, plano free) com:
   - `AP2WEB_ORIGINS=https://app.theprostatereview.com`
   - `AP2WEB_DB_PATH=/data/ap2web.db` (disco persistente 1GB)
   - `AP2WEB_SECRET` (gerada automaticamente)
4. Deploy → aguarde o build (alguns minutos)

O app fica em `https://ap2web.onrender.com` (ou o nome escolhido).

### 3. Aponte o domínio
1. No Render: **Settings → Custom Domains** → adicione `app.theprostatereview.com`
2. Render mostra um registro DNS a criar (host `app`, valor `CNAME`/`ALIAS`/`TXT` de verificação)
3. No painel da **HostGator → cPanel → Zona de DNS / Domínios**, crie esse registro no domínio `theprostatereview.com`
4. Aguarde propagar (pode levar de minutos a horas) → HTTPS automático do Render

### 4. Acesse
`https://app.theprostatereview.com` → cadastre um usuário → use a aba **Confronto**.

**Notas:**
- Plano free do Render "dorme" após ~15min sem acesso; ao visitar, demora ~1min para acordar.
- Se quiser scrapping 24h sem sleep, suba o plano pago ou um VPS (mesmo Dockerfile).
- O blueprint cria disco de 1GB em `/data` — o banco sobrevive a redeploys.

## Telas

- **Confronto** (inicial): escolha uma liga → carrega os times da liga → selecione mandante e visitante nos dropdowns → "Prever confronto". O botão **Demanda de dados** raspa os resultados da liga escolhida sob demanda.
- **Ligas e Jogos**: partidas por liga com previsão por partida.
- **Raspagem**: ações de scrape e histórico de execuções.

## Scraping

| Ação | Fonte | O que coleta |
|---|---|---|
| Raspar jogos de hoje | `matches.asp` | todas as ligas, com stats por time (GP, GF, GA, FTS, CS, BTS, Over 1.5/2.5/3.5, PPG) |
| Resultados `<code>` | `results.asp?pmtype=bydate` | histórico FT/HT da liga (ex.: `brazil2`, `spain`, `argentina3`) |

Códigos de liga: os mesmos usados pelo site (ex.: `england`, `brazil2`, `spain`, `germany`, `italy`, `france`).

## Previsões (modelo)

- λ casa/fora calculados das médias GF/GA dos times no banco
- Matriz Poisson 0–10 gols → probabilidades normalizadas a 100%
- 1X2 + odds, Over/Under 1.5–4.5, BTTS, placar exato, propostas (Lay Empate, Back Over, BTTS Sim/Não, cantos)

## Nota sobre o Soccerstats

O site usa Cloudflare — o scraper contorna com **HTTP/2** (`httpx.Client(http2=True)`). Se bloquear, revalide o `User-Agent`. O nowgoal (fonte original da planilha) estava fora do ar na construção.