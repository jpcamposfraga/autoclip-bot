# 🎬 AutoClip Factory

> Plataforma autônoma e local para Windows 11 para criação de cortes virais com IA a partir de cenas do YouTube, enquadramento dinâmico 9:16 de cinema, queima de legendas animadas e publicação automática no TikTok, Instagram e YouTube Shorts via emulador Android (LDPlayer 9).

---

## 🚀 Funcionalidades Principais

- **Piloto Automático & Entrega no Telegram (Horários de Pico):**
  - Varre canais do YouTube automaticamente sem trabalho manual (`scanner.py`), garantindo zero repetição de vídeos (`processed_sources`).
  - Dispara nos horários otimizados para máxima entrega do algoritmo: **12:00, 18:00 e 21:00**.
  - Envia o vídeo renderizado em 9:16 direto para o seu **Telegram**, com título, gancho e hashtags prontas para copiar e postar no smartphone.
- **Ingestão Rápida com `yt-dlp`:** Baixa automaticamente clipes e cenas em alta definição (1080p).
- **Detecção de Ganchos com Google Gemini:** Utiliza a API do **Gemini Flash** (com cadeia de fallback resiliente e retentativas automáticas) para identificar os momentos de maior tensão, diálogo e potencial de retenção.
- **Extração Multi-Cortes (1 a 5 cortes):** Permite configurar e gerar múltiplos cortes virais não sobrepostos a partir de um único vídeo longo.
- **Enquadramento de Cinema 9:16:** Mantém a proporção panorâmica original do filme centralizada, preenchendo o fundo vertical com o mesmo vídeo ampliado e com desfoque gaussiano (*blurred background*).
- **Legendas Dinâmicas Estilizadas (`.ass`):** Geração de legendas em destaque com tipografia chamativa palavra por palavra sincronizada com o áudio.
- **Tratamento Anti-Copyright:** Aplicação sutil de aceleração (1.03x) e equalização para invalidar hashes rígidos de Content ID.
- **Automação Móvel Oficial (`uiautomator2` + ADB):**
  - Publicação autônoma no **TikTok Oficial** (`com.zhiliaoapp.musically`).
  - Publicação autônoma no **Instagram Oficial** (`com.instagram.android`).
  - Publicação autônoma no **YouTube Shorts** (`com.google.android.youtube`).
  - Suporte nativo a *Android Share Intent* para envio direto do arquivo para a tela de composição.
  - Toques humanizados com micro-jitter aleatório e pausas naturais para mitigar detecções de bot.
- **Agendador Inteligente em Segundo Plano:** Fila com SQLite (`autoclip.db`), controle de quantidade de postagens por dia e intervalo mínimo de horas entre posts.
- **Templates de Copywriting:** Customização do formato de títulos, legendas e hashtags na interface com suporte a variáveis (`{title}` e `{caption}`).
- **Dashboard de Métricas & Controle (Streamlit):** Interface 100% em Python com reprodutor de vídeo, visualização da fila, controle de emuladores e monitoramento de views, likes e comentários.

---

## 🛠️ Stack Tecnológica

| Camada | Ferramenta | Finalidade |
| :--- | :--- | :--- |
| **Interface** | Streamlit | Dashboard web local interativo e reprodutor de mídia |
| **Inteligência Artificial** | Google Gemini 2.5/2.0 Flash (`google-genai`) | Análise de transcrição, seleção de hooks virais e legendas |
| **Download & Métricas** | `yt-dlp` | Ingestão de vídeos e consulta não-intrusiva de métricas públicas |
| **Processamento de Vídeo** | FFmpeg (Gyan build com `libass`) | Corte, layout de cinema 9:16 e queima de legendas |
| **Virtualização & Emulação** | LDPlayer 9 | Execução das contas em instâncias Android |
| **Automação de Tela** | `uiautomator2` + `adbutils` | Toques humanizados e disparo de intents no Android |
| **Banco de Dados** | SQLite3 embutido | Gestão da fila de postagens e histórico de métricas |

---

## 📋 Pré-requisitos

1. **Windows 11** (com GPU dedicada recomendada).
2. **Python 3.10+** (testado e homologado no Python 3.14).
3. **FFmpeg** instalado e configurado no PATH (ou instalado via WinGet: `winget install Gyan.FFmpeg`).
4. **LDPlayer 9** instalado com a **Depuração ADB** ativada nas configurações (*"Abrir conexão local"*).
5. **Chave de API do Google Gemini** (gratuita no [Google AI Studio](https://aistudio.google.com/app/apikey)).

---

## ⚙️ Instalação

Clone o repositório e instale as dependências:

```bash
git clone https://github.com/seu-usuario/autoclip-bot.git
cd autoclip-bot

pip install -r requirements.txt
```

*(Ou instale as dependências diretamente: `pip install streamlit yt-dlp google-genai uiautomator2 adbutils`)*

---

## 🎯 Como Executar

### 1. Iniciar o Painel
Você pode iniciar de duas formas:

- **Via duplo clique:** Execute o arquivo [`run.bat`](file:///C:/Users/João/autoclip-bot/run.bat).
- **Via terminal:**
  ```bash
  streamlit run app.py
  ```

O navegador abrirá automaticamente em `http://localhost:8501`.

### 2. Configurar a Chave do Gemini
Na barra lateral esquerda, insira sua **Gemini API Key**. A chave será salva automaticamente no arquivo local `config.json` e persistida para os próximos usos.

### 3. Conectar o Emulador
Abra o **LDPlayer 9**. O painel detectará a conexão ADB automaticamente em `127.0.0.1:5555`. Se necessário, use a opção de conexão manual na barra lateral.

### 4. Gerar Cortes e Agendar
1. Na aba **🎬 Criador de Cortes**, cole a URL de um clipe do YouTube.
2. Escolha quantos cortes deseja gerar (1 a 5) e clique em **⚡ Processar e Gerar Cortes 9:16**.
3. Assista aos vídeos gerados na pré-visualização, ajuste o título ou legenda e selecione a plataforma de destino (**Instagram Oficial**, **TikTok Oficial** ou **YouTube Shorts**).
4. Clique em **📅 Agendar Postagem**.
5. Na aba **📅 Fila de Postagens**, você pode acompanhar os envios agendados ou clicar em **⚡ Processar Fila Agora** para disparar o robô imediatamente no emulador.

---

## 📁 Estrutura do Projeto

```text
autoclip-bot/
├── app.py              # Interface principal em Streamlit (Dashboard)
├── clipper.py          # Motor de download, análise Gemini e renderização FFmpeg
├── poster.py           # Automação de postagem no Instagram, TikTok e Shorts (uiautomator2)
├── scheduler.py        # Agendador em segundo plano com regras de intervalo e limites
├── metrics.py          # Coletor de métricas públicas de visualizações e engajamento
├── emulator.py         # Utilitários de conexão ADB e injeção na galeria do Android
├── db.py               # Camada de persistência SQLite (autoclip.db)
├── config.py           # Gerenciamento de caminhos, templates e persistência de configs
├── test_smoke.py       # Suíte de testes rápidos de validação das funções principais
├── run.bat             # Inicializador rápido por duplo clique para Windows
├── .gitignore          # Proteção para não versionar vídeos, db e arquivos de configuração
└── docs/plans/         # Planos detalhados de arquitetura e implementação
```

---

## 🔒 Segurança e Boas Práticas

- **Pastas Locais de Mídia:** Os arquivos baixados e renderizados ficam salvos em `media/downloads` e `media/clips`, ambos ignorados pelo `.gitignore` para manter o repositório leve.
- **Credenciais Protegidas:** O arquivo `config.json` e o banco `autoclip.db` não são commitados.
- **Cadência de Postagens:** Recomenda-se manter o limite de 2 a 3 postagens por dia por conta com intervalos de 2 a 4 horas para proteger as contas de limitações das redes sociais.
