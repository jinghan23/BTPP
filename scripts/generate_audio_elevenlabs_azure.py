#!/usr/bin/env python3
"""
Generate audio using ElevenLabs TTS via Azure OpenAI endpoint
"""

import os
import sys
import time
from pathlib import Path
from collections import deque
from dotenv import load_dotenv
import logging
from typing import List
from openai import AzureOpenAI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()

# Directories
TRANSLATIONS_DIR = Path('output/translations')
AUDIO_DIR = Path('output/audio_elevenlabs')
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

# Configuration
MAX_CHUNK_SIZE = 4000  # Characters per chunk
MAX_RETRIES = 3

# Azure OpenAI Configuration
TTS_API_KEY = os.getenv('TTS_API_KEY', '')
TTS_MODEL = 'elevenlabs'  # Try "elevenlabs" as the model name
TTS_VOICE = os.getenv('ELEVENLABS_VOICE', 'nova')  # Voice name

# Rate limiting
QPM = int(os.getenv('TTS_QPM', '5'))


class RateLimiter:
    """Rate limiter to ensure we don't exceed QPM limits"""
    def __init__(self, qpm):
        self.qpm = qpm
        self.min_delay = 60.0 / qpm
        self.request_times = deque(maxlen=qpm)

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

        self.request_times.append(now)


def split_by_paragraphs(text: str, max_chunk_size: int = MAX_CHUNK_SIZE) -> List[str]:
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
                sent_size = len(sent)
                if temp_size + sent_size > max_chunk_size and temp_chunk:
                    chunks.append(''.join(temp_chunk))
                    temp_chunk = [sent]
                    temp_size = sent_size
                else:
                    temp_chunk.append(sent)
                    temp_size += sent_size

            if temp_chunk:
                chunks.append(''.join(temp_chunk))

            continue

        # Check if adding this paragraph exceeds limit
        if current_size + para_size + 2 > max_chunk_size and current_chunk:  # +2 for \n\n
            # Save current chunk and start new one
            chunks.append('\n\n'.join(current_chunk))
            current_chunk = [para]
            current_size = para_size
        else:
            current_chunk.append(para)
            current_size += para_size + 2  # +2 for \n\n

    # Don't forget the last chunk
    if current_chunk:
        chunks.append('\n\n'.join(current_chunk))

    return chunks


def generate_audio_chunk(client, text: str, output_file: Path) -> bool:
    """Generate audio for a single chunk using Azure OpenAI TTS"""

    for attempt in range(MAX_RETRIES):
        try:
            logger.info(f"  Generating audio ({len(text)} chars)...")

            # Call Azure OpenAI TTS API with "elevenlabs" model
            response = client.audio.speech.create(
                model=TTS_MODEL,
                voice=TTS_VOICE,
                input=text
            )

            # Write audio to file
            response.stream_to_file(output_file)

            file_size = output_file.stat().st_size / (1024 * 1024)  # MB
            logger.info(f"  ✓ Saved: {output_file.name} ({file_size:.2f} MB)")
            return True

        except Exception as e:
            logger.error(f"  Attempt {attempt + 1} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
            else:
                logger.error(f"  Failed to generate audio after {MAX_RETRIES} attempts")
                return False

    return False


def merge_audio_files(chapter_num: int, num_parts: int):
    """Merge audio parts into a single file using simple concatenation"""
    part_files = [AUDIO_DIR / f'chapter_{chapter_num:02d}_part{i:02d}.mp3'
                  for i in range(1, num_parts + 1)]

    # Check all parts exist
    if not all(f.exists() for f in part_files):
        logger.error("Not all audio parts exist, skipping merge")
        return

    full_file = AUDIO_DIR / f'chapter_{chapter_num:02d}_full.mp3'

    logger.info(f"Merging {num_parts} audio files...")

    # Simple concatenation (works for MP3)
    with open(full_file, 'wb') as outfile:
        for part_file in part_files:
            with open(part_file, 'rb') as infile:
                outfile.write(infile.read())

    file_size = full_file.stat().st_size / (1024 * 1024)  # MB
    logger.info(f"✓ Merged audio saved: {full_file.name} ({file_size:.2f} MB)")


def generate_chapter_audio(client, chapter_num: int):
    """Generate audio for a chapter with chunking"""

    # Read translation
    trans_file = TRANSLATIONS_DIR / f'chapter_{chapter_num:02d}_cn.md'
    if not trans_file.exists():
        logger.error(f"Translation file not found: {trans_file}")
        return

    text = trans_file.read_text(encoding='utf-8')

    # Skip title (first line)
    lines = text.split('\n', 1)
    if len(lines) > 1:
        text = lines[1]

    logger.info(f"\n{'='*60}")
    logger.info(f"Generating audio for Chapter {chapter_num}")
    logger.info(f"Text length: {len(text)} characters")
    logger.info(f"{'='*60}\n")

    # Split into chunks
    chunks = split_by_paragraphs(text, MAX_CHUNK_SIZE)
    logger.info(f"Split into {len(chunks)} chunks")

    # Initialize rate limiter
    rate_limiter = RateLimiter(QPM)

    # Generate audio for each chunk
    for i, chunk in enumerate(chunks, 1):
        logger.info(f"\nChunk {i}/{len(chunks)}:")

        output_file = AUDIO_DIR / f'chapter_{chapter_num:02d}_part{i:02d}.mp3'

        # Skip if already exists
        if output_file.exists():
            logger.info(f"  Skipping (already exists): {output_file.name}")
            continue

        # Rate limiting
        rate_limiter.wait_if_needed()

        # Generate audio
        success = generate_audio_chunk(client, chunk, output_file)

        if not success:
            logger.error(f"Failed to generate chunk {i}, stopping")
            return

    # Merge all parts into full audio
    logger.info("")
    merge_audio_files(chapter_num, len(chunks))

    logger.info(f"\n✓ Chapter {chapter_num} audio generation complete!")


def main():
    """Main entry point"""

    # Check for API key
    if not TTS_API_KEY:
        logger.error("TTS_API_KEY not found in .env file")
        sys.exit(1)

    # Get chapter number from command line
    if len(sys.argv) < 2:
        logger.error("Usage: python generate_audio_elevenlabs_azure.py <chapter_num>")
        sys.exit(1)

    chapter_num = int(sys.argv[1])

    try:
        # Initialize Azure OpenAI client for ElevenLabs (multimodal endpoint)
        logger.info("Initializing Azure OpenAI client for ElevenLabs...")
        client = AzureOpenAI(
            azure_endpoint='https://bytedance.net/gpt/openapi/online/v2/multimodal/openai/deployments/gpt_openapi',
            api_key=TTS_API_KEY,
            api_version='preview',
            timeout=600,
            max_retries=3
        )

        logger.info(f"TTS Model: {TTS_MODEL}")
        logger.info(f"Voice: {TTS_VOICE}")
        logger.info(f"Rate limit: {QPM} requests/minute")
        logger.info(f"Output directory: {AUDIO_DIR}")

        # Generate audio
        generate_chapter_audio(client, chapter_num)

    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
