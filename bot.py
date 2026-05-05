import os
import logging
import asyncio
import tempfile
import subprocess
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
GOOGLE_AI_MODEL = os.getenv("GOOGLE_AI_MODEL", "gemma-3-27b-it")
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "tiny")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN nao encontrado. Defina TELEGRAM_BOT_TOKEN nos Secrets do GitHub.")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY nao encontrada. Defina GEMINI_API_KEY nos Secrets do GitHub.")

client = genai.Client(api_key=GEMINI_API_KEY)
whisper_model = None

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
user_memory = defaultdict(lambda: deque(maxlen=12))

SYSTEM_PROMPT = """
Voce e o atendente virtual da MGR Design Studio.

A MGR Design Studio oferece servicos de design grafico para marcas, empreendedores, lojas online e profissionais que desejam melhorar sua presenca digital.

Servicos principais:
- logomarcas profissionais;
- identidade visual;
- artes para redes sociais;
- marketing digital;
- posts promocionais;
- materiais de divulgacao;
- embalagens;
- imagens para produtos;
- videos de anuncio para Instagram, Reels, Stories, TikTok e campanhas online.

Valores atuais:
- Logomarca: R$ 30,00.
- Marketing digital: R$ 30,00. Inclui no maximo 2 variacoes.
- Video de anuncio: R$ 60,00. Inclui no maximo 2 variacoes.
- Pacote completo com video + logomarca + propaganda normal: R$ 90,00.

Regras sobre preco:
- Quando o cliente perguntar preco, informe esses valores com clareza.
- Nao invente outros valores.
- Se o cliente pedir algo fora desses pacotes, diga que precisa analisar para montar uma proposta personalizada.
- Se o cliente pedir muitas alteracoes ou variacoes, explique que os pacotes de marketing digital e video incluem no maximo 2 variacoes.
- Se o cliente quiser mais variacoes, diga que pode ser combinado um valor adicional apos entender a quantidade.
- Sempre tente mostrar o pacote de R$ 90,00 como melhor custo-beneficio quando fizer sentido.

Diferenciais da MGR Design Studio:
- visual moderno, original e atrativo;
- foco em transmitir confianca e profissionalismo;
- atendimento rapido;
- entrega personalizada;
- excelente custo-beneficio;
- pacotes acessiveis.

Seu objetivo na conversa:
1. Cumprimente e converse de forma natural.
2. Entenda o que o cliente precisa.
3. Faca perguntas simples quando faltar informacao.
4. Explique os servicos de forma clara.
5. Ajude o cliente a escolher o melhor pacote.
6. Negocie de forma educada, valorizando o trabalho.
7. Tente conduzir o cliente para fechar o pedido ou enviar detalhes do projeto.

Perguntas uteis:
- Qual e o nome da sua marca ou negocio?
- Voce precisa de logomarca, marketing digital, video, identidade visual ou pacote completo?
- Qual e o segmento do seu negocio?
- Voce ja tem alguma ideia, cor ou referencia visual?
- Onde esse material sera usado?
- Tem algum prazo em mente?

Tom de voz:
- portugues brasileiro;
- simpatico, profissional e direto;
- mensagens curtas;
- sem parecer robo;
- fale como atendente humano;
- nao diga que e IA;
- evite prometer algo impossivel.
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ola! Seja bem-vindo a MGR Design Studio. Me conta: voce precisa de logomarca, marketing digital, video de anuncio ou o pacote completo?")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Posso te ajudar com logomarca, marketing digital, identidade visual, artes para redes sociais, materiais de divulgacao, embalagens, imagens para produtos e videos de anuncio.\n\n"
        "Valores principais:\n"
        "Logomarca: R$ 30,00\n"
        "Marketing digital: R$ 30,00, com ate 2 variacoes\n"
        "Video: R$ 60,00, com ate 2 variacoes\n"
        "Pacote video + logomarca + propaganda normal: R$ 90,00\n\n"
        "Voce pode mandar texto ou audio.\n\n"
        "Comandos:\n/start - iniciar\n/help - ajuda\n/reset - apagar memoria da conversa"
    )

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_memory[user_id].clear()
    await update.message.reply_text("Memoria da conversa apagada. Vamos comecar de novo. Qual servico voce precisa?")

def gerar_resposta(prompt: str) -> str:
    logging.info("Usando modelo Google AI: %s", GOOGLE_AI_MODEL)
    conteudo = f"{SYSTEM_PROMPT}\n\n{prompt}"
    response = client.models.generate_content(model=GOOGLE_AI_MODEL, contents=conteudo)
    if response and getattr(response, "text", None):
        return response.text.strip()
    raise RuntimeError("Resposta vazia do modelo.")

def get_whisper_model():
    global whisper_model
    if whisper_model is None:
        logging.info("Carregando modelo Whisper local: %s", WHISPER_MODEL_SIZE)
        whisper_model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
    return whisper_model

def transcrever_audio(caminho_audio: str) -> str:
    model = get_whisper_model()
    segments, info = model.transcribe(caminho_audio, language="pt", beam_size=1, vad_filter=True)
    texto = " ".join(segment.text.strip() for segment in segments).strip()
    if not texto:
        raise RuntimeError("Nao consegui entender o audio.")
    logging.info("Audio transcrito. Idioma: %s | Duracao: %.2fs", info.language, info.duration)
    return texto

def gerar_audio_resposta(texto: str) -> str:
    texto_limpo = texto.replace("\n", " ").strip()
    if len(texto_limpo) > 900:
        texto_limpo = texto_limpo[:900]

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as mp3_file:
        caminho_mp3 = mp3_file.name
    caminho_ogg = caminho_mp3.replace(".mp3", ".ogg")

    subprocess.run(["gtts-cli", "--lang", "pt", "--tld", "com.br", "--output", caminho_mp3, texto_limpo], check=True)
    subprocess.run(["ffmpeg", "-y", "-i", caminho_mp3, "-c:a", "libopus", caminho_ogg], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    Path(caminho_mp3).unlink(missing_ok=True)
    return caminho_ogg

async def responder_texto(update: Update, user_text: str, responder_com_audio: bool = False):
    user_id = update.effective_user.id
    user_memory[user_id].append(f"Cliente: {user_text}")
    historico = "\n".join(list(user_memory[user_id]))
    prompt = f"Historico da conversa:\n{historico}\n\nResponda a ultima mensagem do cliente como atendente da MGR Design Studio."
    try:
        answer = await asyncio.to_thread(gerar_resposta, prompt)
        user_memory[user_id].append(f"MGR Design Studio: {answer}")
        if responder_com_audio:
            caminho_audio = None
            try:
                caminho_audio = await asyncio.to_thread(gerar_audio_resposta, answer)
                with open(caminho_audio, "rb") as audio_file:
                    await update.message.reply_voice(voice=audio_file)
            finally:
                if caminho_audio:
                    Path(caminho_audio).unlink(missing_ok=True)
        else:
            await update.message.reply_text(answer)
    except Exception as e:
        logging.exception("Erro final ao responder: %s", e)
        await update.message.reply_text("Tive um problema para responder agora.\n\nErro resumido:\n" + str(e)[:900])

async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await responder_texto(update, update.message.text)

async def responder_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensagem = update.message
    arquivo_temporario = None
    try:
        await mensagem.reply_text("Recebi seu audio. Vou ouvir e te responder por audio.")
        audio = mensagem.voice or mensagem.audio
        arquivo = await context.bot.get_file(audio.file_id)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as tmp:
            arquivo_temporario = tmp.name
        await arquivo.download_to_drive(arquivo_temporario)
        texto_transcrito = await asyncio.to_thread(transcrever_audio, arquivo_temporario)
        await responder_texto(update, texto_transcrito, responder_com_audio=True)
    except Exception as e:
        logging.exception("Erro ao processar audio: %s", e)
        await mensagem.reply_text("Nao consegui processar esse audio. Pode mandar em texto ou tentar outro audio?\n\nErro resumido:\n" + str(e)[:900])
    finally:
        if arquivo_temporario:
            Path(arquivo_temporario).unlink(missing_ok=True)

def main():
    print(f"MGR Design Studio Bot rodando com modelo {GOOGLE_AI_MODEL} e Whisper {WHISPER_MODEL_SIZE}...")
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))
    app.add_handler(MessageHandler((filters.VOICE | filters.AUDIO) & ~filters.COMMAND, responder_audio))
    app.run_polling()

if __name__ == "__main__":
    main()
