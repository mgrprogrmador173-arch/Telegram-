import os
import logging
from collections import defaultdict, deque

from dotenv import load_dotenv
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

load_dotenv()

# Token temporário de teste do Telegram informado pelo usuário.
TELEGRAM_BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN",
    "8520407101:AAGyWeBw6Mqa63RYCShe4IgJ1bxpiD_vnFg"
)

# Coloque sua chave Gemini no arquivo .env:
# GEMINI_API_KEY=sua_chave_aqui
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY não encontrada. Crie um arquivo .env e coloque: GEMINI_API_KEY=sua_chave_aqui"
    )

genai.configure(api_key=GEMINI_API_KEY)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# Memória curta por usuário
user_memory = defaultdict(lambda: deque(maxlen=12))

SYSTEM_PROMPT = """
Você é o Zapgr Bot, um chatbot do Telegram.

Converse como uma pessoa normal.
Fale em português brasileiro.
Seja educado, simples e direto.
Não diga que é IA o tempo todo.
Evite respostas longas demais.
Se a pessoa pedir orçamento, atendimento ou contato, tente entender a necessidade dela.
Se não souber algo, peça mais detalhes.
"""

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    system_instruction=SYSTEM_PROMPT
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Olá! Eu sou o Zapgr Bot. Pode falar comigo normalmente."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Você pode conversar comigo normalmente.\n\n"
        "Comandos:\n"
        "/start - iniciar\n"
        "/help - ajuda\n"
        "/reset - apagar memória da conversa"
    )

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_memory[user_id].clear()
    await update.message.reply_text("Memória da conversa apagada.")

async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text

    user_memory[user_id].append(f"Usuário: {user_text}")

    historico = "\n".join(list(user_memory[user_id]))

    prompt = f"""
Histórico da conversa:
{historico}

Responda a última mensagem do usuário de forma natural.
"""

    try:
        response = model.generate_content(prompt)

        answer = response.text.strip() if response.text else "Não consegui gerar uma resposta agora."

        user_memory[user_id].append(f"Zapgr Bot: {answer}")

        await update.message.reply_text(answer)

    except Exception as e:
        logging.exception(e)
        await update.message.reply_text(
            "Tive um problema para responder agora. Verifique sua chave Gemini e tente novamente."
        )

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))

    print("Zapgr Bot com Gemini está rodando...")
    app.run_polling()

if __name__ == "__main__":
    main()