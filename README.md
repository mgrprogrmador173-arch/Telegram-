# Zapgr Bot com Gemini

Bot: `@Zapgr_bot`

Este projeto já vem com o token temporário de teste do Telegram dentro do código.

Você só precisa colocar sua chave da Gemini.

## 1. Instalar

```bash
pip install -r requirements.txt
```

## 2. Criar o arquivo `.env`

Crie um arquivo chamado `.env` na mesma pasta do `bot.py`.

Coloque dentro dele:

```env
GEMINI_API_KEY=SUA_CHAVE_GEMINI_AQUI
```

## 3. Rodar

```bash
python bot.py
```

Depois abra o Telegram e mande mensagem para:

```text
@Zapgr_bot
```

## Comandos

- `/start` - iniciar
- `/help` - ajuda
- `/reset` - apagar memória da conversa

## Onde trocar o token do Telegram depois

No arquivo `bot.py`, troque esta parte:

```python
TELEGRAM_BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN",
    "8520407101:AAGyWeBw6Mqa63RYCShe4IgJ1bxpiD_vnFg"
)
```

Ou coloque `TELEGRAM_BOT_TOKEN` nas variáveis de ambiente da hospedagem.

## Hospedagem

Você pode subir no GitHub e hospedar em:

- Render
- Railway
- Fly.io
- VPS
- Docker

Atenção: o GitHub não mantém o bot rodando sozinho. Ele só guarda o código.