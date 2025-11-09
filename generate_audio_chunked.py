#!/usr/bin/env python3
"""
Generate audio files for translated chapters with chunking by paragraphs and rate limiting
"""

import os
import sys
import time
from pathlib import Path
from openai import AzureOpenAI
from dotenv import load_dotenv
import logging
from collections import deque

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()

# Configuration
TRANSLATIONS_DIR = Path('output/translations')
AUDIO_DIR = Path('output/audio')
TTS_MODEL = os.getenv('TTS_MODEL', 'tts-1-hd')
TTS_VOICE = os.getenv('TTS_VOICE', 'nova')
QPM = int(os.getenv('TTS_QPM', 5))  # Queries per minute
MAX_RETRIES = 3
MAX_CHUNK_SIZE = 4000  # Max characters per chunk (API limit ~4096)

# Create output directory
AUDIO_DIR.mkdir(parents=True, exist_ok=True)


class RateLimiter:
    """Rate limiter to ensure we don't exceed QPM limits"""

    def __init__(self, qpm):
        self.qpm = qpm
        self.min_delay = 60.0 / qpm  # 12 seconds for QPM=5
        self.request_times = deque(maxlen=qpm)
        logger.info(f"Rate limiter: QPM={qpm}, Min delay={self.min_delay:.2f}s")

    def wait_if_needed(self):
        """Wait if necessary to respect rate limits"""
        now = time.time()

        # Check minimum delay since last request
        if len(self.request_times) > 0:
            last_request = self.request_times[-1]
            time_since_last = now - last_request

            if time_since_last < self.min_delay:
                sleep_time = self.min_delay - time_since_last
                logger.info(f"  Rate limiting: sleeping {sleep_time:.2f}s")
                time.sleep(sleep_time)
                now = time.time()

        # Check QPM limit (sliding window)
        if len(self.request_times) >= self.qpm:
            oldest_request = self.request_times[0]
            time_since_oldest = now - oldest_request

            if time_since_oldest < 60.0:
                sleep_time = 60.0 - time_since_oldest
                logger.info(f"  Rate limiting: sleeping {sleep_time:.2f}s (QPM limit)")
                time.sleep(sleep_time)
                now = time.time()

        self.request_times.append(now)


def init_client():
    """Initialize Azure OpenAI client for TTS"""
    api_key = os.getenv('TTS_API_KEY')
    if not api_key:
        raise ValueError("No TTS API key found. Set TTS_API_KEY in .env")

    client = AzureOpenAI(
        azure_endpoint='https://search.bytedance.net/gpt/openapi/online/v2/crawl/openai/deployments/gpt_openapi',
        api_key=api_key,
        api_version='preview',
        timeout=1200,
        max_retries=3
    )
    return client


def split_by_paragraphs(text: str, max_chunk_size: int = MAX_CHUNK_SIZE) -> list:
    """
    Split text into chunks by paragraph boundaries
    Each chunk contains complete paragraphs and doesn't exceed max_chunk_size
    """
    # Split by double newline (paragraph boundary)
    paragraphs = text.split('\n\n')

    chunks = []
    current_chunk = []
    current_size = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        para_size = len(para)

        # If single paragraph is too large, we have to split it
        if para_size > max_chunk_size:
            # Save current chunk if exists
            if current_chunk:
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = []
                current_size = 0

            # Split the large paragraph by sentences
            sentences = []
            for delimiter in ['。', '！', '？', '.', '!', '?']:
                if delimiter in para:
                    sentences = para.split(delimiter)
                    sentences = [s + delimiter for s in sentences[:-1]] + [sentences[-1]]
                    break

            if not sentences:
                sentences = [para]

            # Group sentences into chunks
            temp_chunk = []
            temp_size = 0
            for sent in sentences:
                if temp_size + len(sent) > max_chunk_size and temp_chunk:
                    chunks.append(''.join(temp_chunk))
                    temp_chunk = [sent]
                    temp_size = len(sent)
                else:
                    temp_chunk.append(sent)
                    temp_size += len(sent)

            if temp_chunk:
                chunks.append(''.join(temp_chunk))

        # If adding this paragraph exceeds limit, save current chunk
        elif current_size + para_size + 2 > max_chunk_size:  # +2 for \n\n
            if current_chunk:
                chunks.append('\n\n'.join(current_chunk))
            current_chunk = [para]
            current_size = para_size

        # Add paragraph to current chunk
        else:
            current_chunk.append(para)
            current_size += para_size + 2  # +2 for \n\n

    # Add remaining chunk
    if current_chunk:
        chunks.append('\n\n'.join(current_chunk))

    return chunks


def generate_audio_chunk(client, rate_limiter, text: str, output_path: Path) -> bool:
    """Generate audio for a single text chunk"""

    for attempt in range(MAX_RETRIES):
        try:
            # Wait if needed to respect rate limits
            rate_limiter.wait_if_needed()

            # Record start time
            start_time = time.time()

            # Generate audio
            with client.audio.speech.with_streaming_response.create(
                model=TTS_MODEL,
                voice=TTS_VOICE,
                input=text
            ) as response:
                response.stream_to_file(str(output_path))

            # Record end time
            duration = time.time() - start_time
            file_size = output_path.stat().st_size

            logger.info(f"    ✓ Generated in {duration:.2f}s ({file_size/1024:.1f} KB)")
            return True

        except Exception as e:
            logger.error(f"    Attempt {attempt + 1} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                sleep_time = 2 ** attempt
                logger.info(f"    Retrying in {sleep_time}s...")
                time.sleep(sleep_time)
            else:
                logger.error(f"    ✗ Failed to generate audio chunk")
                return False

    return False


def merge_audio_files(chapter_num: int, num_parts: int) -> bool:
    """Merge audio parts into a single file using simple concatenation"""
    part_files = [AUDIO_DIR / f'chapter_{chapter_num:02d}_part{i:02d}.mp3'
                  for i in range(1, num_parts + 1)]

    # Check all parts exist
    if not all(f.exists() for f in part_files):
        logger.error("  Not all audio parts exist, skipping merge")
        return False

    full_file = AUDIO_DIR / f'chapter_{chapter_num:02d}_full.mp3'

    logger.info(f"  Merging {num_parts} parts into {full_file.name}...")

    # Simple concatenation (works for MP3)
    with open(full_file, 'wb') as outfile:
        for part_file in part_files:
            with open(part_file, 'rb') as infile:
                outfile.write(infile.read())

    file_size = full_file.stat().st_size / (1024 * 1024)  # MB

    # Calculate total duration (estimate: ~192 kbps bitrate)
    duration_minutes = (file_size * 8 * 1024) / (192 * 60)

    logger.info(f"  ✓ Merged audio: {full_file.name} ({file_size:.2f} MB, ~{duration_minutes:.2f} min)")
    return True


def generate_audio_for_chapter(client, rate_limiter, chapter_num: int, text: str) -> bool:
    """Generate audio file(s) for a chapter with paragraph-based chunking"""
    logger.info(f"\nGenerating audio for Chapter {chapter_num}...")
    logger.info(f"  Text length: {len(text):,} characters")

    # Remove markdown formatting for cleaner audio
    clean_text = text.replace('#', '').replace('*', '').strip()

    # Split by paragraphs
    chunks = split_by_paragraphs(clean_text)
    logger.info(f"  Split into {len(chunks)} chunks by paragraph boundaries")

    chunk_files = []
    success_count = 0

    for idx, chunk in enumerate(chunks, 1):
        logger.info(f"  Chunk {idx}/{len(chunks)}: {len(chunk):,} chars...")

        # Output path for this chunk
        if len(chunks) == 1:
            output_path = AUDIO_DIR / f"chapter_{chapter_num:02d}.mp3"
        else:
            output_path = AUDIO_DIR / f"chapter_{chapter_num:02d}_part{idx:02d}.mp3"

        # Check if already exists
        if output_path.exists():
            logger.info(f"    ✓ Already exists: {output_path.name}")
            chunk_files.append(output_path)
            success_count += 1
            continue

        # Generate audio for this chunk
        success = generate_audio_chunk(client, rate_limiter, chunk, output_path)

        if success:
            chunk_files.append(output_path)
            success_count += 1
        else:
            logger.error(f"    ✗ Failed chunk {idx}")

    # Summary
    if success_count == len(chunks):
        logger.info(f"  ✓ All {len(chunks)} chunks generated!")
        if len(chunks) > 1:
            total_size = sum(f.stat().st_size for f in chunk_files)
            logger.info(f"  Total size: {total_size/1024/1024:.2f} MB")

            # Merge parts into full file
            merge_audio_files(chapter_num, len(chunks))
        return True
    else:
        logger.error(f"  ✗ Only {success_count}/{len(chunks)} chunks generated")
        return False


def main():
    """Main entry point"""
    # Parse arguments (chapter number)
    if len(sys.argv) > 1:
        try:
            chapter_num = int(sys.argv[1])
            logger.info(f"Processing Chapter {chapter_num} only\n")
            chapter_files = [TRANSLATIONS_DIR / f"chapter_{chapter_num:02d}_cn.md"]
            if not chapter_files[0].exists():
                logger.error(f"Chapter {chapter_num} translation file not found!")
                sys.exit(1)
        except ValueError:
            logger.error(f"Invalid chapter number: {sys.argv[1]}")
            sys.exit(1)
    else:
        logger.error("Please specify a chapter number: python generate_audio_chunked.py <chapter_num>")
        sys.exit(1)

    # Initialize client and rate limiter
    logger.info("="*60)
    logger.info("TTS Audio Generation (Paragraph-based Chunking)")
    logger.info("="*60)
    logger.info(f"Model: {TTS_MODEL}, Voice: {TTS_VOICE}")
    logger.info(f"Max chunk size: {MAX_CHUNK_SIZE:,} characters")
    logger.info(f"Rate limit: QPM={QPM}")

    client = init_client()
    rate_limiter = RateLimiter(QPM)

    # Process chapter
    start_time = time.time()
    chapter_file = chapter_files[0]
    chapter_num = int(chapter_file.stem.split('_')[1])

    text = chapter_file.read_text(encoding='utf-8')
    success = generate_audio_for_chapter(client, rate_limiter, chapter_num, text)

    total_time = time.time() - start_time

    logger.info("\n" + "="*60)
    if success:
        logger.info(f"✓ Chapter {chapter_num} audio complete!")
    else:
        logger.error(f"✗ Chapter {chapter_num} audio failed!")
    logger.info(f"Total time: {total_time/60:.2f} minutes")
    logger.info(f"Audio files saved to: {AUDIO_DIR}")
    logger.info("="*60)


if __name__ == '__main__':
    main()
