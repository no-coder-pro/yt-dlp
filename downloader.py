
import requests
import sys

# Headers to mimic a browser and access the download link
DOWNLOAD_HEADERS = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'accept-language': 'en-US,en;q=0.9',
    'dnt': '1',
    'priority': 'u=0, i',
    'sec-ch-ua': '"Google Chrome";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'document',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'none',
    'sec-fetch-user': '?1',
    'upgrade-insecure-requests': '1',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
}

def download_file(url, output_filename):
    """Downloads a file from a URL and saves it locally."""
    print(f"Starting download from: {url}")
    try:
        with requests.get(url, headers=DOWNLOAD_HEADERS, stream=True) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            block_size = 8192
            downloaded = 0

            with open(output_filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=block_size):
                    f.write(chunk)
                    downloaded += len(chunk)
                    # Calculate and display progress
                    progress = (downloaded / total_size) * 100
                    sys.stdout.write(f"\rDownloaded {downloaded // 1024} KB of {total_size // 1024} KB ({progress:.2f}%)")
                    sys.stdout.flush()
        print(f"\nDownload complete! File saved as: {output_filename}")

    except requests.exceptions.RequestException as e:
        print(f"\nError downloading file: {e}")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python downloader.py <URL> <output_filename>")
        sys.exit(1)

    download_url = sys.argv[1]
    filename = sys.argv[2]
    download_file(download_url, filename)
