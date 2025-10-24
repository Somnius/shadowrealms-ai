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
import json
from collections import defaultdict

# Disable SSL warnings for sites with expired certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class WoDBookSyncer:
    def __init__(self, base_url, local_base_dir):
        self.base_url = base_url.rstrip('/') + '/'
        self.local_base_dir = Path(local_base_dir)
        self.local_base_dir.mkdir(parents=True, exist_ok=True)
        self.choices_file = self.local_base_dir / '.duplicate_choices.json'
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
    
    def load_duplicate_choices(self):
        """Load previously saved duplicate resolution choices"""
        if self.choices_file.exists():
            try:
                with open(self.choices_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load choices file: {e}")
        return {}
    
    def save_duplicate_choices(self, choices):
        """Save duplicate resolution choices for future runs"""
        try:
            with open(self.choices_file, 'w') as f:
                json.dump(choices, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save choices file: {e}")
    
    def get_file_hash(self, file_path, chunk_size=8192):
        """Calculate MD5 hash of a file with progress for large files"""
        md5 = hashlib.md5()
        try:
            file_size = file_path.stat().st_size
            # Show progress bar for files larger than 10MB
            show_progress = file_size > 10 * 1024 * 1024
            
            if show_progress:
                progress_bar = tqdm(
                    total=file_size,
                    unit='B',
                    unit_scale=True,
                    unit_divisor=1024,
                    desc=f"Hashing {file_path.name[:30]}",
                    leave=False
                )
            
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(chunk_size), b''):
                    md5.update(chunk)
                    if show_progress:
                        progress_bar.update(len(chunk))
            
            if show_progress:
                progress_bar.close()
            
            return md5.hexdigest()
        except Exception as e:
            print(f"Error hashing {file_path}: {e}")
            return None
    
    def find_duplicates(self):
        """Find duplicate PDF files based on filename and hash"""
        print("\n🔍 Checking for duplicate files...")
        
        # Find all PDFs
        pdf_files = list(self.local_base_dir.rglob('*.pdf'))
        print(f"   Scanning {len(pdf_files)} PDF files...")
        
        # Group by filename (case-insensitive)
        by_filename = defaultdict(list)
        for pdf_path in pdf_files:
            filename = pdf_path.name.lower()
            by_filename[filename].append(pdf_path)
        
        # Find potential duplicates (same name, different locations)
        print(f"   Calculating hashes for potential duplicates...")
        duplicates = {}
        
        for filename, paths in by_filename.items():
            if len(paths) > 1:
                # Get file info including hash
                file_info = []
                for path in paths:
                    try:
                        size = path.stat().st_size
                        relative = path.relative_to(self.local_base_dir)
                        file_hash = self.get_file_hash(path)
                        
                        if file_hash:
                            file_info.append({
                                'path': path,
                                'relative': str(relative),
                                'size': size,
                                'size_mb': size / (1024 * 1024),
                                'hash': file_hash
                            })
                    except Exception as e:
                        print(f"Error checking {path}: {e}")
                
                if len(file_info) > 1:
                    # Group by hash to identify truly identical files
                    by_hash = defaultdict(list)
                    for info in file_info:
                        by_hash[info['hash']].append(info)
                    
                    # Store duplicates grouped by hash
                    duplicates[filename] = {
                        'all_files': file_info,
                        'by_hash': dict(by_hash)
                    }
        
        return duplicates
    
    def handle_duplicates_interactive(self):
        """Interactively handle duplicate files with persistent choices"""
        duplicates = self.find_duplicates()
        
        if not duplicates:
            print("   ✓ No duplicates found!")
            return
        
        # Load saved choices
        saved_choices = self.load_duplicate_choices()
        
        print(f"   Found {len(duplicates)} duplicate filenames")
        print(f"\n{'='*80}")
        print("Duplicate File Resolution")
        print(f"{'='*80}\n")
        
        removed_count = 0
        kept_count = 0
        auto_resolved = 0
        
        for filename, dup_info in sorted(duplicates.items()):
            all_files = dup_info['all_files']
            by_hash = dup_info['by_hash']
            
            # Check if we have a saved choice for this filename
            saved_choice = saved_choices.get(filename, {})
            
            # Try to auto-resolve based on saved choices
            auto_resolved_this = False
            if saved_choice:
                action = saved_choice.get('action')
                
                if action == 'keep_all':
                    # User chose to keep all versions previously
                    kept_count += len(all_files)
                    auto_resolved += 1
                    auto_resolved_this = True
                    
                elif action == 'keep_one':
                    # User chose to keep specific file(s)
                    keep_paths = set(saved_choice.get('keep_paths', []))
                    
                    # Verify saved paths still exist and match hashes
                    valid_choice = True
                    for file_info in all_files:
                        if file_info['relative'] in keep_paths:
                            # Check if hash matches what was saved
                            saved_hash = saved_choice.get('hash')
                            if saved_hash and saved_hash != file_info['hash']:
                                valid_choice = False
                                break
                    
                    if valid_choice and keep_paths:
                        # Auto-apply saved choice
                        for file_info in all_files:
                            if file_info['relative'] in keep_paths:
                                kept_count += 1
                            else:
                                try:
                                    Path(file_info['path']).unlink()
                                    removed_count += 1
                                except Exception as e:
                                    print(f"   ✗ Failed to delete {file_info['relative']}: {e}")
                        auto_resolved += 1
                        auto_resolved_this = True
            
            # If not auto-resolved, ask user
            if not auto_resolved_this:
                print(f"\n📄 Duplicate: {filename}")
                print(f"   Found in {len(all_files)} locations:\n")
                
                # Show all versions with details grouped by hash
                for i, file_info in enumerate(all_files, 1):
                    print(f"   [{i}] {file_info['relative']}")
                    print(f"       Size: {file_info['size_mb']:.2f} MB ({file_info['size']:,} bytes)")
                    print(f"       Hash: {file_info['hash'][:16]}...")
                
                # Check if files are truly identical
                if len(by_hash) == 1:
                    print(f"\n   ✅ All files have identical content (same hash)")
                else:
                    print(f"\n   ⚠️  Files have different content ({len(by_hash)} unique versions):")
                    for hash_val, files in by_hash.items():
                        print(f"      - {hash_val[:16]}... ({len(files)} file{'s' if len(files) > 1 else ''})")
                
                # Ask user what to do
                print(f"\n   Options:")
                for i in range(len(all_files)):
                    print(f"     {i+1} - Keep this one, delete others")
                print(f"     a - Keep all (skip)")
                print(f"     q - Quit duplicate handling")
                
                while True:
                    choice = input(f"\n   Your choice [1-{len(all_files)}/a/q]: ").strip().lower()
                    
                    if choice == 'q':
                        print("\n   Stopping duplicate handling...")
                        # Save choices made so far
                        self.save_duplicate_choices(saved_choices)
                        return
                    
                    if choice == 'a':
                        print("   Keeping all versions")
                        kept_count += len(all_files)
                        # Save this choice
                        saved_choices[filename] = {
                            'action': 'keep_all',
                            'timestamp': time.time()
                        }
                        break
                    
                    try:
                        choice_num = int(choice)
                        if 1 <= choice_num <= len(all_files):
                            # Delete all except the chosen one
                            keep_file = all_files[choice_num - 1]
                            print(f"\n   Keeping: {keep_file['relative']}")
                            
                            for i, info in enumerate(all_files):
                                if i != (choice_num - 1):
                                    try:
                                        Path(info['path']).unlink()
                                        print(f"   ✓ Deleted: {info['relative']}")
                                        removed_count += 1
                                    except Exception as e:
                                        print(f"   ✗ Failed to delete {info['relative']}: {e}")
                            
                            kept_count += 1
                            
                            # Save this choice
                            saved_choices[filename] = {
                                'action': 'keep_one',
                                'keep_paths': [keep_file['relative']],
                                'hash': keep_file['hash'],
                                'timestamp': time.time()
                            }
                            break
                        else:
                            print(f"   Invalid choice. Enter 1-{len(all_files)}, 'a', or 'q'")
                    except ValueError:
                        print(f"   Invalid input. Enter 1-{len(all_files)}, 'a', or 'q'")
        
        # Save all choices for future runs
        self.save_duplicate_choices(saved_choices)
        
        print(f"\n{'='*80}")
        print(f"Duplicate Resolution Complete!")
        print(f"{'='*80}")
        if auto_resolved > 0:
            print(f"Auto-resolved: {auto_resolved} (based on previous choices)")
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

