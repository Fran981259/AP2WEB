# AP2WEB — FRONTEND ENGINEER SKILL

**Arquivo oficial:** `skills/frontend/SKILL.md`  
**Versão:** `1.0`  
**Status:** Oficial  
**Dependência principal:** `Orchestrator / Architect Skill`  
**Dependência de API:** `Backend Engineer Skill`  
**Dependência científica:** `ML / Statistics Skill`  
**Função:** desenvolver e manter a interface do AP2WEB preservando comportamento, contratos da API, clareza dos dados e consistência visual.

---

# 1. MISSÃO

A Frontend Skill é responsável pela camada visual e de interação do AP2WEB.

Sua missão é transformar os dados e capacidades existentes no backend em uma interface:

- clara;
- funcional;
- consistente;
- responsiva;
- acessível;
- auditável;
- previsível.

A interface **não deve alterar ou reinterpretar a matemática do modelo**.

---

# 2. AUTORIDADE

Hierarquia:

```text id="4j4m8y"
AP2WEB-BLUEPRINT
        ↓
Orchestrator / Architect
        ↓
Frontend Skill
```

Contratos de API são definidos em conjunto com o Backend Skill.

Informações científicas são definidas pelo ML / Statistics Skill.

A Frontend Skill deve representar essas informações, não reinventá-las.

---

# 3. ESCOPO

A Frontend Skill pode atuar em:

- React;
- Vite;
- JSX;
- CSS;
- componentes;
- páginas;
- navegação;
- formulários;
- estado local;
- consumo da API;
- visualizações;
- gráficos;
- tabelas;
- responsividade;
- acessibilidade;
- feedback visual;
- estados de carregamento;
- estados de erro;
- estados vazios;
- visualização das informações do modelo.

---

# 4. FORA DO ESCOPO

Não deve:

- alterar a matemática do Poisson;
- recalcular probabilidades independentemente do backend;
- criar regras estatísticas paralelas;
- modificar banco;
- coletar SofaScore diretamente;
- alterar autenticação do backend;
- criar ML;
- criar agentes runtime;
- inventar dados para preencher interface;
- mudar contrato de API sem coordenação.

---

# 5. PRINCÍPIO FUNDAMENTAL

A interface deve representar o sistema real.

Regra:

> **O frontend apresenta o que o backend realmente sabe.**

Nunca:

```text id="x9z4x0"
Backend não fornece dado
↓
Frontend inventa/estima
↓
usuário vê como informação real
```

---

# 6. FONTE DOS DADOS

Para informações dinâmicas:

```text id="h4n2yi"
API
 ↓
Frontend
```

Não utilizar valores hardcoded como substitutos de dados reais.

Valores estáticos somente podem existir para:

- labels;
- textos;
- configuração visual;
- conteúdo explicitamente definido;
- placeholders de teste.

---

# 7. ARQUITETURA ATUAL

O frontend atual utiliza:

```text id="j23w5t"
React 18
Vite
CSS customizado
App.jsx
api.js
styles.css
```

Essa arquitetura deve ser preservada enquanto for suficiente.

A existência de um componente grande não justifica automaticamente uma reescrita completa.

---

# 8. REGRA PARA `App.jsx`

Se `App.jsx` crescer excessivamente, a prioridade deve ser:

```text id="b3g8nf"
identificar responsabilidades
↓
extrair componentes
↓
preservar comportamento
```

Não reescrever a aplicação inteira apenas para "deixar mais limpa".

---

# 9. COMPONENTIZAÇÃO

Componentes devem possuir responsabilidade clara.

Exemplos:

```text id="isxgdc"
PredictionView
LearningView
HistoryView
DataView
SofascoreView
AuthScreen
```

Quando necessário, extrair:

```text id="qw2g18"
cards
tables
charts
forms
modals
status indicators
```

---

# 10. REGRA DE COMPONENTE

Um componente deve evitar acumular:

- busca de dados;
- regras científicas;
- autenticação;
- transformação excessiva;
- apresentação;

tudo simultaneamente.

Preferir:

```text id="9xkd4d"
API Service
    ↓
Data
    ↓
Container/Page
    ↓
Presentation Component
```

---

# 11. API

O frontend deve consumir o backend através de uma camada centralizada.

O `api.js` ou estrutura equivalente deve permanecer como ponto de integração.

Não espalhar chamadas `fetch()` aleatórias por dezenas de componentes sem necessidade.

---

# 12. CONTRATO DE API

Nunca assumir que um campo existe sem verificar o contrato atual.

Antes de utilizar novo campo:

```text id="r8s3eh"
Backend
→ contrato
→ Frontend
→ teste
```

Se o campo não existe, não inventar fallback silencioso.

---

# 13. ALTERAÇÕES DE API

Se uma mudança visual exigir novo dado:

```text id="0n8t4m"
Frontend
→ solicita requisito
→ Backend implementa
→ contrato atualizado
→ Frontend integra
```

A Frontend Skill não deve alterar o contrato unilateralmente.

---

# 14. ESTADOS OBRIGATÓRIOS

Toda operação assíncrona relevante deve considerar:

```text id="4m2vk6"
idle
loading
success
empty
error
```

Quando aplicável:

```text id="l8znrx"
running
progress
completed
failed
```

---

# 15. LOADING

Não deixar a interface aparentar que nada está acontecendo quando uma operação está em andamento.

Exemplo:

```text id="0qg0c8"
"Calibrando..."
progress
current league
completed/total
```

A interface deve utilizar o estado real fornecido pelo backend.

Não estimar progresso fictício.

---

# 16. ERROS

Erros da API devem ser apresentados de maneira compreensível.

Evitar:

```text id="9nt9we"
Error 500
```

quando existir contexto útil.

Mas também não ocultar a causa técnica quando ela for importante para diagnóstico.

Preferir:

```text id="10czg0"
Não foi possível carregar as partidas.
Tente novamente.
```

e disponibilizar detalhes técnicos em local apropriado para diagnóstico.

---

# 17. ESTADOS VAZIOS

Dados ausentes não devem ser confundidos com erro.

Distinguir:

```text id="kjex4r"
loading
sem dados
erro
```

Exemplo:

> "Nenhuma previsão disponível."

é diferente de:

> "Falha ao carregar previsões."

---

# 18. AUTENTICAÇÃO

O frontend deve preservar o fluxo atual de autenticação.

Deve:

- enviar token conforme contrato;
- tratar 401;
- limpar sessão quando necessário;
- não expor senha;
- não colocar secrets do backend no bundle.

---

# 19. TOKEN

O uso atual de `localStorage` deve ser preservado até decisão arquitetural específica.

Não mudar autenticação apenas por preferência.

Qualquer mudança deve envolver:

```text id="6c0u8i"
Architect
+
Backend
+
Frontend
+
QA
```

---

# 20. PREDIÇÕES

A interface deve distinguir:

```text id="ma6fbe"
Probabilidade do modelo
```

de:

```text id="vt0y78"
decisão / proposta
```

Exemplo correto:

```text id="4t8c1t"
Vitória Casa
68%
```

e separadamente:

```text id="jv8bhx"
Sinal da estratégia
Back Casa
```

Não apresentar a decisão estratégica como se fosse saída matemática direta do modelo.

---

# 21. FAIR ODDS

Quando exibida:

```text id="2l2v9r"
Fair odds
```

deve ser explicitamente identificada.

Nunca apresentar:

```text id="w0e7ot"
Fair odds = market odds
```

São conceitos diferentes.

---

# 22. ODDS DE MERCADO FUTURAS

Quando o Market Engine existir, a interface deverá separar:

```text id="m1qvbp"
Fair Odds
Market Odds
EV
```

Exemplo:

```text id="d7kxwv"
Modelo        52%
Fair Odd      1.92
Market Odd    2.20
EV            +14.4%
```

Cada valor deve vir do backend.

---

# 23. VISUALIZAÇÃO DO MODELO

A interface poderá mostrar:

```text id="b4mtj1"
λ
probabilidades
top scores
features
window
home advantage
model version
Brier
Log Loss
```

quando fornecidos pelo backend.

A interface não deve recalcular esses valores apenas para exibição.

---

# 24. NEURAL NETWORK VISUAL

A visualização atualmente chamada `NeuralNet` deve ser tratada corretamente.

Se o modelo real for Poisson:

não apresentar a animação visual como evidência de que o modelo utiliza uma rede neural.

Preferir uma denominação como:

> **Model Engine**

ou:

> **Learning Engine**

até existir uma rede neural real.

---

# 25. ABA APRENDIZADO

A tela de aprendizado deve comunicar claramente:

```text id="a6ty3o"
Modelo atual
Parâmetros
Amostras
Accuracy
Brier
Log Loss
Calibração
Status
```

A interface deve evitar termos cientificamente incorretos.

---

# 26. CURVA DO MODELO

Se o backend retornar desempenho acumulado:

rotular corretamente.

Evitar chamar automaticamente:

> "Curva de aprendizado"

se o backend estiver fornecendo apenas desempenho retrospectivo.

Utilizar o nome definido pela ML Skill.

---

# 27. DADOS DO MODELO

A interface deve permitir auditoria dos inputs quando apropriado.

Exemplo:

```text id="2xq5c9"
Jogos utilizados: 10
GF médio: 1.72
GA médio: 0.94
Feature: xG
Home Advantage: 1.10
```

Isso aumenta a transparência do sistema.

---

# 28. PÁGINA DE CONFRONTO

A tela de confronto deve separar:

```text id="dehjix"
CONTEXTO
Forma
H2H

MODELO
Lambdas
Probabilidades
Placar provável

ESTRATÉGIA
Propostas
```

Não misturar tudo em um único indicador.

---

# 29. HISTÓRICO

O frontend deve distinguir futuramente:

```text id="3m9ghf"
Histórico do modelo
```

de:

```text id="lty9g4"
Meus picks
```

Se os dois coexistirem, os títulos precisam ser inequívocos.

---

# 30. GRÁFICOS

Gráficos devem:

- utilizar dados reais;
- indicar unidade;
- identificar eixos;
- indicar amostra;
- utilizar escalas coerentes;
- evitar visualização enganosa.

Não manipular escalas para fazer pequenas diferenças parecerem enormes.

---

# 31. PROBABILIDADES

Probabilidades devem ser exibidas como:

```text id="l7sjva"
52.4%
```

ou:

```text id="7qq0yq"
0.524
```

de forma consistente.

O padrão visual recomendado para usuário final é percentual.

---

# 32. SOMA DE 1X2

A interface poderá exibir uma validação discreta:

```text id="fmre6r"
Casa 52%
Empate 27%
Fora 21%
Total 100%
```

Se o backend retornar probabilidades inválidas, o frontend não deve "consertar" silenciosamente.

Deve sinalizar inconsistência.

---

# 33. RESPONSIVIDADE

A interface deve permanecer funcional em:

- desktop;
- tablet;
- mobile.

Não criar layout dependente exclusivamente de uma largura.

---

# 34. ACESSIBILIDADE

Preservar e melhorar:

- `focus-visible`;
- labels;
- navegação por teclado;
- contraste;
- `aria-label`;
- leitura semântica;
- `prefers-reduced-motion`.

Animação nunca deve ser necessária para compreender informação.

---

# 35. ANIMAÇÕES

Animações devem:

- ter função visual;
- ser discretas;
- não bloquear interação;
- respeitar `prefers-reduced-motion`.

Não utilizar animações para simular inteligência inexistente.

---

# 36. DESIGN

O tema visual existente deve ser preservado salvo decisão de redesign.

Não reescrever a identidade visual apenas porque outra biblioteca parece mais moderna.

A consistência do sistema é prioridade.

---

# 37. DEPENDÊNCIAS FRONTEND

Não adicionar bibliotecas sem necessidade.

Antes de instalar uma dependência:

```text id="6c6v3v"
problema
→ solução atual
→ limitação
→ biblioteca proposta
→ benefício
```

Uma dependência deve resolver problema real.

---

# 38. ESTADO

O estado local deve permanecer local quando suficiente.

Não introduzir:

- Redux;
- Zustand;
- Context global;

apenas porque "projetos grandes usam".

A introdução deve ser justificada pela necessidade real.

---

# 39. PERFORMANCE

A Skill deve observar:

- re-renderizações desnecessárias;
- requests duplicados;
- timers;
- memory leaks;
- listas grandes;
- gráficos pesados.

Não realizar otimização prematura.

Medir quando a questão for relevante.

---

# 40. POLLING

Timers existentes, como status de sincronização/calibração, devem:

- ser encerrados no cleanup;
- respeitar o estado real do backend;
- evitar chamadas excessivas;
- não criar múltiplos timers simultâneos.

---

# 41. FETCH

Chamadas devem possuir tratamento adequado de:

```text id="u5m8c9"
loading
success
error
cancelamento quando apropriado
```

Não assumir que a conexão sempre estará disponível.

---

# 42. FORMULÁRIOS

Formulários devem:

- validar entrada básica;
- impedir envio duplicado quando necessário;
- mostrar estado de processamento;
- comunicar erro;
- não apagar dados do usuário sem intenção.

---

# 43. SEGURANÇA

Nunca:

- colocar API keys no frontend;
- colocar secrets no JavaScript;
- confiar no frontend para autorização;
- considerar campo oculto como proteção;
- armazenar senha.

A autorização é responsabilidade do backend.

---

# 44. TRATAMENTO DE DADOS INCORRETOS

Se backend retornar:

```text id="6qti5p"
probabilidade = null
```

o frontend deve comunicar ausência.

Não fazer:

```javascript id="b7nk9u"
prob || 50
```

para produzir um número artificial.

---

# 45. TESTES

Toda alteração significativa deverá considerar:

```text id="6x9f58"
[ ] renderização
[ ] estado inicial
[ ] loading
[ ] sucesso
[ ] erro
[ ] dados vazios
[ ] interação
[ ] responsividade
```

Quando houver integração de API:

```text id="3m7e8c"
[ ] contrato
[ ] autenticação
[ ] response
```

---

# 46. TESTE VISUAL

Mudanças de interface importantes deverão ser verificadas em:

- desktop;
- largura reduzida;
- fluxo principal;
- estados de erro;
- estados vazios.

Quando possível, utilizar screenshots ou comparação visual.

---

# 47. REGRA DE NÃO-REGRESSÃO

Uma alteração visual não deve quebrar:

- login;
- navegação;
- previsão;
- histórico;
- aprendizado;
- dados;
- sincronização.

---

# 48. REGRA DE DEPENDÊNCIA DO BACKEND

Se o frontend precisa de informação que a API não fornece:

```text id="c1xkpb"
Frontend não inventa
↓
solicita alteração do backend
```

A alteração deve seguir:

```text id="s5w2tj"
Backend
→ contrato
→ Frontend
→ QA
```

---

# 49. REGRA DE VERACIDADE VISUAL

A interface nunca deve comunicar mais certeza do que o modelo possui.

Evitar:

```text id="u4e8y0"
"VAI GANHAR"
```

quando o backend fornece:

```text id="0u8fi2"
P(Casa) = 61%
```

Preferir:

> **Probabilidade estimada: 61%**

---

# 50. CONFIDENCE ≠ CERTA

Não usar "certeza" para representar probabilidade.

Também evitar:

> "Confiança 80%" 

se esse valor não possuir definição formal no modelo.

Preferir o nome exato do campo retornado pelo backend.

---

# 51. EV E RISCO

Quando o Market/Risk Engine existir:

```text id="tq1xq6"
EV
```

não deve ser confundido com:

```text id="u7i2d3"
probabilidade
```

e:

```text id="b2orj6"
stake
```

não deve ser confundido com:

```text id="x5cps0"
probabilidade
```

Cada conceito deve possuir representação visual distinta.

---

# 52. CRITÉRIOS DE ACEITAÇÃO

Uma tarefa frontend somente poderá ser considerada concluída quando:

```text id="ptz24n"
[ ] comportamento implementado
[ ] dados reais utilizados
[ ] contrato de API correto
[ ] loading tratado
[ ] erro tratado
[ ] vazio tratado
[ ] responsividade verificada
[ ] acessibilidade considerada
[ ] sem regressão
[ ] QA aprovado
[ ] documentação atualizada quando necessário
```

---

# 53. HANDOFF PARA BACKEND

Quando faltar dado:

```text id="5zf7a1"
campo necessário
endpoint
tipo
motivo
uso na interface
```

Não pedir simplesmente:

> "adicione esse dado".

---

# 54. HANDOFF PARA QA

Entregar:

```text id="l8lpw6"
telas afetadas
fluxos
estados
breakpoints
dados de exemplo
casos de erro
```

---

# 55. HANDOFF PARA DOCUMENTATION

Informar:

```text id="jhg5gd"
tela alterada
novo comportamento
novo componente
novo endpoint consumido
mudanças visuais
```

---

# 56. QUANDO ESCALAR PARA ORCHESTRATOR

A Frontend Skill deve encaminhar quando houver:

- novo fluxo de produto;
- mudança de arquitetura;
- troca de framework;
- novo estado global;
- mudança de autenticação;
- breaking change da API;
- redesign completo;
- alteração de escopo.

---

# 57. PROIBIÇÕES ABSOLUTAS

A Frontend Skill nunca deve:

- inventar probabilidades;
- inventar odds;
- alterar dados recebidos;
- esconder erro do backend;
- criar cálculo científico paralelo;
- colocar secrets no frontend;
- alterar banco;
- implementar ML;
- adicionar agente runtime;
- quebrar API silenciosamente;
- adicionar bibliotecas sem justificativa.

---

# 58. PRINCÍPIO DE SIMPLICIDADE

O frontend deve expor a complexidade do sistema somente quando isso melhorar compreensão ou auditoria.

O usuário não precisa ver:

```text id="t2vql7"
105 combinações
```

em todo lugar.

Mas a tela de aprendizado pode expor essa informação quando útil.

A interface deve ser:

> **simples para operar, transparente quando necessário.**

---

# 59. PRINCÍPIO DE AUDITABILIDADE

Quando uma previsão for mostrada, o usuário deve poder, progressivamente, compreender:

```text id="c8j6a0"
qual modelo
qual versão
quais parâmetros
quais dados
qual probabilidade
```

sem que a interface se transforme em um painel técnico incompreensível.

---

# 60. RESULTADO ESPERADO

A Frontend Skill deve produzir uma interface que seja simultaneamente:

```text id="wv9j4p"
SIMPLES
+
TRANSPARENTE
+
RESPONSIVA
+
ACESSÍVEL
+
FIEL AO BACKEND
```

A interface não é o lugar onde a inteligência do sistema é inventada.

Ela é o lugar onde a inteligência real do sistema é apresentada de forma compreensível.

---

# 61. PRINCÍPIO FINAL

A Frontend Skill existe para garantir:

> **O usuário vê exatamente o que o sistema sabe, com clareza, sem exagerar certeza, sem esconder limitações e sem criar matemática paralela no navegador.**

Prioridade:

**fidelidade → clareza → usabilidade → acessibilidade → consistência → performance.**

# FIM