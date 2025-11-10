#!/usr/bin/env python3
"""
Generate audio files for translated chapters with rate limiting
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
TPM = int(os.getenv('TTS_TPM', 1000))  # Tokens per minute
MAX_RETRIES = 3

# Calculate minimum delay between requests (60 seconds / QPM)
MIN_DELAY = 60.0 / QPM  # 12 seconds for QPM=5

# Create output directory
AUDIO_DIR.mkdir(parents=True, exist_ok=True)


class RateLimiter:
    """Rate limiter to ensure we don't exceed QPM limits"""

    def __init__(self, qpm):
        self.qpm = qpm
        self.min_delay = 60.0 / qpm
        self.request_times = deque(maxlen=qpm)
        logger.info(f"Rate limiter initialized: QPM={qpm}, Min delay={self.min_delay:.2f}s")

    def wait_if_needed(self):
        """Wait if necessary to respect rate limits"""
        now = time.time()

        # If we haven't made QPM requests yet, just check the last request
        if len(self.request_times) > 0:
            last_request = self.request_times[-1]
            time_since_last = now - last_request

            if time_since_last < self.min_delay:
                sleep_time = self.min_delay - time_since_last
                logger.info(f"  Rate limiting: sleeping {sleep_time:.2f}s (last request {time_since_last:.2f}s ago)")
                time.sleep(sleep_time)
                now = time.time()

        # If we've made QPM requests, check the oldest one
        if len(self.request_times) >= self.qpm:
            oldest_request = self.request_times[0]
            time_since_oldest = now - oldest_request

            if time_since_oldest < 60.0:
                sleep_time = 60.0 - time_since_oldest
                logger.info(f"  Rate limiting: sleeping {sleep_time:.2f}s (QPM limit reached)")
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


def generate_audio_for_chapter(client, rate_limiter, chapter_num: int, text: str) -> bool:
    """Generate audio file for a chapter with rate limiting"""
    logger.info(f"Generating audio for Chapter {chapter_num}...")
    logger.info(f"  Text length: {len(text)} characters")

    output_path = AUDIO_DIR / f"chapter_{chapter_num:02d}.mp3"

    # Check if already exists
    if output_path.exists():
        logger.info(f"  ✓ Audio already exists: {output_path}")
        return True

    for attempt in range(MAX_RETRIES):
        try:
            # Wait if needed to respect rate limits
            rate_limiter.wait_if_needed()

            # Record start time
            start_time = time.time()
            logger.info(f"  Calling TTS API (model={TTS_MODEL}, voice={TTS_VOICE})...")

            # Generate audio
            with client.audio.speech.with_streaming_response.create(
                model=TTS_MODEL,
                voice=TTS_VOICE,
                input=text
            ) as response:
                response.stream_to_file(str(output_path))

            # Record end time and calculate duration
            end_time = time.time()
            duration = end_time - start_time

            file_size = output_path.stat().st_size
            logger.info(f"  ✓ Audio generated in {duration:.2f}s: {output_path}")
            logger.info(f"  File size: {file_size:,} bytes ({file_size/1024/1024:.2f} MB)")

            return True

        except Exception as e:
            logger.error(f"  Attempt {attempt + 1} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                sleep_time = 2 ** attempt
                logger.info(f"  Retrying in {sleep_time}s...")
                time.sleep(sleep_time)
            else:
                logger.error(f"  ✗ Failed to generate audio for Chapter {chapter_num}")
                return False

    return False


def process_chapter(client, rate_limiter, chapter_file: Path):
    """Process a single chapter's translation to generate audio"""
    chapter_num = int(chapter_file.stem.split('_')[1])

    # Read translation
    text = chapter_file.read_text(encoding='utf-8')

    # Remove markdown formatting for cleaner audio
    # Keep the text but remove markdown symbols for better TTS
    clean_text = text.replace('#', '').replace('*', '').strip()

    logger.info(f"\n{'='*60}")
    logger.info(f"Processing Chapter {chapter_num}")
    logger.info(f"{'='*60}")

    # Generate audio
    success = generate_audio_for_chapter(client, rate_limiter, chapter_num, clean_text)

    if success:
        logger.info(f"✓ Chapter {chapter_num} audio complete!")
    else:
        logger.error(f"✗ Chapter {chapter_num} audio failed!")

    return success


def main():
    """Main entry point"""
    # Parse arguments
    max_chapters = None
    if len(sys.argv) > 1:
        try:
            max_chapters = int(sys.argv[1])
            logger.info(f"Processing first {max_chapters} chapters only")
        except ValueError:
            logger.error(f"Invalid argument: {sys.argv[1]}")
            sys.exit(1)

    # Initialize client and rate limiter
    logger.info("Initializing TTS client...")
    logger.info(f"Model: {TTS_MODEL}, Voice: {TTS_VOICE}")
    logger.info(f"Rate limits: QPM={QPM}, TPM={TPM}")

    client = init_client()
    rate_limiter = RateLimiter(QPM)

    # Get translation files
    translation_files = sorted(TRANSLATIONS_DIR.glob('chapter_*_cn.md'))

    if not translation_files:
        logger.error("No translation files found!")
        logger.info(f"Looking in: {TRANSLATIONS_DIR}")
        sys.exit(1)

    if max_chapters:
        translation_files = translation_files[:max_chapters]

    logger.info(f"Found {len(translation_files)} translation files to process\n")

    # Process each chapter
    success_count = 0
    fail_count = 0

    start_time = time.time()

    for translation_file in translation_files:
        success = process_chapter(client, rate_limiter, translation_file)
        if success:
            success_count += 1
        else:
            fail_count += 1

    end_time = time.time()
    total_time = end_time - start_time

    logger.info("\n" + "="*60)
    logger.info("Audio generation complete!")
    logger.info(f"Successful: {success_count}/{len(translation_files)}")
    logger.info(f"Failed: {fail_count}/{len(translation_files)}")
    logger.info(f"Total time: {total_time/60:.2f} minutes")
    logger.info(f"Audio files saved to: {AUDIO_DIR}")
    logger.info("="*60)


if __name__ == '__main__':
    main()
