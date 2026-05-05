import os
import logging
import requests
from pathlib import Path
from flask import Flask, request
from google import genai
from dotenv import load_dotenv
from audio_reply import criar_audio_resposta

load_dotenv()

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "mgr-teste")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_AI_MODEL = os.getenv("GOOGLE_AI_MODEL", "gemma-3-27b-it")

if not WHATSAPP_TOKEN:
    raise RuntimeError("WHATSAPP_TOKEN nao encontrado nos Secrets.")
if not WHATSAPP_PHONE_NUMBER_ID:
    raise RuntimeError("WHATSAPP_PHONE_NUMBER_ID nao encontrado nos Secrets.")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY nao encontrado nos Secrets.")

client = genai.Client(api_key=GEMINI_API_KEY)
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

SYSTEM_PROMPT = """
Voce e o atendente virtual da MGR Design Studio.
Fale em portugues brasileiro, de forma simpatica, profissional e direta.

Servicos e valores:
- Logomarca: R$ 30,00.
- Marketing digital: R$ 30,00, com no maximo 2 variacoes.
- Video de anuncio: R$ 60,00, com no maximo 2 variacoes.
- Pacote completo com video + logomarca + propaganda normal: R$ 90,00.

Ajude o cliente a escolher o melhor pacote.
Negocie com educacao, sem desvalorizar o servico.
Se o cliente pedir desconto, ofereca adaptar o pacote ao orcamento.
Sempre tente entender nome da marca, servico desejado, prazo, referencias e onde o material sera usado.
Nao diga que e IA.
"""


def gerar_resposta(texto: str) -> str:
    prompt = f"{SYSTEM_PROMPT}\n\nCliente: {texto}\n\nResponda como atendente da MGR Design Studio."
    response = client.models.generate_content(model=GOOGLE_AI_MODEL, contents=prompt)
    if response and getattr(response, "text", None):
        return response.text.strip()
    return "Certo. Me passa mais detalhes do que voce precisa para eu te ajudar melhor."


def meta_headers(json_content: bool = True):
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    if json_content:
        headers["Content-Type"] = "application/json"
    return headers


def enviar_whatsapp_texto(numero: str, texto: str):
    url = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "text",
        "text": {"body": texto[:4000]},
    }
    r = requests.post(url, headers=meta_headers(), json=payload, timeout=30)
    logging.info("Resposta Meta texto: %s %s", r.status_code, r.text)
    r.raise_for_status()


def subir_audio_meta(caminho_audio: str) -> str:
    url = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_NUMBER_ID}/media"
    data = {"messaging_product": "whatsapp", "type": "audio/mpeg"}
    with open(caminho_audio, "rb") as f:
        files = {"file": ("resposta.mp3", f, "audio/mpeg")}
        r = requests.post(url, headers=meta_headers(False), data=data, files=files, timeout=60)
    logging.info("Upload audio Meta: %s %s", r.status_code, r.text)
    r.raise_for_status()
    return r.json()["id"]


def enviar_whatsapp_audio(numero: str, media_id: str):
    url = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "audio",
        "audio": {"id": media_id},
    }
    r = requests.post(url, headers=meta_headers(), json=payload, timeout=30)
    logging.info("Resposta Meta audio: %s %s", r.status_code, r.text)
    r.raise_for_status()


def responder_com_audio(numero: str, texto_resposta: str):
    caminho_audio = None
    try:
        caminho_audio = criar_audio_resposta(texto_resposta)
        media_id = subir_audio_meta(caminho_audio)
        enviar_whatsapp_audio(numero, media_id)
    finally:
        if caminho_audio:
            Path(caminho_audio).unlink(missing_ok=True)


@app.get("/")
def home():
    return "MGR WhatsApp test bot rodando com resposta em audio."


@app.get("/webhook")
def verificar_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
        return challenge or "", 200

    return "Token invalido", 403


@app.post("/webhook")
def receber_mensagem():
    data = request.get_json(silent=True) or {}
    logging.info("Webhook recebido: %s", data)

    numero = None
    try:
        entry = data.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            return "ok", 200

        msg = messages[0]
        numero = msg.get("from")
        tipo = msg.get("type")

        if tipo == "text":
            texto = msg.get("text", {}).get("body", "")
            resposta = gerar_resposta(texto)
            responder_com_audio(numero, resposta)
        else:
            enviar_whatsapp_texto(numero, "Por enquanto, neste teste, respondo em audio quando voce me manda texto. Pode mandar sua pergunta em texto?")

    except Exception as e:
        logging.exception("Erro no webhook: %s", e)
        if numero:
            try:
                enviar_whatsapp_texto(numero, "Tive um problema para responder em audio agora. Pode tentar novamente?")
            except Exception:
                pass

    return "ok", 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
