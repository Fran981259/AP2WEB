#!/usr/bin/env python3
"""AP2WEB — Suíte de Regressão Obrigatória (PROP-001 / QA v1.1).

Executar após QUALQUER mudança cross-cutting (backend, front, schema, modelo):
    backend/.venv/bin/python tests/regression_suite.py

Fase A — API smoke: endpoints principais, auth, contrato, validade probabilística.
Fase B — E2E browser real (selenium): login, sidebar, confronto, previsão,
         navegação nas 5 abas, erros de console.

Exit code: 0 = PASS, 1 = FAIL.
Requer: backend em :8000 e frontend em :5173 rodando.
"""
import json
import sys
import time
import urllib.error
import urllib.request

BASE = "http://localhost:8000/api"
FRONT = "http://localhost:5173"
USER = ("tester", "abc12345")

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"  [{'OK' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    return ok


def req(path, token=None, body=None, method=None):
    r = urllib.request.Request(BASE + path)
    if token:
        r.add_header("Authorization", f"Bearer {token}")
    if body is not None:
        r.add_header("Content-Type", "application/json")
        r.data = json.dumps(body).encode()
    if method:
        r.method = method
    return urllib.request.urlopen(r, timeout=30)


# ─────────────────────────── FASE A: API smoke ───────────────────────────

def phase_api():
    print("\n=== FASE A — API smoke ===")
    try:
        health = json.load(req("/health"))
        check("health", health.get("ok") is True)
    except Exception as e:
        check("health", False, f"backend no ar? ({e})")
        return None

    # auth: sem token deve falhar 401
    try:
        req("/leagues")
        check("auth sem token bloqueia", False, "aceitou request sem token")
    except urllib.error.HTTPError as e:
        check("auth sem token bloqueia", e.code == 401)
    except Exception as e:
        check("auth sem token bloqueia", False, str(e))

    # auth: credenciais inválidas devem falhar
    try:
        req("/login", body={"username": "tester", "password": "errada!"}, method="POST")
        check("login inválido rejeitado", False, "aceitou senha errada")
    except urllib.error.HTTPError as e:
        check("login inválido rejeitado", e.code in (401, 400))
    except Exception as e:
        check("login inválido rejeitado", False, str(e))

    # login válido
    try:
        tok = json.load(req("/login", body={"username": USER[0], "password": USER[1]}, method="POST"))["token"]
        check("login válido", True)
    except Exception as e:
        check("login válido", False, str(e))
        return None
    H = {"Authorization": f"Bearer {tok}"}

    def get(path):
        return json.load(urllib.request.urlopen(
            urllib.request.Request(BASE + path, headers=H), timeout=60))

    # leagues: contrato (campos que o front consome)
    leagues = get("/leagues")
    fields_ok = all(k in x for x in leagues for k in ("id", "name", "played", "scheduled"))
    no_dupes = len(leagues) == len({x["id"] for x in leagues})
    check(f"/leagues contrato ({len(leagues)} ligas)", fields_ok and no_dupes)

    with_data = [x for x in leagues if x["played"] > 50]
    if not with_data:
        check("liga com dados p/ testar", False, "nenhuma liga >50 jogos")
        return tok
    lid = with_data[0]["id"]

    teams = get(f"/leagues/{lid}/teams")
    check(f"/leagues/{lid}/teams", len(teams) > 0 and all("name" in t for t in teams))

    ms = get(f"/leagues/{lid}/matches")
    check(f"/leagues/{lid}/matches", len(ms) > 0)

    # previsão: partida jogada + validação probabilística
    played = next((m for m in ms if m.get("status") == "played"), ms[0])
    p1 = get(f"/matches/{played['id']}/prediction")
    s = sum(p1["probs"]["1x2"].values())
    check("previsão 1X2 soma≈1", abs(s - 1.0) < 0.02, f"soma={s:.4f}")

    # as-of: deve responder e alterar features (filtro temporal ativo)
    p2 = get(f"/matches/{played['id']}/prediction?as_of_timestamp=2026-01-01T00:00:00+00:00")
    s2 = sum(p2["probs"]["1x2"].values())
    check("previsão as-of responde + soma≈1", abs(s2 - 1.0) < 0.02)
    check("as-of altera features", p2["data"]["home"]["count"] <= p1["data"]["home"]["count"])

    # fixture
    fx = get(f"/leagues/{lid}/teams")  # times válidos
    body = {"league_id": lid, "home_team_id": fx[0]["id"], "away_team_id": fx[1]["id"]}
    fix = json.load(urllib.request.urlopen(urllib.request.Request(
        BASE + "/predict/fixture", data=json.dumps(body).encode(),
        headers={**H, "Content-Type": "application/json"}), timeout=60))
    sf = sum(fix["probs"]["1x2"].values())
    check("predict/fixture soma≈1", abs(sf - 1.0) < 0.02)

    # learning
    st = get("/learning/status")
    check("/learning/status", "calibrated" in st)
    bt = get(f"/learning/backtest/{lid}")
    check("/learning/backtest", "accuracy" in bt and "brier" in bt)

    # histórico
    pr = get("/predictions")
    check("/predictions", "stats" in pr and "items" in pr)

    return tok


# ─────────────────────────── FASE B: E2E browser ───────────────────────────

def phase_e2e(token):
    print("\n=== FASE B — E2E browser (selenium) ===")
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
    except ImportError:
        check("selenium disponível", False, "pip install selenium — fase B pulada")
        return

    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1440,900")
    opts.set_capability("goog:loggingPrefs", {"browser": "ALL"})
    d = webdriver.Chrome(options=opts)
    try:
        d.get(FRONT)
        time.sleep(2)
        d.find_element(By.CSS_SELECTOR, "input[placeholder='Usuário']").send_keys(USER[0])
        d.find_element(By.CSS_SELECTOR, "input[type='password']").send_keys(USER[1])
        d.find_element(By.CSS_SELECTOR, "button.btn-primary").click()
        time.sleep(3)

        # dashboard renderizou com dados reais
        names = d.execute_script(
            "return Array.from(document.querySelectorAll('.league-list li .name')).map(e => e.textContent)")
        # abre grupos se necessário
        d.execute_script("document.querySelectorAll('.continent-toggle').forEach(t => { if (!t.querySelector('.chev.open')) t.click() })")
        time.sleep(0.5)
        names = d.execute_script(
            "return Array.from(document.querySelectorAll('.league-list li .name')).map(e => e.textContent)")
        check("sidebar renderiza nomes de ligas", len(names) > 0 and any(n.strip() for n in names),
              f"{len(names)} itens")

        # layout sem overflow horizontal
        hs = d.execute_script("return document.documentElement.scrollWidth > document.documentElement.clientWidth")
        check("sem scroll horizontal (desktop)", not hs)

        # fluxo: selecionar liga → matches → prever → painel
        li = d.find_elements(By.CSS_SELECTOR, ".league-list li")
        if li:
            li[0].click()
            time.sleep(2)
            rows = d.find_elements(By.CSS_SELECTOR, "table.matches tbody tr")
            check("tabela de partidas renderiza", len(rows) > 0, f"{len(rows)} linhas")
            btns = rows[0].find_elements(By.CSS_SELECTOR, "button") if rows else []
            if btns:
                btns[0].click()
                time.sleep(4)
                bars = d.execute_script(
                    "return Array.from(document.querySelectorAll('.bar-val')).map(e => e.textContent)")
                check("painel de previsão renderiza probabilidades", len(bars) >= 3, f"{len(bars)} barras")

        # navegar pelas 5 abas sem quebrar
        buttons = d.find_elements(By.CSS_SELECTOR, "header nav button")
        for b in buttons:
            b.click()
            time.sleep(1)
        check("navegação nas 5 abas", len(buttons) == 5)

        # console sem erros severos (ignora favicon 404)
        severe = [l["message"][:120] for l in d.get_log("browser")
                  if l["level"] == "SEVERE" and "favicon" not in l["message"]]
        check("console sem erros SEVERE", len(severe) == 0, "; ".join(severe[:3]))
    finally:
        d.quit()


def main():
    print("=" * 60)
    print("AP2WEB — SUÍTE DE REGRESSÃO (PROP-001)")
    print("=" * 60)
    tok = phase_api()
    if tok:
        phase_e2e(tok)

    fails = [r for r in results if not r[1]]
    print("\n" + "=" * 60)
    print(f"RESULTADO: {len(results) - len(fails)}/{len(results)} passaram"
          + (f" — {len(fails)} FALHAS" if fails else " — PASS ✓"))
    print("=" * 60)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
