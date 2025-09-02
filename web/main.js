const form = document.getElementById('scrape-form');
const resultBox = document.getElementById('result');
const errorBox = document.getElementById('error');
const loading = document.getElementById('loading');
const steps = document.querySelectorAll('.progress .step');
const pages = document.querySelectorAll('.page');
const titlescreen = document.getElementById('titlescreen');
const titlescreen2 = document.getElementById('titlescreen2');
const titlescreen3 = document.getElementById('titlescreen3');

let currentPage = 0;
let currentScraper = 'carousell'; // Track current scraper mode

// Set initial state to match default HTML
document.addEventListener('DOMContentLoaded', () => {
  // Ensure Carousell is active by default
  const carousellToggle = document.getElementById('carousell-toggle');
  const facebookToggle = document.getElementById('facebook-toggle');
  const ebayToggle = document.getElementById('ebay-toggle');
  if (carousellToggle && facebookToggle && ebayToggle) {
    carousellToggle.classList.add('active');
    facebookToggle.classList.remove('active');
    ebayToggle.classList.remove('active');
  }
});

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
      body: JSON.stringify({ item, brand, model, notes, condition, min_price, max_price: '', location: 'singapore', days_since_listed: 30, target_days, speed_mode, use_gemini, run_id: runId, scraper: currentScraper }),
    });
    const data = await resp.json();
    if (!data.ok) throw new Error(data.error || 'Unknown error');

    // Check if we have valid prediction data
    if (!data.predicted_price || data.data_points === 0 || data.data_points === "0") {
      throw new Error('No data available for price prediction. Try adjusting your search criteria or check back later when more listings are available.');
    }

    // Update prediction display
    document.getElementById('predicted_price').textContent = `S$${parseFloat(data.predicted_price).toFixed(2)}`;
    document.getElementById('target_timeframe').textContent = `${data.target_days} days`;
    document.getElementById('data_points').textContent = data.data_points;

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

// Theme toggle functionality
const facebookToggle = document.getElementById('facebook-toggle');
const carousellToggle = document.getElementById('carousell-toggle');
const ebayToggle = document.getElementById('ebay-toggle');
const platformName = document.getElementById('platform-name');
const mainLogo = document.getElementById('main-logo');

function showTitlescreen(screen, callback) {
  screen.classList.remove('hidden');
  screen.style.display = 'flex';
  screen.classList.remove('fade-out');
  
  setTimeout(() => {
    screen.classList.add('fade-out');
    setTimeout(() => {
      screen.style.display = 'none';
      screen.classList.add('hidden');
      if (callback) callback();
    }, 500);
  }, 1500);
}

function switchToFacebook() {
  showTitlescreen(titlescreen2, () => {
    document.body.classList.remove('ebay-theme');
    document.body.classList.add('blue-theme');
    facebookToggle.classList.add('active');
    carousellToggle.classList.remove('active');
    ebayToggle.classList.remove('active');
    platformName.textContent = 'Marketplace';
    platformName.className = 'title-red';
    mainLogo.src = '/logo2.png';
    currentScraper = 'facebook';
    
    // Update speed selection images to blue versions
    const speedImages = document.querySelectorAll('.speed-image');
    speedImages[0].src = '/bluecar.png'; // Normal speed
    speedImages[1].src = '/blueplane.png'; // Fast speed
    speedImages[2].src = '/bluerocket.png'; // Ultra fast speed
    
    // Update loading animation camera to shop
    const loadingCamera = document.querySelector('.cam-spin');
    if (loadingCamera) loadingCamera.src = '/shop.png';
  });
}

function switchToCarousell() {
  showTitlescreen(titlescreen, () => {
    document.body.classList.remove('blue-theme', 'ebay-theme');
    carousellToggle.classList.add('active');
    facebookToggle.classList.remove('active');
    ebayToggle.classList.remove('active');
    platformName.textContent = 'carousell';
    platformName.className = 'title-red';
    mainLogo.src = '/logo.png';
    currentScraper = 'carousell';
    
    // Update speed selection images back to original versions
    const speedImages = document.querySelectorAll('.speed-image');
    speedImages[0].src = '/car.png'; // Normal speed
    speedImages[1].src = '/plane.png'; // Fast speed
    speedImages[2].src = '/rocket.png'; // Ultra fast speed
    
    // Update loading animation back to camera
    const loadingCamera = document.querySelector('.cam-spin');
    if (loadingCamera) loadingCamera.src = '/camera.png';
  });
}

function switchToEbay() {
  showTitlescreen(titlescreen3, () => {
    document.body.classList.remove('blue-theme');
    document.body.classList.add('ebay-theme');
    ebayToggle.classList.add('active');
    facebookToggle.classList.remove('active');
    carousellToggle.classList.remove('active');
    platformName.innerHTML = '<span class="letter-e">e</span><span class="letter-b">b</span><span class="letter-a">a</span><span class="letter-y">y</span>';
    platformName.className = 'title-ebay';
    mainLogo.src = '/logo3.png';
    currentScraper = 'ebay';
    
    // Update speed selection images to eBay versions
    const speedImages = document.querySelectorAll('.speed-image');
    speedImages[0].src = '/ebaycar.png'; // Normal speed
    speedImages[1].src = '/ebayplane.png'; // Fast speed
    speedImages[2].src = '/ebayrocket.png'; // Ultra fast speed
    
    // Update loading animation to shopping bag
    const loadingCamera = document.querySelector('.cam-spin');
    if (loadingCamera) loadingCamera.src = '/shoppingbag.png';
  });
}

facebookToggle.addEventListener('click', switchToFacebook);
carousellToggle.addEventListener('click', switchToCarousell);
ebayToggle.addEventListener('click', switchToEbay);
