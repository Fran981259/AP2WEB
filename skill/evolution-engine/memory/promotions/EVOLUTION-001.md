# EVOLUTION-001 — Promoção PROP-001 + PROP-002

**Data:** 21/08/2026
**Aprovação:** Humana (usuário autorizou "então faça 001" + "002 go")

## Mudanças promovidas

### PROP-001 → QA (novo artefato)
- **O quê:** suíte de regressão obrigatória `tests/regression_suite.py`
  - Fase A: smoke API (health, auth ×3, contratos, validade probabilística 1X2≈1, as-of temporal)
  - Fase B: E2E selenium (login, sidebar com nomes, sem overflow, tabela, painel previsão, 5 abas, console SEVERE)
- **Por quê:** Padrões P1/P2 — regressões cross-cutting escapavam e chegavam ao usuário (EVT-004/006/008/009/010/012)
- **Validação:** primeira execução real → **20/20 PASS**

### PROP-002 → Backend Skill v1.0 → v1.1
- **O quê:** checklist obrigatório §38.1 (grep call sites + handoff + suíte 100% PASS)
- **Por quê:** EVT-006/EVT-012 — refatoração incompleta gerou HTTP 500 global e 404 ilegítimo
- **Rollback:** git revert do skill doc; suíte permanece como ferramenta neutra

## Resultado esperado vs observado
- Esperado: interceptar regressões cross-cutting antes do usuário
- Observado: a própria suíte já validou o estado atual (20/20); monitoramento nas próximas tarefas confirmará a redução de reincidência (revisitar após ~10 tarefas)
