# Zapgr Bot com Gemini

Bot: `@Zapgr_bot`

## 1. Instalar

```bash
pip install -r requirements.txt
```

## 2. Criar o arquivo `.env`

Copie o arquivo `.env.example` para `.env` na mesma pasta do `bot.py`.

Exemplo de conteudo:

```env
TELEGRAM_BOT_TOKEN=SEU_TOKEN_DO_BOT_TELEGRAM
GEMINI_API_KEY=SUA_CHAVE_GEMINI_AQUI
# opcional (padrao: gemini-2.5-flash)
GEMINI_MODEL=gemini-2.5-flash
```

## 3. Rodar

```bash
python bot.py
```

Na inicializacao, o bot valida se o modelo configurado em `GEMINI_MODEL` existe e se sua chave tem acesso a ele.

## Sobre "abrir com Gemini 1.5 e depois 2.5"

Este projeto agora usa **apenas** o modelo definido em `GEMINI_MODEL` (padrao `gemini-2.5-flash`).

Se estiver `gemini-1.5-flash` no ambiente/workflow, o bot converte automaticamente para `gemini-2.5-flash` e registra um warning no log.

Se voce perceber comportamento diferente, normalmente e por um destes motivos:
- `GEMINI_MODEL` definido no ambiente com outro valor;
- falta de acesso ao modelo escolhido na chave da API;
- logs antigos de deploy misturados com logs novos.

Com a validacao de modelo no startup, o processo falha cedo quando o modelo nao estiver acessivel.

Se voce perceber comportamento diferente, normalmente e por um destes motivos:
- `GEMINI_MODEL` definido no ambiente com outro valor;
- falta de acesso ao modelo escolhido na chave da API;
- logs antigos de deploy misturados com logs novos.

Com a validacao de modelo no startup, o processo falha cedo quando o modelo nao estiver acessivel.

## Comandos

- `/start` - iniciar
- `/help` - ajuda
- `/reset` - apagar memoria da conversa

## Hospedagem

Você pode subir no GitHub e hospedar em:

- Render
- Railway
- Fly.io
- VPS
- Docker

Atenção: o GitHub não mantém o bot rodando sozinho. Ele só guarda o código.
