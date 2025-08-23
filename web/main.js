const form = document.getElementById('scrape-form');
const resultBox = document.getElementById('result');
const errorBox = document.getElementById('error');
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

  const item = document.getElementById('item').value.trim();
  const brand = document.getElementById('brand').value.trim();
  const notes = document.getElementById('notes').value.trim();
  const condition = document.getElementById('condition').value;
  const min_price = document.getElementById('min_price').value;

  try {
    const resp = await fetch('/api/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ item, brand, notes, condition, min_price }),
    });
    const data = await resp.json();
    if (!data.ok) throw new Error(data.error || 'Unknown error');

    linkQuery.href = data.query_url;
    linkQuery.textContent = data.query_url;
    countSpan.textContent = data.count;
    downloadLink.href = data.download_csv_url;
    screenshotImg.src = data.view_screenshot_url;

    show(resultBox);
  } catch (err) {
    errorBox.textContent = err.message || String(err);
    show(errorBox);
  }
});
