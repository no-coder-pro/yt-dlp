from flask import Flask, request, jsonify, Response, stream_with_context
import requests
import cloudscraper
import re
import base64
import time

app = Flask(__name__)

# Global cookie cache
_cookie_cache = {
    'cookies': {
        '_ga': 'GA1.1.1317316867.1760597222',
        '_ga_MF283RRQCW': 'GS2.1.s1761052232$o5$g0$t1761052232$j60$l0$h0',
    },
    'last_updated': time.time()
}

def get_fresh_cookies():
    """Auto-update cookies if they're older than 1 hour"""
    global _cookie_cache
    
    current_time = time.time()
    cache_age = current_time - _cookie_cache['last_updated']
    
    if cache_age > 3600:
        try:
            scraper = cloudscraper.create_scraper(
                browser={
                    'browser': 'chrome',
                    'platform': 'windows',
                    'desktop': True
                }
            )
            
            response = scraper.get('https://cnvmp3.com/v39')
            
            if scraper.cookies:
                new_cookies = {}
                for cookie in scraper.cookies:
                    new_cookies[cookie.name] = cookie.value
                
                if new_cookies:
                    _cookie_cache['cookies'] = new_cookies
                    _cookie_cache['last_updated'] = current_time
        except Exception:
            pass
    
    return _cookie_cache['cookies']

def extract_youtube_id(url):
    """Extract YouTube video ID from URL"""
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com\/watch\?.*?v=([a-zA-Z0-9_-]{11})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    if len(url) == 11 and re.match(r'^[a-zA-Z0-9_-]{11}$', url):
        return url
    
    return None

def get_download_link(youtube_id, quality):
    """Get YouTube video download link from cnvmp3.com"""
    cookies = get_fresh_cookies()
    
    headers = {
        'accept': '*/*',
        'accept-language': 'en-US,en;q=0.9,bn;q=0.8',
        'content-type': 'application/json',
        'dnt': '1',
        'origin': 'https://cnvmp3.com',
        'priority': 'u=1, i',
        'referer': 'https://cnvmp3.com/v39',
        'sec-ch-ua': '"Google Chrome";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
    }
    
    quality_map = {
        '144': 0, '240': 1, '360': 2, '480': 3,
        '720': 4, '1080': 5, '1440': 6, '2160': 7, '4k': 7,
    }
    
    quality_value = quality_map.get(str(quality).lower(), 4)
    
    json_data = {
        'youtube_id': youtube_id,
        'quality': quality_value,
        'formatValue': 1,
    }
    
    response = requests.post('https://cnvmp3.com/check_database.php', 
                           cookies=cookies, 
                           headers=headers, 
                           json=json_data)
    
    return response.json()

@app.route('/download', methods=['GET'])
def download_video():
    """
    API endpoint to get YouTube video download links
    Returns both original link and proxy download link
    """
    try:
        url = request.args.get('url')
        quality = request.args.get('quality', '720')
        
        if not url:
            return jsonify({
                'status': 'error',
                'message': 'URL parameter is required'
            }), 400
        
        youtube_id = extract_youtube_id(url)
        
        if not youtube_id:
            return jsonify({
                'status': 'error',
                'message': 'Invalid YouTube URL or video ID'
            }), 400
        
        result = get_download_link(youtube_id, quality)
        
        if not result:
            return jsonify({
                'status': 'error',
                'message': 'Failed to get download link'
            }), 400
        
        if not result.get('success'):
            return jsonify({
                'status': 'error',
                'message': result.get('error', 'No entry found for the provided youtube_id and quality'),
                'details': result
            }), 400
        
        data = result.get('data', {})
        original_url = data.get('server_path') or data.get('download_url') or data.get('url')
        title = data.get('title', '')
        
        if not original_url:
            return jsonify({
                'status': 'error',
                'message': 'Download link not found in response',
                'details': result
            }), 400
        
        encoded_url = base64.urlsafe_b64encode(original_url.encode()).decode()
        
        host_url = request.host_url.rstrip('/')
        proxy_url = f"{host_url}/get?url={encoded_url}"
        
        return jsonify({
            'status': 'success',
            'youtube_id': youtube_id,
            'quality': quality,
            'title': title,
            'direct_download_link': proxy_url,
            'original_link': original_url,
            'note': 'Use direct_download_link - it works immediately in browser or download manager'
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/get', methods=['GET'])
def proxy_download():
    """
    Proxy download endpoint - Streams file with proper headers
    """
    try:
        encoded_url = request.args.get('url')
        
        if not encoded_url:
            return jsonify({
                'status': 'error',
                'message': 'URL parameter is required'
            }), 400
        
        try:
            download_url = base64.urlsafe_b64decode(encoded_url.encode()).decode()
        except Exception:
            return jsonify({
                'status': 'error',
                'message': 'Invalid URL encoding'
            }), 400
        
        cookies = get_fresh_cookies()
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
            'Referer': 'https://cnvmp3.com/v39',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,bn;q=0.8',
            'DNT': '1',
        }
        
        response = requests.get(download_url, headers=headers, cookies=cookies, stream=True)
        
        if response.status_code != 200:
            return jsonify({
                'status': 'error',
                'message': f'Failed to download file. Status: {response.status_code}'
            }), response.status_code
        
        filename = 'video.mp3'
        content_disposition = response.headers.get('Content-Disposition', '')
        if 'filename=' in content_disposition:
            filename = content_disposition.split('filename=')[-1].strip('"')
        
        def generate():
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk
        
        return Response(
            stream_with_context(generate()),
            content_type=response.headers.get('Content-Type', 'application/octet-stream'),
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Cache-Control': 'no-cache'
            }
        )
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/', methods=['GET'])
def index():
    """API documentation"""
    host_url = request.host_url.rstrip('/')
    
    return jsonify({
        'name': 'YouTube Downloader API',
        'version': '2.0',
        'note': 'Use direct_download_link - it works immediately in browser or download manager',
        'example_request': f'GET {host_url}/download?url=https://youtu.be/dQw4w9WgXcQ&quality=720',
        'mp3_quality_options': ['96kbps', '128kbps', '256kbps', '320kbps'],
        'mp4_quality_options': ['144p', '240p', '360p', '480p', '720p', '1080p', '1440p', '2160p'],
        'endpoints': {
            '/download': 'Get YouTube video download link',
            '/get': 'Proxy download (auto-used by direct_download_link)'
        }
    })

# Vercel serverless handler
app_handler = app

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
