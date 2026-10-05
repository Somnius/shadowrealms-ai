# World of Darkness Books Sync

This directory contains the World of Darkness books synchronized from a configured book source (see `.env` file).

## Setup

No manual setup required! The sync script automatically creates and manages its own virtual environment.

### Local bulk archive (`World_of_Darkness.tar`)

If you keep a **full offline mirror** as a single tarball, store it at **`data/World_of_Darkness.tar`** (the entire `data/` tree is gitignored). Do not commit large archives under `books/`.

- If you still have `books/World_of_Darkness.tar` from an older layout, run from the repo root:
  - Ensure `data/` is writable by your user (Docker sometimes creates it as root):  
    `sudo chown -R "$USER:$USER" data`
  - Then: `./scripts/move-wod-archive-to-data.sh`

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
- ✅ **Auto-Retry**: Retries failed downloads 3 times with exponential backoff (2s, 4s, 8s)
- ✅ **Rate Limiting**: 1 second delay between downloads to avoid overwhelming server
- ✅ **Smart Skipping**: Skips files that already exist with matching size
- ✅ **Progress Bars**: Shows progress for each file download (no verbose output)
- ✅ **Directory Structure**: Preserves the exact directory structure locally
- ✅ **All File Types**: Downloads PDFs, HTML, images, and all other files
- ✅ **HTML Rewriting**: Converts index.html files to use local paths
- ✅ **Book List**: Generates `book-list.txt` with all PDF files and paths
- ✅ **Hash-Based Duplicate Detection**: Uses MD5 hashes to accurately identify truly identical files
- ✅ **Interactive Cleanup**: Asks which duplicate to keep before deletion
- ✅ **Persistent Choices**: Remembers your duplicate resolution choices for future runs (no repeated prompts)

## Duplicate Detection

The sync script includes intelligent duplicate detection that runs after syncing files.

### How It Works

1. **Hash-Based Comparison**: Calculates MD5 hash of each file to determine if files are truly identical
2. **Smart Detection**: Identifies files with the same name in different directories
3. **Content Verification**: Shows you which duplicates have identical content vs different versions
4. **Interactive Cleanup**: Asks you to choose which duplicate to keep
5. **Persistent Choices**: Saves your decisions in `.duplicate_choices.json` for future runs

### Duplicate Resolution

When duplicates are found, you'll be prompted with:
```
📄 Duplicate: vampire - the masquerade.pdf
   Found in 2 locations:

   [1] Classic World of Darkness/Vampire/Vampire - The Masquerade.pdf
       Size: 26.61 MB (27,899,891 bytes)
       Hash: a1b2c3d4e5f6g7h8...
   [2] oWoD/Vampire - The Masquerade.pdf
       Size: 26.61 MB (27,899,891 bytes)
       Hash: a1b2c3d4e5f6g7h8...

   ✅ All files have identical content (same hash)

   Options:
     1 - Keep this one, delete others
     2 - Keep this one, delete others
     a - Keep all (skip)
     q - Quit duplicate handling

   Your choice [1-2/a/q]:
```

### Persistent Choices

Your choices are automatically saved to `.duplicate_choices.json`. The next time you run the sync script:
- **Previously resolved duplicates won't be shown again**
- **Automatic cleanup** happens based on your saved preferences
- **Only new duplicates** will prompt you for input
- **Hash verification** ensures files haven't changed before auto-applying saved choices

To reset your choices, simply delete `.duplicate_choices.json` in the books directory.

## Importing rule books

`import_books.py` puts the official rule books into ChromaDB for Laya's rules answers. It is a plain script (PyMuPDF and fixed rules); no AI reads the books. What it writes is described in `docs/rules/RULE_BOOKS_RAG.md`: `rule_books_v5`, `rule_books_classic`, and `rule_books_chronicle` for adventures attached to one chronicle.

Install the deps once (`pip install -r books/requirements.txt`), then from the repo root:

```bash
python books/import_books.py extract                 # PDF -> blocks, cached in data/rule_books/cache (keyed by file sha256)
python books/import_books.py chunk --dry-run         # chunk everything, print the summary table (also data/rule_books/chunk_summary.md)
python books/import_books.py import --only v5-corebook,v5-players-guide   # or --edition v5, or --all
python books/import_books.py status --chroma
python books/import_books.py eval --only v5-corebook                        # sampled headings
python books/import_books.py eval --questions books/eval_questions.yaml     # hand-written questions
python books/import_books.py attach --book v5-fall-of-london --campaign 12   # an adventure, for chronicle 12 only
python books/import_books.py delete --book v5-camarilla                      # add --campaign N for an attached book
```

Options (before or after the command): `--only id,id`, `--edition v5|classic`, `--dry-run` (no Chroma, no state file), `--chroma-host/--chroma-port` (default `CHROMADB_HOST`/`CHROMADB_PORT`, else localhost:8000), `--lmstudio-url` (default `LM_STUDIO_URL`, else localhost:1234; the model is `EMBEDDING_MODEL`, default bge-m3), `--batch 64`, `--pace-ms 200`, `--no-resume`, `--force`, `--workers 4` (max 8), `--tokenizer auto|bge-m3|estimate`. `RULE_BOOKS_ROOT` points at the books folder if it isn't `books/World_of_Darkness`.

- **Embedding** goes through the backend's own `services.vector_store` (same embedding function and collection settings), so the backend reads the collections without a re-embed. LM Studio is shared with the live app: imports go in batches with a pause between them (`--pace-ms`).
- **Resumable:** `data/rule_books/state.json` keeps, per book, the file hash, the chunk set hash, how many chunks are in and the timings. Ids are deterministic (`book_id:00042`) and written with upsert, so a stopped import just continues. If a book's chunks change (new PDF, new manifest settings, new importer version), the old chunks are removed first. A book marked done is still counted in Chroma, and imported again when chunks are missing (e.g. after the admin delete). If Chroma or LM Studio is down, the command stops with a one-line error and the book is marked `error`/`partial`; run it again to resume.
- **Token counts** use the bge-m3 tokenizer (`tokenizers` and its `tokenizer.json` from the Hugging Face cache, or `BGE_M3_TOKENIZER`). Chunk ids depend on the counts, so `import`/`attach` refuse to fall back to the words × 1.35 estimate unless you pass `--tokenizer estimate`.
- **Kinds:** rules books give `rules`, `sidebar`, `example` and `fiction` chunks; every chunk of a lore book is `lore` and of an adventure `adventure`.
- **Adventures** (`kind: adventure`) are never imported globally; `attach` puts one into `rule_books_chronicle` with that chronicle's `campaign_id` (ids get a `c<id>:` prefix). Other books need `--force` to be attached.
- **Image-only PDFs** (scans without a text layer) are found automatically, skipped and listed. No OCR for now.
- **Duplicates:** a chunk whose text is already in a higher-precedence book of the same edition is skipped. When a higher-precedence book's chunks change, the books below it in that edition are chunked again on the next import (imports run in precedence order).
- **eval** has two modes; reports go to `data/rule_books/eval/`.
  - Default: up to 40 outline headings per imported book (seeded), each asked as is and as "How does X work?", scored hit@1/3/5 and MRR against that section's pages, plus edition leaks and (Classic) line leaks. The query is the heading itself, so this mostly checks the plumbing (sections, pages, filters, leaks), not how well real questions are answered.
  - `--questions books/eval_questions.yaml`: about 50 hand-written questions taken from the repo's rules specs (`docs/rules/V5.md`, `docs/rules/CLASSIC_REVISED.md`); gold is the printed core page those specs cite, ±1. This is the better measure of retrieval quality. `--check` only validates the file.

### The manifest (`books/manifest.yaml`)

One entry per book. Required: `book_id` (slug), `path` (relative to `books/World_of_Darkness`), `title`, `edition` (`v5`/`classic`), `line` (`vampire`/`werewolf`/`mage`/`all`), `version` (`v5`/`revised`), `kind` (`rules`/`lore`/`adventure`), `precedence` (lower wins), `year` (0 = not printed in the PDF). Optional:

- `include` / `exclude`: PDF page ranges, e.g. `exclude: 431-436`
- `page_offset`: printed page = PDF page + offset, when the PDF has no page labels and no printed page numbers the script can find
- `strip_lines`: regexes for lines to drop (web-capture headers, stamps)
- `sidebar_fonts`: regexes for the sidebar font (V5 default: Gill Sans / Futura / IBM Plex Sans)
- `toc_fixes`: typo fixes for outline titles, e.g. `{Venture: Ventrue}`
- `outline`: `auto` (PDF outline, else headings by font size), `toc`, `sizes` or `none`
- `toc`: an outline to use instead of the PDF's, as `[level, title, pdf_page]` entries (a long top-level title the PDF outline repeats is dropped automatically, with a warning)
- `page_map_from`: another copy of the same book that has printed page numbers; each paragraph takes the printed page of the matching page there (the text-only VtM Revised core uses the scan)
- `skip_sections`: regexes for sections to leave out (default: contents, index, credits)
- `notes`

The `excluded:` list at the end records files left out on purpose and why. To add a book: add an entry, run `chunk --dry-run --only <id>` and check its row in the table (pages, chunks, % with a heading path, kinds, warnings), then `import --only <id>`.

Tests (synthetic PDFs only, no book text): `python -m pytest -q books/tests`.

## Generated Files

- `book-list.txt` - Complete list of all PDF files with their paths (auto-generated after each sync)
- `index.html` - Directory listings (rewritten to work locally)
- All downloaded books and files in their original directory structure

## Handling Duplicates

After sync completes, the script will automatically check for duplicate files (same filename in different directories).

**What happens:**

1. Script scans all PDFs and finds files with the same name
2. Shows you all versions with their locations and sizes
3. Asks which one to keep (or keep all)
4. Deletes the ones you don't want

**Example interaction:**
```
📄 Duplicate: Vampire The Masquerade.pdf
   Found in 2 locations:

   [1] Classic World of Darkness/Vampire/Vampire The Masquerade.pdf
       Size: 25.60 MB (26,843,545 bytes)
   
   [2] oWoD/Core Books/Vampire The Masquerade.pdf
       Size: 25.60 MB (26,843,545 bytes)

   ℹ️  All files have identical size - likely the same content

   Options:
     1 - Keep this one, delete others
     2 - Keep this one, delete others
     a - Keep all (skip)
     q - Quit duplicate handling

   Your choice [1-2/a/q]: 1
```

**Options:**
- **1, 2, etc.** - Keep that version, delete all others
- **a** - Keep all versions (skip this duplicate)
- **q** - Stop duplicate checking (keep remaining duplicates)

## Running Periodically

You can run the sync script anytime to check for new additions. It will:
- Skip existing files (if size matches)
- Download only new files
- Update the book-list.txt
- Check for duplicates (interactive)

Example cron job to sync daily at 2 AM:
```bash
0 2 * * * cd /path/to/shadowrealms-ai/books && ./sync.sh >> sync.log 2>&1
```

**Note:** For automated runs (cron), duplicates won't be handled interactively. Run manually when needed to clean up duplicates.

## Statistics

After each sync, you'll see:
- Number of files downloaded
- Number of files skipped (already up to date)
- Number of failed downloads
- Total time taken

## Interrupting

You can safely interrupt the sync (Ctrl+C) at any time. Just run it again to resume where it left off.

## Directory Structure

```
books/
├── sync.sh              # sync: downloads the books
├── sync_wod_books.py    # sync implementation
├── import_books.py      # rule-book importer (see "Importing rule books")
├── rbimport/            # the importer's code
├── manifest.yaml        # which books are imported, and how
├── eval_questions.yaml  # hand-written retrieval questions
├── tests/               # importer tests (synthetic PDFs)
├── requirements.txt     # Python dependencies
├── README.md            # this file
├── venv/                # virtual environment of sync.sh (auto-created)
├── book-list.txt        # generated PDF list
└── World_of_Darkness/   # downloaded books (mirrors the source)
```

Workflow: `./sync.sh` to download, then `python books/import_books.py chunk --dry-run` and `import` (see above).
