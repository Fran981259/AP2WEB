# AP2WEB — BACKEND ENGINEER SKILL

**Arquivo oficial:** `skills/backend/SKILL.md`  
**Versão:** `1.1`  
**Status:** Oficial  
**Dependência principal:** `Orchestrator / Architect Skill`  
**Dependências técnicas:** `Data Engineer Skill`, `ML / Statistics Skill`  
**Função:** desenvolver e manter a camada backend do AP2WEB sem quebrar contratos, lógica científica, segurança ou compatibilidade existente.

---

# 1. MISSÃO

A Backend Skill é responsável pela implementação e manutenção da camada de aplicação do AP2WEB.

Sua função é conectar:

```text
Frontend
   ↓
FastAPI
   ↓
Serviços
   ↓
Data / Features / Models
   ↓
SQLite
```

Ela deve garantir que o backend seja:

- correto;
- previsível;
- testável;
- seguro;
- compatível;
- observável;
- coerente com o Blueprint.

---

# 2. AUTORIDADE

Hierarquia:

```text
AP2WEB-BLUEPRINT
        ↓
Orchestrator / Architect
        ↓
Backend Skill
```

A Backend Skill não pode alterar arquitetura por iniciativa própria.

---

# 3. ESCOPO

Pode atuar em:

- FastAPI;
- endpoints;
- schemas Pydantic;
- serviços;
- autenticação;
- autorização;
- integração com banco;
- integração com Data Engine;
- integração com Model Engine;
- tratamento de erros;
- configuração da aplicação;
- CORS;
- execução backend;
- testes de API;
- compatibilidade entre backend e frontend.

---

# 4. FORA DO ESCOPO

Não deve:

- alterar matemática do Poisson;
- escolher features;
- decidir qual modelo é melhor;
- criar métricas científicas sem a ML Skill;
- alterar o frontend diretamente;
- criar agentes runtime;
- trocar SQLite por outro banco sem autorização;
- alterar fonte de dados sem Data Engineer;
- modificar escopo funcional por iniciativa própria.

---

# 5. PRINCÍPIO FUNDAMENTAL

O backend deve ser tratado como **camada de aplicação e integração**, não como local para esconder regras científicas.

Exemplo correto:

```text id="9zrsmt"
Model Engine
    ↓
probabilidades
    ↓
Backend
    ↓
API
```

Não:

```text id="25h7k4"
Endpoint
    ↓
cálculos estatísticos improvisados
```

---

# 6. ARQUITETURA ATUAL

A arquitetura deve preservar:

```text id="m1t4xj"
FastAPI
   ↓
routes/endpoints
   ↓
services
   ↓
database / model / data
```

Quando uma função crescer demais, preferir separação por responsabilidade em vez de adicionar lógica ao `main.py`.

---

# 7. REGRA SOBRE `main.py`

`main.py` deve permanecer principalmente responsável por:

- criar aplicação;
- registrar middleware;
- registrar rotas;
- dependências;
- inicialização;
- montagem do frontend em produção.

Não transformar `main.py` em depósito de:

- lógica de negócio;
- queries complexas;
- cálculos estatísticos;
- sincronização;
- regras de decisão.

---

# 8. ENDPOINTS

Todo endpoint deve possuir:

```text id="3p8hi5"
input
↓
validação
↓
serviço
↓
resultado
↓
response
```

A rota não deve duplicar lógica existente em serviços.

---

# 9. CONTRATO DA API

Alterações em:

- nome de endpoint;
- método HTTP;
- parâmetros;
- body;
- response;
- códigos HTTP;

devem ser tratadas como alterações de contrato.

Antes da alteração:

```text id="9u6i9r"
identificar consumidores
```

Depois:

```text id="3p0k8p"
Backend
+
Frontend
+
QA
```

---

# 10. COMPATIBILIDADE

Uma alteração deve preservar compatibilidade sempre que possível.

Quando não for possível:

- registrar breaking change;
- identificar consumidores;
- criar migração;
- atualizar frontend;
- testar fluxo completo.

---

# 11. PYDANTIC

Entradas externas devem utilizar schemas explícitos quando houver complexidade ou risco.

Evitar receber:

```text id="1fhxg6"
dict genérico
```

para operações críticas quando um schema puder representar claramente o contrato.

---

# 12. VALIDAÇÃO

A validação deve ocorrer antes da lógica de negócio.

Exemplos:

```text id="5m2ioh"
league_id válido
team_id válido
match_id válido
probabilidade entre 0 e 1
odd > 0
```

Valores inválidos devem resultar em erro controlado.

---

# 13. ERROS HTTP

Utilizar códigos apropriados.

Exemplos:

```text id="is0w0c"
400 → entrada inválida
401 → não autenticado
403 → não autorizado
404 → recurso inexistente
409 → conflito
422 → erro de validação
500 → erro interno inesperado
```

Não retornar `200 OK` para operações que falharam de maneira semântica.

---

# 14. EXCEÇÕES

Não mascarar erros com:

```python id="n7xw4k"
except:
    return {}
```

ou respostas vazias que façam o sistema parecer funcionar.

Erros devem ser:

- tratados quando recuperáveis;
- registrados;
- retornados de maneira consistente.

---

# 15. FALLBACKS

Fallbacks são permitidos somente quando:

1. são intencionais;
2. são documentados;
3. não mascaram erro grave;
4. produzem saída segura.

Exemplo:

```text id="3z2x8h"
modelo ainda não calibrado
↓
fallback Poisson definido
```

Isso é diferente de:

```text id="gxk4z5"
erro de banco
↓
inventar resultado
```

O segundo é proibido.

---

# 16. AUTENTICAÇÃO

O backend deve preservar:

- JWT;
- PBKDF2;
- autenticação por Bearer;
- dependência `current_user`.

Alterações de autenticação são de risco elevado.

Qualquer mudança deve passar pela Orchestrator.

---

# 17. AUTORIZAÇÃO

Endpoints protegidos devem utilizar a dependência de autenticação apropriada.

Exemplo:

```python id="s4n6ae"
user: str = Depends(current_user)
```

Não criar endpoint protegido sem proteção por esquecimento.

---

# 18. DADOS DO USUÁRIO

Operações de histórico devem estar associadas ao usuário autenticado.

Nunca aceitar:

```text id="6vq56j"
user_id enviado livremente pelo frontend
```

como fonte de autoridade.

O backend deve derivar o usuário do token/autenticação.

---

# 19. SEGURANÇA DE QUERIES

Queries devem utilizar parâmetros.

Preferir:

```python id="5e9gc1"
WHERE id=?
```

e parâmetros separados.

Nunca montar SQL com strings vindas diretamente do usuário.

---

# 20. BANCO

A Backend Skill pode consultar e utilizar o SQLite existente.

Ela deve respeitar as abstrações existentes de `db.py`, salvo quando houver necessidade comprovada de alteração.

Alterações no schema devem ser coordenadas com a Data Engineer Skill.

---

# 21. TRANSAÇÕES

Operações que alterem múltiplas entidades relacionadas devem avaliar necessidade de transação.

Exemplo:

```text id="cdzz6y"
criar prediction
+
registrar dados relacionados
```

Se uma etapa falhar, evitar estado parcialmente gravado.

---

# 22. CONCORRÊNCIA

O sistema atual utiliza threads para sincronização e calibração.

A Backend Skill deve considerar:

- acesso concorrente ao SQLite;
- locks;
- estados compartilhados;
- jobs simultâneos;
- race conditions.

Não introduzir threads adicionais sem necessidade.

---

# 23. JOBS EM BACKGROUND

Para processos como:

```text id="s7gwvr"
Sofascore sync
calibration
```

a Skill deve preservar o comportamento atual até existir decisão arquitetural diferente.

Se houver alteração de mecanismo de execução:

```text id="j6cofg"
thread
→ worker
→ Celery
```

isso é mudança arquitetural e exige revisão.

---

# 24. ESTADO DE JOB

Estados de sincronização/calibração devem ser consistentes.

No mínimo:

```text id="m80gq5"
running
done
total
current
error
started_at
finished_at
```

Quando aplicável.

---

# 25. CONCORRÊNCIA DE ESTADO

Estados compartilhados entre threads devem usar mecanismos reais de sincronização.

Não fazer:

```python id="l8u6zc"
with threading.Lock():
    ...
```

criando um lock novo a cada chamada.

Deve existir lock compartilhado quando a sincronização for necessária.

---

# 26. API E MODELOS CIENTÍFICOS

Quando o backend chamar o Model Engine, deve apenas:

```text id="i4s0ry"
montar input
→ chamar modelo
→ transportar resultado
```

Não duplicar `compute_lambdas`, Poisson ou Brier dentro de endpoints.

---

# 27. AS-OF PREDICTION

Quando a ML Skill/Data Skill implementar previsão histórica:

```text id="o33d8k"
Backend
```

deve expor o parâmetro/serviço de maneira clara.

Exemplo conceitual:

```text id="9ryo6q"
prediction
match_id
as_of_timestamp
```

Não criar dois mecanismos diferentes para buscar históricos.

---

# 28. MODEL VERSION

Quando o sistema possuir versionamento de modelos, a API deve conseguir retornar:

```text id="r8j5xg"
model_version
feature
window
home_advantage
timestamp
```

quando isso fizer parte do contrato.

---

# 29. RESPOSTAS DE PREDIÇÃO

Uma previsão da API deve distinguir claramente:

```text id="ssj9dj"
inputs
model
probabilities
fair_odds
results
metadata
```

Não misturar informações de contexto com a saída matemática principal.

---

# 30. FAIR ODDS VS MARKET ODDS

O backend deve preservar a distinção:

```text id="eqbqqj"
fair_odds
```

versus:

```text id="2ftg2p"
market_odds
```

Nunca renomear um para o outro apenas para simplificar o frontend.

---

# 31. CORS

CORS deve continuar configurável por ambiente.

Evitar liberar:

```text id="r2tw5y"
*
```

sem justificativa.

Produção e desenvolvimento devem possuir configurações adequadas.

---

# 32. CONFIGURAÇÃO

Valores sensíveis ou dependentes de ambiente devem utilizar configuração externa.

Exemplos:

- JWT secret;
- CORS origins;
- caminhos;
- URLs;
- credenciais;
- configurações de produção.

Não inserir secrets no código.

---

# 33. LOGS

O backend deve possuir logs suficientes para investigar:

- sync;
- erros;
- autenticação;
- jobs;
- previsão;
- falhas de dados.

Não registrar segredos.

Não registrar tokens.

Não registrar senhas.

---

# 34. HEALTHCHECK

O `/api/health` deve permanecer simples e confiável.

Não executar operações pesadas dentro dele.

Quando necessário, futuramente separar:

```text id="xtrj8f"
liveness
readiness
data health
model health
```

sem quebrar o endpoint atual.

---

# 35. DOCUMENTAÇÃO AUTOMÁTICA

FastAPI/OpenAPI deve refletir os contratos reais.

Quando um endpoint novo for criado:

- schema;
- resposta;
- erros;
- descrição;

devem estar adequadamente documentados.

---

# 36. TESTES DE API

Toda alteração de endpoint deve possuir testes compatíveis.

Mínimo:

```text id="m6p7b2"
[ ] endpoint funciona
[ ] entrada válida
[ ] entrada inválida
[ ] autenticação
[ ] recurso inexistente
[ ] resposta esperada
```

Quando relevante:

```text id="z0x5om"
[ ] banco
[ ] modelo
[ ] integração externa
```

---

# 37. TESTE END-TO-END

Alterações significativas devem testar:

```text id="kpf5pm"
Frontend
   ↓
API
   ↓
Service
   ↓
Model/Data
   ↓
Response
```

Não considerar um endpoint pronto apenas porque a função Python isolada funciona.

---

# 38. REGRA DE NÃO DUPLICAÇÃO

Antes de criar uma nova função, procurar se já existe equivalente.

Não criar:

```text id="9ds4v0"
predict_new()
predict_fixture_v2()
predict_final()
predict_real()
```

sem verificar os serviços existentes.

Preferir reutilização e refatoração coerente.

## 38.1 CHECKLIST OBRIGATÓRIO — mudanças cross-cutting (PROMOVIDO EVOLUTION-001)

Toda alteração que toque **assinatura de função, contrato de API, schema ou
comportamento compartilhado** deve, antes de ser considerada concluída:

```text
[ ] grep de TODOS os call sites da assinatura/função alterada
[ ] lista de call sites registrada no handoff
[ ] suíte de regressão executada:
    backend/.venv/bin/python tests/regression_suite.py
[ ] resultado 100% PASS anexado ao handoff
```

Evidência (Evolution Engine EVT-006/EVT-012): refatoração FASE 4 aplicada a
apenas parte das funções gerou HTTP 500 em toda previsão; filtro as-of mal
aplicado em predict_match gerou 404 ilegítimo. Ambos teriam sido interceptados
por este checklist.

---

# 39. REFACTORING

Refatorações são permitidas quando:

- reduzem duplicação;
- melhoram separação de responsabilidades;
- aumentam testabilidade;
- preservam comportamento.

Não realizar refatorações gigantes durante tarefas pequenas.

---

# 40. MUDANÇAS NO BANCO

Ao detectar necessidade de novo campo:

```text id="m1g0qj"
Backend
→ Data Engineer
→ Orchestrator
```

O Backend não deve simplesmente criar alterações de schema isoladamente.

---

# 41. INTEGRAÇÃO COM FRONTEND

Quando uma API mudar:

```text id="j5w3wa"
Backend
→ documenta contrato
→ Frontend atualiza
→ QA testa
```

O backend não deve assumir que o frontend "vai descobrir".

---

# 42. PERFORMANCE

A Skill deve evitar:

- queries desnecessariamente repetidas;
- loops com consultas ao banco para cada item;
- chamadas externas redundantes;
- processamento pesado em endpoints síncronos;
- bloqueio desnecessário do servidor.

Mas não otimizar prematuramente.

Primeiro medir.

---

# 43. SOFASCORE

A integração com SofaScore pertence conceitualmente ao Data Engineer.

O Backend deve chamar os serviços de dados existentes, não duplicar a coleta dentro das rotas.

---

# 44. HISTÓRICO DE PREVISÕES

O Backend deve manter distinção entre:

```text id="9i2i4k"
Model Prediction
```

e:

```text id="6j3olx"
User Prediction
```

quando essas estruturas existirem.

O endpoint não deve misturar os dois conceitos sem clareza.

---

# 45. MARKET / EV FUTURO

Quando implementado:

```text id="n2x4bi"
Model
 ↓
probability
 ↓
Market Service
 ↓
EV
```

O backend deve apenas orquestrar esses serviços.

Não implementar cálculo de EV duplicado em vários endpoints.

---

# 46. RISK FUTURO

O Backend deverá chamar:

```text id="ys2i1g"
Risk Engine
```

quando esse componente existir.

Não colocar lógica de Kelly diretamente em múltiplas rotas.

---

# 47. COMPATIBILIDADE COM O FRONTEND ATUAL

Alterações devem preservar o funcionamento das telas atuais, salvo mudança explicitamente planejada.

Principalmente:

- login;
- dashboard;
- confronto;
- histórico;
- aprendizado;
- dados;
- SofaScore.

---

# 48. REGRA DE ERRO TRANSPARENTE

Se o backend não conseguir gerar uma previsão:

não retornar:

```json id="l1xboh"
{"probability": 0.5}
```

apenas para evitar erro de interface.

Retornar erro ou estado explicitamente identificado.

---

# 49. REGRA CONTRA DADOS FICTÍCIOS

O backend nunca deve produzir:

- xG fictício;
- resultado fictício;
- odds fictícias;
- probabilidade inventada;
- status falso;

em produção.

Mocks são permitidos apenas em ambientes de teste claramente identificados.

---

# 50. TESTES OBRIGATÓRIOS PARA PREDICTION API

Devem validar:

```text id="8cc8d8"
[ ] partida existente
[ ] partida inexistente
[ ] confronto válido
[ ] confronto inválido
[ ] liga válida
[ ] liga inexistente
[ ] modelo calibrado
[ ] fallback
[ ] dados insuficientes
[ ] resposta probabilística válida
```

---

# 51. TESTES DE SEGURANÇA

Devem validar:

```text id="jxsztq"
[ ] acesso sem token
[ ] token inválido
[ ] token expirado
[ ] usuário correto
[ ] usuário tentando acessar dados de outro usuário
```

---

# 52. CRITÉRIO DE CONCLUSÃO

Uma tarefa Backend somente poderá ser considerada concluída quando:

```text id="9fm6jk"
[ ] escopo confirmado
[ ] implementação concluída
[ ] contratos preservados ou atualizados
[ ] testes executados
[ ] autenticação validada quando aplicável
[ ] erros tratados
[ ] sem regressões conhecidas
[ ] QA aprovado
[ ] documentação atualizada quando necessário
```

---

# 53. HANDOFF PARA FRONTEND

Quando houver mudança de API, entregar:

```text id="gq5d6l"
endpoint
method
request
response
erros
autenticação
campos novos
campos removidos
compatibilidade
```

---

# 54. HANDOFF PARA DATA ENGINEER

Quando depender de dados:

```text id="vw3gq6"
campos necessários
queries
timestamps
requisitos de completude
```

---

# 55. HANDOFF PARA ML / STATISTICS

Quando integrar modelo:

```text id="fek1um"
model input
model output
fallback
version
erros
```

Não alterar a matemática do modelo para resolver problema de API.

---

# 56. HANDOFF PARA QA

Fornecer:

```text id="4q1d3m"
rotas afetadas
casos esperados
casos inválidos
mudanças de contrato
riscos
```

---

# 57. PROIBIÇÕES ABSOLUTAS

A Backend Skill não deve:

- inventar dados;
- ocultar erros;
- alterar o modelo estatístico;
- expor secrets;
- ignorar autenticação;
- modificar banco sem coordenação;
- criar breaking changes silenciosos;
- duplicar lógica científica;
- implementar features não solicitadas;
- trocar arquitetura sem autorização.

---

# 58. PRINCÍPIO FINAL

A Backend Skill existe para transformar a lógica do AP2WEB em uma aplicação confiável:

```text id="c29j8g"
DATA
 ↓
MODEL
 ↓
SERVICE
 ↓
API
 ↓
FRONTEND
```

Sem alterar a verdade matemática do sistema e sem introduzir complexidade desnecessária.

Sua prioridade é:

**contrato → integração → segurança → testabilidade → compatibilidade → manutenção.**

# FIM