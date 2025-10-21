import requests
import time
import os
from flask import Flask, jsonify, request, redirect

app = Flask(__name__)

# Common headers and cookies for ssvid.app API requests
COMMON_HEADERS = {
    'accept': '*/*',
    'accept-language': 'en-US,en;q=0.9,bn;q=0.8',
    'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'dnt': '1',
    'origin': 'https://ssvid.app',
    'priority': 'u=1, i',
    'referer': 'https://ssvid.app/en30',
    'sec-ch-ua': '"Google Chrome";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
    'x-requested-with': 'XMLHttpRequest',
}

COMMON_COOKIES = {
    '_ga': 'GA1.1.629536978.1759997878',
    '_ga_6LBJSB3S9E': 'GS2.1.s1761029103$o7$g1$t1761030380$j3$l0$h0',
    '_ga_4GK2EGV9LP': 'GS2.1.s1761029103$o7$g1$t1761030380$j3$l0$h0',
    '_ga_GZNX0NRT3R': 'GS2.1.s1761029103$o7$g1$t1761030380$j3$l0$h0',
    '_ga_KM2F3J46SD': 'GS2.1.s1761029103$o7$g1$t1761030380$j3$l0$h0',
}


def _make_request(url, data, params={'hl': 'en'}, cookies=None, headers=None):
    """Makes a POST request to the specified URL."""
    try:
        response = requests.post(url, params=params, cookies=cookies, headers=headers, data=data)
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

    # 1. Make an initial GET request to ssvid.app/en30 to get necessary cookies
    try:
        initial_response = requests.get('https://ssvid.app/en30', cookies=COMMON_COOKIES, headers=COMMON_HEADERS)
        initial_response.raise_for_status()
        session_cookies = initial_response.cookies
        print("Initial GET request to ssvid.app/en30 successful.")
    except requests.exceptions.RequestException as e:
        print(f"Initial GET request to https://ssvid.app/en30 failed: {e}")
        print(f"Detailed error: {type(e).__name__} - {e}")
        return jsonify({"error": "Failed to initialize session with ssvid.app. The service might be down or inaccessible."}), 502

    # 2. Search for the video
    search_data = _make_request('https://ssvid.app/api/ajax/search', data={'query': video_url, 'vt': 'home'}, cookies=session_cookies, headers=COMMON_HEADERS)
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
    convert_data = _make_request('https://ssvid.app/api/ajax/convert', data={'vid': vid, 'k': k_value}, cookies=session_cookies, headers=COMMON_HEADERS)
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
