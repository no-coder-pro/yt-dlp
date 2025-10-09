import requests
from flask import Flask, jsonify, request, redirect
from bs4 import BeautifulSoup
import urllib.parse

app = Flask(__name__)


def _fetch_from_ssvid_search(query: str) -> dict:
    """
    Performs a search request to the ssvid.app API.
    """
    cookies = {
        '_ga': 'GA1.1.629536978.1759997878',
    }
    headers = {
        'accept': '*/*',
        'accept-language': 'en-US,en;q=0.9',
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'origin': 'https://ssvid.app',
        'referer': 'https://ssvid.app/',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
    }
    data = {'query': query, 'vt': 'youtube'}
    response = requests.post(
        'https://ssvid.app/api/ajax/search',
        cookies=cookies,
        headers=headers,
        data=data
    )
    response.raise_for_status()  # Will raise an exception for non-2xx status codes
    return response.json()


def _fetch_from_ssvid_convert(vid: str, k: str) -> dict:
    """
    Performs a convert request to the ssvid.app API to get the final download link.
    """
    cookies = {
        '_ga': 'GA1.1.629536978.1759997878',
    }
    headers = {
        'accept': '*/*',
        'accept-language': 'en-US,en;q=0.9',
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'origin': 'https://ssvid.app',
        'referer': f'https://ssvid.app/en/download/{vid}',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
    }
    data = {'vid': vid, 'k': k}
    response = requests.post(
        'https://ssvid.app/api/ajax/convert',
        cookies=cookies,
        headers=headers,
        data=data
    )
    response.raise_for_status()
    return response.json()


def _fetch_from_youtubemultidownloader(playlist_url: str) -> list:
    """
    Scrapes video data from a YouTube playlist using youtubemultidownloader.org.
    """
    headers = {
        'accept': '*/*',
        'content-type': 'application/x-www-form-urlencoded',
        'origin': 'https://youtubemultidownloader.org',
        'referer': 'https://youtubemultidownloader.org/en/',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
    }
    data = {'playlist_url': playlist_url}
    response = requests.post(
        'https://youtubemultidownloader.org/process.php',
        headers=headers,
        data=data
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'html.parser')
    video_list = []
    table_body = soup.find('table', class_='table').find('tbody')

    if table_body:
        for row in table_body.find_all('tr'):
            cols = row.find_all('td')
            if len(cols) >= 4:
                video_url_anchor = cols[3].find('a')
                raw_youtube_url = None
                if video_url_anchor and 'url=' in video_url_anchor['href']:
                    raw_youtube_url = urllib.parse.unquote(video_url_anchor['href'].split('url=')[-1])

                video_list.append({
                    "index": cols[0].get_text(strip=True),
                    "thumbnail_url": cols[1].find('img')['src'] if cols[1].find('img') else None,
                    "title": cols[2].get_text(strip=True),
                    "youtube_url": raw_youtube_url
                })
    return video_list

@app.route('/')
def index():
    # Get the base URL to construct example links dynamically
    base_url = request.host_url.rstrip('/')
    return jsonify({
        "message": "Welcome to the Video Scraper API!",
        "endpoints": [
            {
                "path": "/api/search",
                "method": "GET",
                "description": "Search for a single video and get download links.",
                "query_params": {
                    "query": "string (required) - The URL or search term for the video."
                },
                "example": f"{base_url}/api/search?query=https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            },
            {
                "path": "/api/convert",
                "method": "GET",
                "description": "Gets the final download link for a specific video format.",
                "query_params": {
                    "vid": "string (required) - The 'vid' from the /api/search response.",
                    "k": "string (required) - The 'k' key for the desired format from the /api/search response."
                },
                "example": f"{base_url}/api/convert?vid=dQw4w9WgXcQ&k=" + urllib.parse.quote_plus("i/tWHqAqn5qbF2md4+soShfOBnMBau2qSBx7T5GWmad8X1Lu/5b9BjlQOf2DhtE=")
            },
            {
                "path": "/api/playlist-data",
                "method": "GET",
                "description": "Extract video data from a YouTube playlist.",
                "query_params": {
                    "playlist_url": "string (required) - The URL of the YouTube playlist."
                },
                "example": f"{base_url}/api/playlist-data?playlist_url=https://www.youtube.com/playlist?list=PL-Db3tS3u0im_5T102FUTx822iG-W42iS"
            }
        ]
    })

@app.route('/api/search', methods=['GET'])
def ssvid_search():
    try:
        query = request.args.get('query')
        if not query:
            return jsonify({"error": "Query parameter 'query' is required."}), 400

        search_data = _fetch_from_ssvid_search(query)

        # Check if the search was successful and links are available
        if search_data.get('status') == 'ok' and 'links' in search_data:
            base_url = request.host_url.rstrip('/')
            vid = search_data.get('vid')

            if vid:
                # Iterate through all formats (mp4, mp3, etc.) and qualities
                for format_type, qualities in search_data['links'].items():
                    for quality_key, details in qualities.items():
                        k_value = details.get('k')
                        if k_value:
                            # Construct the direct download link using our /api/convert endpoint
                            details['download_url'] = f"{base_url}/api/convert?vid={vid}&k={urllib.parse.quote_plus(k_value)}"

        return jsonify(search_data)
    except requests.exceptions.RequestException as e:
        return jsonify({"error": "External API request failed", "details": str(e)}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/convert', methods=['GET'])
def ssvid_convert():
    try:
        vid = request.args.get('vid')
        k = request.args.get('k')

        if not vid or not k:
            return jsonify({"error": "Query parameters 'vid' and 'k' are required."}), 400

        convert_data = _fetch_from_ssvid_convert(vid, k)

        if convert_data.get('status') == 'ok' and 'dlink' in convert_data:
            # Redirect the user directly to the final download link
            return redirect(convert_data['dlink'], code=302)
        else:
            return jsonify({"error": "Failed to get download link from external API.", "details": convert_data}), 502
    except requests.exceptions.RequestException as e:
        return jsonify({"error": "External API request failed", "details": str(e)}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/playlist-data', methods=['GET'])
def playlist_data_extractor():
    try:
        playlist_url = request.args.get('playlist_url')

        if not playlist_url:
            return jsonify({"error": "Parameter 'playlist_url' is required."}), 400

        if "youtube.com/watch?v=" not in playlist_url and "youtube.com/playlist" not in playlist_url:
            return jsonify({"error": "Invalid YouTube playlist URL provided. Please provide a valid YouTube URL."}), 400

        video_list = _fetch_from_youtubemultidownloader(playlist_url)
        if not video_list:
            return jsonify({
                "success": False,
                "message": "No videos found or failed to parse HTML. Check the playlist URL or the target website's structure."
            }), 404
        
        return jsonify({
            "success": True,
            "message": "Playlist videos processed successfully.",
            "videos": video_list
        })
    except requests.exceptions.RequestException as e:
        return jsonify({"error": "External API request failed", "details": str(e)}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500
