import os
import logging
import asyncio
import tempfile
from collections import defaultdict, deque
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from faster_whisper import WhisperModel
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Modelo Gemma pela API do Google AI Studio.
GOOGLE_AI_MODEL = os.getenv("GOOGLE_AI_MODEL", "gemma-3-27b-it")

# Modelo local para transcricao de audio.
# tiny e mais leve para GitHub Actions. Pode trocar para base se quiser mais qualidade.
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "tiny")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError(
        "TELEGRAM_BOT_TOKEN nao encontrado. Defina TELEGRAM_BOT_TOKEN nos Secrets do GitHub."
    )

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY nao encontrada. Defina GEMINI_API_KEY nos Secrets do GitHub."
    )

client = genai.Client(api_key=GEMINI_API_KEY)
whisper_model = None

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Ola! Eu sou o Zapgr Bot. Pode falar comigo normalmente. Agora tambem aceito audio."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Voce pode conversar comigo por texto ou audio.\n\n"
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
    logging.info("Usando modelo Google AI: %s", GOOGLE_AI_MODEL)

    conteudo = f"""
{SYSTEM_PROMPT}

{prompt}
"""

    response = client.models.generate_content(
        model=GOOGLE_AI_MODEL,
        contents=conteudo,
    )

    if response and getattr(response, "text", None):
        return response.text.strip()

    raise RuntimeError("Resposta vazia do modelo.")

def get_whisper_model():
    global whisper_model
    if whisper_model is None:
        logging.info("Carregando modelo Whisper local: %s", WHISPER_MODEL_SIZE)
        whisper_model = WhisperModel(
            WHISPER_MODEL_SIZE,
            device="cpu",
            compute_type="int8"
        )
    return whisper_model

def transcrever_audio(caminho_audio: str) -> str:
    model = get_whisper_model()
    segments, info = model.transcribe(
        caminho_audio,
        language="pt",
        beam_size=1,
        vad_filter=True,
    )

    texto = " ".join(segment.text.strip() for segment in segments).strip()

    if not texto:
        raise RuntimeError("Nao consegui entender o audio.")

    logging.info("Audio transcrito. Idioma: %s | Duracao: %.2fs", info.language, info.duration)
    return texto

async def responder_texto(update: Update, user_text: str):
    user_id = update.effective_user.id

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
        erro_curto = str(e)[:900]
        await update.message.reply_text(
            "Tive um problema com o modelo Gemma.\n\n"
            "Erro resumido:\n"
            f"{erro_curto}\n\n"
            "Confira TELEGRAM_BOT_TOKEN, GEMINI_API_KEY e se o modelo Gemma esta disponivel para sua chave."
        )

async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await responder_texto(update, update.message.text)

async def responder_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensagem = update.message
    arquivo_temporario = None

    try:
        await mensagem.reply_text("Recebi seu audio. Vou transcrever e responder.")

        audio = mensagem.voice or mensagem.audio
        arquivo = await context.bot.get_file(audio.file_id)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as tmp:
            arquivo_temporario = tmp.name

        await arquivo.download_to_drive(arquivo_temporario)

        texto_transcrito = await asyncio.to_thread(transcrever_audio, arquivo_temporario)
        await mensagem.reply_text(f"Entendi: {texto_transcrito}")

        await responder_texto(update, texto_transcrito)

    except Exception as e:
        logging.exception("Erro ao processar audio: %s", e)
        erro_curto = str(e)[:900]
        await mensagem.reply_text(
            "Nao consegui processar esse audio.\n\n"
            "Erro resumido:\n"
            f"{erro_curto}"
        )

    finally:
        if arquivo_temporario:
            try:
                Path(arquivo_temporario).unlink(missing_ok=True)
            except Exception:
                pass

def main():
    print(f"Zapgr Bot rodando com modelo {GOOGLE_AI_MODEL} e Whisper {WHISPER_MODEL_SIZE}...")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))
    app.add_handler(MessageHandler((filters.VOICE | filters.AUDIO) & ~filters.COMMAND, responder_audio))

    app.run_polling()

if __name__ == "__main__":
    main()
