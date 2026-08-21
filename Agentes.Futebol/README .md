# ⚽ Soccer Predictor AI - Sistema Multiagentes de Análise Preditiva de Futebol

Uma plataforma de análise estatística e previsão de partidas de futebol que combina a arquitetura de **Sistemas Multiagentes (CrewAI)** com pipelines rigorosos de **Machine Learning (Scikit-Learn / XGBoost)** e uma interface moderna em **React + Vite** (`http://localhost:5173/`).

O projeto aplica na prática a metodologia do livro *"Mãos à Obra: Aprendizado de Máquina com Scikit-Learn & TensorFlow"* (Aurélien Géron), transformando cada etapa do ciclo de vida de ML em um agente especializado autônomo.

---

## 📸 Demonstração e Arquitetura

O sistema opera conectando o frontend web local com um backend assíncrono de IA:

```text
 [ FRONTEND ]                                 [ BACKEND ]
 Dashboard React (Vite)                       FastAPI + CrewAI (Python)
 http://localhost:5173                       http://localhost:8000
        │                                             │
        │─── POST /api/analisar (Time A x Time B) ───►│
        │                                             ├──► 1. Agente Engenheiro de Dados
        │                                             ├──► 2. Agente Cientista de ML
        │                                             ├──► 3. Agente Analista de Odds (EV+)
        │                                             └──► 4. Agente Gestor de Risco (Kelly)
        │                                             │
        │◄── Response (JSON com Diagnóstico e EV+) ───│
```

---

## 🤖 A Equipe de Agentes (Fundamentada no Livro)

Cada agente desempenha um papel chave na esteira de desenvolvimento:

1. **`Data Engineer Agent` (Capítulo 2 - End-to-End Pipeline):**
   * Coleta dados de partidas recentes, histórico H2H e métricas avançadas (*xG*, posse produtiva, desfalques).
   * Executa imputação de dados (`SimpleImputer`), escalonamento (`StandardScaler`) e engenharias de *features*.
2. **`ML Modeling Agent` (Capítulos 3, 4 e 7 - Classificação e Ensembles):**
   * Alimenta os modelos preditivos (`RandomForestClassifier`, `XGBoost`, `LogisticRegression`).
   * Calcula as probabilidades estatísticas reais da partida ($P_{	ext{Vitória Casa}}$, $P_{	ext{Empate}}$, $P_{	ext{Vitória Fora}}$), priorizando métricas como ROC-AUC e Log-Loss sobre acurácia simples.
3. **`Value Analyst Agent` (Capítulo 3 - Métricas e Limiares):**
   * Compara as probabilidades reais calculadas pelo modelo com as cotações/odds oferecidas pelas casas de apostas.
   * Identifica **Valor Esperado Positivo ($EV+$)**: 
     $$	ext{EV} = (P_{	ext{Modelo}} 	imes 	ext{Odds}) - 1$$
4. **`Risk Management Agent` (Capítulos 1 e 2 - Tomada de Decisão):**
   * Avalia a volatilidade e aplica o **Critério de Kelly** para definir o dimensionamento rigoroso de capital (*stake management*), protegendo a banca do usuário.

---

## 🛠️ Tecnologias Utilizadas

### **Frontend**
* **React 18** (Vite)
* **Tailwind CSS** (Interface e visualização)
* **Lucide React** / **Recharts** (Gráficos estatísticos)

### **Backend & IA**
* **Python 3.10+**
* **FastAPI** (API REST de alta performance)
* **CrewAI** / **LangChain** (Orquestração de Agentes)
* **Scikit-Learn** & **XGBoost** (Pipelines e modelos ML)
* **Pandas** & **NumPy** (Manipulação estatística de dados)

---

## 🚀 Como Executar o Projeto

### **Pré-requisitos**
* Node.js (v18+)
* Python (v3.10+)
* Chave de API da OpenAI (`OPENAI_API_KEY`) ou provedor LLM equivalente

---

### **1. Configurando e Rodando o Backend (FastAPI)**

```bash
# Clone o repositório
git clone https://github.com/seu-usuario/soccer-predictor-ai.git
cd soccer-predictor-ai/backend

# Crie e ative o ambiente virtual
python -m venv venv
# Linux/macOS:
source venv/bin/activate
# Windows:
# venv\Scripts\activate

# Instale as dependências
pip install -r requirements.txt

# Configure suas variáveis de ambiente
cp .env.example .env
# Adicione sua OPENAI_API_KEY no arquivo .env

# Execute o servidor FastAPI
uvicorn main:app --reload --port 8000
```
O servidor rodará em `http://localhost:8000`.

---

### **2. Configurando e Rodando o Frontend (Vite + React)**

```bash
# Navegue até a pasta do frontend
cd ../frontend

# Instale os pacotes Node
npm install

# Inicie o servidor de desenvolvimento Vite
npm run dev
```
Acesse a aplicação no seu navegador em: **`http://localhost:5173/`**

---

## 📁 Estrutura de Arquivos

```text
soccer-predictor-ai/
├── backend/
│   ├── agents/            # Definição dos Agentes e Suas Tarefas (CrewAI)
│   ├── models/            # Scripts de treinamento e pipelines (.pkl / .json)
│   ├── services/          # Conectores de APIs e Web Scraping de Futebol
│   ├── main.py            # API FastAPI com rotas CORS para o localhost:5173
│   └── requirements.txt   # Dependências Python
├── frontend/
│   ├── src/
│   │   ├── components/    # Componentes de UI (Cards de jogos, Tabelas, Odds)
│   │   ├── services/      # Integração via Axios/Fetch com o Backend (:8000)
│   │   ├── App.jsx        # Dashboard Principal
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
└── README.md
```

---

## 📊 Exemplo de Resposta da API (`/api/analisar`)

```json
{
  "partida": "Flamengo vs Palmeiras",
  "probabilidades_modelo": {
    "casa": 0.48,
    "empate": 0.28,
    "fora": 0.24
  },
  "odds_mercado": {
    "casa": 2.30,
    "empate": 3.20,
    "fora": 3.10
  },
  "diagnostico_agentes": {
    "ev_casa": 0.104,
    "recomendacao": "Aposta com Valor Esperado Positivo (EV+)",
    "selecao": "Vitória Casa (Flamengo)",
    "stake_sugerida": "2.1% da banca (Critério de Kelly fracionado)"
  }
}
```

---

## ⚠️ Isenção de Responsabilidade (Disclaimer)

Este projeto foi construído para fins **educacionais, acadêmicos e de pesquisa** em inteligência artificial e aprendizado de máquina. Modelos preditivos trabalham com probabilidades e não garantem resultados futuros. Gerencie seus investimentos com responsabilidade.

---

## 📝 Licença

Distribuído sob a licença MIT. Veja `LICENSE` para mais informações.
