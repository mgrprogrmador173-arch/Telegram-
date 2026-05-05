const fs = require('fs');
const path = require('path');
const qrcode = require('qrcode-terminal');
const QRCode = require('qrcode');
const { Client, LocalAuth } = require('whatsapp-web.js');
const { GoogleGenAI } = require('@google/genai');

const GEMINI_API_KEY = process.env.GEMINI_API_KEY;
const GOOGLE_AI_MODEL = process.env.GOOGLE_AI_MODEL || 'gemini-2.5-flash-lite';
const QR_DIR = process.env.QR_DIR || 'qr-code';
const WHATSAPP_PAIRING_NUMBER_RAW = process.env.WHATSAPP_PAIRING_NUMBER || '';
const WHATSAPP_PAIRING_NUMBER = WHATSAPP_PAIRING_NUMBER_RAW.replace(/\D/g, '');
const PAIRING_MAX_ATTEMPTS = Number(process.env.PAIRING_MAX_ATTEMPTS || 5);
const PAIRING_RETRY_SECONDS = Number(process.env.PAIRING_RETRY_SECONDS || 30);

if (!GEMINI_API_KEY) {
  throw new Error('GEMINI_API_KEY nao encontrada nos Secrets.');
}

fs.mkdirSync(QR_DIR, { recursive: true });

const ai = new GoogleGenAI({ apiKey: GEMINI_API_KEY });
const memory = new Map();
let pairingStarted = false;
let isReady = false;
let lastQr = null;
let qrCounter = 0;

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

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

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

async function salvarQr(qr) {
  qrCounter += 1;
  const numero = String(qrCounter).padStart(3, '0');

  console.log(`Novo QR Code recebido: ${numero}`);
  qrcode.generate(qr, { small: true });

  const pngPath = path.join(QR_DIR, `qr-${numero}.png`);
  const txtPath = path.join(QR_DIR, `qr-${numero}.txt`);
  const latestPngPath = path.join(QR_DIR, 'qr-latest.png');
  const latestTxtPath = path.join(QR_DIR, 'qr-latest.txt');

  await QRCode.toFile(pngPath, qr, { type: 'png', margin: 2, width: 900 });
  await QRCode.toFile(latestPngPath, qr, { type: 'png', margin: 2, width: 900 });

  fs.writeFileSync(txtPath, qr, 'utf8');
  fs.writeFileSync(latestTxtPath, qr, 'utf8');

  console.log('QR Code salvo em PNG:');
  console.log(pngPath);
  console.log('Ultimo QR atualizado em:');
  console.log(latestPngPath);
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

async function gerarCodigosPorNumero() {
  if (!WHATSAPP_PAIRING_NUMBER || pairingStarted) return;
  pairingStarted = true;

  console.log(`Modo codigo por telefone ativo. Numero terminado em ${WHATSAPP_PAIRING_NUMBER.slice(-4)}.`);
  console.log(`Vou tentar gerar ate ${PAIRING_MAX_ATTEMPTS} codigos, com intervalo de ${PAIRING_RETRY_SECONDS}s.`);

  for (let attempt = 1; attempt <= PAIRING_MAX_ATTEMPTS; attempt++) {
    if (isReady) return;

    try {
      console.log('============================================================');
      console.log(`TENTATIVA ${attempt}/${PAIRING_MAX_ATTEMPTS} - GERANDO CODIGO...`);
      const code = await client.requestPairingCode(WHATSAPP_PAIRING_NUMBER);
      const codePath = path.join(QR_DIR, `pairing-code-${attempt}.txt`);
      fs.writeFileSync(codePath, code, 'utf8');
      fs.writeFileSync(path.join(QR_DIR, 'pairing-code-latest.txt'), code, 'utf8');
      console.log('CODIGO PARA CONECTAR COM NUMERO:');
      console.log(code);
      console.log('Use imediatamente no WhatsApp:');
      console.log('Aparelhos conectados > Conectar aparelho > Conectar com numero de telefone');
      console.log('============================================================');
    } catch (error) {
      console.error(`Tentativa ${attempt} falhou ao gerar codigo.`);
      console.error(error && error.message ? error.message : error);
    }

    if (attempt < PAIRING_MAX_ATTEMPTS) {
      console.log(`Aguardando ${PAIRING_RETRY_SECONDS}s antes de tentar novo codigo...`);
      await sleep(PAIRING_RETRY_SECONDS * 1000);
    }
  }

  console.log('Acabaram as tentativas de codigo por telefone.');
  if (lastQr) {
    console.log('Como alternativa, vou salvar o QR Code em PNG.');
    await salvarQr(lastQr);
  }
}

client.on('qr', async (qr) => {
  lastQr = qr;

  if (WHATSAPP_PAIRING_NUMBER) {
    await gerarCodigosPorNumero();
    return;
  }

  await salvarQr(qr);
});

client.on('ready', () => {
  isReady = true;
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
