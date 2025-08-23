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
  // In Linux containers, force system python3 path to avoid Windows venv remnants
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

// Helper: run a Python process and parse JSON from stdout (last JSON object)
function runPythonJson(args) {
  return new Promise((resolve, reject) => {
    const pyPath = getPythonPath();
    const child = spawn(pyPath, args, { cwd: BASE_DIR, windowsHide: true });
    let out = '';
    let err = '';
    child.stdout.on('data', (d) => { out += d.toString(); });
    child.stderr.on('data', (d) => { err += d.toString(); });
    child.on('error', (e) => reject(new Error(`Failed to start Python: ${e.message}`)));
    child.on('close', (code) => {
      let jsonStr = (out || '').trim();
      const lastBrace = jsonStr.lastIndexOf('{');
      if (lastBrace > 0) jsonStr = jsonStr.slice(lastBrace);
      try {
        const data = JSON.parse(jsonStr || '{}');
        if (data && data.ok) return resolve(data);
        return reject(new Error(data && data.error ? data.error : `Python exited with code ${code}. stderr=${err.slice(-400)}`));
      } catch (e) {
        return reject(new Error(`Failed to parse JSON. code=${code}. stderr=${err.slice(-400)}`));
      }
    });
  });
}

app.post('/api/run', async (req, res) => {
  try {
    const { item = 'baby chair', brand = '', model = '', notes = '', condition = '3', min_price = '0', headless = false, delay = 15 } = req.body || {};
    // All sort options to iterate: Best(1), Recent(3), High->Low(5), Low->High(4), Nearby(6)
    const sorts = ['1', '3', '5', '4', '6'];

    // Ensure processed dir exists
    try { fs.mkdirSync(PROCESSED_DIR, { recursive: true }); } catch (_) {}

    const csvPaths = [];
    let lastQueryUrl = '';
    let lastScreenshotName = '';

    for (const sort of sorts) {
      const args = [
        path.join(BASE_DIR, 'scrape_cli.py'),
        '--item', String(item),
        '--condition', String(condition),
        '--min_price', String(min_price),
        '--sort', String(sort),
        '--delay', String(delay),
      ];
      if (String(brand).trim()) args.push('--brand', String(brand));
      if (String(model).trim()) args.push('--model', String(model));
      if (String(notes).trim()) args.push('--notes', String(notes));
      if (headless) args.push('--headless');

      const data = await runPythonJson(args);
      if (data.query_url) lastQueryUrl = data.query_url;
      if (data.screenshot_path) lastScreenshotName = path.basename(data.screenshot_path);
      if (data.csv_path) csvPaths.push(String(data.csv_path));
    }

    // Merge CSVs via merge_csvs.py
    const itemSlug = [String(item), String(brand), String(model), String(notes)].filter(Boolean).join(' ').trim() || 'items';
    const mergeArgs = [
      path.join(BASE_DIR, 'merge_csvs.py'),
      PROCESSED_DIR,
      itemSlug,
      ...csvPaths,
    ];
    const merged = await runPythonJson(mergeArgs);
    const combinedName = path.basename(merged.csv_path || '');

    return res.json({
      ok: true,
      query_url: lastQueryUrl,
      count: merged.count || 0,
      csv_name: combinedName,
      screenshot_name: lastScreenshotName,
      download_csv_url: combinedName ? `/download/processed/${combinedName}` : '',
      view_screenshot_url: lastScreenshotName ? `/view/raw/${lastScreenshotName}` : '',
    });
  } catch (e) {
    return res.status(500).json({ ok: false, error: e.message || String(e) });
  }
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
