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

### Sync Script (`sync.sh`)
- ✅ **Recursive Download**: Downloads all files from World of Darkness directory and subdirectories
- ✅ **Resume Support**: Automatically resumes interrupted downloads
- ✅ **Smart Skipping**: Skips files that already exist with matching size
- ✅ **Progress Bars**: Shows progress for each file download (no verbose output)
- ✅ **Directory Structure**: Preserves the exact directory structure locally
- ✅ **All File Types**: Downloads PDFs, HTML, images, and all other files
- ✅ **HTML Rewriting**: Converts index.html files to use local paths
- ✅ **Book List**: Generates `book-list.txt` with all PDF files and paths

### Parser Script (`parse_books.py`)
- ✅ **Multi-core Processing**: Utilizes all CPU cores for parallel PDF processing
- ✅ **GPU Acceleration**: GPU-accelerated embedding generation for 10-50x faster processing
- ✅ **Optimized Performance**: Memory-efficient processing of large PDFs
- ✅ **Text Extraction**: Extracts and cleans text from PDFs using pdfplumber
- ✅ **Smart Chunking**: Chunks text for RAG/Vector database ingestion
- ✅ **Embedding Generation**: Optional on-the-fly embedding creation (saves post-processing time)
- ✅ **Caching**: Skips already processed PDFs (unless forced)
- ✅ **JSON Output**: Structured JSON format with optional embeddings
- ✅ **Progress Tracking**: Real-time progress bars for batch processing

## Parsing PDFs for RAG/Vector Database

After syncing books, you can parse them for ingestion into your RAG system.

### Setup GPU Support (HIGHLY RECOMMENDED)

For GPU-accelerated embedding generation (10-50x faster):

```bash
cd books/
source venv/bin/activate

# Install GPU support
pip install torch sentence-transformers

# Verify GPU is detected
python -c "import torch; print('GPU Available:' , torch.cuda.is_available())"
```

### Basic Usage

```bash
cd books/
source venv/bin/activate

# Parse all PDFs (text only)
python parse_books.py

# Parse with GPU-accelerated embeddings (RECOMMENDED!)
python parse_books.py --embeddings

# Use specific number of workers
python parse_books.py --workers 8 --embeddings

# Larger chunks for more context
python parse_books.py --chunk-size 1500 --overlap 300 --embeddings

# Reprocess everything with embeddings
python parse_books.py --force --embeddings
```

### Parser Options

**Performance:**
- `--workers N` - Number of parallel processes (default: CPU cores - 1)
- `--embeddings` - Generate embeddings (GPU-accelerated if available)
- `--embedding-model MODEL` - Embedding model to use (default: all-MiniLM-L6-v2)
- `--embedding-batch-size N` - Batch size for embeddings (default: 32)

**Processing:**
- `--chunk-size N` - Characters per chunk (default: 1000)
- `--overlap N` - Overlap between chunks (default: 200)
- `--force` - Reprocess all PDFs even if cached
- `--output-dir DIR` - Custom output directory (default: books/parsed)

**Embedding Models (alternatives):**
- `sentence-transformers/all-MiniLM-L6-v2` - Fast, 384 dims (default)
- `sentence-transformers/all-mpnet-base-v2` - Better quality, 768 dims, slower
- `nomic-ai/nomic-embed-text-v1.5` - Optimized for retrieval, 768 dims

### Output Format

Parsed books are saved as JSON in `books/parsed/`:
```json
{
  "metadata": {
    "filename": "Book.pdf",
    "relative_path": "World of Darkness/oWoD/Book.pdf",
    "system": "World of Darkness",
    "category": "oWoD",
    "file_size": 5242880
  },
  "processing_info": {
    "total_pages": 250,
    "total_chunks": 500,
    "chunk_size": 1000,
    "embeddings_generated": true,
    "embedding_model": "all-MiniLM-L6-v2",
    "embedding_device": "cuda"
  },
  "chunks": [
    {
      "text": "...",
      "page_number": 1,
      "chunk_id": "abc123def456",
      "word_count": 180,
      "char_count": 950,
      "embedding": [0.123, -0.456, ...],  // Only if --embeddings was used
      "embedding_dim": 384  // Only if --embeddings was used
    }
  ]
}
```

**With Embeddings:** Files include 384-dimensional (or 768 for larger models) vector embeddings ready for direct ChromaDB/vector database insertion.

## Importing to RAG/Vector Database

### ⚠️ Important: Selective Import Strategy

**DO NOT import all books automatically!** Instead, use campaign-specific book sets for better performance and quality.

### Why Selective Import?

✅ **Better Retrieval Quality** - Less noise, more relevant results  
✅ **Faster Searches** - Fewer vectors to compare  
✅ **Lower Memory** - Only load what you need  
✅ **No Rule Conflicts** - Avoid mixing incompatible systems/editions  
✅ **Focused Context** - AI gets relevant rules, not everything  

### Architecture

Your system uses a smart two-tier approach:

```
Global (campaign_id: 0)
└── Core WoD rules available to ALL campaigns

Campaign-Specific (campaign_id: 1, 2, 3...)
└── Only books relevant to that campaign
```

### Import Books Selectively

```bash
cd books/
source venv/bin/activate

# List available parsed books
python import_to_rag.py --list

# List predefined book sets
python import_to_rag.py --list-sets

# Import core rules globally (available to all campaigns)
python import_to_rag.py --import-set core_only --campaign-id 0

# Import Vampire books for campaign #1
python import_to_rag.py --import-set vampire_basic --campaign-id 1

# Import Werewolf books for campaign #2
python import_to_rag.py --import-set werewolf_full --campaign-id 2

# Check what's imported
python import_to_rag.py --list-imported
```

### Available Book Sets

- **`core_only`** - Essential WoD mechanics (minimal)
- **`vampire_basic`** - Core Vampire rules
- **`vampire_full`** - Complete Vampire game
- **`werewolf_full`** - Complete Werewolf game
- **`mage_basic`** - Core Mage rules
- **`crossover`** - Multi-game campaigns (start minimal)

### Model Compatibility

✅ **Works with BOTH LM Studio and Ollama**

The embeddings are only for retrieval. Both models receive the same text chunks:
```
Query → Embedding → Vector Search → Text Chunks → LLM (LM Studio OR Ollama)
```

### Performance Impact

**Small campaign (5-10 books, ~5K chunks):**
- Retrieval: ~50-200ms
- Context size: ~3-5 chunks
- Token usage: Moderate

**Large campaign (50+ books, ~50K chunks):**
- Retrieval: ~500-2000ms ⚠️
- Context size: Often irrelevant chunks mixed in
- Token usage: Higher, less focused

**Recommendation:** Keep campaigns under 15 books for best performance.

## Generated Files

- `book-list.txt` - Complete list of all PDF files with their paths (auto-generated after each sync)
- `parsed/` - Directory containing parsed JSON files (one per PDF)
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
├── sync.sh              # 1. Sync script - downloads books
├── sync_wod_books.py    # Sync implementation
├── parse_books.py       # 2. Parser - extracts text + embeddings
├── import_to_rag.py     # 3. Importer - adds to vector DB
├── requirements.txt     # Python dependencies
├── README.md           # This file
├── venv/               # Virtual environment (auto-created)
├── book-list.txt       # Generated PDF list
├── parsed/             # Parsed JSON files (auto-created)
└── World of Darkness/  # Downloaded books (mirrors website)
```

**Workflow:**
1. `./sync.sh` → Download PDFs
2. `python parse_books.py --embeddings` → Parse + generate embeddings
3. `python import_to_rag.py --import-set vampire_basic --campaign-id 1` → Import selectively

Note: The `venv/` directory is automatically created and managed by the sync script.

