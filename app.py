import requests
import time
import os
from flask import Flask, jsonify, request, redirect

app = Flask(__name__)

# Common headers and cookies for ssvid.app API requests
COMMON_HEADERS = {
    'accept': '*/*',
    'accept-language': 'en-US,en;q=0.9',
    'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'origin': 'https://ssvid.app',
    'referer': 'https://ssvid.app/',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
    'x-requested-with': 'XMLHttpRequest',
}

COMMON_COOKIES = {
    '_ga': 'GA1.1.629536978.1759997878',
}

def _parse_proxy_string(proxy_str):
    """Parses a proxy string (IP:PORT:USERNAME:PASSWORD) into a dictionary."""
    parts = proxy_str.strip().split(':')
    if len(parts) == 4:
        ip, port, username, password = parts
        return {
            "http": f"http://{username}:{password}@{ip}:{port}",
            "https": f"https://{username}:{password}@{ip}:{port}",
        }
    return None

def _make_request(url, data, params={'hl': 'en'}, proxies=None):
    """Makes a POST request to the specified URL."""
    try:
        response = requests.post(url, params=params, cookies=COMMON_COOKIES, headers=COMMON_HEADERS, data=data, proxies=proxies)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Request to {url} failed: {e}")
        return None

def _find_quality_key(links, quality):
    """Finds the 'k' value for the requested quality."""
    for format_type in links:
        if isinstance(links[format_type], dict):
            for key, details in links[format_type].items():
                if isinstance(details, dict) and details.get('q') == quality:
                    return details.get('k')
    return None

@app.route('/')
def index():
    base_url = request.host_url.rstrip('/')
    return jsonify({
        "message": "Welcome to the YouTube Downloader API!",
        "endpoint": "/api/ytdl",
        "method": "GET",
        "query_params": {
            "url": "string (required) - The YouTube video URL.",
            "quality": "string (required) - The desired quality (e.g., '1080p', '720p', '128kbps' for mp3)."
        },
        "example": f"{base_url}/api/ytdl?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ&quality=720p"
    })

@app.route('/api/ytdl', methods=['GET'])
def get_download_link():
    video_url = request.args.get('url')
    quality = request.args.get('quality')

    if not video_url or not quality:
        return jsonify({"error": "Missing required query parameters: 'url' and 'quality'."}), 400

    proxies = None
    try:
        script_dir = os.path.dirname(__file__)
        proxy_file_path = os.path.join(script_dir, 'proxy.txt')
        with open(proxy_file_path, 'r') as f:
            proxy_line = f.readline().strip()
            if proxy_line:
                proxies = _parse_proxy_string(proxy_line)
                if not proxies:
                    print("Warning: Could not parse proxy string from proxy.txt. Proceeding without proxy.")
            else:
                print("Warning: proxy.txt is empty. Proceeding without proxy.")
    except FileNotFoundError:
        print("Warning: proxy.txt not found. Proceeding without proxy.")
    except Exception as e:
        print(f"Error reading or parsing proxy.txt: {e}. Proceeding without proxy.")

    # 1. Search for the video
    search_data = _make_request('https://ssvid.app/api/ajax/search', data={'query': video_url, 'vt': 'home'}, proxies=proxies)
    if not search_data or search_data.get('status') != 'ok':
        return jsonify({"error": "Failed to search for the video. The service might be down or the URL is invalid."}), 502

    vid = search_data.get('vid')
    title = search_data.get('title')
    links = search_data.get('links')

    if not vid or not links:
        return jsonify({"error": "Could not extract video information from the search result."}), 500

    # 2. Find the requested quality and get the 'k' key
    k_value = _find_quality_key(links, quality)
    if not k_value:
        return jsonify({
            "error": f"Quality '{quality}' not found.",
            "available_qualities": {fmt: [q.get('q') for q_key, q in v.items() if isinstance(q, dict)] for fmt, v in links.items() if isinstance(v, dict)}
        }), 404

    # 3. Start the conversion
    convert_data = _make_request('https://ssvid.app/api/ajax/convert', data={'vid': vid, 'k': k_value})
    if not convert_data:
        return jsonify({"error": "Failed to start the conversion process."}), 502

    c_status = convert_data.get('c_status')

    if c_status == 'CONVERTED' and convert_data.get('dlink'):
        download_url = convert_data['dlink']
        print(f"Generated download link for '{title}': {download_url}")
        return jsonify({
            "title": title,
            "download_url": download_url
        })
    else:
        print(f"Failed to get the final download link. Details: {convert_data}")
        return jsonify({"error": "Failed to get the final download link.", "details": convert_data}), 500

if __name__ == '__main__':
    app.run(debug=True)
