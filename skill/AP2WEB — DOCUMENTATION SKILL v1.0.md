# AP2WEB — DOCUMENTATION SKILL

**Arquivo oficial:** `skills/documentation/SKILL.md`  
**Versão:** `1.0`  
**Status:** Oficial  
**Dependência principal:** `Orchestrator / Architect Skill`  
**Dependências:** todas as Skills, conforme a natureza da alteração  
**Função:** manter a documentação do AP2WEB fiel ao código, à arquitetura, à metodologia científica e às decisões oficiais do projeto.

---

# 1. MISSÃO

A Documentation Skill é responsável por garantir que o conhecimento oficial do AP2WEB permaneça:

- correto;
- atualizado;
- rastreável;
- consistente;
- reproduzível;
- alinhado ao código real;
- alinhado ao Blueprint.

Sua responsabilidade central é impedir que exista:

```text id="g5f0j4"
DOCUMENTAÇÃO ≠ SISTEMA REAL
```

---

# 2. PRINCÍPIO FUNDAMENTAL

A documentação deve descrever **o que realmente existe**, não o que o projeto gostaria de possuir.

Regra:

> **Código e comportamento validado são evidência. Documentação é representação dessa evidência.**

Nunca documentar uma funcionalidade como implementada antes de sua validação.

---

# 3. HIERARQUIA DE AUTORIDADE

A Documentation Skill deverá respeitar:

```text id="x3glj7"
Blueprint oficial
      ↓
Estado real validado do código
      ↓
Resultados de testes
      ↓
Decisões arquiteturais registradas
      ↓
README / documentação operacional
```

Uma documentação antiga não supera o comportamento real do sistema.

---

# 4. ESCOPO

A Skill pode atuar em:

- Blueprint;
- README;
- documentação técnica;
- arquitetura;
- documentação de API;
- documentação de modelos;
- metodologia;
- changelog;
- decisões arquiteturais;
- instruções de instalação;
- instruções de execução;
- documentação das Skills;
- documentação de experimentos;
- documentação de versões;
- registro de limitações;
- roadmap oficial.

---

# 5. FORA DO ESCOPO

A Documentation Skill não deve:

- implementar funcionalidades;
- alterar código para "combinar" com documentação;
- decidir arquitetura sozinha;
- declarar sucesso sem evidência;
- alterar métricas;
- inventar resultados;
- redefinir metodologia científica;
- criar novas funcionalidades.

Quando encontrar inconsistência:

```text id="a5v4mu"
IDENTIFICAR
→ REGISTRAR
→ ENCAMINHAR
```

A correção deve ocorrer na fonte verdadeira, não através de documentação enganosa.

---

# 6. TIPOS DE DOCUMENTAÇÃO

O projeto deve distinguir:

## 6.1 Normativa

Define o que deve ser feito.

Exemplo:

```text id="9gg2am"
AP2WEB-BLUEPRINT.md
```

## 6.2 Descritiva

Explica o que existe.

Exemplo:

```text id="4mvz2n"
README.md
```

## 6.3 Experimental

Registra experimentos e resultados.

Exemplo:

```text id="2n6q6s"
experiments/
```

## 6.4 Operacional

Explica como executar e operar.

Exemplo:

```text id="b3n64b"
RUNBOOK.md
```

---

# 7. AP2WEB-BLUEPRINT

O Blueprint é o documento de maior importância operacional.

Ele deve conter:

- objetivo;
- escopo;
- arquitetura;
- fases;
- regras;
- componentes;
- limites;
- critérios de aceitação;
- decisões importantes.

A Documentation Skill não pode alterar o Blueprint silenciosamente.

Mudanças relevantes exigem registro de versão.

---

# 8. README

O README deve ser:

- claro;
- fiel;
- útil para instalação;
- útil para entendimento;
- coerente com o estado atual.

Não deve conter promessas de funcionalidades futuras como se fossem implementadas.

---

# 9. IMPLEMENTADO VS PLANEJADO

Toda documentação deve distinguir claramente:

```text id="j1m15y"
✅ Implementado
🚧 Em desenvolvimento
📋 Planejado
❌ Removido / descontinuado
```

Não usar linguagem ambígua.

---

# 10. REGRA DE VERACIDADE TÉCNICA

Não escrever:

> "O sistema utiliza XGBoost"

se XGBoost não estiver efetivamente sendo utilizado.

Não escrever:

> "O sistema aprende continuamente"

se não existe retreinamento contínuo.

Não escrever:

> "Rede neural"

quando a implementação real é Poisson.

Não escrever:

> "Odds de mercado"

quando o sistema está mostrando `fair_odds`.

---

# 11. NOMENCLATURA OFICIAL

A Documentation Skill deve preservar termos tecnicamente corretos.

### Modelo atual

> Motor probabilístico Poisson adaptativo.

### Processo atual

> Calibração por grid search e backtesting temporal.

### Probabilidades

> Probabilidades estimadas pelo modelo.

### Odds calculadas pelo modelo

> Fair odds.

### Odds externas

> Market odds.

### Histórico do usuário

> User predictions / user picks.

### Histórico do modelo

> Model predictions.

---

# 12. DOCUMENTAÇÃO DO MODELO

A documentação do modelo deve apresentar:

```text id="j9g9li"
inputs
fórmulas
parâmetros
features
processamento
outputs
limitações
```

Nunca apenas:

> "O modelo usa IA."

---

# 13. DOCUMENTAÇÃO DO POISSON

Deve explicar:

```text id="m7qv9s"
λ_home
λ_away
Poisson PMF
matriz de placares
agregação 1X2
BTTS
Over/Under
fair odds
```

Quando uma aproximação ou heurística existir, ela deve ser identificada explicitamente.

---

# 14. DOCUMENTAÇÃO DA CALIBRAÇÃO

Deve registrar:

```text id="vhx3x6"
home_advantage grid
window grid
feature grid
número de combinações
métrica de seleção
mínimo de amostras
```

Também deve explicar:

> A seleção de hiperparâmetros não equivale automaticamente a validação fora da amostra.

---

# 15. DOCUMENTAÇÃO DO BACKTEST

Deve registrar:

- como as partidas são ordenadas;
- quais dados estavam disponíveis;
- como o histórico é construído;
- quando o resultado entra no histórico;
- como são calculadas as métricas;
- como vazamento é evitado.

Quando a metodologia for aprimorada:

```text id="ml2h4h"
backtest antigo
→ metodologia nova
```

registrar a mudança.

---

# 16. DOCUMENTAÇÃO DAS MÉTRICAS

Para cada métrica utilizada, explicar:

```text id="8i6jgc"
nome
fórmula
interpretação
melhor/mínimo
limitações
```

No mínimo:

- Accuracy;
- Brier Score;
- Log Loss.

Futuramente:

- Calibration;
- ECE;
- ROI;
- Yield.

---

# 17. EXPERIMENTOS

Todo experimento científico relevante deverá ser registrado.

Estrutura recomendada:

```text id="3j7zfo"
experiments/
├── EXP-001/
│   ├── README.md
│   ├── methodology.md
│   └── results.md
```

Cada experimento deve conter:

```text id="b0rh4b"
objetivo
hipótese
dataset
período
features
modelo
parâmetros
metodologia
métricas
resultado
conclusão
```

---

# 18. RESULTADOS

Nunca registrar apenas:

> "Melhorou."

Registrar:

```text id="amz6g2"
Baseline
Novo modelo
Dataset
Período
Brier
Log Loss
Accuracy
Calibration
```

quando disponíveis.

---

# 19. RESULTADO NÃO EXECUTADO

Se um experimento não foi executado:

```text id="e1q9n0"
STATUS: NÃO EXECUTADO
```

Não preencher com números estimados.

---

# 20. LIMITAÇÕES

Todo componente científico relevante deve possuir uma seção de limitações.

Exemplos:

- amostra pequena;
- xG ausente;
- modelo simplificado;
- hipóteses de independência;
- truncamento da matriz;
- falta de dados de mercado;
- ausência de fatores externos.

---

# 21. DATASET

A documentação deve registrar:

```text id="htc0vn"
fonte
período
número de partidas
cobertura
campos
tratamento de missing
timestamp
limitações
```

Nunca assumir que a origem dos dados é autoexplicativa.

---

# 22. DATA QUALITY

Quando a infraestrutura estiver disponível, registrar indicadores como:

```text id="4u0p8s"
total
scores
timestamps
xG coverage
stats coverage
duplicates
invalid records
```

---

# 23. VERSIONAMENTO

Mudanças significativas devem produzir versão documental.

Exemplo:

```text id="qgnq0y"
Blueprint v1.0
Blueprint v1.1
Blueprint v2.0
```

Usar incremento coerente com o impacto.

---

# 24. CHANGELOG

Mudanças relevantes devem ser registradas em:

```text id="h79j6v"
CHANGELOG.md
```

Categorias:

```text id="lcj2qg"
Added
Changed
Fixed
Removed
Scientific
Security
```

---

# 25. DECISÕES ARQUITETURAIS

Decisões importantes devem possuir registro separado.

Estrutura:

```text id="vm7fyx"
docs/
└── decisions/
    ├── ADR-001.md
    ├── ADR-002.md
    └── ...
```

Cada decisão deve registrar:

```text id="n3x9a9"
Contexto
Problema
Alternativas
Decisão
Motivo
Consequências
```

---

# 26. REGRA DE NÃO-REESCRITA DO HISTÓRICO

Não apagar uma decisão anterior apenas porque a decisão atual mudou.

Registrar:

```text id="yo5gae"
Decisão anterior
→ substituída por
→ nova decisão
```

Isso preserva rastreabilidade.

---

# 27. DOCUMENTAÇÃO DE API

Toda API pública do backend deve possuir documentação coerente com:

- método;
- endpoint;
- request;
- response;
- autenticação;
- erros;
- exemplos.

A fonte primária técnica da API continua sendo OpenAPI/FastAPI.

A documentação manual deve permanecer coerente.

---

# 28. DOCUMENTAÇÃO DE FRONTEND

Documentar somente o que é útil para manutenção:

- arquitetura;
- páginas;
- componentes relevantes;
- estado;
- integração;
- convenções.

Não documentar cada detalhe trivial do JSX.

---

# 29. DOCUMENTAÇÃO DE BANCO

Quando o schema for relevante:

```text id="m0c5f9"
tabela
campo
tipo
finalidade
relacionamentos
índices
```

Mudanças devem ser registradas.

---

# 30. DOCUMENTAÇÃO DAS SKILLS

Cada Skill deve possuir seu próprio:

```text id="9ohm7e"
SKILL.md
```

e seguir o mesmo padrão de versionamento e autoridade.

A Documentation Skill deve manter o inventário das Skills.

---

# 31. INVENTÁRIO DE SKILLS

Manter uma visão equivalente a:

```text id="6c4nqe"
Orchestrator
Data Engineer
ML / Statistics
Backend
Frontend
QA / Evaluation
Documentation
```

Para cada uma:

```text id="ojkw73"
versão
status
responsabilidade
dependências
```

---

# 32. DOCUMENTAÇÃO DO FLUXO DAS SKILLS

O projeto deve possuir uma visão de:

```text id="xmr8f1"
Orchestrator
      ↓
Specialist Skill
      ↓
QA
      ↓
Documentation
```

Quando várias Skills estiverem envolvidas:

```text id="2jtx4d"
Data
 ↓
ML
 ↓
Backend
 ↓
Frontend
 ↓
QA
 ↓
Documentation
```

---

# 33. REGRA DE SINCRONIZAÇÃO

Quando código, Blueprint e README divergirem:

A Documentation Skill deve:

1. identificar a divergência;
2. descobrir qual é a realidade validada;
3. informar a Orchestrator;
4. atualizar a documentação apropriada;
5. registrar a decisão quando necessário.

Não esconder divergência silenciosamente.

---

# 34. DOCUMENTAÇÃO DE ALTERAÇÕES

Após uma tarefa relevante, registrar:

```text id="m8cb3k"
O que mudou
Por que mudou
Quem/qual Skill mudou
Arquivos afetados
Testes
Resultado
Riscos residuais
```

---

# 35. REGRA DE SOURCE OF TRUTH

Cada informação deve possuir uma fonte primária.

Exemplos:

```text id="rj3x6x"
Arquitetura → Blueprint
API → OpenAPI + documentação
Modelo → ML docs + código
Dados → Data docs + banco
Decisão → ADR
Execução → Runbook
```

Evitar duplicar a mesma informação em cinco arquivos diferentes.

---

# 36. EVITAR DOCUMENTAÇÃO DUPLICADA

Se uma informação mudar frequentemente, manter uma única fonte primária e referenciar essa fonte nos demais documentos.

Isso reduz inconsistências.

---

# 37. RUNBOOK

Quando o projeto possuir procedimentos operacionais recorrentes, documentar:

```text id="c56qsd"
como iniciar
como sincronizar
como calibrar
como verificar status
como executar testes
como diagnosticar falhas
```

---

# 38. INSTALAÇÃO

A documentação de instalação deve conter:

- requisitos;
- dependências;
- ambiente;
- variáveis;
- banco;
- backend;
- frontend;
- execução;
- problemas conhecidos.

Os comandos devem refletir o estado real do projeto.

---

# 39. CONFIGURAÇÃO

Documentar variáveis relevantes:

```text id="f1mo7w"
nome
finalidade
obrigatória/opcional
exemplo
sensibilidade
```

Nunca publicar secrets reais.

---

# 40. SEGURANÇA

Documentar:

- autenticação;
- secrets;
- CORS;
- tokens;
- limitações;
- recomendações de produção.

Não colocar credenciais reais.

---

# 41. DOCUMENTAÇÃO DE MODELOS FUTUROS

Quando XGBoost for implementado, adicionar documentação específica.

Não antecipar sua existência no README atual como funcionalidade implementada.

---

# 42. DOCUMENTAÇÃO DE ENSEMBLE

O mesmo princípio:

```text id="4gc2pz"
documentar somente após implementação validada.
```

---

# 43. DOCUMENTAÇÃO DE AGENTES INTERNOS

Quando os agentes runtime existirem, documentar:

```text id="xdyxk4"
agente
objetivo
entrada
saída
ferramentas
autoridade
limites
fallback
auditoria
```

Isso não deve ser confundido com as Skills de desenvolvimento.

---

# 44. DOCUMENTAÇÃO DE DECISÕES DE AGENTES

Qualquer agente que tenha autoridade para produzir uma decisão operacional deverá possuir trilha de auditoria documentável.

---

# 45. REGRA CONTRA MARKETING TÉCNICO INFLADO

Não utilizar linguagem como:

- "revolucionário";
- "inteligência preditiva avançada";
- "probabilidade real";
- "garantia";
- "alta precisão";

sem evidência objetiva.

---

# 46. DOCUMENTAÇÃO CIENTÍFICA

Quando uma afirmação estatística for feita, sempre que possível registrar:

```text id="2rur0x"
fonte
metodologia
amostra
métrica
limitação
```

---

# 47. REGRA SOBRE EXEMPLOS

Exemplos numéricos devem ser identificados quando forem apenas ilustrativos.

Exemplo:

> "Exemplo documental — não representa previsão real."

Isso evita que o usuário confunda demonstração com resultado real.

---

# 48. REGRA SOBRE STATUS

Usar estados consistentes:

```text id="z9tqbl"
PLANNED
IN_PROGRESS
IMPLEMENTED
VALIDATED
DEPRECATED
BLOCKED
```

Quando aplicável.

---

# 49. RELEASE NOTES

Toda versão relevante deverá poder gerar uma nota de versão contendo:

```text id="f7yngk"
o que mudou
melhorias
correções
impacto
compatibilidade
testes
limitações
```

---

# 50. DOCUMENTAÇÃO COMO PARTE DO DONE

Uma tarefa relevante não estará totalmente concluída quando:

```text id="wq5e6l"
código = pronto
```

O estado correto é:

```text id="wfutxg"
código
+
testes
+
validação
+
documentação
```

---

# 51. HANDOFF DA DOCUMENTATION SKILL

Ao atualizar documentação, informar:

```text id="v5v2n2"
documentos alterados
versão
motivo
fonte da informação
decisões registradas
```

---

# 52. QUANDO A DOCUMENTAÇÃO DEVE BLOQUEAR UMA ENTREGA

A Skill deve alertar a Orchestrator quando:

- o comportamento implementado não puder ser descrito claramente;
- código e documentação discordarem;
- uma funcionalidade estiver sendo anunciada como concluída sem validação;
- métricas documentadas não tiverem origem verificável;
- existir decisão arquitetural não registrada;
- existirem instruções de execução desatualizadas.

---

# 53. REGRA DE DOCUMENTAÇÃO PÓS-ALTERAÇÃO

Depois de uma alteração relevante:

```text id="9t6cyw"
IMPLEMENTAÇÃO
   ↓
QA
   ↓
DOCUMENTATION
   ↓
FINALIZAÇÃO
```

A Documentation Skill deve receber o resultado validado, não uma hipótese.

---

# 54. TESTE DA DOCUMENTAÇÃO

Quando possível, verificar:

```text id="w20c2e"
comandos executam?
paths existem?
endpoints existem?
nomes estão corretos?
versões correspondem?
```

Documentação operacional deve ser testável.

---

# 55. REGRA CONTRA DOCUMENTAÇÃO PROFÉTICA

Não registrar:

> "O sistema agora possui XGBoost."

enquanto XGBoost estiver apenas planejado.

Registrar:

> "XGBoost está planejado para a Fase X."

---

# 56. REGRA DE HISTÓRICO

Quando o comportamento mudar:

```text id="p3x7k0"
antes
→ decisão
→ depois
```

quando relevante.

Não reescrever o passado de forma que pareça que a arquitetura atual sempre existiu.

---

# 57. CRITÉRIO DE ACEITAÇÃO

A Documentation Skill só considera seu trabalho concluído quando:

```text id="32jzq5"
[ ] Conteúdo baseado em evidência
[ ] Terminologia correta
[ ] Blueprint consistente
[ ] README consistente
[ ] Mudanças registradas
[ ] Versão adequada
[ ] Exemplos identificados
[ ] Instruções verificadas quando possível
```

---

# 58. PROIBIÇÕES ABSOLUTAS

A Documentation Skill nunca deve:

- inventar funcionalidades;
- inventar métricas;
- esconder limitações;
- declarar sucesso sem evidência;
- alterar código;
- alterar metodologia científica;
- mudar decisões arquiteturais;
- adicionar tecnologia no README antes da implementação;
- chamar heurística de ML;
- chamar fair odds de market odds;
- chamar previsão probabilística de certeza.

---

# 59. PRINCÍPIO DE CONSISTÊNCIA

Os seguintes elementos devem permanecer coerentes:

```text id="1dbstb"
Blueprint
README
API docs
ML docs
Data docs
Skills
Changelog
ADRs
```

Quando houver conflito:

> **a inconsistência deve ser resolvida, não mascarada.**

---

# 60. PRINCÍPIO FINAL

A Documentation Skill existe para garantir que:

> **qualquer pessoa ou LLM possa abrir o repositório, ler a documentação e compreender exatamente o que existe, o que foi validado, o que está sendo construído, o que foi decidido e quais limitações permanecem.**

A prioridade é:

**verdade → rastreabilidade → consistência → reprodução → clareza.**

# FIM