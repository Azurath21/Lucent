require('dotenv').config();
const express = require('express');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');

const app = express();
const PORT = process.env.PORT || 3000;

const BASE_DIR = __dirname;
const WEB_DIR = path.join(BASE_DIR, 'web');
const RAW_DIR = path.join(BASE_DIR, 'raw');
const PROCESSED_DIR = path.join(BASE_DIR, 'processed');

const progressStore = {};

app.use(express.json({ limit: '1mb' }));
app.use(express.static(WEB_DIR));

function getPythonPath() {
  if (process.platform === 'win32') {
    const venvPyWin = path.join(BASE_DIR, '.venv', 'Scripts', 'python.exe');
    if (fs.existsSync(venvPyWin)) return venvPyWin;
    return 'python';
  }
  const candidates = ['/usr/bin/python3', '/usr/local/bin/python3', 'python3', 'python'];
  for (const c of candidates) {
    try {
      if (c.startsWith('/')) {
        if (fs.existsSync(c)) return c;
      } else {
        return c;
      }
    } catch (_) { /* ignore */ }
  }
  return 'python3';
}

app.get('/', (req, res) => {
  res.sendFile(path.join(WEB_DIR, 'index.html'));
});

function runPythonJson(args, timeoutMs = 0) {
  return new Promise((resolve, reject) => {
    const pyPath = getPythonPath();
    const child = spawn(pyPath, args, { cwd: BASE_DIR, windowsHide: true });
    let out = '';
    let err = '';
    let isResolved = false;
    
    let timeout = null;
    if (timeoutMs > 0) {
      timeout = setTimeout(() => {
        if (!isResolved) {
          isResolved = true;
          child.kill('SIGTERM');
          reject(new Error(`Python process timed out after ${timeoutMs/1000} seconds`));
        }
      }, timeoutMs);
    }
    
    child.stdout.on('data', (d) => { out += d.toString(); });
    child.stderr.on('data', (d) => { err += d.toString(); });
    child.on('error', (e) => {
      if (!isResolved) {
        isResolved = true;
        if (timeout) clearTimeout(timeout);
        reject(new Error(`Failed to start Python: ${e.message}`));
      }
    });
    child.on('close', (code) => {
      if (isResolved) return;
      isResolved = true;
      if (timeout) clearTimeout(timeout);
      let jsonStr = (out || '').trim();
      
      console.log('DEBUG: Raw Python output:', out.slice(-500));
      
      const lastBrace = jsonStr.lastIndexOf('{');
      if (lastBrace >= 0) {
        const candidate = jsonStr.slice(lastBrace);
        try {
          JSON.parse(candidate);
          jsonStr = candidate;
          console.log('DEBUG: Using extracted JSON:', candidate);
        } catch (e) {
          console.log('DEBUG: JSON extraction failed, using full output');
          jsonStr = jsonStr;
        }
      }
      
      try {
        const data = JSON.parse(jsonStr || '{}');
        if (data && data.ok) return resolve(data);
        if (data && data.predicted_price !== undefined) return resolve(data);
        if (data && data.success !== undefined) return resolve(data);
        return reject(new Error(data && data.error ? data.error : `Python exited with code ${code}. stderr=${err.slice(-400)}. stdout=${out.slice(-200)}`));
      } catch (e) {
        console.log('DEBUG: JSON parsing failed, raw output:', out);
        console.log('DEBUG: Extracted jsonStr:', jsonStr);
        return reject(new Error(`Failed to parse JSON. code=${code}. stdout=${out.slice(-200)}. stderr=${err.slice(-400)}`));
      }
    });
  });
}

function runPython(args) {
  return new Promise((resolve, reject) => {
    const pyPath = getPythonPath();
    const child = spawn(pyPath, args, { cwd: BASE_DIR, windowsHide: true });
    let out = '';
    let err = '';
    child.stdout.on('data', (d) => { out += d.toString(); });
    child.stderr.on('data', (d) => { err += d.toString(); });
    child.on('error', (e) => reject(new Error(`Failed to start Python: ${e.message}`)));
    child.on('close', (code) => {
      if (code !== 0) {
        return reject(new Error(`Python exited with code ${code}. stderr=${err.slice(-400)}`));
      }
      resolve(out);
    });
  });
}

app.post('/api/start-run', async (req, res) => {
  const runId = `run_${Date.now()}`;
  progressStore[runId] = { status: 'starting', step: 0, total: 1, message: 'Starting scraper...' };
  res.json({ ok: true, run_id: runId });
});

app.post('/api/run', async (req, res) => {
  const { item, brand, model, notes, condition, min_price, target_days, speed_mode, weighting_method } = req.body;
  const runId = `run_${Date.now()}`;
  const scraperMode = 'carousell';
  
  try {

    if (!item) {
      return res.status(400).json({ ok: false, error: 'Item is required' });
    }

    const runDir = path.join(PROCESSED_DIR, runId);
    fs.mkdirSync(runDir, { recursive: true });

    let lastQueryUrl = '';
    let lastScreenshotName = '';
    const csvPaths = [];
    let combinedCsvPath = '';

    if (scraperMode === 'ebay') {
      progressStore[runId] = { status: 'scraping', step: 1, total: 1, message: 'Scraping eBay with interval method...' };

      const args = [
        '-m', 'ebay.ebay_cli',
        '--item', String(item),
        '--brand', String(brand || ''),
        '--model', String(model || ''),
        '--notes', String(notes || ''),
        '--condition', String(condition || '3'),
        '--min_price', String(min_price || '0'),
        '--mode', speed_mode || 'ultra_fast',
      ];
      
      const data = await runPythonJson(args);
      if (data.query_url) lastQueryUrl = data.query_url;
      if (data.csv_path) {
        const src = String(data.csv_path);
        const dest = path.join(runDir, path.basename(src));
        try {
          fs.renameSync(src, dest);
          csvPaths.push(dest);
        } catch (e) {
          csvPaths.push(src);
        }
      }
      
      combinedCsvPath = csvPaths[0] || '';
      
    } else if (scraperMode === 'facebook') {
      progressStore[runId] = { status: 'scraping', step: 1, total: 1, message: 'Scraping 1 of 1...' };

      const sortOptions = ['3', '4', '5', '6', '7'];
      let pagesToScrape;
      let totalPages;
      
      switch (speed_mode) {
        case 'ultra_fast':
          pagesToScrape = sortOptions.slice(0, 1);
          totalPages = 1;
          break;
        case 'fast':
          pagesToScrape = sortOptions.slice(0, 2);
          totalPages = 2;
          break;
        default:
          pagesToScrape = sortOptions;
          totalPages = 5;
      }
      
      progressStore[runId] = { status: 'scraping', step: 1, total: totalPages, message: `Scraping 1 of ${totalPages}...` };
      
      for (let i = 0; i < pagesToScrape.length; i++) {
        const sortValue = pagesToScrape[i];
        progressStore[runId] = { 
          status: 'scraping', 
          step: i + 1, 
          total: totalPages, 
          message: `Scraping ${i + 1} of ${totalPages}...` 
        };
        
        const args = [
          '-m', 'carousell.scrape_cli',
          '--item', String(item),
          '--brand', String(brand || ''),
          '--model', String(model || ''),
          '--notes', String(notes || ''),
          '--condition', String(condition || ''),
          '--min_price', String(min_price || ''),
          '--sort', sortValue,
        ];
        const data = await runPythonJson(args);
      if (data.query_url) lastQueryUrl = data.query_url;
      if (data.screenshot_path) lastScreenshotName = path.basename(data.screenshot_path);
      if (data.csv_path) {
        const src = String(data.csv_path);
        const dest = path.join(runDir, path.basename(src));
        try {
          fs.renameSync(src, dest);
          csvPaths.push(dest);
        } catch (e) {
          csvPaths.push(src);
        }
      }
    }

      let combinedName;
      
      if (speed_mode === 'ultra_fast' && csvPaths.length === 1) {
        combinedCsvPath = csvPaths[0];
        combinedName = path.basename(combinedCsvPath);
        progressStore[runId] = { 
          status: 'merging', 
          step: 1, 
          total: 1, 
          message: 'Using single CSV file (ultra fast mode)...' 
        };
      } else {
        progressStore[runId] = { 
          status: 'merging', 
          step: 1, 
          total: 1, 
          message: 'Merging CSV files...' 
        };
        
        const itemSlug = [String(item), String(brand), String(model), String(notes)].filter(Boolean).join(' ').trim() || 'items';
        const mergeArgs = [
          path.join(BASE_DIR, 'utils', 'merge_csvs.py'),
          runDir,
          itemSlug,
          ...csvPaths,
        ];
        const merged = await runPythonJson(mergeArgs);
        combinedCsvPath = merged.csv_path;
        combinedName = path.basename(combinedCsvPath || '');
      }
      
    } else {
      progressStore[runId] = { status: 'scraping', step: 0, total: 5, message: 'Starting scrape...' };

      const sortOptions = ['3', '4', '5', '6', '7'];
      let pagesToScrape;
      let totalPages;
      
      switch (speed_mode) {
        case 'ultra_fast':
          pagesToScrape = sortOptions.slice(0, 1);
          totalPages = 1;
          break;
        case 'fast':
          pagesToScrape = sortOptions.slice(0, 2);
          totalPages = 2;
          break;
        default:
          pagesToScrape = sortOptions;
          totalPages = 5;
      }
      
      progressStore[runId] = { status: 'scraping', step: 1, total: totalPages, message: `Scraping 1 of ${totalPages}...` };
      
      for (let i = 0; i < pagesToScrape.length; i++) {
        const sortValue = pagesToScrape[i];
        progressStore[runId] = { 
          status: 'scraping', 
          step: i + 1, 
          total: totalPages, 
          message: `Scraping ${i + 1} of ${totalPages}...` 
        };
        
        const args = [
          '-m', 'carousell.scrape_cli',
          '--item', String(item),
          '--brand', String(brand || ''),
          '--model', String(model || ''),
          '--notes', String(notes || ''),
        '--condition', String(condition || ''),
        '--min_price', String(min_price || ''),
        '--sort', sortValue,
      ];
      const data = await runPythonJson(args);
      if (data.query_url) lastQueryUrl = data.query_url;
      if (data.screenshot_path) lastScreenshotName = path.basename(data.screenshot_path);
      if (data.csv_path) {
        const src = String(data.csv_path);
        const dest = path.join(runDir, path.basename(src));
        try {
          fs.renameSync(src, dest);
          csvPaths.push(dest);
        } catch (e) {
          csvPaths.push(src);
        }
      }
    }

      let combinedName;
      
      if (speed_mode === 'ultra_fast' && csvPaths.length === 1) {
        combinedCsvPath = csvPaths[0];
        combinedName = path.basename(combinedCsvPath);
        progressStore[runId] = { 
          status: 'merging', 
          step: 1, 
          total: 1, 
          message: 'Using single CSV file (ultra fast mode)...' 
        };
      } else {
        progressStore[runId] = { 
          status: 'merging', 
          step: 1, 
          total: 1, 
          message: 'Merging CSV files...' 
        };
        
        const itemSlug = [String(item), String(brand), String(model), String(notes)].filter(Boolean).join(' ').trim() || 'items';
        const mergeArgs = [
          path.join(BASE_DIR, 'utils', 'merge_csvs.py'),
          runDir,
          itemSlug,
          ...csvPaths,
        ];
        const merged = await runPythonJson(mergeArgs);
        combinedCsvPath = merged.csv_path;
        combinedName = path.basename(combinedCsvPath || '');
      }
    }

    const queryText = [String(item), String(brand), String(model), String(notes)].filter(Boolean).join(' ').trim();
    let weightedResp;
    let weightedCsvPath;
    
    console.log(`DEBUG: weighting_method = "${weighting_method}" (type: ${typeof weighting_method})`);
    
    if (weighting_method === 'heuristic') {
      progressStore[runId] = { 
        status: 'weighting', 
        step: 1, 
        total: 1, 
        message: 'Applying heuristic weighting...' 
      };
      
      const heuristicArgs = [
        path.join(BASE_DIR, 'utils', 'heuristic_score.py'),
        combinedCsvPath,
        queryText,
      ];
      console.log('DEBUG: Running heuristic weighting with args:', heuristicArgs);
      weightedResp = await runPythonJson(heuristicArgs);
      console.log('DEBUG: Heuristic weighting response:', weightedResp);
      weightedCsvPath = weightedResp.csv_path;
    } else {
      progressStore[runId] = { 
        status: 'weighting', 
        step: 1, 
        total: 1, 
        message: 'Applying AI weighting (this may take a while)...' 
      };
      
      const weightArgs = [
        path.join(BASE_DIR, 'csv_score.py'),
        combinedCsvPath,
        runDir,
        queryText,
        '--batch-size=30',
      ];
      console.log('DEBUG: Running AI weighting with args:', weightArgs);
      weightedResp = await runPythonJson(weightArgs);
      console.log('DEBUG: AI weighting response:', weightedResp);
      weightedCsvPath = weightedResp.csv_path;
    }
    
    progressStore[runId] = { 
      status: 'predicting', 
      step: 1, 
      total: 1, 
      message: 'Running price prediction model...' 
    };
    
    const csvForPrediction = weightedCsvPath || combinedCsvPath;
    console.log('DEBUG: Using CSV for prediction:', csvForPrediction);
    
    if (!fs.existsSync(csvForPrediction)) {
      console.error('ERROR: CSV file not found for prediction:', csvForPrediction);
      return res.json({
        ok: false,
        error: 'CSV file not found for price prediction. The weighting process may have failed.'
      });
    }
    
    const price_predictor = req.body.price_predictor || 'simple';
    const predictorScript = price_predictor === 'advanced' 
      ? 'price_predictor.py' 
      : 'simple_price_predictor.py';
    
    const predictionArgs = [
      path.join(BASE_DIR, 'utils', predictorScript),
      csvForPrediction,
      String(target_days),
    ];
    console.log('DEBUG: Using price predictor:', price_predictor, 'Script:', predictorScript);
    console.log('DEBUG: Running prediction with args:', predictionArgs);
    const prediction = await runPythonJson(predictionArgs);
    console.log('DEBUG: Prediction result:', prediction);

    delete progressStore[runId];

    try {
      const rawFiles = fs.readdirSync(RAW_DIR);
      for (const file of rawFiles) {
        if (file.endsWith('.html')) {
          try {
            fs.unlinkSync(path.join(RAW_DIR, file));
          } catch (e) {
          }
        }
      }
      
      const processedDirs = fs.readdirSync(PROCESSED_DIR);
      for (const dir of processedDirs) {
        if (dir.startsWith('run_')) {
          try {
            fs.rmSync(path.join(PROCESSED_DIR, dir), { recursive: true, force: true });
          } catch (e) {
          }
        }
      }
    } catch (e) {
      console.log('Cleanup warning:', e.message);
    }

    if (!prediction || !prediction.predicted_price || prediction.data_points === 0 || prediction.data_points === "0") {
      console.log('DEBUG: Invalid prediction data:', prediction);
      return res.json({
        ok: false,
        error: 'No data available for price prediction. Try adjusting your search criteria or check back later when more listings are available.'
      });
    }

    return res.json({
      ok: true,
      predicted_price: prediction.predicted_price,
      target_days: prediction.target_days,
      data_points: prediction.data_points,
      model_accuracy_mae: prediction.model_accuracy_mae,
      price_stats: prediction.price_stats,
      time_stats: prediction.time_stats,
      run_id: runId,
    });
  } catch (e) {
    delete progressStore[runId];
    
    try {
      const rawFiles = fs.readdirSync(RAW_DIR);
      for (const file of rawFiles) {
        if (file.endsWith('.html')) {
          try {
            fs.unlinkSync(path.join(RAW_DIR, file));
          } catch (cleanupErr) {
          }
        }
      }
      
      const processedDirs = fs.readdirSync(PROCESSED_DIR);
      for (const dir of processedDirs) {
        if (dir.startsWith('run_')) {
          try {
            fs.rmSync(path.join(PROCESSED_DIR, dir), { recursive: true, force: true });
          } catch (cleanupErr) {
          }
        }
      }
    } catch (cleanupErr) {
      console.log('Error cleanup warning:', cleanupErr.message);
    }
    
    return res.status(500).json({ ok: false, error: e.message || String(e) });
  }
});

app.get('/api/progress/:runId', (req, res) => {
  const { runId } = req.params;
  const progress = progressStore[runId];
  if (!progress) {
    return res.json({ status: 'completed', message: 'Process completed' });
  }
  res.json(progress);
});

app.get('/download/processed/:filename', (req, res) => {
  const fp = path.join(PROCESSED_DIR, req.params.filename);
  res.download(fp);
});

app.get('/download/processed/run/:runId/:filename', (req, res) => {
  const { runId, filename } = req.params;
  const fp = path.join(PROCESSED_DIR, runId, filename);
  res.download(fp);
});

app.get('/view/raw/:filename', (req, res) => {
  const fp = path.join(RAW_DIR, req.params.filename);
  res.sendFile(fp);
});

app.listen(PORT, () => {
  console.log(`Server running at http://127.0.0.1:${PORT}`);
});
