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

// Progress tracking store
const progressStore = {};

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
function runPythonJson(args, timeoutMs = 120000) { // 2 minute default timeout
  return new Promise((resolve, reject) => {
    const pyPath = getPythonPath();
    const child = spawn(pyPath, args, { cwd: BASE_DIR, windowsHide: true });
    let out = '';
    let err = '';
    let isResolved = false;
    
    // Set up timeout only if timeoutMs > 0
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
      
      // Try to find the last complete JSON object
      const lastBrace = jsonStr.lastIndexOf('{');
      if (lastBrace >= 0) {
        // Extract from the last opening brace to the end
        const candidate = jsonStr.slice(lastBrace);
        try {
          // Test if this is valid JSON
          JSON.parse(candidate);
          jsonStr = candidate;
        } catch (e) {
          // If extraction failed, use the full output
          jsonStr = jsonStr;
        }
      }
      
      try {
        const data = JSON.parse(jsonStr || '{}');
        if (data && data.ok) return resolve(data);
        // For simple_price_predictor.py, accept any valid JSON (no "ok" field required)
        if (data && data.predicted_price !== undefined) return resolve(data);
        return reject(new Error(data && data.error ? data.error : `Python exited with code ${code}. stderr=${err.slice(-400)}. stdout=${out.slice(-200)}`));
      } catch (e) {
        return reject(new Error(`Failed to parse JSON. code=${code}. stdout=${out.slice(-200)}. stderr=${err.slice(-400)}`));
      }
    });
  });
}

// Helper: run a Python process and return raw stdout (for Facebook scraper)
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

// Start run endpoint - returns run ID immediately
app.post('/api/start-run', async (req, res) => {
  const runId = `run_${Date.now()}`;
  progressStore[runId] = { status: 'starting', step: 0, total: 5, message: 'Initializing...' };
  res.json({ ok: true, run_id: runId });
});

// Main processing endpoint
app.post('/api/run', async (req, res) => {
  const { item, brand, model, notes, condition, min_price, max_price, location, days_since_listed, target_days, speed_mode, use_gemini, run_id, scraper } = req.body;
  const runId = run_id || `run_${Date.now()}`;
  const scraperMode = scraper || 'carousell'; // Default to carousell
  
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

    if (scraperMode === 'facebook' || scraperMode === 'ebay') {
      // Route Facebook UI to Carousell scraper instead
      progressStore[runId] = { status: 'scraping', step: 0, total: 5, message: 'Starting scrape...' };

      // Determine number of pages based on speed mode (same as Carousell)
      const sortOptions = ['3', '4', '5', '6', '7']; // Different sort metrics
      let pagesToScrape;
      let totalPages;
      
      switch (speed_mode) {
        case 'ultra_fast':
          pagesToScrape = sortOptions.slice(0, 1); // Only first sort method
          totalPages = 1;
          break;
        case 'fast':
          pagesToScrape = sortOptions.slice(0, 2); // First 2 sort methods
          totalPages = 2;
          break;
        default: // 'normal'
          pagesToScrape = sortOptions; // All 5 sort methods
          totalPages = 5;
      }
      
      // Update progress store with correct total
      progressStore[runId] = { status: 'scraping', step: 0, total: totalPages, message: 'Starting scrape...' };
      
      // Scrape with selected sort metrics (same as Carousell)
      for (let i = 0; i < pagesToScrape.length; i++) {
        const sortValue = pagesToScrape[i];
        progressStore[runId] = { 
          status: 'scraping', 
          step: i + 1, 
          total: totalPages, 
          message: `Scraping with sort method ${i + 1} of ${totalPages}...` 
        };
        
        const args = [
          path.join(BASE_DIR, 'carousell', 'scrape_cli.py'),
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
          // If move fails, fallback to using original path
          csvPaths.push(src);
        }
      }
    }

      // Handle CSV combining (same as Carousell)
      let combinedName;
      
      if (speed_mode === 'ultra_fast' && csvPaths.length === 1) {
        // Ultra fast: Skip merging, use single CSV directly
        combinedCsvPath = csvPaths[0];
        combinedName = path.basename(combinedCsvPath);
        progressStore[runId] = { 
          status: 'merging', 
          step: 1, 
          total: 1, 
          message: 'Using single CSV file (ultra fast mode)...' 
        };
      } else {
        // Normal/Fast: Merge multiple CSVs
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
      // Original Carousell scraper mode
      // Store progress for this run
      progressStore[runId] = { status: 'scraping', step: 0, total: 5, message: 'Starting scrape...' };

      // Determine number of pages based on speed mode
      const sortOptions = ['3', '4', '5', '6', '7']; // Different sort metrics
      let pagesToScrape;
      let totalPages;
      
      switch (speed_mode) {
        case 'ultra_fast':
          pagesToScrape = sortOptions.slice(0, 1); // Only first sort method
          totalPages = 1;
          break;
        case 'fast':
          pagesToScrape = sortOptions.slice(0, 2); // First 2 sort methods
          totalPages = 2;
          break;
        default: // 'normal'
          pagesToScrape = sortOptions; // All 5 sort methods
          totalPages = 5;
      }
      
      // Update progress store with correct total
      progressStore[runId] = { status: 'scraping', step: 0, total: totalPages, message: 'Starting scrape...' };
      
      // Scrape with selected sort metrics
      for (let i = 0; i < pagesToScrape.length; i++) {
        const sortValue = pagesToScrape[i];
        progressStore[runId] = { 
          status: 'scraping', 
          step: i + 1, 
          total: totalPages, 
          message: `Scraping with sort method ${i + 1} of ${totalPages}...` 
        };
        
        const args = [
          path.join(BASE_DIR, 'carousell', 'scrape_cli.py'),
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
          // If move fails, fallback to using original path
          csvPaths.push(src);
        }
      }
    }

      // Handle CSV combining based on speed mode for Carousell
      let combinedName;
      
      if (speed_mode === 'ultra_fast' && csvPaths.length === 1) {
        // Ultra fast: Skip merging, use single CSV directly
        combinedCsvPath = csvPaths[0];
        combinedName = path.basename(combinedCsvPath);
        progressStore[runId] = { 
          status: 'merging', 
          step: 1, 
          total: 1, 
          message: 'Using single CSV file (ultra fast mode)...' 
        };
      } else {
        // Normal/Fast: Merge multiple CSVs
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

    // Always run Gemini scoring for price prediction
    progressStore[runId] = { 
      status: 'scoring', 
      step: 0, 
      total: 1, 
      message: 'Starting AI relevance scoring...' 
    };
    
    const queryText = [String(item), String(brand), String(model), String(notes)].filter(Boolean).join(' ').trim();
    const key = String(process.env.GOOGLE_API_KEY || '');
    if (!key) {
      throw new Error('GOOGLE_API_KEY is required for price prediction.');
    }
    
    // Score the CSV with extended timeout for AI processing
    const weightArgs = [
      path.join(BASE_DIR, 'csv_score.py'),
      combinedCsvPath,
      runDir,
      queryText,
      '--batch-size=30',
    ];
    const weightedResp = await runPythonJson(weightArgs, 0); // No timeout - let AI weighting complete fully
    const weightedCsvPath = weightedResp.csv_path;
    
    // Run price prediction
    progressStore[runId] = { 
      status: 'predicting', 
      step: 1, 
      total: 1, 
      message: 'Running price prediction model...' 
    };
    
    const predictionArgs = [
      path.join(BASE_DIR, 'utils', 'simple_price_predictor.py'),
      combinedCsvPath,
      String(target_days),
    ];
    const prediction = await runPythonJson(predictionArgs);

    // Clear progress when done
    delete progressStore[runId];

    // Cleanup: Delete ALL raw and processed files after successful prediction
    try {
      // Delete all raw HTML files
      const rawFiles = fs.readdirSync(RAW_DIR);
      for (const file of rawFiles) {
        if (file.endsWith('.html')) {
          try {
            fs.unlinkSync(path.join(RAW_DIR, file));
          } catch (e) {
            // Ignore cleanup errors
          }
        }
      }
      
      // Delete all processed run directories
      const processedDirs = fs.readdirSync(PROCESSED_DIR);
      for (const dir of processedDirs) {
        if (dir.startsWith('run_')) {
          try {
            fs.rmSync(path.join(PROCESSED_DIR, dir), { recursive: true, force: true });
          } catch (e) {
            // Ignore cleanup errors
          }
        }
      }
    } catch (e) {
      // Ignore cleanup errors - don't fail the response
      console.log('Cleanup warning:', e.message);
    }

    // Check if prediction has valid data
    if (!prediction.predicted_price || prediction.data_points === 0 || prediction.data_points === "0") {
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
      model_accuracy: prediction.model_accuracy_mae,
      price_stats: prediction.price_stats,
      time_stats: prediction.time_stats,
      run_id: runId,
    });
  } catch (e) {
    // Clear progress when done
    delete progressStore[runId];
    
    // Cleanup ALL files even on error
    try {
      // Delete all raw HTML files
      const rawFiles = fs.readdirSync(RAW_DIR);
      for (const file of rawFiles) {
        if (file.endsWith('.html')) {
          try {
            fs.unlinkSync(path.join(RAW_DIR, file));
          } catch (cleanupErr) {
            // Ignore cleanup errors
          }
        }
      }
      
      // Delete all processed run directories
      const processedDirs = fs.readdirSync(PROCESSED_DIR);
      for (const dir of processedDirs) {
        if (dir.startsWith('run_')) {
          try {
            fs.rmSync(path.join(PROCESSED_DIR, dir), { recursive: true, force: true });
          } catch (cleanupErr) {
            // Ignore cleanup errors
          }
        }
      }
    } catch (cleanupErr) {
      // Ignore cleanup errors
      console.log('Error cleanup warning:', cleanupErr.message);
    }
    
    return res.status(500).json({ ok: false, error: e.message || String(e) });
  }
});

// Progress endpoint
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

// New: nested route for per-run outputs
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
