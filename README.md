# Zapgr Bot com Gemma

Bot: `@Zapgr_bot`

Este bot usa Telegram + Google AI Studio com modelo **Gemma**.

## Secrets obrigatorios no GitHub

Abra:

https://github.com/mgrprogrmador173-arch/Telegram-/settings/secrets/actions

Crie estes secrets:

```env
TELEGRAM_BOT_TOKEN=SEU_TOKEN_DO_BOT_TELEGRAM
GEMINI_API_KEY=SUA_CHAVE_DO_GOOGLE_AI_STUDIO
```

A chave continua se chamando `GEMINI_API_KEY`, porque e a chave da API do Google AI Studio.

## Modelo usado

O workflow esta configurado para usar:

```env
GOOGLE_AI_MODEL=gemma-3-27b-it
```

## Rodar no GitHub Actions

Abra:

https://github.com/mgrprogrmador173-arch/Telegram-/actions/workflows/run-bot.yml

Clique em:

```text
Run workflow
```

## Comandos do bot

- `/start` - iniciar
- `/help` - ajuda
- `/reset` - apagar memoria da conversa

## Observacao

O GitHub Actions e bom para teste, mas nao e hospedagem 24h ideal. Ele pode parar quando atingir o limite de execucao.
