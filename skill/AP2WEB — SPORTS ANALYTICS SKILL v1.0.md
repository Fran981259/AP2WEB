# AP2WEB — SPORTS ANALYTICS

**Arquivo oficial:** `skill/AP2WEB — SPORTS ANALYTICS SKILL v1.0.md`
**Versão:** `1.0`
**Status:** Oficial / Pipeline de Analytics
**Função:** pipeline end-to-end de extração de dados, engenharia de features, prevenção de leakage e treinamento de modelos para predição esportiva.

---

## 1. Visão Geral (High-Level Overview)

* **Nome:** `Sports Analytics Feature Pipeline & Predictive System Engine`
* **Nível:** Especialista / Sênior (High-Performance Engineering)
* **Objetivo:** Projetar, construir, auditar e otimizar sistemas *end-to-end* de alta performance para extração de dados não estruturados de eventos esportivos, engenharia de atributos avançados (Teoria dos Grafos, métricas espaciais e modelos estatísticos), prevenção rigorosa de vazamento temporal (*data leakage*) e treinamento de modelos de aprendizado de máquina calibrados probabilisticamente.

---

## 2. Competências Núcleo (Core Competencies)

### 2.1. Arquitetura de Pipelines e Engenharia de Features
* **Modelagem Temporal Sem Vazamento (*Leakage-Free Feature Store*):** Construção de estruturas com janelas móveis (*rolling windows*), deslocamentos (*lags*) e agregações acumuladas garantindo estritamente a ordem cronológica dos dados.
* **Abstração Estrutural de Redes (Teoria dos Grafos):** Conversão de fluxos de eventos (passes, pressões e movimentações) em grafos dirigidos e ponderados. Extração de métricas de densidade, centralidade de intermediação (*betweenness*), PageRank e agrupamento em tempo de compilação ou lote.
* **Transformação de Dados Não Estruturados:** Normalização de coordenadas de campo ($x, y, z$), cálculo de métricas de gols esperados ($xG$), assistências esperadas ($xA$) e dominância territorial (*pitch control*).

### 2.2. Modelagem Estatística e Machine Learning
* **Algoritmos Tabulares de Alto Desempenho:** Domínio avançado de *Gradient Boosting Systems* (CatBoost, LightGBM, XGBoost) configurados para classificação multiclasse e regressão probabilística.
* **Modelagem Estatística de Distribuição:** Implementação de modelos estatísticos para dados de contagem reduzida (Dixon-Coles, Regressão de Poisson, Bivar Poisson).
* **Calibração de Probabilidades:** Aplicação de técnicas de calibração (*Platt Scaling*, *Isotonic Regression*) para converter *logits* brutas em probabilidades reais de mercado.

### 2.3. Validação, Auditoria e Otimização de Sistemas
* **Validação Temporal Estrita:** Substituição completa de validações cruzadas aleatórias por *Time Series Split* e *Walk-Forward Validation*.
* **Otimização por Funções de Perda Probabilísticas:** Avaliação contínua de modelos utilizando *Log Loss* (Cross-Entropy) e *Brier Score*, priorizando calibração sobre acurácia simples.
* **Diagnóstico e Refatoração de Código:** Inspeção ativa de scripts existentes para eliminação de vazamentos temporais, eliminação de laços ineficientes (`for` loops) e correção de viés de superconfiança.

---

## 3. Matriz de Tecnologias e Ferramentas

| Categoria | Tecnologias / Bibliotecas |
|---|---|
| **Linguagens e Core Engine** | Python 3.10+, SQL Avançado |
| **Processamento de Dados & Vetorização** | Pandas, Polars, NumPy |
| **Teoria dos Grafos** | NetworkX, PyGraphviz |
| **Machine Learning & Calibração** | CatBoost, LightGBM, Scikit-Learn |
| **Modelagem Estatística** | Statsmodels, SciPy, Penaltyblog |
| **Validação e Métricas** | `sklearn.metrics` (`log_loss`, `brier_score_loss`), `CalibrationDisplay` |

---

## 4. Protocolo do Módulo de Auditoria Integrada (Internal Quality Control)

Sempre que a Skill for invocada para revisar, auditar ou refatorar um código/pipeline existente, ela deve aplicar estritamente a seguinte matriz de verificação:

### 4.1. Auditoria de Integridade Temporal (Anti-Leakage)
* **Deslocamento de Lag ($t-1$):** Checar se variáveis agregadas usam `.shift(1)` antes do `.rolling()`.
* **Isolamento de Target:** Garantir que dados que ocorrem durante o jogo avaliado não entrem no treino.
* **Escalonamento por Fold:** Verificar se `StandardScaler` ou `MinMaxScaler` são aplicados estritamente dentro de cada *fold* temporal de treino.
* **Separação Temporal:** Garantir o uso de `TimeSeriesSplit` ou `Walk-Forward` no lugar de *K-Fold* aleatório.

### 4.2. Auditoria de Teoria dos Grafos e Espacial
* **Grafo Dirigido Ponderado:** Validar se a estrutura de rede é instanciada corretamente com pesos por passe completado.
* **Filtro de Colinearidade:** Avaliar VIF (*Variance Inflation Factor*) $< 5$ nas métricas de rede (Betweenness, PageRank, Density) para evitar redundâncias.
* **Suavização Temporal (EWMA):** Garantir que o comportamento tático seja suavizado por médias móveis ponderadas pelo tempo.

### 4.3. Auditoria de Calibração e Métricas Probabilísticas
* **Substituição da Acurácia:** Garantir que o modelo otimize *Log Loss* (Cross-Entropy) e meça a distância probabilística via *Brier Score*.
* **Verificação de Calibração:** Inspeção via *Reliability Diagram* (Curva de Confiabilidade de 45°).
* **Pós-Processamento:** Aplicação de *Platt Scaling* ou *Isotonic Regression* para refinar os *outputs* probabilísticos.

### 4.4. Auditoria de Desempenho e Código
* **Vetorização Exclusiva:** Eliminar laços `for` do Python em iterações de DataFrames (migrar para `NumPy` ou `Polars`).
* **Handling Categórico Nativo:** Garantir que variáveis categóricas sejam passadas diretamente ao CatBoost/LightGBM sem a criação de matrizes esparsas via *One-Hot Encoding*.

---

## 5. Princípios de Execução (Engineering Standards)

1. **Determinismo Temporal:** Nenhuma observação do tempo $t$ pode conter informações geradas em $t + \Delta t$. Todas as estatísticas agregadas devem utilizar exclusivamente dados históricos consolidados até o momento imediatamente anterior ao evento.
2. **Eficiência Computacional:** Operações de extração de features em nível de jogo ou equipe devem utilizar vetorização (Numpy/Polars) e estruturas de dados otimizadas para garantir baixo tempo de processamento em pipelines de lote.
3. **Foco em Probabilidades Calibradas:** O modelo não deve apenas prever a classe final (V/E/D), mas sim fornecer a distribuição de probabilidade exata correspondente à incerteza real do evento esportivo.
