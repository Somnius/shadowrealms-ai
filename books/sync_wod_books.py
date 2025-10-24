#!/usr/bin/env python3
"""
World of Darkness Books Sync Script
Downloads and syncs books from the-eye.eu/public/Books/rpg.rem.uz/World of Darkness/
"""

import os
import sys
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, unquote
from pathlib import Path
from tqdm import tqdm
import time
import re
import urllib3
import hashlib
from collections import defaultdict

# Disable SSL warnings for sites with expired certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class WoDBookSyncer:
    def __init__(self, base_url, local_base_dir):
        self.base_url = base_url.rstrip('/') + '/'
        self.local_base_dir = Path(local_base_dir)
        self.local_base_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
        })
        # Disable SSL verification for sites with expired certificates
        self.session.verify = False
        self.downloaded_files = []
        self.skipped_files = []
        self.failed_files = []
        
    def parse_directory_listing(self, url):
        """Parse an Apache/nginx directory listing and extract links"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            items = {'dirs': [], 'files': []}
            
            # Find all links in the directory listing
            for link in soup.find_all('a'):
                href = link.get('href')
                if not href or href.startswith(('?', '#', '/', 'http://localhost', 'https://localhost')):
                    continue
                
                # Skip parent directory links
                if href in ['../', '../']:
                    continue
                
                full_url = urljoin(url, href)
                
                # Only process URLs within our base path
                if not full_url.startswith(self.base_url):
                    continue
                
                if href.endswith('/'):
                    items['dirs'].append(full_url)
                else:
                    items['files'].append(full_url)
            
            return items
        except Exception as e:
            print(f"Error parsing directory {url}: {e}")
            return {'dirs': [], 'files': []}
    
    def get_remote_file_size(self, url):
        """Get the size of a remote file without downloading it"""
        try:
            response = self.session.head(url, timeout=10, allow_redirects=True)
            if response.status_code == 200:
                return int(response.headers.get('content-length', 0))
        except:
            pass
        return None
    
    def get_local_path(self, url):
        """Convert a URL to a local file path"""
        # Remove base URL to get relative path
        relative_path = url.replace(self.base_url, '')
        relative_path = unquote(relative_path)
        
        # Remove trailing slash for directories
        relative_path = relative_path.rstrip('/')
        
        return self.local_base_dir / relative_path
    
    def download_file(self, url, local_path, resume=True, max_retries=3):
        """Download a file with resume support, progress bar, and retry logic"""
        local_path = Path(local_path)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Check if file exists and get its size
        existing_size = 0
        if local_path.exists() and resume:
            existing_size = local_path.stat().st_size
        
        # Get remote file size
        remote_size = self.get_remote_file_size(url)
        
        # Skip if file exists and sizes match
        if existing_size > 0 and remote_size and existing_size == remote_size:
            self.skipped_files.append(str(local_path.relative_to(self.local_base_dir)))
            return True
        
        # Retry loop with exponential backoff
        for attempt in range(max_retries):
            try:
                # Prepare headers for resume
                headers = {}
                mode = 'wb'
                if local_path.exists() and resume:
                    existing_size = local_path.stat().st_size
                    if existing_size > 0:
                        headers['Range'] = f'bytes={existing_size}-'
                        mode = 'ab'
                
                response = self.session.get(url, headers=headers, stream=True, timeout=30)
                
                # Check if resume is supported
                if existing_size > 0 and response.status_code == 416:
                    # Range not satisfiable - file is already complete
                    self.skipped_files.append(str(local_path.relative_to(self.local_base_dir)))
                    return True
                
                if response.status_code not in [200, 206]:
                    if attempt < max_retries - 1:
                        retry_delay = 2 ** attempt  # 1s, 2s, 4s
                        time.sleep(retry_delay)
                        continue
                    print(f"Failed to download {url}: HTTP {response.status_code}")
                    self.failed_files.append(str(local_path.relative_to(self.local_base_dir)))
                    return False
                
                # Get total size
                total_size = existing_size
                if response.status_code == 206:
                    # Partial content
                    content_range = response.headers.get('content-range', '')
                    if content_range:
                        total_size = int(content_range.split('/')[-1])
                else:
                    total_size = int(response.headers.get('content-length', 0))
                
                # Create progress bar
                filename = local_path.name
                if len(filename) > 40:
                    filename = filename[:37] + '...'
                
                progress_bar = tqdm(
                    total=total_size,
                    initial=existing_size,
                    unit='B',
                    unit_scale=True,
                    unit_divisor=1024,
                    desc=filename,
                    leave=False
                )
                
                # Download and write file
                with open(local_path, mode) as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            progress_bar.update(len(chunk))
                
                progress_bar.close()
                self.downloaded_files.append(str(local_path.relative_to(self.local_base_dir)))
                
                # Small delay between successful downloads to be nice to the server
                time.sleep(1)
                return True
                
            except Exception as e:
                if attempt < max_retries - 1:
                    # Exponential backoff: 2s, 4s, 8s
                    retry_delay = 2 ** (attempt + 1)
                    print(f"Retry {attempt + 1}/{max_retries} after {retry_delay}s: {local_path.name}")
                    time.sleep(retry_delay)
                else:
                    print(f"Error downloading {url}: {e}")
                    self.failed_files.append(str(local_path.relative_to(self.local_base_dir)))
                    return False
        
        return False
    
    def rewrite_html_file(self, html_path):
        """Rewrite HTML file to use local paths"""
        try:
            with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            soup = BeautifulSoup(content, 'html.parser')
            
            # Update all anchor tags
            for link in soup.find_all('a'):
                href = link.get('href')
                if href and not href.startswith(('#', '?')):
                    # Convert to relative local path
                    if href.startswith('http'):
                        # Absolute URL - make it relative
                        if href.startswith(self.base_url):
                            relative = href.replace(self.base_url, '')
                            link['href'] = unquote(relative)
                    else:
                        # Already relative - just decode
                        link['href'] = unquote(href)
            
            # Write back the modified HTML
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(str(soup))
                
        except Exception as e:
            print(f"Error rewriting HTML {html_path}: {e}")
    
    def sync_directory(self, url, depth=0):
        """Recursively sync a directory"""
        indent = "  " * depth
        dir_name = unquote(url.rstrip('/').split('/')[-1]) or "root"
        print(f"{indent}📁 Syncing: {dir_name}")
        
        items = self.parse_directory_listing(url)
        
        # Download files in this directory
        if items['files']:
            print(f"{indent}   Found {len(items['files'])} files")
            for file_url in items['files']:
                local_path = self.get_local_path(file_url)
                self.download_file(file_url, local_path)
                
                # Rewrite HTML files
                if local_path.suffix.lower() in ['.html', '.htm']:
                    self.rewrite_html_file(local_path)
        
        # Recursively process subdirectories
        if items['dirs']:
            print(f"{indent}   Found {len(items['dirs'])} subdirectories")
            for dir_url in items['dirs']:
                self.sync_directory(dir_url, depth + 1)
    
    def generate_book_list(self):
        """Generate book-list.txt with all PDFs found"""
        book_list_path = self.local_base_dir / 'book-list.txt'
        
        print("\n📚 Generating book list...")
        pdf_files = sorted(self.local_base_dir.rglob('*.pdf'))
        
        with open(book_list_path, 'w', encoding='utf-8') as f:
            f.write(f"World of Darkness Books - PDF List\n")
            f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total PDFs: {len(pdf_files)}\n")
            f.write("=" * 80 + "\n\n")
            
            for pdf_path in pdf_files:
                relative_path = pdf_path.relative_to(self.local_base_dir)
                f.write(f"{relative_path}\n")
        
        print(f"   ✓ Found {len(pdf_files)} PDF files")
        print(f"   ✓ Book list saved to: {book_list_path}")
    
    def get_file_hash(self, file_path, chunk_size=8192):
        """Calculate MD5 hash of a file"""
        md5 = hashlib.md5()
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(chunk_size), b''):
                    md5.update(chunk)
            return md5.hexdigest()
        except Exception as e:
            print(f"Error hashing {file_path}: {e}")
            return None
    
    def find_duplicates(self):
        """Find duplicate PDF files based on filename and size"""
        print("\n🔍 Checking for duplicate files...")
        
        # Find all PDFs
        pdf_files = list(self.local_base_dir.rglob('*.pdf'))
        
        # Group by filename (case-insensitive)
        by_filename = defaultdict(list)
        for pdf_path in pdf_files:
            filename = pdf_path.name.lower()
            by_filename[filename].append(pdf_path)
        
        # Find actual duplicates (same name, different locations)
        duplicates = {}
        for filename, paths in by_filename.items():
            if len(paths) > 1:
                # Get file sizes
                file_info = []
                for path in paths:
                    try:
                        size = path.stat().st_size
                        relative = path.relative_to(self.local_base_dir)
                        file_info.append({
                            'path': path,
                            'relative': relative,
                            'size': size,
                            'size_mb': size / (1024 * 1024)
                        })
                    except Exception as e:
                        print(f"Error checking {path}: {e}")
                
                if file_info:
                    duplicates[filename] = file_info
        
        return duplicates
    
    def handle_duplicates_interactive(self):
        """Interactively handle duplicate files"""
        duplicates = self.find_duplicates()
        
        if not duplicates:
            print("   ✓ No duplicates found!")
            return
        
        print(f"   Found {len(duplicates)} duplicate filenames")
        print(f"\n{'='*80}")
        print("Duplicate File Resolution")
        print(f"{'='*80}\n")
        
        removed_count = 0
        kept_count = 0
        
        for filename, file_list in sorted(duplicates.items()):
            print(f"\n📄 Duplicate: {filename}")
            print(f"   Found in {len(file_list)} locations:\n")
            
            # Show all versions with details
            for i, info in enumerate(file_list, 1):
                print(f"   [{i}] {info['relative']}")
                print(f"       Size: {info['size_mb']:.2f} MB ({info['size']:,} bytes)")
            
            # Check if they're identical (same size)
            sizes = [f['size'] for f in file_list]
            if len(set(sizes)) == 1:
                print(f"\n   ℹ️  All files have identical size - likely the same content")
            else:
                print(f"\n   ⚠️  Different file sizes detected!")
            
            # Ask user what to do
            print(f"\n   Options:")
            for i in range(len(file_list)):
                print(f"     {i+1} - Keep this one, delete others")
            print(f"     a - Keep all (skip)")
            print(f"     q - Quit duplicate handling")
            
            while True:
                choice = input(f"\n   Your choice [1-{len(file_list)}/a/q]: ").strip().lower()
                
                if choice == 'q':
                    print("\n   Stopping duplicate handling...")
                    return
                
                if choice == 'a':
                    print("   Keeping all versions")
                    kept_count += len(file_list)
                    break
                
                try:
                    choice_num = int(choice)
                    if 1 <= choice_num <= len(file_list):
                        # Delete all except the chosen one
                        keep_file = file_list[choice_num - 1]
                        print(f"\n   Keeping: {keep_file['relative']}")
                        
                        for i, info in enumerate(file_list):
                            if i != (choice_num - 1):
                                try:
                                    info['path'].unlink()
                                    print(f"   ✓ Deleted: {info['relative']}")
                                    removed_count += 1
                                except Exception as e:
                                    print(f"   ✗ Failed to delete {info['relative']}: {e}")
                        
                        kept_count += 1
                        break
                    else:
                        print(f"   Invalid choice. Enter 1-{len(file_list)}, 'a', or 'q'")
                except ValueError:
                    print(f"   Invalid input. Enter 1-{len(file_list)}, 'a', or 'q'")
        
        print(f"\n{'='*80}")
        print(f"Duplicate Resolution Complete!")
        print(f"{'='*80}")
        print(f"Files kept:    {kept_count}")
        print(f"Files removed: {removed_count}")
        print(f"{'='*80}\n")
    
    def run(self):
        """Main sync process"""
        print("=" * 80)
        print("World of Darkness Books Sync")
        print("=" * 80)
        print(f"Source: {self.base_url}")
        print(f"Target: {self.local_base_dir}")
        print("=" * 80)
        print()
        
        start_time = time.time()
        
        try:
            # Start recursive sync
            self.sync_directory(self.base_url)
            
            # Generate book list
            self.generate_book_list()
            
            # Check for duplicates
            self.handle_duplicates_interactive()
            
            # Summary
            elapsed = time.time() - start_time
            print("\n" + "=" * 80)
            print("Sync Complete!")
            print("=" * 80)
            print(f"Downloaded:  {len(self.downloaded_files)} files")
            print(f"Skipped:     {len(self.skipped_files)} files (already up to date)")
            print(f"Failed:      {len(self.failed_files)} files")
            print(f"Total time:  {elapsed:.1f} seconds")
            
            if self.failed_files:
                print("\n⚠️  Failed downloads:")
                for failed in self.failed_files[:10]:  # Show first 10
                    print(f"   - {failed}")
                if len(self.failed_files) > 10:
                    print(f"   ... and {len(self.failed_files) - 10} more")
            
            print("=" * 80)
            
        except KeyboardInterrupt:
            print("\n\n⚠️  Sync interrupted by user")
            print(f"Downloaded so far: {len(self.downloaded_files)} files")
            print("You can run the script again to resume.")
            sys.exit(1)


def main():
    # Configuration
    BASE_URL = "https://the-eye.eu/public/Books/rpg.rem.uz/World%20of%20Darkness/"
    
    # Get script directory and set local directory
    script_dir = Path(__file__).parent
    LOCAL_DIR = script_dir
    
    # Create syncer and run
    syncer = WoDBookSyncer(BASE_URL, LOCAL_DIR)
    syncer.run()


if __name__ == "__main__":
    main()

