const express = require('express');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');

const app = express();
const PORT = process.env.PORT || 5000;

const BASE_DIR = __dirname;
const WEB_DIR = path.join(BASE_DIR, 'web');
const RAW_DIR = path.join(BASE_DIR, 'raw');
const PROCESSED_DIR = path.join(BASE_DIR, 'processed');

app.use(express.json({ limit: '1mb' }));
app.use(express.static(WEB_DIR));

function getPythonPath() {
  if (process.platform === 'win32') {
    // Prefer local venv on Windows only
    const venvPyWin = path.join(BASE_DIR, '.venv', 'Scripts', 'python.exe');
    if (fs.existsSync(venvPyWin)) return venvPyWin;
    return 'python';
  }
  // In Linux containers, prefer system python3
  const candidates = ['/usr/bin/python3', '/usr/local/bin/python3', 'python3', 'python'];
  for (const c of candidates) {
    try {
      if (c.startsWith('/')) {
        if (fs.existsSync(c)) return c;
      } else {
        return c; // let PATH resolve it
      }
    } catch (_) { /* ignore */ }
  }
  return 'python3';
}

app.get('/', (req, res) => {
  res.sendFile(path.join(WEB_DIR, 'index.html'));
});

app.post('/api/run', (req, res) => {
  const { item = 'baby chair', condition = '3', min_price = '0', max_price = '150', sort = '3', headless = false, delay = 15 } = req.body || {};

  const args = [
    path.join(BASE_DIR, 'scrape_cli.py'),
    '--item', String(item),
    '--condition', String(condition),
    '--min_price', String(min_price),
    '--max_price', String(max_price),
    '--sort', String(sort),
    '--delay', String(delay),
  ];
  if (headless) args.push('--headless');

  const py = spawn(getPythonPath(), args, { cwd: BASE_DIR, windowsHide: true });

  let out = '';
  let err = '';
  py.stdout.on('data', (d) => { out += d.toString(); });
  py.stderr.on('data', (d) => { err += d.toString(); });
  py.on('close', (code) => {
    // Try to parse last JSON object from stdout
    let jsonStr = out.trim();
    // In case there are logs before JSON, attempt to grab the last {...}
    const lastBrace = jsonStr.lastIndexOf('{');
    if (lastBrace > 0) jsonStr = jsonStr.slice(lastBrace);
    try {
      const data = JSON.parse(jsonStr);
      if (data.ok) {
        const csvName = path.basename(data.csv_path || '');
        const shotName = path.basename(data.screenshot_path || '');
        res.json({
          ok: true,
          query_url: data.query_url,
          count: data.count || 0,
          csv_name: csvName,
          screenshot_name: shotName,
          download_csv_url: csvName ? `/download/processed/${csvName}` : '',
          view_screenshot_url: shotName ? `/view/raw/${shotName}` : '',
        });
      } else {
        res.status(500).json({ ok: false, error: data.error || 'Unknown error from scraper' });
      }
    } catch (e) {
      res.status(500).json({ ok: false, error: `Failed to parse scraper output. code=${code}. stderr=${err.slice(-400)}` });
    }
  });
});

app.get('/download/processed/:filename', (req, res) => {
  const fp = path.join(PROCESSED_DIR, req.params.filename);
  res.download(fp);
});

app.get('/view/raw/:filename', (req, res) => {
  const fp = path.join(RAW_DIR, req.params.filename);
  res.sendFile(fp);
});

app.listen(PORT, () => {
  console.log(`Server running at http://127.0.0.1:${PORT}`);
});
