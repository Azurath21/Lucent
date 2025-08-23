from flask import Flask, request, send_from_directory, jsonify
import os
from run_carousell_scraper import CarousellScraper

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
RAW_DIR = os.path.join(BASE_DIR, 'raw')
PROCESSED_DIR = os.path.join(BASE_DIR, 'processed')
WEB_DIR = os.path.join(BASE_DIR, 'web')

app = Flask(__name__, static_folder=WEB_DIR, static_url_path='/')
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret")


def _norm(val: str | None, default: str) -> str:
    if val is None or str(val).strip() == "":
        return default
    return str(val).strip()


@app.get('/')
def static_index():
    # Serve the JS front-end
    return send_from_directory(WEB_DIR, 'index.html')


@app.post('/api/run')
def api_run():
    data = request.get_json(silent=True) or {}
    item = _norm(data.get('item'), 'baby chair')
    condition = _norm(data.get('condition'), '3')  # layered_condition default: brand new
    min_price = _norm(data.get('min_price'), '0')
    max_price = _norm(data.get('max_price'), '150')
    sort = _norm(data.get('sort'), '3')  # default: recent

    scraper = CarousellScraper(
        item=item,
        condition=condition,
        min_price=min_price,
        max_price=max_price,
        sort=sort,
        headless=False,
    )
    try:
        result = scraper.run_and_save()
        csv_name = os.path.basename(result.get('csv_path', ''))
        screenshot_name = os.path.basename(result.get('screenshot_path', ''))
        return jsonify({
            'ok': True,
            'query_url': scraper.url,
            'count': result.get('count', 0),
            'csv_name': csv_name,
            'screenshot_name': screenshot_name,
            'download_csv_url': f"/download/processed/{csv_name}" if csv_name else '',
            'view_screenshot_url': f"/view/raw/{screenshot_name}" if screenshot_name else '',
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        try:
            scraper.quit()
        except Exception:
            pass


@app.get('/download/processed/<path:filename>')
def download_processed(filename):
    return send_from_directory(PROCESSED_DIR, filename, as_attachment=True)


@app.get('/view/raw/<path:filename>')
def view_raw(filename):
    # Serve screenshot inline
    return send_from_directory(RAW_DIR, filename)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="127.0.0.1", port=port, debug=True)
