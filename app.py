
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
        print(f"Detailed error: {type(e).__name__} - {e}")
        if e.response is not None:
            print(f"Response status code: {e.response.status_code}")
            print(f"Response text: {e.response.text}")
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

    all_proxies = []
    try:
        script_dir = os.path.dirname(__file__)
        proxy_file_path = os.path.join(script_dir, 'proxy.txt')
        with open(proxy_file_path, 'r') as f:
            for line in f:
                proxy_str = line.strip()
                if proxy_str:
                    parsed_proxy = _parse_proxy_string(proxy_str)
                    if parsed_proxy:
                        all_proxies.append(parsed_proxy)
                    else:
                        print(f"Warning: Could not parse proxy string: {proxy_str}")
        if not all_proxies:
            print("Warning: No valid proxies found in proxy.txt. Proceeding without proxy.")
    except FileNotFoundError:
        print("Warning: proxy.txt not found. Proceeding without proxy.")
    except Exception as e:
        print(f"Error reading or parsing proxy.txt: {e}. Proceeding without proxy.")

    search_data = None
    if all_proxies:
        for i, proxy_config in enumerate(all_proxies):
            print(f"Attempting search with proxy {i+1}/{len(all_proxies)}")
            search_data = _make_request('https://ssvid.app/api/ajax/search', data={'query': video_url, 'vt': 'home'}, proxies=proxy_config)
            if search_data and search_data.get('status') == 'ok':
                print(f"Search successful with proxy {i+1}.")
                break
            else:
                print(f"Search failed with proxy {i+1}. Trying next proxy...")
        if not search_data or search_data.get('status') != 'ok':
            return jsonify({"error": "Failed to search for the video after trying all available proxies. The service might be down or the URL is invalid."}), 502
    else:
        # If no proxies are configured or found, try without proxies
        print("Attempting search without proxies.")
        search_data = _make_request('https://ssvid.app/api/ajax/search', data={'query': video_url, 'vt': 'home'})
        if not search_data or search_data.get('status') != 'ok':
            return jsonify({"error": "Failed to search for the video without proxies. The service might be down or the URL is invalid."}), 502

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
