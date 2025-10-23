# World of Darkness Books Sync

This directory contains the World of Darkness books synchronized from the-eye.eu.

## Setup

No manual setup required! The sync script automatically creates and manages its own virtual environment.

Requirements:
- Python 3.7 or higher
- `python3-venv` package (usually included with Python)

If you get an error about venv not being available, install it:
```bash
# Debian/Ubuntu
sudo apt install python3-venv

# Fedora/RHEL
sudo dnf install python3-venv
```

## Usage

Simply run the sync script:

```bash
cd books/
./sync.sh
```

Or from the project root:

```bash
./books/sync.sh
```

The script will automatically:
1. Create a virtual environment (first run only)
2. Install required dependencies (first run or when updated)
3. Run the sync process

## Features

- ✅ **Recursive Download**: Downloads all files from World of Darkness directory and subdirectories
- ✅ **Resume Support**: Automatically resumes interrupted downloads
- ✅ **Smart Skipping**: Skips files that already exist with matching size
- ✅ **Progress Bars**: Shows progress for each file download (no verbose output)
- ✅ **Directory Structure**: Preserves the exact directory structure locally
- ✅ **All File Types**: Downloads PDFs, HTML, images, and all other files
- ✅ **HTML Rewriting**: Converts index.html files to use local paths
- ✅ **Book List**: Generates `book-list.txt` with all PDF files and paths

## Generated Files

- `book-list.txt` - Complete list of all PDF files with their paths (auto-generated after each sync)
- `index.html` - Directory listings (rewritten to work locally)
- All downloaded books and files in their original directory structure

## Running Periodically

You can run the sync script anytime to check for new additions. It will:
- Skip existing files (if size matches)
- Download only new files
- Update the book-list.txt

Example cron job to sync daily at 2 AM:
```bash
0 2 * * * cd /path/to/shadowrealms-ai/books && ./sync.sh >> sync.log 2>&1
```

## Statistics

After each sync, you'll see:
- Number of files downloaded
- Number of files skipped (already up to date)
- Number of failed downloads
- Total time taken

## Interrupting

You can safely interrupt the sync (Ctrl+C) at any time. Just run it again to resume where it left off.

## Directory Structure

After running, the books directory will contain:
```
books/
├── sync.sh              # Main sync script (run this)
├── sync_wod_books.py    # Python sync implementation
├── requirements.txt     # Python dependencies
├── README.md           # This file
├── venv/               # Virtual environment (auto-created)
├── book-list.txt       # Generated PDF list
└── World of Darkness/  # Downloaded books (mirrors website structure)
```

Note: The `venv/` directory is automatically created and managed by the sync script.

