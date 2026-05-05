import os
import logging
import asyncio
from collections import defaultdict, deque

from dotenv import load_dotenv
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError(
        "TELEGRAM_BOT_TOKEN nao encontrado. Defina TELEGRAM_BOT_TOKEN no ambiente ou no arquivo .env."
    )

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY nao encontrada. Defina GEMINI_API_KEY no ambiente ou no arquivo .env."
    )

genai.configure(api_key=GEMINI_API_KEY)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

user_memory = defaultdict(lambda: deque(maxlen=12))

SYSTEM_PROMPT = """
Voce e o Zapgr Bot, um chatbot do Telegram.

Converse como uma pessoa normal.
Fale em portugues brasileiro.
Seja educado, simples e direto.
Nao diga que e IA o tempo todo.
Evite respostas longas demais.
Se a pessoa pedir orcamento, atendimento ou contato, tente entender a necessidade dela.
Se nao souber algo, peca mais detalhes.
"""


def validar_modelo(model_name: str) -> None:
    try:
        genai.get_model(f"models/{model_name}")
    except Exception as exc:
        raise RuntimeError(
            f"Modelo Gemini invalido ou sem acesso: {model_name}. Ajuste GEMINI_MODEL."
        ) from exc


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Ola! Eu sou o Zapgr Bot. Pode falar comigo normalmente."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Voce pode conversar comigo normalmente.\n\n"
        "Comandos:\n"
        "/start - iniciar\n"
        "/help - ajuda\n"
        "/reset - apagar memoria da conversa"
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_memory[user_id].clear()
    await update.message.reply_text("Memoria da conversa apagada.")


def gerar_resposta(prompt: str) -> str:
    logging.info("Usando modelo Gemini configurado: %s", GEMINI_MODEL)
    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=SYSTEM_PROMPT
    )
    response = model.generate_content(prompt)

    if response and getattr(response, "text", None):
        return response.text.strip()

    raise RuntimeError("Resposta vazia da Gemini.")


async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text

    user_memory[user_id].append(f"Usuario: {user_text}")

    historico = "\n".join(list(user_memory[user_id]))

    prompt = f"""
Historico da conversa:
{historico}

Responda a ultima mensagem do usuario de forma natural.
"""

    try:
        answer = await asyncio.to_thread(gerar_resposta, prompt)
        user_memory[user_id].append(f"Zapgr Bot: {answer}")
        await update.message.reply_text(answer)

    except Exception as e:
        logging.exception("Erro final ao responder: %s", e)
        erro = str(e)
        erro_curto = erro[:900]
        await update.message.reply_text(
            "Tive um problema com a Gemini.\n\n"
            "Erro resumido:\n"
            f"{erro_curto}\n\n"
            "Confira GEMINI_API_KEY, GEMINI_MODEL e se a API Gemini esta ativa."
        )


def main():
    validar_modelo(GEMINI_MODEL)

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))

    print(f"Zapgr Bot rodando com modelo {GEMINI_MODEL}...")
    app.run_polling()


if __name__ == "__main__":
    main()
