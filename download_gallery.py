#!/usr/bin/env python3
import os
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re
import uuid
import unicodedata

class GalleryDownloader:
    def __init__(self):
        self.base_url = "https://www.olografix.org"
        self.gallery_url = f"{self.base_url}/category/photogallery/"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.download_dir = "downloads"
        os.makedirs(self.download_dir, exist_ok=True)

    def slugify(self, value):
        """
        Convert to ASCII. Convert spaces to hyphens. Remove characters that aren't alphanumerics,
        underscores, or hyphens. Convert to lowercase. Also strip leading and trailing whitespace.
        """
        value = str(value)
        value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
        value = re.sub(r'[^\w\s-]', '', value).strip().lower()
        return re.sub(r'[-\s]+', '-', value)

    def generate_random_filename(self, original_filename):
        """Generate a random filename while preserving the original extension"""
        # Get the file extension from the original filename
        ext = os.path.splitext(original_filename)[1].lower()
        # Generate a random UUID and combine with the original extension
        return f"{uuid.uuid4().hex}{ext}"

    def get_page_content(self, url):
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return None

    def download_image(self, url, album_dir):
        try:
            response = requests.get(url, headers=self.headers, stream=True)
            response.raise_for_status()
            
            # Get original filename for extension
            original_filename = os.path.basename(urlparse(url).path)
            if not original_filename:
                original_filename = url.split('/')[-1]
            
            # Generate random filename while keeping extension
            new_filename = self.generate_random_filename(original_filename)
            filepath = os.path.join(album_dir, new_filename)
            
            print(f"Downloading: {url} -> {new_filename}")
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            time.sleep(1)  # Be nice to the server
            
        except requests.RequestException as e:
            print(f"Error downloading {url}: {e}")

    def process_album_page(self, url, album_name):
        print(f"\nProcessing album: {album_name}")
        content = self.get_page_content(url)
        if not content:
            return

        soup = BeautifulSoup(content, 'html.parser')
        
        # Create album directory with slugified name
        slugified_album_name = self.slugify(album_name)
        album_dir = os.path.join(self.download_dir, slugified_album_name)
        os.makedirs(album_dir, exist_ok=True)

        # Find all gallery images
        for img_link in soup.find_all('a', href=True):
            href = img_link['href']
            # Check if link points to an image
            if re.search(r'\.(jpg|jpeg|png|gif|webp)$', href, re.I):
                # Skip thumbnail/cache versions
                if 'cache' in href:
                    continue
                    
                # Make sure we have absolute URL
                full_url = urljoin(self.base_url, href)
                self.download_image(full_url, album_dir)

    def get_album_links(self, page_url):
        content = self.get_page_content(page_url)
        if not content:
            return []

        soup = BeautifulSoup(content, 'html.parser')
        albums = []
        
        # Find all post titles
        for post in soup.find_all('h3', class_='post-title'):
            link = post.find('a')
            if link and link.get('href') and link.get('title'):
                albums.append({
                    'url': link['href'],
                    'title': link['title']
                })
        
        return albums

    def run(self):
        print("Starting gallery download...")
        
        # Process all pages
        page = 1
        while True:
            page_url = self.gallery_url if page == 1 else f"{self.gallery_url}page/{page}/"
            print(f"\nProcessing page {page}: {page_url}")
            
            albums = self.get_album_links(page_url)
            if not albums:
                print(f"No albums found on page {page}, stopping.")
                break
                
            for album in albums:
                self.process_album_page(album['url'], album['title'])
            
            page += 1
            if page > 9:  # Based on the pagination in your HTML
                break
                
            # time.sleep(2)  # Be nice to the server
        
        print("\nDownload completed!")

if __name__ == "__main__":
    downloader = GalleryDownloader()
    downloader.run()