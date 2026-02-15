// agent-gateway.js
const express = require('express');
const bodyParser = require('body-parser');
const fs = require('fs');
const { spawn } = require('child_process'); // Для вызова Python скрипта [3, 4]

const PQC_PRIVATE_KEY_HEX = process.env.PQC_PRIVATE_KEY_HEX;
if (!PQC_PRIVATE_KEY_HEX) {
  console.error('Error: PQC_PRIVATE_KEY_HEX environment variable is not set. PQC signing will not work.');
  process.exit(1);
}
const LOG_PATH = './logs/agent_journal.json'; // Изменен путь на относительный
if (!fs.existsSync('./logs')) fs.mkdirSync('./logs'); // Создать директорию logs, если ее нет
if (!fs.existsSync(LOG_PATH)) fs.writeFileSync(LOG_PATH, '[]'); // Инициализировать как пустой массив JSON

const app = express();
app.use(bodyParser.json());

app.post('/agent', async (req, res) => {
  const { tool, role, payload } = req.body;
  const identity = `${role}_x0tta6bl4`;
  
  // Вызов Python скрипта для PQC подписи [3, 4]
  const signProcess = spawn('python3', ['pqc_signer.py', 'sign', '--data', payload, '--private-key', PQC_PRIVATE_KEY_HEX]);
  let signature_output = '';
  let error_output = '';
  signProcess.stdout.on('data', (data) => {
    signature_output += data.toString();
  });
  signProcess.stderr.on('data', (data) => {
    error_output += data.toString();
    console.error(`stderr from pqc_signer.py: ${data}`);
  });
  await new Promise((resolve) => {
    signProcess.on('close', (code) => {
      if (code!== 0) {
        console.error(`pqc_signer.py exited with code ${code}. Error: ${error_output}`);
      }
      resolve();
    });
  });

  const signature = signature_output.trim(); // Предполагается, что скрипт возвращает подпись напрямую

  const entry = {
    timestamp: new Date().toISOString(),
    tool, role, identity, payload, signature // Включить подпись в лог
  };
  let log = [];
  try {
    const logContent = fs.readFileSync(LOG_PATH);
    if (logContent.length > 0) {
      log = JSON.parse(logContent);
    }
  } catch (parseError) {
    console.error(`Error parsing agent_journal.json: ${parseError}`);
    // Если файл поврежден, начнем с чистого листа
    log = [];
  }

  log.push(entry);
  fs.writeFileSync(LOG_PATH, JSON.stringify(log, null, 2));
  res.json({ payload: payload, signature: signature }); // Вернуть PQC подпись
});

app.listen(4000, '0.0.0.0', () => {
  console.log('Agent Gateway listening on http://0.0.0.0:4000');
});
