# Bot do Telegram — Quiz da Família
Bot interativo para o Telegram desenvolvido para animar as reuniões presenciais de família 

O jogo funciona em tempo real no grupo da família: o bot atua como apresentador do quiz, controla a entrada de participantes, lança perguntas de múltipla escolha com temporizador de 30 segundos, calcula bônus por velocidade de resposta e exibe o pódio final. 

STACK

* Linguagem: Python 3.11+
* Framework Telegram: python-telegram-bot (v20+ async)
* Gerenciador de Pacotes: uv (Astral)
* Containerização: Docker & Docker Compose
* CI/CD: GitHub Actions com Deploy via SSH
 
COMO FUNCIONA O JOGO (MECÂNICA V1) 

1. Abertura (/iniciar_jogo): O bot cria o lobby no grupo. Os membros da família clicam no botão "Entrar no Jogo".
2. Rodada: O bot faz perguntas de múltipla escolha com 30s de limite.
3. Pontuação:
* Acerto base: +100 pontos.
* Bônus de agilidade: Até +50 pontos extras para quem responder mais rápido.
4. Fechamento: Após a última pergunta, o bot revela a classificação geral e celebra o pódio!

COMO RODAR LOCALMENTE (DESENVOLVIMENTO)
  Pré-requisitos:
* Python 3.11+ e uv instalados.
* Um token de bot criado no @BotFather. 
Passos:
1. Clone o repositório:
```bash
git clone https://github.com/seu-usuario/quiz-familia-bot.git
cd quiz-familia-bot
```
2. Instale as dependências com o uv:
```bash
uv sync
```
3. Salve token criado no @BotFather num arquivo .env
4. Execute o bot:
```bash
uv run python bot_quiz.py
```
COMO RODAR VIA DOCKER (LOCAL OU SERVIDOR)

1. Crie ou edite o arquivo perguntas.json com o quiz da semana.

2. Suba o container:
```bash
docker compose up -d --build
```
  
COMO ATUALIZAR AS PERGUNTAS PARA A REUNIÃO

O arquivo perguntas.json está mapeado como um volume do Docker. Para trocar o quiz da semana:

1. Atualize a lista no arquivo perguntas.json.
2. O formato deve seguir este padrão:
```json
[
	{
	"id": 1,
	"pergunta": "Qual é a comida favorita da Vovó?",
	"opcoes": ["Lasanha", "Feijoada", "Bacalhau", "Pizza"],
	"resposta_correta": 1,
	"explicacao": "A feijoada de domingo é imbatível!"
	}
]
```