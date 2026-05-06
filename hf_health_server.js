const http = require('http');

const port = process.env.PORT || 7860;

const server = http.createServer((req, res) => {
  res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
  res.end(`
    <!doctype html>
    <html lang="pt-BR">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>MGR WhatsApp Bot</title>
        <style>
          body { font-family: Arial, sans-serif; padding: 32px; max-width: 720px; margin: auto; }
          code { background: #eee; padding: 2px 6px; border-radius: 4px; }
        </style>
      </head>
      <body>
        <h1>MGR WhatsApp Bot</h1>
        <p>Servidor ativo.</p>
        <p>O bot roda em segundo plano dentro do Space.</p>
        <p>Se precisar fazer login, veja os logs do Space ou o arquivo <code>qr-code/qr-latest.png</code>.</p>
      </body>
    </html>
  `);
});

server.listen(port, '0.0.0.0', () => {
  console.log(`Health server rodando na porta ${port}`);
});
