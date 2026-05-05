import os
import asyncio
import logging
import tempfile
from pathlib import Path
from collections import defaultdict, deque

from dotenv import load_dotenv
from google import genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from telegram_audio import transcrever_audio, gerar_audio_resposta

load_dotenv()
logging.basicConfig(level=logging.INFO)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_AI_MODEL = os.getenv("GOOGLE_AI_MODEL", "gemini-2.5-flash-lite")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN nao encontrado.")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY nao encontrada.")

client = genai.Client(api_key=GEMINI_API_KEY)
memoria = defaultdict(lambda: deque(maxlen=10))

PROMPT = """
Voce e atendente da MGR Design Studio.
Servicos: logomarca, marketing digital, artes para redes sociais e video de anuncio.
Valores: Logomarca R$30; Marketing digital R$30 com ate 2 variacoes; Video R$60 com ate 2 variacoes; Pacote video + logomarca + propaganda normal R$90.
Responda em portugues brasileiro, de forma simpatica, profissional e muito resumida.
Use no maximo 3 frases curtas. Nao diga que e IA. Negocie sem desvalorizar o servico.
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ola! Sou da MGR Design Studio. Voce precisa de logomarca, marketing digital, video ou pacote completo?")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Logomarca R$30 | Marketing R$30 | Video R$60 | Pacote completo R$90. Pode mandar texto ou audio.")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    memoria[update.effective_user.id].clear()
    await update.message.reply_text("Memoria apagada. Qual servico voce precisa?")

def gerar_resposta(user_id: int, texto: str) -> str:
    memoria[user_id].append(f"Cliente: {texto}")
    historico = "\n".join(memoria[user_id])
    prompt = f"{PROMPT}\n\nHistorico:\n{historico}\n\nResponda como atendente da MGR."
    resposta = client.models.generate_content(model=GOOGLE_AI_MODEL, contents=prompt)
    texto_resposta = getattr(resposta, "text", "") or "Certo. Me passa mais detalhes para eu te ajudar melhor."
    texto_resposta = texto_resposta.strip()
    memoria[user_id].append(f"MGR: {texto_resposta}")
    return texto_resposta

async def responder_texto(update: Update, texto: str, audio: bool = False):
    try:
        resposta = await asyncio.to_thread(gerar_resposta, update.effective_user.id, texto)
        if audio:
            caminho = None
            try:
                caminho = await asyncio.to_thread(gerar_audio_resposta, resposta)
                with open(caminho, "rb") as f:
                    await update.message.reply_voice(voice=f)
            finally:
                if caminho:
                    Path(caminho).unlink(missing_ok=True)
        else:
            await update.message.reply_text(resposta)
    except Exception as e:
        logging.exception(e)
        await update.message.reply_text("Tive um problema para responder agora. Tente novamente em instantes.")

async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await responder_texto(update, update.message.text, audio=False)

async def responder_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    temp = None
    try:
        await update.message.reply_text("Recebi seu audio. Vou ouvir e responder por audio.")
        audio = update.message.voice or update.message.audio
        arquivo = await context.bot.get_file(audio.file_id)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as tmp:
            temp = tmp.name
        await arquivo.download_to_drive(temp)
        texto = await asyncio.to_thread(transcrever_audio, temp)
        await responder_texto(update, texto, audio=True)
    except Exception as e:
        logging.exception(e)
        await update.message.reply_text("Nao consegui processar esse audio. Pode mandar em texto?")
    finally:
        if temp:
            Path(temp).unlink(missing_ok=True)

app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("reset", reset))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))
app.add_handler(MessageHandler((filters.VOICE | filters.AUDIO) & ~filters.COMMAND, responder_audio))

print(f"MGR Telegram rodando com {GOOGLE_AI_MODEL}, audio e voz 1.5x...")
app.run_polling()
