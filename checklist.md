# AP2WEB - Auditoria e Checklist de Entrega

Data da auditoria: 2026-09-16

Legenda: `[x]` verificado nesta auditoria; `[~]` existe, mas tem ressalva ou só consta em registro anterior; `[ ]` pendente/não verificado.

## Resumo executivo

- [x] Backend compila.
- [x] Ruff passa em `backend/app` e `tests`.
- [x] Mypy passa no escopo configurado (8 módulos).
- [x] ESLint passa sem warnings nesta execução.
- [x] Build de produção do frontend passa.
- [x] Smoke test do Uvicorn real passa para health, readiness e headers.
- [x] Compose passa pela validação de configuração YAML.
- [ ] Suíte pytest completa passa: a execução fica bloqueada em `tests/test_rbac.py::test_user_cannot_sync`, esperando o lifespan do `TestClient`.
- [ ] Docker Engine acessível: cliente está instalado, mas `docker info` falha com permissão negada no socket `/var/run/docker.sock`.
- [~] O checklist anterior registra deploy Compose/Railway, migração, backup/restore e monitoramento em 2026-09-13. São registros do projeto, não foram reexecutados nem verificados de forma independente nesta auditoria.

## Aplicação e qualidade

- [x] FastAPI/lifespan e endpoints `/api/health`, `/api/ready` e `/api/health/dependencies` existem.
- [x] Compilação: `python3 -m compileall -q backend/app tests` passou.
- [x] Ruff: `backend/.venv/bin/ruff check backend/app tests` passou.
- [x] Mypy: passou nos 8 módulos configurados.
- [x] ESLint: passou sem erros ou warnings nesta execução.
- [x] Frontend: `npm --prefix frontend run build` passou.
- [x] Runtime HTTP: `tests/runtime_http_suite.py` passou em Uvicorn real nesta auditoria.
- [ ] Testes HTTP in-process: `TestClient` trava no handshake de lifespan.
- [ ] Suíte completa: não aprovada até eliminar o travamento e obter exit code zero.
- [~] ESLint sem warning foi observado agora; o warning React citado em relatórios anteriores não apareceu nesta execução, mas requer confirmar no estado de código/CI correspondente.

## Segurança e backend

- [x] Configuração de produção exige secret forte, CORS explícito, cookies seguros, RBAC e Redis para rate limit.
- [x] Sessões persistentes, refresh rotation, CSRF, RBAC e auditoria estão implementados.
- [x] Trusted proxy depende de CIDR configurado.
- [x] Dados sensíveis são redigidos na auditoria.
- [~] Redis health aparece no endpoint de dependências; verificar que a implementação executa uma operação Redis real e falha fechada quando Redis está indisponível.
- [~] Existe worker standalone e armazenamento persistente de jobs/heartbeat/leases.
- [ ] Configuração de produção rejeita explicitamente `AP2WEB_ENABLE_WORKER=true`; há worker em thread opt-in no código, então confirmar bloqueio para impedir duplicação em API replicada.
- [ ] Testes HTTP de auth/RBAC/CSRF/readiness não têm execução completa verde nesta auditoria.
- [ ] PostgreSQL e Redis não puderam ser testados nesta sessão: os testes de integração foram skipped sem serviços acessíveis.

## Modelagem e dados

- [x] Protocolo científico existe em `PROTOCOLO-AVALIACAO-CIENTIFICA.md`.
- [x] O protocolo exige holdout congelado, walk-forward, baselines, métricas e artefatos reproduzíveis.
- [~] Bayesian/context/XGBoost permanecem experimentais conforme checklist anterior; não promover sem protocolo concluído.
- [~] O checklist anterior indica que odds reais não alimentam os cálculos de mercado/risco.
- [ ] Revalidar resultado preditivo com snapshot congelado, baselines e relatório reproduzível.

## Docker de homologação

- [x] `deploy/docker-compose.test.yml` define API, worker, frontend, PostgreSQL e Redis.
- [x] `deploy/frontend.Dockerfile` e `deploy/nginx.conf` existem.
- [x] Compose inclui health checks e volumes de teste.
- [x] `docker compose ... config --quiet` passou nesta auditoria.
- [ ] Executar `docker compose -f deploy/docker-compose.test.yml up --build` nesta sessão: bloqueado por falta de permissão ao daemon Docker.
- [ ] Verificar containers saudáveis em conjunto.
- [ ] Criar job via API e confirmar processamento/status pelo worker.
- [ ] Testar persistência após recriar containers.
- [ ] Executar integração real com PostgreSQL e Redis neste ambiente.

## Swarm e VPS Debian/Tailscale

- [ ] Stack Docker Swarm versionada e validada.
- [ ] Registry, secrets e configs Swarm definidos.
- [ ] Rolling update e rollback testados.
- [ ] Persistência e posicionamento de PostgreSQL/Redis definidos para os nós reais.
- [ ] IP Tailscale `100.95.111.24` confirmado no servidor.
- [ ] ACL Tailscale, firewall, SSH e HTTPS auditados.
- [ ] Nenhuma porta PostgreSQL/Redis/API interna exposta publicamente.
- [ ] Reboot da VPS e recuperação de serviços testados.

## Backup e operação

- [~] Checklist anterior registra backup/restore em Compose e monitoramento UptimeRobot em 2026-09-13; confirmar escopo, retenção, destino externo e alertas no ambiente real.
- [ ] Verificar backup externo criptografado e política de retenção.
- [ ] Repetir restore a partir do backup mais recente e comparar contagens/checksums.
- [ ] Confirmar alertas para API, readiness, worker, Redis, PostgreSQL e disco.
- [ ] Documentar procedimento de recuperação e rollback da VPS.

## Ações prioritárias

1. Corrigir a suíte travada no handshake `TestClient`/lifespan; executar a suíte inteira até exit code zero.
2. Obter acesso autorizado ao daemon Docker e executar a stack de homologação completa.
3. Testar integração API -> PostgreSQL/Redis -> worker com criação, conclusão, falha e cancelamento de job.
4. Confirmar as alegações registradas para Railway, migração, backup/restore e monitoramento, anexando evidências reproduzíveis.
5. Só então iniciar a auditoria de Swarm/VPS/Tailscale.

## Limite desta auditoria

Este checklist diferencia evidência reproduzida em 2026-09-16 de status registrados anteriormente no projeto. Acesso negado ao daemon Docker impediu verificar containers nesta sessão; o relatório não trata documentação histórica como prova atual de disponibilidade.
