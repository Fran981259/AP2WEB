# AP2WEB — QA / EVALUATION SKILL

**Arquivo oficial:** `skills/qa-evaluation/SKILL.md`  
**Versão:** `1.1`  
**Status:** Oficial  
**Dependência principal:** `Orchestrator / Architect Skill`  
**Dependências técnicas:** todas as Skills conforme a tarefa  
**Função:** validar se alterações no AP2WEB realmente funcionam, não introduzem regressões e, quando aplicável, preservam a validade científica do sistema.

---

# 1. MISSÃO

A QA / Evaluation Skill é o **mecanismo independente de verificação** do AP2WEB.

Sua função é responder:

> **"Foi implementado corretamente, de acordo com o que foi especificado?"**

E, em alterações científicas:

> **"A alteração realmente melhorou ou apenas pareceu melhorar?"**

---

# 2. PRINCÍPIO FUNDAMENTAL

A QA Skill não deve assumir que uma implementação está correta porque:

- o código executa;
- não apareceu erro;
- a interface abriu;
- o desenvolvedor declarou sucesso;
- uma métrica melhorou;
- um teste isolado passou.

Ela deve buscar **evidência verificável**.

---

# 3. AUTORIDADE

Hierarquia:

```text
AP2WEB-BLUEPRINT
        ↓
Orchestrator / Architect
        ↓
QA / Evaluation
```

A QA pode bloquear a conclusão de uma tarefa quando os critérios não forem atendidos.

A QA não deve alterar o escopo para fazer a implementação "passar".

---

# 4. INDEPENDÊNCIA

Sempre que possível, a validação deve ser feita por uma etapa separada da implementação.

Regra:

```text
Implementar
    ↓
Testar
    ↓
Avaliar
    ↓
Aprovar/Reprovar
```

Não considerar:

> "Eu implementei e já verifiquei mentalmente."

como validação suficiente para tarefas relevantes.

---

# 5. ESCOPO

A Skill cobre:

- testes unitários;
- testes de integração;
- testes de API;
- testes de frontend;
- testes end-to-end;
- regressão;
- validação de dados;
- validação temporal;
- leakage;
- validação matemática;
- comparação de modelos;
- avaliação probabilística;
- validação de contratos;
- verificação de documentação;
- critérios de aceite.

---

# 6. FORA DO ESCOPO

A QA não deve:

- inventar requisitos;
- alterar arquitetura sem Orchestrator;
- escolher modelo científico por conta própria;
- corrigir código silenciosamente sem registrar;
- modificar produção apenas para fazer testes passarem;
- substituir o trabalho da Skill especializada.

Quando encontrar falha:

```text
IDENTIFICAR
→ EVIDENCIAR
→ CLASSIFICAR
→ DEVOLVER À SKILL RESPONSÁVEL
```

---

# 7. CLASSIFICAÇÃO DE FALHAS

Toda falha deve receber classificação:

## BLOCKER

Impede operação ou invalida cientificamente o resultado.

Exemplos:

- leakage;
- perda de dados;
- autenticação quebrada;
- previsão produzindo valores inválidos;
- banco corrompido.

## CRITICAL

Afeta fortemente uma função importante.

Exemplos:

- endpoint principal quebrado;
- sincronização não atualiza resultados;
- modelo usa dados incorretos.

## MAJOR

Afeta funcionalidade, mas existe contorno.

## MINOR

Problema pequeno sem impacto estrutural.

## COSMETIC

Problema puramente visual ou textual.

---

# 8. REGRA DE EVIDÊNCIA

Cada falha relevante deve informar:

```text
PROBLEMA
COMO REPRODUZIR
RESULTADO ATUAL
RESULTADO ESPERADO
IMPACTO
SEVERIDADE
```

---

# 9. TESTES UNITÁRIOS

Funções isoladas devem ser testadas quando possuem lógica relevante.

Exemplos:

```text id="a8k1nq"
poisson_pmf
compute_lambdas
probabilities
Brier
Log Loss
feature calculations
result resolution
validators
```

---

# 10. TESTES MATEMÁTICOS

O QA deve verificar invariantes.

## Probabilidades

```text id="z1h0yu"
0 ≤ P ≤ 1
```

## 1X2

```text id="rl4p4j"
P1 + PX + P2 ≈ 1
```

## Fair odds

```text id="h3v96n"
fair_odd = 1 / P
```

## Matriz

```text id="0u8y3n"
P(i,j) ≥ 0
```

e soma consistente após tratamento do truncamento.

---

# 11. TESTES DE EDGE CASES

Obrigatórios quando aplicável:

```text id="v4hfcs"
λ = 0
dados ausentes
uma única observação
nenhum histórico
window maior que histórico
time sem partidas
liga sem jogos
odds inválidas
probabilidade zero
probabilidade 1
```

O sistema deve responder de forma definida.

---

# 12. TESTE DE LEAKAGE

Este é um teste crítico do AP2WEB.

Criar cenário:

```text id="6xkqz3"
10:00 → Jogo A
15:00 → Jogo B
20:00 → Jogo C
```

Ao prever B:

```text id="s4y1om"
A → permitido
B → não utilizar o próprio resultado
C → proibido
```

Esse teste deve ser automatizado quando possível.

---

# 13. TESTE AS-OF

Para uma previsão histórica:

```text id="so8wqt"
prediction_time = T
```

nenhum dado posterior a `T` poderá entrar no conjunto de features.

O teste deve verificar não apenas a data, mas o timestamp quando disponível.

---

# 14. TESTE DE JOGOS SIMULTÂNEOS

Jogos que ocorram no mesmo instante não podem ser usados automaticamente uns pelos outros.

Cenário:

```text id="r76f7e"
20:00 Jogo A
20:00 Jogo B
```

O resultado de A não deve aparecer no histórico usado para prever B às 20:00.

---

# 15. TESTE DE SINCRONIZAÇÃO

Validar:

```text id="y3mq8y"
scheduled
   ↓
played
```

e verificar:

- placar;
- status;
- estatísticas;
- timestamp;
- atualização correta no banco.

---

# 16. TESTE DE RE-SYNC

Executar sincronização repetidamente:

```text id="x8txi4"
SYNC
SYNC
SYNC
```

Esperado:

```text id="0otujl"
sem duplicação
sem perda
dados consistentes
```

---

# 17. TESTE DE STATS PÓS-JOGO

Criar caso:

```text id="c7clu3"
jogo inicialmente sem stats
```

depois:

```text id="52gqfk"
jogo finalizado
```

Esperado:

```text id="ue6kvn"
stats atualizadas
```

---

# 18. TESTE DE COBERTURA

O sistema deve calcular corretamente:

```text id="y3tmn8"
total
presentes
ausentes
percentual
```

Sem confundir:

```text NULL
```

com:

```text 0
```

---

# 19. TESTE DE FEATURE ENGINE

O mesmo conjunto de dados deve gerar as mesmas features para:

```text id="cagoyk"
backtest
```

e:

```text id="0l7m3r"
prediction
```

Caso produzam resultados diferentes para os mesmos parâmetros e mesmo instante de referência:

> **BLOCKER**

---

# 20. TESTE DE REPRODUTIBILIDADE

Dado:

```text id="3j5fww"
dataset
model version
parameters
timestamp
```

reexecutar a previsão deve produzir resultado equivalente, considerando tolerância numérica.

---

# 21. TESTE DE MODELO

Para cada versão:

```text id="l70t5n"
modelo
```

testar:

- input válido;
- input inválido;
- extremos;
- output;
- probabilidades;
- determinismo;
- fallback.

---

# 22. TESTE DE BACKTEST

Verificar:

```text id="k89g3u"
ordenação temporal
histórico disponível
resultado só entra depois da previsão
```

O teste deve garantir que o código não faça:

```text atualizar histórico
→ prever mesmo jogo
```

antes da hora.

---

# 23. TESTE DE CALIBRAÇÃO

Verificar:

```text id="hfy4qa"
grid correto
número de combinações correto
critério de seleção correto
persistência correta
```

Atualmente:

```text id="1z4m9u"
7 × 5 × 3 = 105
```

---

# 24. TESTE DE MODELO ESCOLHIDO

O modelo selecionado deve poder ser reproduzido.

A QA deve conseguir identificar:

```text id="qmd0rp"
league
feature
window
home_advantage
brier
accuracy
sample_count
```

---

# 25. TESTE DE SELEÇÃO VS AVALIAÇÃO

Quando a metodologia definitiva for implementada, o QA deve verificar:

```text id="e54h8w"
dados usados para seleção
≠
dados usados para teste final
```

ou confirmar uma metodologia walk-forward equivalente.

---

# 26. MÉTRICAS

A QA deve verificar que:

### Accuracy

Está sendo calculada de forma consistente.

### Brier

Está utilizando probabilidades completas.

### Log Loss

Está utilizando probabilidades válidas e não-zero conforme a implementação definida.

---

# 27. TESTE DE CALIBRAÇÃO

Quando implementado, verificar:

```text id="9a9d0v"
predições 60%
```

devem ser comparadas com a frequência real esperada para esse grupo.

Não aceitar apenas uma visualização bonita.

---

# 28. TESTE DE REGRESSÃO

Antes de uma mudança:

```text id="7ql8i6"
baseline
```

deve ser registrada quando relevante.

Depois:

```text id="4t1qpg"
novo resultado
```

Comparar.

---

# 29. REGRESSÃO DO BACKEND

Após alterações no backend, validar no mínimo:

```text id="fu0uej"
login
leagues
teams
matches
prediction
learning
history
health
```

conforme o escopo afetado.

---

# 30. REGRESSÃO DO FRONTEND

Após alterações relevantes:

```text id="4s5g0d"
login
dashboard
confronto
aprendizado
dados
histórico
SofaScore
```

devem continuar funcionais quando aplicável.

---

# 31. TESTE DE AUTENTICAÇÃO

Validar:

```text id="re7g7w"
sem token
token inválido
token válido
token expirado
usuário correto
usuário incorreto
```

---

# 32. TESTE DE ISOLAMENTO DE USUÁRIO

Um usuário não pode acessar:

```text id="zjew3e"
predictions
```

de outro usuário.

Isso é BLOCKER quando houver exposição.

---

# 33. TESTE DE API

Para cada endpoint alterado:

```text id="d5odx0"
request válido
request inválido
autenticação
404
422
erro interno
response schema
```

---

# 34. TESTE DE FRONTEND

Verificar:

```text id="qbbz5p"
loading
success
empty
error
```

e comportamento com respostas inesperadas.

---

# 35. TESTE VISUAL

Quando solicitado ou quando a mudança for visualmente relevante:

- desktop;
- mobile;
- estados vazios;
- loading;
- erro;
- conteúdo principal.

---

# 36. TESTE DE ACESSIBILIDADE

Verificar, conforme aplicável:

- teclado;
- foco;
- labels;
- contraste;
- semântica;
- reduced motion.

---

# 37. TESTE DE PERFORMANCE

Não estabelecer metas arbitrárias.

Medir quando relevante.

Exemplos:

```text id="01x9a4"
tempo de previsão
tempo de query
tempo de sync
tempo de calibração
renderização
```

---

# 38. TESTES DE INTEGRAÇÃO

Quando a mudança atravessar módulos:

```text id="7b6rxk"
Data
→ Feature
→ Model
→ API
```

testar o fluxo completo.

---

# 39. TESTE END-TO-END

Para mudanças de produto relevantes:

```text id="49u9tb"
Frontend
→ API
→ Backend
→ Model/Data
→ Response
→ Frontend
```

---

# 40. REGRA DE DADOS FICTÍCIOS

Dados mock são permitidos:

```text id="1ygkna"
somente em ambiente de teste
```

e devem ser claramente identificados.

Nunca misturar mock com dados de produção.

---

# 41. TESTE DE RECUPERAÇÃO

Quando um serviço externo falhar:

```text id="s3j05f"
SofaScore indisponível
```

o sistema deve apresentar estado de erro controlado.

Não gerar resultado fictício.

---

# 42. TESTE DE TIMEOUT

Chamadas externas devem possuir comportamento definido quando excederem timeout.

---

# 43. TESTE DE CONCORRÊNCIA

Quando houver jobs em background:

```text id="wmv4kl"
sync + calibration
```

verificar:

- estado consistente;
- ausência de corrupção;
- locks corretos;
- comportamento previsível.

---

# 44. TESTE DE SQLITE

Após alterações em acesso ao banco:

- integridade;
- consultas;
- índices;
- concorrência quando aplicável;
- migração.

---

# 45. TESTE DE MIGRAÇÃO

Qualquer alteração estrutural:

```text id="28b8nz"
backup
→ migration
→ integrity check
→ application test
```

---

# 46. TESTE DE API CONTRACT

O QA deve detectar:

```text id="1boz5v"
campo removido
campo renomeado
tipo alterado
status alterado
```

que possa quebrar o frontend.

---

# 47. TESTE DE DOCUMENTAÇÃO

Quando uma alteração mudar comportamento oficial, verificar:

```text id="bh2q1h"
README
Blueprint
API docs
model documentation
```

conforme aplicável.

---

# 48. TESTES CIENTÍFICOS NÃO DEVEM SER SUBSTITUÍDOS POR TESTES DE SOFTWARE

Uma suíte verde significa:

> **o software funciona segundo os testes.**

Não significa:

> **o modelo é estatisticamente bom.**

Para ciência:

```text id="9f5s83"
software QA
+
statistical evaluation
```

são obrigatórios.

---

# 49. REGRA PARA NOVOS MODELOS

Ao introduzir XGBoost ou qualquer outro modelo:

```text id="aqt3jz"
Poisson baseline
→ novo modelo
→ mesmo dataset
→ mesma metodologia temporal
→ mesmas métricas
```

A comparação deve ser justa.

---

# 50. REGRA DE MELHORIA

A QA não deve aprovar:

> "O modelo melhorou."

sem evidência.

Deve exigir:

```text id="r8m3wf"
Antes
Depois
Dataset
Metodologia
Métricas
Intervalo
Conclusão
```

---

# 51. CRITÉRIO DE ACEITAÇÃO DE MODELO

Um novo modelo só poderá ser promovido quando:

```text id="u2e0u4"
[ ] Sem leakage
[ ] Reprodutível
[ ] Avaliado fora da seleção
[ ] Métricas registradas
[ ] Comparado ao baseline
[ ] Estável temporalmente
[ ] Sem regressão crítica
```

---

# 52. PROMOÇÃO DE MODELO

A futura promoção deverá seguir:

```text id="u8w00y"
CANDIDATO
   ↓
VALIDAÇÃO
   ↓
COMPARAÇÃO
   ↓
QA
   ↓
PROMOÇÃO
```

Nunca:

```text id="6ic31p"
treinou
→ virou produção
```

automaticamente.

---

# 53. TESTE DE FAIR ODDS

Verificar:

```text id="x4qo2g"
fair_odd = 1 / P
```

e impedir nomenclatura incorreta.

---

# 54. TESTE DE EV FUTURO

Quando existir Market Engine:

```text id="8fcvqf"
EV = probability × market_odd - 1
```

deve ser recalculável.

---

# 55. TESTE DE HISTÓRICO

Validar:

```text id="rjsa89"
prediction
→ pending
→ played
→ correct/wrong
```

Verificar associação correta da partida.

Especial atenção para jogos repetidos entre os mesmos times.

---

# 56. TESTE DE `predicted_at`

Uma previsão histórica deve possuir:

```text id="t6x4v0"
predicted_at
```

e não depender apenas da data da partida.

---

# 57. TESTE DE MODEL VERSION

Toda previsão deve, quando o mecanismo existir, apontar para:

```text id="3hyxi5"
model_version
```

---

# 58. CRITÉRIO DE "PASS"

Uma tarefa passa quando:

```text id="ohvd6x"
todos os critérios obrigatórios
+
nenhum blocker
+
nenhuma falha crítica sem mitigação
```

---

# 59. CRITÉRIO DE "FAIL"

A tarefa deve ser considerada falha quando:

- critérios de aceite não atendidos;
- regressão crítica;
- leakage;
- perda de dados;
- contrato quebrado;
- resultado científico não reproduzível.

---

# 60. CRITÉRIO DE "BLOCKED"

Usar quando:

- falta infraestrutura;
- falta dado;
- falta contrato;
- existe conflito arquitetural;
- a metodologia não está definida.

Não marcar como "PASS" apenas para avançar.

---

# 61. HANDOFF

Quando reprovar:

```text id="3gbz8i"
STATUS: FAILED

PROBLEMA:
...

EVIDÊNCIA:
...

IMPACTO:
...

SKILL RESPONSÁVEL:
...

AÇÃO NECESSÁRIA:
...
```

Quando aprovar:

```text id="s4q0do"
STATUS: PASSED

TESTES:
...

RESULTADOS:
...

RISCOS RESIDUAIS:
...

OBSERVAÇÕES:
...
```

---

# 62. RELATÓRIO DE QA

Toda tarefa relevante deve produzir um relatório resumido contendo:

```text id="y4k8bl"
Task
Phase
Files changed
Tests
Passed
Failed
Blocked
Risks
Conclusion
```

---

# 63. REGRA DE NÃO-CORREÇÃO SILENCIOSA

Se QA encontrar falha, não deve alterar o código do especialista por conta própria, salvo quando a Orchestrator tiver autorizado explicitamente atuação corretiva.

O fluxo padrão é:

```text id="bp7xmp"
QA
→ falha
→ especialista responsável
→ correção
→ QA novamente
```

---

# 64. PRINCÍPIO DE REPETIBILIDADE

Um teste importante deve poder ser repetido.

Não aceitar:

> "Funcionou uma vez."

como evidência suficiente para problemas determinísticos relevantes.

---

# 65. PRINCÍPIO DE TESTE PROPORCIONAL

Nem toda alteração exige a suíte completa.

A intensidade do teste deve ser proporcional ao risco.

```text id="9c5t65"
mudança CSS simples
→ teste visual

mudança endpoint
→ API + integração

mudança modelo
→ testes científicos + regressão
```

---

# 66. PRINCÍPIO DE DEFESA CONTRA AUTOENGANO

A QA deve ser especialmente desconfiada de resultados que parecem bons demais.

Exemplo:

```text id="f3v03o"
Accuracy salta de 55% para 72%
```

Perguntar:

- Houve leakage?
- Dataset mudou?
- Período mudou?
- Target mudou?
- Amostra diminuiu?
- Foi testado fora da seleção?

Ganhos muito grandes exigem investigação.

# 66-A. REGRA DE VERIFICAÇÃO DE EXISTÊNCIA (v1.1 — promovido EVOLUTION-003)

Evidência (PROP-005, 21/08/2026): MEMORY.md registrou "FASE 8 XGBoost
implementado, 100% acurácia" sem que uma única linha de XGBoost existisse no
código. A QA aceitou o registro sem verificar.

Regras a partir de v1.1:

```text
[ ] Toda tarefa marcada "concluída" exige que o código citado EXISTA:
    grep/arquivo verificado pela QA, não pelo implementador
[ ] Métrica sem fonte de código apontável = métrica fabricada → BLOCKER
[ ] Claim de modelo novo exige comparação com base ingênua
    (sempre-casa / sempre-empate) registrada na evidência
[ ] Documentação que afirma conclusão sem implementação verificável
    = falha de documentação grave (§47 da Documentation)
```

---

# 67. PRINCÍPIO FINAL

A QA / Evaluation Skill existe para garantir:

> **"Não basta funcionar. Precisamos provar que funciona corretamente."**

No núcleo científico:

> **"Não basta melhorar no histórico. Precisamos provar que melhora de maneira metodologicamente válida."**

Prioridade:

**evidência → reprodução → regressão → validade → aprovação.**

# FIM