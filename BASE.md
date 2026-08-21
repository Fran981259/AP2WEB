# AP2WEB — DOCUMENTO BASE OFICIAL DE IMPLANTAÇÃO
## Master Blueprint / Source of Truth

**Status:** OFICIAL  
**Versão:** 1.0  
**Função:** Documento mestre para orientar qualquer LLM, desenvolvedor ou agente de engenharia que participe da evolução do AP2WEB.  
**Regra principal:** este documento deve ser tratado como a **fonte única de verdade da implantação**. Nenhuma alteração estrutural deve ser feita contrariando suas regras sem uma revisão formal deste documento.

---

# 1. OBJETIVO DO DOCUMENTO

Este documento define, de forma determinística, **o que será mantido, o que será corrigido, o que será construído, em qual ordem e com quais critérios de aceitação**.

O objetivo é impedir que uma LLM:

- reescreva partes funcionais sem necessidade;
- introduza tecnologias desnecessárias;
- substitua o modelo Poisson prematuramente;
- implemente agentes internos antes da hora;
- confunda agentes de desenvolvimento com agentes de runtime;
- trate heurísticas como Machine Learning;
- altere a arquitetura por preferência pessoal;
- adicione funcionalidades fora do escopo;
- declare uma funcionalidade como concluída sem validação objetiva.

---

# 2. PRINCÍPIO CENTRAL DO PROJETO

O AP2WEB **não será reconstruído do zero**.

O sistema atual possui valor técnico comprovado e será evoluído incrementalmente.

O princípio oficial é:

> **Preservar o que funciona, corrigir o que compromete a confiabilidade, medir antes de substituir e somente adicionar complexidade quando houver benefício comprovado.**

---

# 3. ESTADO ATUAL OFICIAL

O AP2WEB atualmente possui:

```text
Sofascore
   ↓
Sincronização de dados
   ↓
SQLite
   ↓
Histórico de partidas
   ↓
Features xG / gols / blend
   ↓
Calibração por liga
   ↓
Modelo Poisson
   ↓
Probabilidades 1X2
   ↓
Over / Under / BTTS / Placar
   ↓
FastAPI
   ↓
React
```

Componentes conhecidos:

- FastAPI;
- Uvicorn;
- React;
- Vite;
- SQLite;
- SofaScore;
- modelo Poisson;
- calibração por grid search;
- backtesting temporal;
- Brier Score;
- autenticação JWT;
- histórico de previsões/picks;
- interface web.

---

# 4. CLASSIFICAÇÃO OFICIAL DO MOTOR ATUAL

O motor atual deve ser descrito como:

> **Motor probabilístico Poisson adaptativo, calibrado por liga através de backtesting temporal e otimização de hiperparâmetros.**

Não utilizar, sem implementação real:

- "rede neural";
- "IA generativa";
- "XGBoost";
- "Random Forest";
- "Logistic Regression";
- "CrewAI";
- "Machine Learning supervisionado".

Esses termos somente poderão aparecer como tecnologias do sistema quando existirem efetivamente no código e forem utilizadas no pipeline.

---

# 5. DEFINIÇÃO OFICIAL DE "APRENDIZADO"

No estado atual, o sistema possui:

```text
dados históricos
        ↓
105 combinações de parâmetros
        ↓
backtesting
        ↓
Brier + Accuracy
        ↓
melhor combinação
        ↓
persistência por liga
```

Isso deve ser considerado:

> **calibração / otimização de hiperparâmetros baseada em dados.**

Não deve ser descrito como aprendizado contínuo.

O sistema atual **não possui aprendizado online contínuo**.

---

# 6. DISTINÇÃO OBRIGATÓRIA ENTRE COMPONENTES

## 6.1 Core científico

Responsável por:

- dados;
- features;
- Poisson;
- futuros modelos ML;
- calibração;
- backtesting;
- avaliação;
- probabilidades.

O core científico deve ser determinístico, auditável e independente de LLM.

## 6.2 Camada de agentes de desenvolvimento

São os **Model Skills / agentes utilizados para desenvolver o AP2WEB**.

Eles trabalham fora do runtime do produto.

Exemplos:

```text
Data/ML Engineer Skill
Backend Engineer Skill
Frontend Engineer Skill
QA/Testing Skill
Architecture/Review Skill
```

Eles não fazem parte do AP2WEB executado pelo usuário.

## 6.3 Agentes internos do produto

São agentes que poderão existir futuramente **dentro do AP2WEB**.

Eles NÃO fazem parte da primeira etapa de implantação.

Possíveis agentes futuros:

```text
Data Agent
Model Agent
Value Agent
Risk Agent
Evaluation Agent
```

Esses agentes somente serão implementados após a estabilização do core científico.

---

# 7. REGRA ABSOLUTA SOBRE OS AGENTES

Nenhum agente interno poderá:

- inventar probabilidades;
- substituir o cálculo matemático do modelo;
- produzir números estatísticos sem origem;
- alterar parâmetros do modelo sem registro;
- declarar uma previsão sem receber dados do core;
- substituir o banco de dados;
- substituir o pipeline de features.

O fluxo correto será:

```text
Dados
 ↓
Core científico
 ↓
Probabilidade
 ↓
Agente interpreta/orquestra
```

Nunca:

```text
LLM
 ↓
"acho que o time tem 63%"
```

---

# 8. OBJETIVO FINAL DO AP2WEB

A evolução prevista do sistema é:

```text
FASE A
Baseline Poisson confiável
        ↓
FASE B
Avaliação científica rigorosa
        ↓
FASE C
Machine Learning supervisionado
        ↓
FASE D
Comparação Poisson × ML
        ↓
FASE E
Ensemble
        ↓
FASE F
Odds de mercado
        ↓
FASE G
EV
        ↓
FASE H
Gestão de risco
        ↓
FASE I
Agentes internos, somente se justificarem sua existência
```

A ordem acima é obrigatória.

---

# 9. O QUE DEVE SER MANTIDO

Os seguintes componentes são considerados patrimônio técnico do projeto e devem ser preservados:

## Dados

- SofaScore como fonte atual;
- SQLite;
- tabelas de ligas;
- times;
- partidas;
- estatísticas históricas.

## Modelo

- Poisson;
- `home_advantage`;
- `window`;
- `feature`;
- xG;
- gols;
- blend.

## Avaliação

- backtesting temporal;
- Brier Score;
- Accuracy.

## Backend

- FastAPI;
- endpoints atuais;
- autenticação;
- estrutura de serviços.

## Frontend

- React;
- Vite;
- interface atual;
- abas atuais;
- visualização do modelo;
- dashboard.

Nada disso deve ser substituído somente por preferência tecnológica.

---

# 10. O QUE DEVE SER CORRIGIDO

## Prioridade CRÍTICA

### 10.1 Timestamp das partidas

Atualmente o sistema converte `startTimestamp` para apenas:

```text
YYYY-MM-DD
```

Isso deve ser corrigido.

O banco deve armazenar o momento real do kickoff.

Requisito:

```text
kickoff_datetime
```

ou equivalente em UTC.

A ordem temporal deve ser baseada no instante real da partida.

Nunca utilizar apenas:

```text
data + id
```

como substituto do horário real.

---

## 10.2 Previsão "AS OF"

O sistema deve conseguir responder:

> "Quais dados estavam disponíveis no momento em que esta previsão deveria ter sido feita?"

O motor deverá aceitar conceitualmente:

```text
as_of_timestamp
```

Para qualquer previsão histórica:

```text
dados utilizados < kickoff da partida
```

É proibido utilizar dados posteriores.

---

## 10.3 Unificação do Feature Engine

Atualmente existem lógicas semelhantes em:

- `learning.py`;
- `prediction.py`.

Isso deverá ser unificado.

Criar uma camada única conceitual:

```text
Feature Engine
```

Ela será utilizada tanto por:

```text
Backtest
```

quanto por:

```text
Prediction
```

Treinamento e previsão devem utilizar a mesma lógica de construção de features.

---

## 10.4 Atualização de estatísticas de jogos existentes

O sincronizador atualmente pode atualizar placar/status sem obrigatoriamente atualizar estatísticas.

Isso deve ser corrigido.

Fluxo obrigatório:

```text
Jogo scheduled
   ↓
jogo termina
   ↓
status = played
   ↓
stats ainda não existem?
   ↓
SIM → coletar stats
```

Também deve existir possibilidade de corrigir estatísticas incompletas.

---

## 10.5 Controle de cobertura de dados

O sistema deve informar:

```text
total de jogos
jogos com placar
jogos com xG
jogos com posse
jogos com chutes
etc.
```

Deve ser possível saber a cobertura das features.

---

# 11. REQUISITO DE INTEGRIDADE DO DATASET

O sistema deverá conseguir identificar:

```text
100% dos jogos
100% dos resultados
% com xG
% com estatísticas
% com timestamp válido
```

Exemplo:

```text
Matches: 428
Scores: 428 / 428
xG: 391 / 428
Timestamp: 428 / 428
```

Nenhuma LLM deverá assumir que a cobertura é 100% sem medir.

---

# 12. FEATURE ENGINE OFICIAL

O Feature Engine deverá produzir, no mínimo:

```text
gf_avg
ga_avg
xg_avg
xga_avg
```

de acordo com a feature escolhida.

As features atuais são:

```text
xg
goals
blend
```

O `blend` atual corresponde conceitualmente a:

```text
50% gols + 50% xG
```

Qualquer alteração dessa proporção deverá ser tratada como experimento separado.

---

# 13. REQUISITOS DO MODELO POISSON

O Poisson continuará como baseline oficial.

Ele deve:

1. receber features;
2. calcular lambdas;
3. construir matriz de placares;
4. derivar probabilidades;
5. gerar 1X2;
6. gerar mercados derivados.

Não deve:

- consultar LLM;
- depender de texto gerado;
- possuir regras de decisão escondidas;
- misturar estratégia de aposta com cálculo probabilístico.

---

# 14. CORREÇÕES MATEMÁTICAS DO MOTOR

Devem ser avaliadas e corrigidas:

### 14.1 Nomenclatura

A função atualmente descrita como "média harmônica" utiliza média aritmética.

A documentação deverá ser corrigida.

### 14.2 `MAX_GOALS`

A matriz truncada em 10 gols deverá ser tratada explicitamente.

Preferência:

```text
MAX_GOALS maior
+
normalização da massa da matriz
```

### 14.3 Tipo de `poisson_pmf`

`k` deve ser tratado como inteiro.

### 14.4 Odds do modelo

O campo atualmente calculado como:

```text
1 / probabilidade
```

deve ser chamado de:

```text
fair_odds
```

e nunca de "market odds".

---

# 15. SEPARAÇÃO MODEL / STRATEGY

O cálculo:

```text
P(Casa) = 0.70
```

é responsabilidade do modelo.

A decisão:

```text
Back Casa
```

é responsabilidade da estratégia.

Portanto, futuramente:

```text
Model
  ↓
Probability
  ↓
Strategy
  ↓
Signal
```

As regras atuais de thresholds devem ser tratadas como:

> **Strategy / Decision Rules**

e não como parte do Machine Learning.

---

# 16. HEURÍSTICAS

Toda heurística deverá ser identificada explicitamente.

Exemplo:

```text
Cantos = lambda × 5.2
```

não deve ser apresentado como modelo estatístico de cantos.

Até existir um modelo específico, deve ser identificado como:

> **Estimativa heurística**

ou removido da saída preditiva principal.

---

# 17. CALIBRAÇÃO

A calibração atual utiliza:

```text
HOME_ADVANTAGE_GRID
WINDOW_GRID
FEATURE_GRID
```

Total:

```text
7 × 5 × 3 = 105
```

Isso será mantido inicialmente.

Porém, a seleção deverá futuramente ser separada da avaliação final.

Modelo não deve ser escolhido e avaliado exclusivamente no mesmo conjunto.

---

# 18. NOVA METODOLOGIA DE AVALIAÇÃO

A próxima metodologia deverá utilizar avaliação temporal.

Prioridade:

```text
Walk-forward
```

Exemplo:

```text
1..100 → prevê 101
1..101 → prevê 102
1..102 → prevê 103
...
```

O objetivo é reproduzir a situação real.

---

# 19. MÉTRICAS OFICIAIS

Além de:

```text
Accuracy
Brier Score
```

serão introduzidas:

```text
Log Loss
Calibration
```

Posteriormente:

```text
ROI
Yield
Profit
```

somente quando existir mercado/odd real devidamente registrado.

---

# 20. HISTÓRICO DE PREVISÕES DO MODELO

Deverá existir separação conceitual entre:

```text
MODEL PREDICTIONS
```

e:

```text
USER PREDICTIONS
```

## Model Prediction

Registra tudo que o motor previu.

Deve conter, quando aplicável:

```text
match_id
predicted_at
model_version
prob_home
prob_draw
prob_away
lambda_home
lambda_away
feature
window
home_advantage
fair_odds
```

## User Prediction

Registra a decisão do usuário:

```text
user_id
model_prediction_id
pick
odd
stake
created_at
status
```

---

# 21. VERSIONAMENTO DO MODELO

Toda previsão futura deverá poder ser associada a uma versão.

Exemplo:

```text
poisson-v2.1
```

A versão deverá permitir identificar:

```text
features
parameters
data cutoff
calibration
```

Não depender de memória humana.

---

# 22. `predicted_at`

Toda previsão deverá registrar:

```text
predicted_at
```

Sem essa informação, a avaliação histórica fica limitada.

---

# 23. ODDS

Quando a camada de mercado for implementada, deverá separar:

```text
fair_odds
```

de:

```text
market_odds
```

Também deverá guardar:

```text
odds_source
odds_timestamp
```

Porque odds são temporais.

---

# 24. EV

Somente depois de existir odd real:

```text
EV = probability × market_odds - 1
```

O EV deve ser calculado pelo sistema determinístico.

LLM não deve inventar EV.

---

# 25. RISK ENGINE

Depois da camada EV:

```text
EV
 ↓
Risk Engine
 ↓
Kelly
```

A implementação deve permitir fração configurável.

Exemplos:

```text
1/4 Kelly
1/2 Kelly
Kelly completo
```

A gestão de risco não deve ser descrita como garantia de proteção da banca.

---

# 26. MACHINE LEARNING

Somente após a baseline Poisson estar corrigida e validada.

Primeiro modelo candidato:

```text
XGBoost
```

Mas não substituir o Poisson.

A arquitetura futura deverá comparar:

```text
Poisson
vs
XGBoost
```

usando os mesmos conjuntos temporais.

---

# 27. REGRA PARA INTRODUÇÃO DO XGBOOST

XGBoost só deverá ser mantido se demonstrar benefício mensurável.

Critérios principais:

```text
Brier
Log Loss
Calibration
```

Accuracy isolada não é suficiente.

Se XGBoost não melhorar o baseline, o Poisson continuará como modelo principal.

---

# 28. ENSEMBLE

Somente após comparação dos modelos.

Possibilidade futura:

```text
Poisson
+
XGBoost
↓
Ensemble
```

A combinação deve ser validada empiricamente.

Não implementar ensemble apenas porque "parece melhor".

---

# 29. AGENTES INTERNOS DO PRODUTO

Não fazem parte da implantação inicial.

Eles entram somente depois da estabilização do core.

Possível arquitetura futura:

```text
Data Agent
Model Agent
Value Agent
Risk Agent
Evaluation Agent
```

## Data Agent

Atua sobre:

- qualidade;
- integridade;
- sincronização;
- cobertura.

## Model Agent

Atua sobre:

- seleção;
- treinamento;
- calibração;
- comparação de modelos.

## Value Agent

Atua sobre:

- odds;
- fair odds;
- EV.

## Risk Agent

Atua sobre:

- Kelly;
- limites;
- exposição.

## Evaluation Agent

Atua sobre:

- performance;
- Brier;
- Log Loss;
- calibração;
- acompanhamento do modelo.

Nenhum deles substituirá os cálculos matemáticos do core.

---

# 30. AGENTES DE DESENVOLVIMENTO

Os Model Skills usados durante a construção do projeto são externos ao runtime.

Eles terão como função:

```text
analisar
implementar
testar
revisar
documentar
```

Eles nunca devem modificar o projeto fora do escopo definido neste documento.

---

# 31. ORDEM OFICIAL DE IMPLANTAÇÃO

## FASE 0 — Congelamento

Não adicionar novas funcionalidades.

Preservar o estado atual.

Catalogar:

```text
arquivos
dependências
endpoints
banco
features
modelo
frontend
```

---

## FASE 1 — Data Integrity

Implementar:

```text
timestamp completo
kickoff real
UTC
ordenação temporal correta
```

Validar:

```text
jogos do mesmo dia
jogos simultâneos
timezone
```

---

## FASE 2 — Sync Correctness

Corrigir:

```text
stats pós-jogo
atualização de jogos existentes
re-sync
dados incompletos
```

Implementar cobertura de dados.

---

## FASE 3 — Feature Engine

Criar pipeline único.

Deve existir uma única fonte para:

```text
gf
ga
xg
xga
window
blend
```

Utilizada por:

```text
backtest
prediction
```

---

## FASE 4 — As-of Prediction

Criar capacidade de reproduzir:

```text
"o que o modelo teria sabido naquele momento?"
```

Garantir ausência de dados futuros.

---

## FASE 5 — Poisson Baseline V2

Corrigir:

```text
matriz
normalização
nomenclatura
fair odds
tipagem
```

Não alterar a filosofia do modelo.

---

## FASE 6 — Evaluation Engine

Implementar:

```text
model_predictions
predicted_at
model_version
Brier
Log Loss
Calibration
```

---

## FASE 7 — Walk-forward Validation

Substituir avaliações metodologicamente frágeis por avaliação temporal robusta.

---

## FASE 8 — ML Experimental

Implementar:

```text
XGBoost
```

como modelo paralelo.

Comparar contra Poisson.

---

## FASE 9 — Ensemble

Somente se os resultados justificarem.

---

## FASE 10 — Market Engine

Adicionar:

```text
market odds
fair odds
EV
```

---

## FASE 11 — Risk Engine

Adicionar:

```text
Kelly fracionado
limites
exposição
```

---

## FASE 12 — Agent Runtime

Somente após todas as fases científicas anteriores.

---

# 32. CRITÉRIO DE PASSAGEM ENTRE FASES

Nenhuma fase será considerada concluída porque o código "funciona".

Uma fase somente pode ser marcada como concluída quando:

```text
implementação
+
teste
+
validação
+
documentação
```

estiverem concluídos.

---

# 33. REGRA DE NÃO-REGRESSÃO

Nenhuma alteração futura poderá destruir:

- dados existentes;
- previsões existentes;
- compatibilidade do banco;
- API funcional;
- cálculo Poisson;
- histórico;
- frontend funcional.

Toda mudança estrutural deve considerar migração compatível.

---

# 34. REGRA CONTRA COMPLEXIDADE DESNECESSÁRIA

Não introduzir:

- Redis;
- Celery;
- Kafka;
- PostgreSQL;
- Kubernetes;
- microsserviços;
- novos frameworks;
- múltiplos LLMs;
- agentes internos;

sem necessidade comprovada.

A pergunta obrigatória antes de adicionar tecnologia é:

> **Qual problema concreto existente esta tecnologia resolve?**

---

# 35. REGRA CONTRA "EMBELEZAMENTO TÉCNICO"

É proibido adicionar tecnologia apenas para:

- parecer mais profissional;
- aumentar a lista de dependências;
- usar buzzwords;
- transformar uma função simples em agente;
- substituir código funcional por arquitetura mais complexa.

---

# 36. REGRA DE VERACIDADE

O código deve ser a autoridade final.

Nunca declarar:

> "usa XGBoost"

se o código não usa XGBoost.

Nunca declarar:

> "IA aprende continuamente"

se não existe retreinamento automático.

Nunca declarar:

> "probabilidade real"

para uma estimativa do modelo.

Nunca declarar:

> "odd de mercado"

para uma odd justa calculada pelo modelo.

---

# 37. REGRA DE AUDITORIA PARA QUALQUER LLM

Toda LLM que trabalhar no projeto deve seguir esta ordem:

```text
1. Ler este documento.
2. Identificar a fase atual.
3. Ler os arquivos relevantes.
4. Não assumir comportamento não comprovado.
5. Não alterar arquitetura fora da fase.
6. Implementar somente o escopo autorizado.
7. Testar.
8. Relatar alterações.
9. Relatar riscos.
10. Atualizar documentação.
```

---

# 38. A LLM NÃO DEVE FAZER

É proibido:

- reescrever o projeto inteiro;
- trocar SQLite sem autorização;
- trocar Poisson por ML sem autorização;
- adicionar CrewAI ao runtime apenas porque está no README antigo;
- adicionar agentes internos antecipadamente;
- apagar funcionalidades;
- remover histórico;
- modificar banco sem migração;
- criar números fictícios para testes de produção;
- mascarar falhas com fallback silencioso;
- chamar heurística de Machine Learning;
- chamar fair odds de market odds.

---

# 39. PROTOCOLO DE ALTERAÇÃO

Antes de modificar um módulo:

```text
PERGUNTA 1:
Qual problema estamos corrigindo?

PERGUNTA 2:
Em qual fase isso está autorizado?

PERGUNTA 3:
Qual comportamento atual será preservado?

PERGUNTA 4:
Como provar que a alteração funciona?

PERGUNTA 5:
Qual risco de regressão existe?
```

Se alguma resposta não estiver clara, a implementação deve parar naquele ponto lógico e investigar o código/documentação existente antes de inventar uma solução.

---

# 40. CHECKLIST MÍNIMO DE VALIDAÇÃO

Antes de considerar o sistema pronto para avaliação científica:

```text
- [ ] Timestamp completo das partidas
- [ ] Timezone padronizado
- [ ] Ordenação temporal correta
- [ ] Nenhum dado futuro utilizado
- [ ] Stats pós-jogo atualizadas
- [ ] Cobertura de xG conhecida
- [ ] Feature Engine único
- [ ] Backtest usa mesmas features da previsão
- [ ] Poisson corrigido
- [ ] Matriz normalizada
- [ ] Fair odds corretamente identificadas
- [ ] Model predictions persistidas
- [ ] predicted_at persistido
- [ ] model_version persistido
- [ ] Brier calculado
- [ ] Log Loss calculado
- [ ] Calibração avaliada
- [ ] Walk-forward implementado
```

---

# 41. CHECKLIST DO ML FUTURO

Antes de adicionar XGBoost:

```text
- [ ] Baseline Poisson validada
- [ ] Dataset supervisionado definido
- [ ] Target definido
- [ ] Features documentadas
- [ ] Leakage auditado
- [ ] Split temporal definido
- [ ] Métricas definidas
- [ ] Experimento reproduzível
```

Depois:

```text
- [ ] XGBoost treinado
- [ ] Probabilidades produzidas
- [ ] Brier comparado
- [ ] Log Loss comparado
- [ ] Calibration comparada
- [ ] Resultado documentado
```

---

# 42. CHECKLIST DOS AGENTES INTERNOS FUTUROS

Somente implementar depois que o core estiver estável.

```text
- [ ] Definir responsabilidade de cada agente
- [ ] Definir ferramentas permitidas
- [ ] Definir entradas
- [ ] Definir saídas
- [ ] Definir limites
- [ ] Definir auditoria
- [ ] Definir fallback
- [ ] Definir quando o agente pode agir
```

Nenhum agente deve possuir autoridade irrestrita.

---

# 43. ARQUITETURA FINAL ALVO

A arquitetura desejada, após todas as fases, é:

```text
                         AP2WEB
                            │
                 ┌──────────┴──────────┐
                 │                     │
             DATA CORE            AGENT LAYER
                 │                     │
          ┌──────┴──────┐       ┌─────┴─────┐
          ↓             ↓       ↓           ↓
      SofaScore      SQLite   Data Agent  Model Agent
          │                         │           │
          └──────────┬──────────────┘           │
                     ↓                          │
               Feature Engine                  │
                     │                          │
              ┌──────┴───────┐                 │
              ↓              ↓                 │
           Poisson        XGBoost              │
              │              │                 │
              └──────┬───────┘                 │
                     ↓                          │
                  Ensemble                      │
                     ↓                          │
                Calibration                     │
                     ↓                          │
              Probabilities                     │
                     │                          │
              ┌──────┴──────┐                   │
              ↓             ↓                   ↓
          Fair Odds      Evaluation        Value Agent
                            │                   │
                            ↓                   ↓
                         Metrics            EV
                            │                   │
                            └────────┬──────────┘
                                     ↓
                                 Risk Agent
                                     ↓
                                Risk Engine
                                     ↓
                                Application
```

---

# 44. VISÃO DE LONGO PRAZO

O projeto não será tratado como:

> "um sistema que dá palpites."

O objetivo técnico é evoluir para:

> **uma plataforma auditável de modelagem probabilística, Machine Learning e análise de mercado aplicada ao futebol.**

O valor do projeto estará na capacidade de responder:

```text
Que dados foram utilizados?
      ↓
Qual modelo foi utilizado?
      ↓
Qual versão?
      ↓
Qual previsão foi produzida?
      ↓
Quais probabilidades?
      ↓
Qual era a informação disponível?
      ↓
Qual foi o resultado?
      ↓
Qual foi a qualidade da previsão?
      ↓
O modelo melhorou?
```

---

# 45. REGRA FINAL

Qualquer LLM que leia este documento deve entender:

> **Não estamos procurando adicionar o máximo possível de IA.**
>
> **Estamos construindo primeiro uma base estatística correta, auditável e mensurável.**
>
> **Machine Learning será adicionado para provar se melhora o baseline.**
>
> **Agentes internos serão adicionados somente quando houver uma função concreta para eles.**
>
> **Complexidade nunca será introduzida sem justificativa mensurável.**

A sequência oficial é:

```text
CORRIGIR
→
VALIDAR
→
MEDIR
→
MELHORAR
→
COMPARAR
→
EVOLUIR
```

**Nunca:**

```text
ADICIONAR TECNOLOGIA
→
TORCER PARA MELHORAR
```

---

# 46. ESTADO DO DOCUMENTO

Este documento é o **Blueprint Base de Implantação do AP2WEB**.

Qualquer alteração de escopo deverá gerar uma nova versão deste documento.

Versões futuras deverão preservar:

- histórico das decisões;
- justificativa das mudanças;
- funcionalidades removidas;
- funcionalidades adicionadas;
- impacto arquitetural.

**Não alterar o escopo por interpretação silenciosa.**

**Não substituir decisões deste documento por preferências individuais de uma LLM.**

---

## FIM DO DOCUMENTO BASE OFICIAL