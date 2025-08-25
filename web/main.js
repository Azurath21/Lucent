const form = document.getElementById('scrape-form');
const resultBox = document.getElementById('result');
const errorBox = document.getElementById('error');
const loading = document.getElementById('loading');
const linkQuery = document.getElementById('query_url');
const countSpan = document.getElementById('count');
const downloadLink = document.getElementById('download_csv');
const screenshotImg = document.getElementById('screenshot');

function show(el) { el.classList.remove('hidden'); }
function hide(el) { el.classList.add('hidden'); }

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  hide(resultBox);
  hide(errorBox);
  show(loading);

  const item = document.getElementById('item').value.trim();
  const brand = document.getElementById('brand').value.trim();
  const model = document.getElementById('model').value.trim();
  const notes = document.getElementById('notes').value.trim();
  const condition = document.getElementById('condition').value.trim();
  const min_price = document.getElementById('min_price').value.trim();
  const target_days = document.getElementById('target_days').value.trim();
  const use_gemini = true; // Always use Gemini for price prediction

  let progressInterval = null;
  const loadingText = document.querySelector('#loading .loading-text');

  try {
    // First, get a run ID
    const startResp = await fetch('/api/start-run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
    const startData = await startResp.json();
    if (!startData.ok) throw new Error(startData.error || 'Failed to start');
    
    const runId = startData.run_id;
    
    // Start polling for progress updates
    progressInterval = setInterval(async () => {
      try {
        const progressResp = await fetch(`/api/progress/${runId}`);
        const progress = await progressResp.json();
        
        if (progress.status === 'completed') {
          clearInterval(progressInterval);
          return;
        }
        
        // Update loading message
        if (loadingText) {
          loadingText.textContent = progress.message || 'Processing...';
        }
      } catch (e) {
        // Ignore progress polling errors
      }
    }, 500);

    // Now start the main processing
    const resp = await fetch('/api/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ item, brand, model, notes, condition, min_price, target_days, use_gemini, run_id: runId }),
    });
    const data = await resp.json();
    if (!data.ok) throw new Error(data.error || 'Unknown error');

    // Update prediction display
    document.getElementById('predicted_price').textContent = `S$${data.predicted_price}`;
    document.getElementById('target_timeframe').textContent = `${data.target_days} days`;
    document.getElementById('data_points').textContent = data.data_points;
    document.getElementById('model_accuracy').textContent = data.model_accuracy === "N/A" ? "N/A" : `±S$${data.model_accuracy}`;

    show(resultBox);
  } catch (err) {
    errorBox.textContent = err.message || String(err);
    show(errorBox);
  }
  
  if (progressInterval) clearInterval(progressInterval);
  hide(loading);
});
