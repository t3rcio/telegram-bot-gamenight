import asyncio
import json
import logging
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

logging.basicConfig(level=logging.INFO)

GAME_STATE = {
    "admin_id": None,
    "em_andamento": False,
    "pausado": False,  # Estado de pausa
    "tempo_por_pergunta": 60,  # Padrão: 60s
    "jogadores": {},  # {user_id: {"name": str, "pontos": int}}
    "respostas_rodada": {},  # {user_id: opcao_index}
    "pergunta_atual_idx": 0,
    "perguntas": [],
}

TELEGRAM_BOT_TOKEN = os.environ.get("BOT_TOKEN","")
if not TELEGRAM_BOT_TOKEN:
    print("Gere o token do Bot no @BotFather e exporte no .env com o nome BOT_TOKEN")
    sys.exit(0)


def carregar_perguntas():
    with open("perguntas.json", "r", encoding="utf-8") as f:
        return json.load(f)


def is_admin(user_id: int) -> bool:
    return GAME_STATE["admin_id"] is None or GAME_STATE["admin_id"] == user_id


async def cmd_tempo(update: Update, context: ContextTypes.DEFAULT_TYPE):    
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Apenas o Admin pode alterar o tempo.")
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text(
            f"⏱️ Tempo atual: **{GAME_STATE['tempo_por_pergunta']}s**.\nPara alterar use: `/tempo 45`",
            parse_mode="Markdown",
        )
        return

    novo_tempo = int(context.args[0])
    if novo_tempo < 10 or novo_tempo > 300:
        await update.message.reply_text("⚠️ Escolha um tempo entre 10 e 300 segundos.")
        return

    GAME_STATE["tempo_por_pergunta"] = novo_tempo
    await update.message.reply_text(
        f"✅ Tempo por pergunta ajustado para **{novo_tempo} segundos**!",
        parse_mode="Markdown",
    )


async def cmd_iniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):    
    if GAME_STATE["em_andamento"]:
        await update.message.reply_text("⚠️ Já existe uma partida em andamento!")
        return

    GAME_STATE["admin_id"] = update.effective_user.id
    GAME_STATE["jogadores"] = {}
    GAME_STATE["perguntas"] = carregar_perguntas()
    GAME_STATE["pergunta_atual_idx"] = 0
    GAME_STATE["pausado"] = False

    keyboard = [[InlineKeyboardButton("✋ Entrar no Jogo", callback_data="join_game")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    admin_name = update.effective_user.first_name
    await update.message.reply_text(
        f"🎮 **NOVO QUIZ CRIADO POR {admin_name}!**\n\n"
        f"⏱️ Tempo por pergunta: **{GAME_STATE['tempo_por_pergunta']}s**\n"
        f"Clique no botão abaixo para entrar. O Admin deve digitar `/comecar` quando todos estiverem prontos!",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )


async def cmd_comecar(update: Update, context: ContextTypes.DEFAULT_TYPE):    
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Apenas o Admin pode iniciar a rodada!")
        return

    if not GAME_STATE["jogadores"]:
        await update.message.reply_text("⚠️ Ninguém entrou no jogo ainda!")
        return

    GAME_STATE["em_andamento"] = True
    GAME_STATE["pausado"] = False
    await update.message.reply_text("🚀 **O Quiz vai começar agora! Preparem-se!**")
    await proxima_pergunta(context, update.effective_chat.id)


async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):    
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Apenas o Admin pode pausar o jogo.")
        return

    if not GAME_STATE["em_andamento"]:
        await update.message.reply_text("⚠️ Nenhuma partida está em andamento.")
        return

    if GAME_STATE["pausado"]:
        await update.message.reply_text("⏸️ O jogo já está pausado!")
        return

    GAME_STATE["pausado"] = True
    await update.message.reply_text("⏸️ **O jogo foi PAUSADO pelo Admin!**\nUse `/continuar` para retomar.")


async def cmd_continuar(update: Update, context: ContextTypes.DEFAULT_TYPE):    
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Apenas o Admin pode retomar o jogo.")
        return

    if not GAME_STATE["em_andamento"]:
        await update.message.reply_text("⚠️ Nenhuma partida está em andamento.")
        return

    if not GAME_STATE["pausado"]:
        await update.message.reply_text("▶️ O jogo já está rolando normal!")
        return

    GAME_STATE["pausado"] = False
    await update.message.reply_text("▶️ **O jogo foi RETOMADO!** O temporizador voltou a contar.")


async def btn_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Registra entrada dos jogadores."""
    query = update.callback_query
    user = query.from_user

    if user.id not in GAME_STATE["jogadores"]:
        GAME_STATE["jogadores"][user.id] = {"name": user.first_name, "pontos": 0}
        await query.answer("Você entrou no jogo!")
        await query.message.reply_text(f"👤 **{user.first_name}** entrou na partida!")
    else:
        await query.answer("Você já está cadastrado!", show_alert=True)


async def proxima_pergunta(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    idx = GAME_STATE["pergunta_atual_idx"]
    perguntas = GAME_STATE["perguntas"]

    if idx >= len(perguntas):
        await encerrar_jogo(context, chat_id)
        return

    GAME_STATE["respostas_rodada"] = {}
    q_data = perguntas[idx]

    # Teclado em coluna única para legibilidade em telas de celulares
    keyboard = []
    letras = ["A", "B", "C", "D"]
    for i, opc in enumerate(q_data["opcoes"]):
        texto_botao = f"{letras[i]}) {opc}"
        keyboard.append([InlineKeyboardButton(texto_botao, callback_data=f"ans_{i}")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    msg = (
        f"❓ **Pergunta {idx + 1}/{len(perguntas)}**\n\n"
        f"{q_data['pergunta']}\n\n"
        f"⏳ Tempo: **{GAME_STATE['tempo_por_pergunta']}s**"
    )

    await context.bot.send_message(
        chat_id=chat_id, text=msg, reply_markup=reply_markup, parse_mode="Markdown"
    )

    # Temporizador resiliente à pausa (checa a cada 1s)
    tempo_restante = GAME_STATE["tempo_por_pergunta"]
    while tempo_restante > 0:
        if not GAME_STATE["em_andamento"]:
            return

        if not GAME_STATE["pausado"]:
            await asyncio.sleep(1)
            tempo_restante -= 1
        else:
            await asyncio.sleep(1)    
    await finalizar_rodada(context, chat_id)


async def btn_resposta(update: Update, context: ContextTypes.DEFAULT_TYPE):    
    query = update.callback_query
    user = query.from_user

    if GAME_STATE["pausado"]:
        await query.answer("⏸️ O jogo está pausado no momento!", show_alert=True)
        return

    if user.id not in GAME_STATE["jogadores"]:
        await query.answer("Você não está participando desta partida!", show_alert=True)
        return

    if user.id in GAME_STATE["respostas_rodada"]:
        await query.answer("Você já respondeu esta pergunta!", show_alert=True)
        return

    opcao_escolhida = int(query.data.split("_")[1])
    GAME_STATE["respostas_rodada"][user.id] = opcao_escolhida

    await query.answer("Resposta registrada!")
    await query.message.reply_text(f"📩 **{user.first_name}** respondeu!")


async def finalizar_rodada(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    idx = GAME_STATE["pergunta_atual_idx"]
    q_data = GAME_STATE["perguntas"][idx]
    correta = q_data["resposta_correta"]

    texto_resultado = f"⏰ **Fim do tempo!**\n\n"
    texto_resultado += f"✅ Resposta correta: **{q_data['opcoes'][correta]}**\n"
    texto_resultado += f"💡 __{q_data['explicacao']}__\n\n"
    texto_resultado += "📊 **Resultado da rodada:**\n"

    for u_id, dados in GAME_STATE["jogadores"].items():
        resp = GAME_STATE["respostas_rodada"].get(u_id)
        if resp == correta:
            dados["pontos"] += 1
            texto_resultado += f"• {dados['name']}: ✅ Acertou!\n"
        elif resp is not None:
            texto_resultado += f"• {dados['name']}: ❌ Errou\n"
        else:
            texto_resultado += f"• {dados['name']}: 💤 Não respondeu\n"

    await context.bot.send_message(
        chat_id=chat_id, text=texto_resultado, parse_mode="Markdown"
    )

    GAME_STATE["pergunta_atual_idx"] += 1
    await asyncio.sleep(5)  # Pausa de 5s entre perguntas
    await proxima_pergunta(context, chat_id)


async def encerrar_jogo(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    GAME_STATE["em_andamento"] = False
    GAME_STATE["pausado"] = False
    GAME_STATE["admin_id"] = None

    ranking = sorted(
        GAME_STATE["jogadores"].values(), key=lambda x: x["pontos"], reverse=True
    )

    texto_fim = "🏆 **FIM DO QUIZ! RANKING FINAL:**\n\n"
    podium = ["🥇", "🥈", "🥉"]
    for i, pos in enumerate(ranking):
        icon = podium[i] if i < 3 else "👤"
        texto_fim += f"{icon} {pos['name']} — {pos['pontos']} ponto(s)\n"

    await context.bot.send_message(chat_id=chat_id, text=texto_fim, parse_mode="Markdown")


def main():
    TOKEN = "SEU_TELEGRAM_BOT_TOKEN"

    app = Application.builder().token(TOKEN).build()

    # Handlers de Comandos Admin
    app.add_handler(CommandHandler("tempo", cmd_tempo))
    app.add_handler(CommandHandler("iniciar", cmd_iniciar))
    app.add_handler(CommandHandler("comecar", cmd_comecar))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("continuar", cmd_continuar))

    # Handlers de Botoes
    app.add_handler(CallbackQueryHandler(btn_join, pattern="^join_game$"))
    app.add_handler(CallbackQueryHandler(btn_resposta, pattern="^ans_"))
    
    app.run_polling()


if __name__ == "__main__":
    main()