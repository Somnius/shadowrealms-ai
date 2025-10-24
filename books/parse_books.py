#!/usr/bin/env python3
"""
PDF Book Parser for RAG/Vector Database
Batch processes all PDFs in the books directory and outputs structured JSON
Optimized for multi-core processing and high performance
"""

import os
import sys
import json
import hashlib
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
from tqdm import tqdm
import pdfplumber
from multiprocessing import Pool, cpu_count, Manager
from functools import partial
import gc

# Optional GPU support for embeddings
try:
    import torch
    from sentence_transformers import SentenceTransformer
    GPU_AVAILABLE = torch.cuda.is_available()
except ImportError:
    GPU_AVAILABLE = False
    torch = None
    SentenceTransformer = None


def _process_single_pdf_worker(pdf_path: Path, books_dir: Path, output_dir: Path,
                                chunk_size: int, overlap: int, 
                                generate_embeddings: bool = False,
                                embedding_model_name: str = None) -> Dict[str, Any]:
    """
    Worker function for multiprocessing - processes a single PDF
    Must be a module-level function for pickling
    """
    result = {
        'filename': pdf_path.name,
        'success': False,
        'pages': 0,
        'chunks': 0,
        'embeddings_generated': False,
        'error': None
    }
    
    try:
        # Create a temporary parser instance for this worker
        parser = BookParser(
            books_dir, 
            output_dir,
            generate_embeddings=generate_embeddings,
            embedding_model_name=embedding_model_name
        )
        
        # Process the PDF
        data = parser.process_pdf(pdf_path, chunk_size, overlap)
        
        # Save the result
        parser.save_processed_data(pdf_path, data)
        
        # Update result
        result['success'] = True
        result['pages'] = data['processing_info']['total_pages']
        result['chunks'] = data['processing_info']['total_chunks']
        result['embeddings_generated'] = data['processing_info'].get('embeddings_generated', False)
        
        # Clean up memory
        del parser
        gc.collect()
        
    except Exception as e:
        result['error'] = str(e)
    
    return result


class BookParser:
    """Parses PDF books and chunks them for RAG/Vector database ingestion"""
    
    def __init__(self, books_dir, output_dir=None, generate_embeddings=False, 
                 embedding_model_name=None):
        self.books_dir = Path(books_dir)
        self.output_dir = Path(output_dir) if output_dir else self.books_dir / 'parsed'
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Embedding configuration
        self.generate_embeddings = generate_embeddings
        self.embedding_model = None
        self.embedding_model_name = embedding_model_name
        self.device = None
        
        if self.generate_embeddings:
            if not GPU_AVAILABLE:
                print("⚠️  Warning: GPU not available. Embeddings will be generated on CPU (slower).")
                self.device = 'cpu'
            else:
                self.device = 'cuda'
                print(f"✅ GPU detected: {torch.cuda.get_device_name(0)}")
            
            # Load embedding model
            if self.embedding_model_name is None:
                self.embedding_model_name = 'sentence-transformers/all-MiniLM-L6-v2'  # Fast, good quality
            
            print(f"📊 Loading embedding model: {self.embedding_model_name}")
            self.embedding_model = SentenceTransformer(self.embedding_model_name, device=self.device)
            print(f"   Model loaded on: {self.device}")
        
        # Processing statistics
        self.stats = {
            'total_pdfs': 0,
            'processed': 0,
            'skipped': 0,
            'failed': 0,
            'total_pages': 0,
            'total_chunks': 0,
            'total_embeddings': 0
        }
    
    def find_all_pdfs(self) -> List[Path]:
        """Find all PDF files in the books directory"""
        print("🔍 Scanning for PDF files...")
        pdfs = list(self.books_dir.rglob('*.pdf'))
        pdfs = sorted(pdfs)
        print(f"   Found {len(pdfs)} PDF files")
        return pdfs
    
    def get_output_path(self, pdf_path: Path) -> Path:
        """Get the output JSON path for a PDF"""
        # Create a unique identifier from the relative path
        relative_path = pdf_path.relative_to(self.books_dir)
        # Replace path separators with underscores and change extension
        output_name = str(relative_path).replace('/', '_').replace('\\', '_')
        output_name = output_name.replace('.pdf', '.json')
        return self.output_dir / output_name
    
    def is_already_processed(self, pdf_path: Path) -> bool:
        """Check if PDF has already been processed"""
        output_path = self.get_output_path(pdf_path)
        if not output_path.exists():
            return False
        
        # Check if the PDF has been modified since processing
        try:
            with open(output_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                processed_time = datetime.fromisoformat(data.get('processed_at', '2000-01-01'))
                pdf_modified = datetime.fromtimestamp(pdf_path.stat().st_mtime)
                return processed_time > pdf_modified
        except:
            return False
    
    def extract_text_from_pdf(self, pdf_path: Path, use_ocr: bool = False) -> List[Dict[str, Any]]:
        """Extract text from PDF with page information (optimized)"""
        pages_data = []
        
        try:
            # Open PDF with optimized settings
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)
                
                for page_num, page in enumerate(pdf.pages):
                    try:
                        # Extract text with optimized settings
                        text = page.extract_text(
                            x_tolerance=3,
                            y_tolerance=3,
                            layout=True
                        )
                        
                        if not text or not text.strip():
                            continue
                        
                        # Clean and process text
                        cleaned_text = self._clean_text(text)
                        
                        if not cleaned_text:
                            continue
                        
                        # Extract page metadata
                        page_info = {
                            'page_number': page_num + 1,
                            'text': cleaned_text,
                            'word_count': len(cleaned_text.split()),
                            'char_count': len(cleaned_text)
                        }
                        
                        pages_data.append(page_info)
                        
                    except Exception as page_error:
                        # Skip problematic pages but continue processing
                        continue
                    
                    # Memory cleanup for large PDFs
                    if page_num % 50 == 0 and page_num > 0:
                        gc.collect()
                        
        except Exception as e:
            raise Exception(f"Error extracting text: {e}")
        
        return pages_data
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize extracted text"""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove page numbers and headers/footers (standalone numbers)
        text = re.sub(r'^\d+\s*$', '', text, flags=re.MULTILINE)
        
        # Clean up common PDF artifacts while preserving punctuation
        text = re.sub(r'[^\w\s\.\,\!\?\;\:\-\(\)\[\]\{\}\"\'\/\&\#\@\$\%\+\=\*]', '', text)
        
        return text.strip()
    
    def chunk_text(self, pages_data: List[Dict[str, Any]], 
                   chunk_size: int = 1000, overlap: int = 200) -> List[Dict[str, Any]]:
        """Chunk text into manageable pieces for RAG (optimized)"""
        chunks = []
        
        # Pre-compile regex for better performance
        sentence_pattern = re.compile(r'(?<=[.!?])\s+')
        
        for page_data in pages_data:
            text = page_data['text']
            page_num = page_data['page_number']
            
            # Split into sentences (optimized)
            sentences = [s.strip() for s in sentence_pattern.split(text) if s.strip()]
            
            if not sentences:
                continue
            
            # Create chunks
            current_chunk = ""
            current_sentences = []
            
            for sentence in sentences:
                # Check if adding this sentence would exceed chunk size
                test_chunk = current_chunk + ' ' + sentence if current_chunk else sentence
                
                if len(test_chunk) > chunk_size and current_chunk:
                    # Save current chunk
                    chunk_text = current_chunk.strip()
                    chunks.append({
                        'text': chunk_text,
                        'page_number': page_num,
                        'sentence_count': len(current_sentences),
                        'word_count': len(chunk_text.split()),
                        'char_count': len(chunk_text),
                        'chunk_id': hashlib.md5(chunk_text.encode()).hexdigest()[:12]
                    })
                    
                    # Start new chunk with overlap
                    if overlap > 0 and len(current_sentences) >= 2:
                        overlap_sentences = current_sentences[-2:]
                        current_chunk = ' '.join(overlap_sentences) + ' ' + sentence
                        current_sentences = overlap_sentences + [sentence]
                    else:
                        current_chunk = sentence
                        current_sentences = [sentence]
                else:
                    current_chunk = test_chunk
                    current_sentences.append(sentence)
            
            # Add final chunk if it has content
            if current_chunk.strip():
                chunk_text = current_chunk.strip()
                chunks.append({
                    'text': chunk_text,
                    'page_number': page_num,
                    'sentence_count': len(current_sentences),
                    'word_count': len(chunk_text.split()),
                    'char_count': len(chunk_text),
                    'chunk_id': hashlib.md5(chunk_text.encode()).hexdigest()[:12]
                })
        
        return chunks
    
    def generate_embeddings_for_chunks(self, chunks: List[Dict[str, Any]], 
                                       batch_size: int = 32) -> List[Dict[str, Any]]:
        """Generate embeddings for chunks using GPU-accelerated model"""
        if not self.generate_embeddings or not self.embedding_model:
            return chunks
        
        # Extract texts for batch processing
        texts = [chunk['text'] for chunk in chunks]
        
        # Generate embeddings in batches (more efficient for GPU)
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i+batch_size]
            # Encode with show_progress_bar=False to avoid nested progress bars
            batch_embeddings = self.embedding_model.encode(
                batch_texts,
                show_progress_bar=False,
                convert_to_numpy=True
            )
            all_embeddings.extend(batch_embeddings.tolist())
        
        # Add embeddings to chunks
        for chunk, embedding in zip(chunks, all_embeddings):
            chunk['embedding'] = embedding
            chunk['embedding_dim'] = len(embedding)
        
        return chunks
    
    def get_book_metadata(self, pdf_path: Path) -> Dict[str, Any]:
        """Extract metadata about the book"""
        relative_path = pdf_path.relative_to(self.books_dir)
        
        # Try to extract book system/category from path
        path_parts = relative_path.parts
        system = path_parts[0] if len(path_parts) > 0 else 'unknown'
        category = path_parts[1] if len(path_parts) > 1 else 'general'
        
        return {
            'filename': pdf_path.name,
            'relative_path': str(relative_path),
            'system': system,
            'category': category,
            'file_size': pdf_path.stat().st_size,
            'file_modified': datetime.fromtimestamp(pdf_path.stat().st_mtime).isoformat()
        }
    
    def process_pdf(self, pdf_path: Path, chunk_size: int = 1000, 
                    overlap: int = 200) -> Dict[str, Any]:
        """Process a single PDF file"""
        # Extract text from PDF
        pages_data = self.extract_text_from_pdf(pdf_path)
        
        if not pages_data:
            raise Exception("No text could be extracted from PDF")
        
        # Chunk the text
        chunks = self.chunk_text(pages_data, chunk_size, overlap)
        
        # Generate embeddings if requested
        embeddings_generated = False
        if self.generate_embeddings:
            chunks = self.generate_embeddings_for_chunks(chunks)
            embeddings_generated = True
        
        # Get metadata
        metadata = self.get_book_metadata(pdf_path)
        
        # Create result
        result = {
            'metadata': metadata,
            'processing_info': {
                'processed_at': datetime.now().isoformat(),
                'chunk_size': chunk_size,
                'overlap': overlap,
                'total_pages': len(pages_data),
                'total_chunks': len(chunks),
                'total_words': sum(page['word_count'] for page in pages_data),
                'total_chars': sum(page['char_count'] for page in pages_data),
                'embeddings_generated': embeddings_generated,
                'embedding_model': self.embedding_model_name if embeddings_generated else None,
                'embedding_device': self.device if embeddings_generated else None
            },
            'chunks': chunks
        }
        
        return result
    
    def save_processed_data(self, pdf_path: Path, data: Dict[str, Any]):
        """Save processed data to JSON"""
        output_path = self.get_output_path(pdf_path)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def process_all(self, chunk_size: int = 1000, overlap: int = 200, 
                    force: bool = False, workers: Optional[int] = None):
        """Process all PDFs in the books directory (optimized with multiprocessing)"""
        pdfs = self.find_all_pdfs()
        self.stats['total_pdfs'] = len(pdfs)
        
        if not pdfs:
            print("No PDF files found to process.")
            return
        
        # Determine number of workers
        if workers is None:
            workers = max(1, cpu_count() - 1)  # Leave one core free
        
        print(f"\n📚 Processing {len(pdfs)} PDF files...")
        print(f"   Output directory: {self.output_dir}")
        print(f"   Chunk size: {chunk_size} chars, Overlap: {overlap} chars")
        print(f"   Workers: {workers} parallel processes")
        print()
        
        # Filter PDFs that need processing
        if not force:
            pdfs_to_process = []
            for pdf_path in pdfs:
                if not self.is_already_processed(pdf_path):
                    pdfs_to_process.append(pdf_path)
                else:
                    self.stats['skipped'] += 1
            
            print(f"   Found {self.stats['skipped']} already processed (skipping)")
            print(f"   Will process {len(pdfs_to_process)} PDFs\n")
        else:
            pdfs_to_process = pdfs
        
        if not pdfs_to_process:
            print("All PDFs already processed. Use --force to reprocess.")
            return
        
        # Create worker function with bound parameters
        worker_func = partial(
            _process_single_pdf_worker,
            books_dir=self.books_dir,
            output_dir=self.output_dir,
            chunk_size=chunk_size,
            overlap=overlap,
            generate_embeddings=self.generate_embeddings,
            embedding_model_name=self.embedding_model_name if self.generate_embeddings else None
        )
        
        # Process PDFs in parallel
        results = []
        with Pool(processes=workers) as pool:
            # Use imap_unordered for better performance
            for result in tqdm(
                pool.imap_unordered(worker_func, pdfs_to_process),
                total=len(pdfs_to_process),
                desc="Processing PDFs",
                unit="file"
            ):
                results.append(result)
                
                # Update statistics
                if result['success']:
                    self.stats['processed'] += 1
                    self.stats['total_pages'] += result['pages']
                    self.stats['total_chunks'] += result['chunks']
                    if result['embeddings_generated']:
                        self.stats['total_embeddings'] += result['chunks']
                    
                    emb_str = " (with embeddings)" if result['embeddings_generated'] else ""
                    tqdm.write(f"✅ {result['filename']}: {result['pages']} pages, {result['chunks']} chunks{emb_str}")
                else:
                    self.stats['failed'] += 1
                    tqdm.write(f"❌ Failed: {result['filename']} - {result['error']}")
                
                # Periodic garbage collection
                if len(results) % 10 == 0:
                    gc.collect()
    
    def print_summary(self):
        """Print processing summary"""
        print("\n" + "=" * 80)
        print("Processing Complete!")
        print("=" * 80)
        print(f"Total PDFs found:    {self.stats['total_pdfs']}")
        print(f"Newly processed:     {self.stats['processed']}")
        print(f"Skipped (cached):    {self.stats['skipped']}")
        print(f"Failed:              {self.stats['failed']}")
        print(f"Total pages:         {self.stats['total_pages']}")
        print(f"Total chunks:        {self.stats['total_chunks']}")
        if self.generate_embeddings:
            print(f"Total embeddings:    {self.stats['total_embeddings']}")
            print(f"Embedding device:    {self.device}")
        print(f"\nOutput directory:    {self.output_dir}")
        print("=" * 80)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Parse PDF books for RAG/Vector database ingestion (Multi-core optimized)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  # Process all PDFs with default settings
  python parse_books.py
  
  # Use all CPU cores
  python parse_books.py --workers {cpu_count()}
  
  # Generate embeddings with GPU acceleration (recommended!)
  python parse_books.py --embeddings
  
  # Use a different embedding model
  python parse_books.py --embeddings --embedding-model sentence-transformers/all-mpnet-base-v2
  
  # Full power: all cores + GPU embeddings + large chunks
  python parse_books.py --workers {cpu_count()} --embeddings --chunk-size 1500 --overlap 300
  
  # Reprocess everything with embeddings
  python parse_books.py --force --embeddings
  
  # Process specific directory
  python parse_books.py --books-dir /path/to/books --embeddings
  
GPU Support:
  Install: pip install torch sentence-transformers
  {'✅ GPU Available' if GPU_AVAILABLE else '❌ GPU Not Detected'}
        """
    )
    parser.add_argument(
        '--books-dir',
        type=str,
        default=None,
        help='Directory containing PDF books (default: script directory)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default=None,
        help='Output directory for parsed JSON files (default: books-dir/parsed)'
    )
    parser.add_argument(
        '--chunk-size',
        type=int,
        default=1000,
        help='Maximum characters per chunk (default: 1000)'
    )
    parser.add_argument(
        '--overlap',
        type=int,
        default=200,
        help='Characters overlap between chunks (default: 200)'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=None,
        help=f'Number of parallel workers (default: {max(1, cpu_count() - 1)})'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Reprocess all PDFs even if already processed'
    )
    parser.add_argument(
        '--embeddings',
        action='store_true',
        help='Generate embeddings for chunks (GPU-accelerated if available)'
    )
    parser.add_argument(
        '--embedding-model',
        type=str,
        default='sentence-transformers/all-MiniLM-L6-v2',
        help='Embedding model to use (default: all-MiniLM-L6-v2, fast and good quality)'
    )
    parser.add_argument(
        '--embedding-batch-size',
        type=int,
        default=32,
        help='Batch size for embedding generation (default: 32)'
    )
    
    args = parser.parse_args()
    
    # Check GPU availability if embeddings requested
    if args.embeddings and not GPU_AVAILABLE:
        print("⚠️  Warning: GPU libraries not available. Install torch and sentence-transformers for GPU support:")
        print("   pip install torch sentence-transformers")
        print("   Continuing with CPU (will be slower)...")
        print()
    
    # Determine books directory
    if args.books_dir:
        books_dir = Path(args.books_dir)
    else:
        # Use script directory
        books_dir = Path(__file__).parent
    
    # Create parser
    parser_instance = BookParser(
        books_dir, 
        args.output_dir,
        generate_embeddings=args.embeddings,
        embedding_model_name=args.embedding_model if args.embeddings else None
    )
    
    print("=" * 80)
    print("PDF Book Parser for RAG/Vector Database")
    print("=" * 80)
    print(f"Books directory: {books_dir}")
    if args.embeddings:
        print(f"Embedding model: {args.embedding_model}")
        print(f"Device: {'GPU (CUDA)' if GPU_AVAILABLE else 'CPU'}")
    print("=" * 80)
    print()
    
    try:
        # Process all PDFs
        parser_instance.process_all(
            chunk_size=args.chunk_size,
            overlap=args.overlap,
            force=args.force,
            workers=args.workers
        )
        
        # Print summary
        parser_instance.print_summary()
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Processing interrupted by user")
        print(f"Processed so far: {parser_instance.stats['processed']} files")
        parser_instance.print_summary()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

