# ClinicAI-Triagem 🩺🤖

ClinicAI-Triagem é um assistente virtual inteligente, construído com Python, FastAPI e a API do Google Gemini, projetado para realizar uma triagem médica inicial através de uma interface de chat. O agente é capaz de guiar o usuário, coletar informações sobre seus sintomas de forma estruturada e identificar potenciais situações de emergência.

## ✨ Funcionalidades

- **Interface de Chat Conversacional**: Interage com o usuário de forma empática e profissional para coletar informações de saúde.
- **Coleta Estruturada de Dados**: Faz perguntas para obter queixa principal, sintomas, duração, intensidade e histórico relevante.
- **Detecção de Emergência**: Utiliza palavras-chave para identificar sintomas que indicam uma emergência e instrui o usuário a procurar ajuda imediata.
- **Geração de Resumo (JSON)**: Ao final da coleta, gera um objeto JSON estruturado com os dados do paciente, ideal para integração com prontuários eletrônicos.
- **Persistência de Conversas**: Salva o histórico de todas as interações em um banco de dados MongoDB.
- **Arquitetura Reativa com LangGraph**: Utiliza um grafo de estados para gerenciar o fluxo da conversa de forma robusta e modular.

## 🛠️ Tecnologias Utilizadas

- **Backend**: FastAPI
- **Modelo de Linguagem (LLM)**: Google Gemini (via `google-generativeai`)
- **Orquestração do Agente**: LangGraph
- **Banco de Dados**: MongoDB (com `motor` para operações assíncronas)
- **Servidor ASGI**: Uvicorn

---

## 🚀 Como Rodar o Projeto

Siga os passos abaixo para configurar e executar o projeto em sua máquina local.

### 1. Pré-requisitos

- **Python 3.9+**
- **Git**
- Uma instância do **MongoDB** (pode ser local ou um cluster gratuito no MongoDB Atlas)
- Uma **Chave de API do Google Gemini**. Você pode obter uma no Google AI Studio.

### 2. Configuração do Ambiente

**a. Clone o repositório:**

```bash
git clone https://github.com/seu-usuario/clinicai-triagem.git
cd clinicai-triagem
```
> **Nota**: Substitua `seu-usuario/clinicai-triagem` pela URL correta do seu repositório no GitHub.

**b. Crie e ative um ambiente virtual:**

```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

**c. Instale as dependências:**

Crie um arquivo `requirements.txt` na raiz do projeto com o seguinte conteúdo:

```txt
fastapi
uvicorn[standard]
python-dotenv
google-generativeai
langgraph
motor
bson
```

Em seguida, instale os pacotes:

```bash
pip install -r requirements.txt
```

**d. Configure as variáveis de ambiente:**

Crie um arquivo chamado `.env` na raiz do projeto e adicione as seguintes chaves, substituindo pelos seus valores:

```env
GEMINI_API_KEY="SUA_CHAVE_DE_API_DO_GEMINI"
MONGO_URI="SUA_URI_DE_CONEXAO_DO_MONGODB"
MONGO_DB="clinicai"
```

### 3. Executando a Aplicação

Com o ambiente virtual ativado, inicie o servidor FastAPI com o Uvicorn:

```bash
uvicorn app.main:app --reload
```

O servidor estará disponível em `http://127.0.0.1:8000`. Você pode acessar a documentação interativa da API em `http://127.0.0.1:8000/docs`.