const qrcode = require('qrcode-terminal');
const { Client, LocalAuth } = require('whatsapp-web.js');
const { GoogleGenAI } = require('@google/genai');

const GEMINI_API_KEY = process.env.GEMINI_API_KEY;
const GOOGLE_AI_MODEL = process.env.GOOGLE_AI_MODEL || 'gemini-2.5-flash-lite';

if (!GEMINI_API_KEY) {
  throw new Error('GEMINI_API_KEY nao encontrada nos Secrets.');
}

const ai = new GoogleGenAI({ apiKey: GEMINI_API_KEY });
const memory = new Map();

const SYSTEM_PROMPT = `
Voce e o atendente virtual da MGR Design Studio.

A MGR oferece design grafico, logomarca, marketing digital, artes para redes sociais e videos de anuncio.

Valores:
- Logomarca: R$ 30,00.
- Marketing digital: R$ 30,00, com ate 2 variacoes.
- Video de anuncio: R$ 60,00, com ate 2 variacoes.
- Pacote completo com video + logomarca + propaganda normal: R$ 90,00.

Regras:
- Responda em portugues brasileiro.
- Seja simpatico, profissional e direto.
- Respostas curtas, no maximo 3 frases.
- Nao diga que e IA.
- Nao invente valores.
- Ajude o cliente a escolher o melhor pacote.
- Negocie sem desvalorizar o servico.
- Se faltar informacao, pergunte apenas uma ou duas coisas por vez.
`;

function addMemory(userId, line) {
  if (!memory.has(userId)) memory.set(userId, []);
  const hist = memory.get(userId);
  hist.push(line);
  if (hist.length > 10) hist.shift();
}

async function gerarResposta(userId, texto) {
  addMemory(userId, `Cliente: ${texto}`);
  const historico = memory.get(userId).join('\n');
  const prompt = `${SYSTEM_PROMPT}\n\nHistorico:\n${historico}\n\nResponda como atendente da MGR Design Studio.`;

  const response = await ai.models.generateContent({
    model: GOOGLE_AI_MODEL,
    contents: prompt,
  });

  const resposta = (response.text || 'Certo. Me passa mais detalhes para eu te ajudar melhor.').trim();
  addMemory(userId, `MGR: ${resposta}`);
  return resposta;
}

const client = new Client({
  authStrategy: new LocalAuth({ clientId: 'mgr-whatsapp-webjs' }),
  puppeteer: {
    headless: true,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-gpu',
    ],
  },
});

client.on('qr', (qr) => {
  console.log('Escaneie este QR Code com o WhatsApp:');
  qrcode.generate(qr, { small: true });
});

client.on('ready', () => {
  console.log('MGR WhatsApp Web JS Bot conectado e rodando.');
});

client.on('message', async (msg) => {
  try {
    const texto = (msg.body || '').trim();

    if (!texto) {
      await msg.reply('Por enquanto, me mande sua mensagem em texto para eu te atender melhor.');
      return;
    }

    if (texto.toLowerCase() === '/reset') {
      memory.delete(msg.from);
      await msg.reply('Memoria apagada. Qual servico voce precisa?');
      return;
    }

    const resposta = await gerarResposta(msg.from, texto);
    await msg.reply(resposta);
  } catch (error) {
    console.error('Erro ao responder:', error);
    await msg.reply('Tive um problema para responder agora. Tente novamente em instantes.');
  }
});

client.initialize();
