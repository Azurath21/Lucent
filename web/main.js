const form = document.getElementById('scrape-form');
const resultBox = document.getElementById('result');
const errorBox = document.getElementById('error');
const loading = document.getElementById('loading');
const steps = document.querySelectorAll('.progress .step');
const pages = document.querySelectorAll('.page');
const titlescreen = document.getElementById('titlescreen');

let currentPage = 0;

// Titlescreen fade out after 2 seconds
window.addEventListener('load', () => {
  setTimeout(() => {
    titlescreen.classList.add('fade-out');
    setTimeout(() => {
      titlescreen.style.display = 'none';
    }, 500); // Wait for fade transition to complete
  }, 2000);
});

function show(el) { el.classList.remove('hidden'); }
function hide(el) { el.classList.add('hidden'); }

function setActiveStep(index) {
  steps.forEach((step, i) => {
    step.classList.toggle('active', i <= index);
  });
}

function showPage(pageIndex) {
  pages.forEach((page, i) => {
    page.classList.toggle('active', i === pageIndex);
  });
  setActiveStep(pageIndex);
  currentPage = pageIndex;
}

// Navigation event listeners
document.getElementById('next-0').addEventListener('click', () => showPage(1));
document.getElementById('prev-1').addEventListener('click', () => showPage(0));
document.getElementById('next-1').addEventListener('click', () => showPage(2));
document.getElementById('prev-2').addEventListener('click', () => showPage(1));

// Progress indicator click navigation
steps.forEach((step, index) => {
  step.addEventListener('click', () => showPage(index));
});

// Speed selection handling
const speedOptions = document.querySelectorAll('.speed-option');
const speedModeInput = document.getElementById('speed_mode');

speedOptions.forEach(option => {
  option.addEventListener('click', () => {
    // Remove selected class from all options
    speedOptions.forEach(opt => opt.classList.remove('selected'));
    // Add selected class to clicked option
    option.classList.add('selected');
    // Update hidden input value
    speedModeInput.value = option.dataset.speed;
  });
});

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  hide(resultBox);
  hide(errorBox);

  const item = document.getElementById('item').value.trim();
  const brand = document.getElementById('brand').value.trim();
  const model = document.getElementById('model').value.trim();
  const notes = document.getElementById('notes').value.trim();
  const condition = document.getElementById('condition').value.trim();
  const min_price = document.getElementById('min_price').value.trim();
  const target_days = document.getElementById('target_days').value.trim();
  const speed_mode = document.getElementById('speed_mode').value.trim();
  const use_gemini = true; // Always use Gemini for price prediction

  // Custom validation with specific error messages
  const missingFields = [];
  if (!item) missingFields.push('Item name');
  if (!target_days) missingFields.push('Target days to sell');
  if (!speed_mode) missingFields.push('Scraping speed mode');

  if (missingFields.length > 0) {
    const errorMsg = `Please fill in the following required fields: ${missingFields.join(', ')}`;
    errorBox.textContent = errorMsg;
    show(errorBox);
    return;
  }

  show(loading);

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
      body: JSON.stringify({ item, brand, model, notes, condition, min_price, target_days, speed_mode, use_gemini, run_id: runId }),
    });
    const data = await resp.json();
    if (!data.ok) throw new Error(data.error || 'Unknown error');

    // Check if we have valid prediction data
    if (!data.predicted_price || data.data_points === 0 || data.data_points === "0") {
      throw new Error('No data available for price prediction. Try adjusting your search criteria or check back later when more listings are available.');
    }

    // Update prediction display
    document.getElementById('predicted_price').textContent = `S$${data.predicted_price}`;
    document.getElementById('target_timeframe').textContent = `${data.target_days} days`;
    document.getElementById('data_points').textContent = data.data_points;
    document.getElementById('model_accuracy').textContent = data.model_accuracy === "N/A" ? "N/A" : `±S$${data.model_accuracy}`;

    show(resultBox);
    // Fill all steps when result is ready
    setActiveStep(steps.length - 1);
  } catch (err) {
    // Handle different types of errors
    let errorMessage = err.message || String(err);
    
    // Check for network or server errors
    if (err.name === 'TypeError' && err.message.includes('fetch')) {
      errorMessage = 'Network error. Please check your connection and try again.';
    } else if (errorMessage.includes('500') || errorMessage.includes('Internal Server Error')) {
      errorMessage = 'Server error occurred. Please try again in a few moments.';
    }
    
    errorBox.textContent = errorMessage;
    show(errorBox);
  }
  
  if (progressInterval) clearInterval(progressInterval);
  hide(loading);
});
