'''
Version 0.1 - A very simple prototype
'''
import asyncio
import os
import json
import logging
import time
import sys

from typing import Dict, Any, List, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("BOT_TOKEN","")
if not TELEGRAM_BOT_TOKEN:
    print("Gere o token do Bot no @BotFather e exporte no .env com o nome BOT_TOKEN")
    sys.exit(0)

class GameState:
    def __init__(self):
        self.is_active: bool = False
        self.phase: str = "IDLE"
        self.players: Dict[int, str] = {}
        self.scores: Dict[int, int] = {}
        self.questions: List[Dict[str, Any]] = []
        self.current_question_index: int = 0
        self.answers_current_round: Dict[int, Dict[str, Any]] = {}
        self.question_start_time: float = 0.0
        self.timer_task: Optional[asyncio.Task] = None

games: Dict[int, GameState] = {}

def get_game(chat_id: int) -> GameState:
    if chat_id not in games:
        games[chat_id] = GameState()
    return games[chat_id]

def load_questions(filepath: str = "perguntas.json") -> List[Dict[str, Any]]:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Erro ao carregar perguntas: {e}")
        return []

async def start_game_command(update: Update, context: ContextTypes.DEFAULT_TYPE):    
    chat_id = update.effective_chat.id
    game = get_game(chat_id)

    if game.is_active:
        await update.message.reply_text("⚠️ Já existe um jogo em andamento neste grupo!")
        return

    questions = load_questions()
    if not questions:
        await update.message.reply_text("❌ Nenhuma pergunta encontrada no arquivo `perguntas.json`.")
        return

    # Reinicia o estado do jogo
    game.is_active = True
    game.phase = "LOBBY"
    game.players.clear()
    game.scores.clear()
    game.questions = questions
    game.current_question_index = 0

    keyboard = [
        [
            InlineKeyboardButton("✋ Entrar no Jogo", callback_data="join_game"),
            InlineKeyboardButton("🚀 Começar!", callback_data="start_quiz"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🍕 **A TERÇA DO QUIZ VAI COMECAR!** 🎉\n\n"
        "Quem for participar da reunião de hoje, clique no botão **Entrar no Jogo**.\n"
        "Quando todos estiverem prontos, cliquem em **Começar!**",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )

async def process_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    user = query.from_user
    game = get_game(chat_id)

    await query.answer()

    if not game.is_active:
        await query.edit_message_text("Este jogo já foi encerrado.")
        return

    # --- FASE 1: LOBBY ---
    if query.data == "join_game" and game.phase == "LOBBY":
        if user.id not in game.players:
            game.players[user.id] = user.first_name
            game.scores[user.id] = 0
            
            lista_jogadores = "\n".join([f"• {name}" for name in game.players.values()])
            
            keyboard = [
                [
                    InlineKeyboardButton("✋ Entrar no Jogo", callback_data="join_game"),
                    InlineKeyboardButton("🚀 Começar!", callback_data="start_quiz"),
                ]
            ]
            
            await query.edit_message_text(
                f"🍕 **A TERÇA DO QUIZ VAI COMECAR!** 🎉\n\n"
                f"**Jogadores Confirmados ({len(game.players)}):**\n{lista_jogadores}\n\n"
                f"Clique em **Entrar no Jogo** para se juntar ou **Começar!** para iniciar.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )
        return

    elif query.data == "start_quiz" and game.phase == "LOBBY":
        if len(game.players) == 0:
            await context.bot.send_message(chat_id, "⚠️ Pelo menos 1 pessoa precisa entrar no jogo!")
            return
        
        game.phase = "QUESTION"
        await query.edit_message_text("🎬 **O Quiz vai começar agora!** Preparem-se...")
        await asyncio.sleep(2)
        await send_next_question(chat_id, context)
        return

    if query.data.startswith("ans_") and game.phase == "QUESTION":
        if user.id not in game.players:
            await context.bot.send_message(
                chat_id=user.id, 
                text="Você não se cadastrou no início da partida, mas pode participar na próxima rodada!"
            )
            return

        if user.id in game.answers_current_round:
            return  # Já respondeu nesta rodada

        selected_option = int(query.data.split("_")[1])
        elapsed_time = time.time() - game.question_start_time

        game.answers_current_round[user.id] = {
            "option": selected_option,
            "time": elapsed_time,
        }

        # Feedback em privado/toast para o jogador
        await query.answer(text=f"Resposta registrada em {elapsed_time:.1f}s!", show_alert=False)

        # Se todos os jogadores registrados já responderam, encerra a pergunta imediatamente
        if len(game.answers_current_round) == len(game.players):
            if game.timer_task and not game.timer_task.done():
                game.timer_task.cancel()
            await evaluate_round(chat_id, context)

# Timer
async def send_next_question(chat_id: int, context: ContextTypes.DEFAULT_TYPE):    
    game = get_game(chat_id)
    game.answers_current_round.clear()

    q_data = game.questions[game.current_question_index]
    total_q = len(game.questions)

    # Monta botões das alternativas
    buttons = []
    labels = ["A", "B", "C", "D"]
    for idx, opt in enumerate(q_data["opcoes"]):
        buttons.append([InlineKeyboardButton(f"{labels[idx]}) {opt}", callback_data=f"ans_{idx}")])

    reply_markup = InlineKeyboardMarkup(buttons)

    msg = await context.bot.send_message(
        chat_id=chat_id,
        text=f"❓ **Pergunta {game.current_question_index + 1} de {total_q}** ⏳ *(Tempo: 30s)*\n\n"
             f"**{q_data['pergunta']}**",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )

    game.question_start_time = time.time()
    game.timer_task = asyncio.create_task(question_timer(chat_id, context, 30))

# 30 secs
async def question_timer(chat_id: int, context: ContextTypes.DEFAULT_TYPE, seconds: int):    
    try:
        await asyncio.sleep(seconds)        
        game = get_game(chat_id)
        if game.phase == "QUESTION":
            await context.bot.send_message(chat_id, "⌛ **Tempo esgotado!**")
            await evaluate_round(chat_id, context)

    except asyncio.CancelledError:
        pass

async def evaluate_round(chat_id: int, context: ContextTypes.DEFAULT_TYPE):    
    game = get_game(chat_id)
    game.phase = "EVALUATION"

    q_data = game.questions[game.current_question_index]
    correct_idx = q_data["resposta_correta"]
    correct_label = ["A", "B", "C", "D"][correct_idx]
    correct_text = q_data["opcoes"][correct_idx]

    resumo_rodada = []
    
    for user_id, user_name in game.players.items():
        user_ans = game.answers_current_round.get(user_id)
        
        if user_ans and user_ans["option"] == correct_idx:
            # PONTUAÇÃO: 100 base + bônus de agilidade (até 50 pts) se respondeu rápido
            time_taken = user_ans["time"]
            speed_bonus = max(0, int((30 - time_taken) * 1.66))  # 30s -> ~50 pts de bônus max
            total_points = 100 + speed_bonus
            
            game.scores[user_id] += total_points
            resumo_rodada.append(f"✅ **{user_name}**: +{total_points} pts ({time_taken:.1f}s)")
        elif user_ans:
            resumo_rodada.append(f"❌ **{user_name}**: Errou")
        else:
            resumo_rodada.append(f"💤 **{user_name}**: Não respondeu")

    texto_revelacao = (
        f"🎯 **Resposta Correta:** {correct_label}) {correct_text}\n"
        f"💡 *{q_data.get('explicacao', '')}*\n\n"
        f"📊 **Desempenho da Rodada:**\n" + "\n".join(resumo_rodada)
    )

    await context.bot.send_message(chat_id, texto_revelacao, parse_mode="Markdown")
    await asyncio.sleep(4)
    
    game.current_question_index += 1
    if game.current_question_index < len(game.questions):
        game.phase = "QUESTION"
        await send_next_question(chat_id, context)
    else:
        await finish_game(chat_id, context)

async def finish_game(chat_id: int, context: ContextTypes.DEFAULT_TYPE):    
    game = get_game(chat_id)    
    ranking = sorted(game.scores.items(), key=lambda x: x[1], reverse=True)
    
    medals = ["🥇", "🥈", "🥉"]
    podio_str = []
    
    for idx, (user_id, score) in enumerate(ranking):
        name = game.players[user_id]
        icon = medals[idx] if idx < 3 else "🏅"
        podio_str.append(f"{icon} **{idx+1}º Lugar:** {name} — {score} pts")

    podio_texto = "\n".join(podio_str)

    await context.bot.send_message(
        chat_id,
        f"🏆 **FIM DO JOGO DE HOJE!** 🏆\n\n"
        f"Confira o Pódio da NAF:\n\n{podio_texto}\n\n"
        f"Parabéns a todos! Na próxima Terça tem mais! 🎉",
        parse_mode="Markdown",
    )

    # Reset
    game.is_active = False
    game.phase = "IDLE"

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("iniciar_jogo", start_game_command))
    app.add_handler(CallbackQueryHandler(process_callbacks))

    logger.info("Bot de Quiz da Família iniciado!")
    app.run_polling()

if __name__ == "__main__":
    main()