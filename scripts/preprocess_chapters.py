#!/usr/bin/env python3
"""
Preprocess extracted chapters to fix PDF artifacts before translation
- Merge paragraphs broken by page boundaries
- Fix hyphenation and word breaks
- Preserve intentional paragraph breaks
"""

import os
import sys
import time
from pathlib import Path
from openai import AzureOpenAI
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()

# Configuration
CHAPTERS_DIR = Path('output/chapters')
PROCESSED_DIR = Path('output/chapters_processed')
MAX_RETRIES = 3
TEMPERATURE = 1.0


def init_client():
    """Initialize Azure OpenAI client"""
    api_key = os.getenv('GPT_OPENAI_AK')
    if not api_key:
        raise ValueError("No API key found. Set GPT_OPENAI_AK in .env")

    client = AzureOpenAI(
        azure_endpoint='https://search.bytedance.net/gpt/openapi/online/v2/crawl/openai/deployments/gpt_openapi',
        api_key=api_key,
        api_version='preview',
        timeout=1200,
        max_retries=3
    )
    return client


def clean_and_format_chapter(client, text: str, chapter_num: int) -> str:
    """Use GPT-5 to clean PDF artifacts AND add Markdown formatting"""
    logger.info(f"Cleaning and formatting Chapter {chapter_num}...")

    prompt = f"""You are a text preprocessing expert. Clean up this English book chapter AND add Markdown formatting in ONE step.

TASK 1 - FIX PDF ARTIFACTS:
1. **Broken paragraphs**: Merge paragraphs split by page breaks (no topic change)
2. **Hyphenated words**: Fix words split across lines (e.g., "meno-\\npause" → "menopause")
3. **Broken sentences**: Merge sentences incorrectly split across paragraphs
4. PRESERVE intentional paragraph breaks (topic changes, new sections)

TASK 2 - ADD MARKDOWN FORMATTING:
1. Chapter title → `# Title` (H1)
2. Chapter subtitle/tagline → `*subtitle*` (italic)
3. Section headings → `## Heading` (H2)
4. Keep all paragraph text unchanged

RULES:
- DO NOT change any words or rephrase content
- DO NOT add or remove content
- Only fix paragraph breaks and add Markdown symbols

Example output format:
```
# 1. The Stats. The Stigma. The Silence.

*How we think and talk about menopause matters.*

Life expectancy for women is about 81 years...

## PERCEPTION MATTERS

Our cultural and societal views on aging...

## CHANGING FOR THE BETTER

Menopause is a time to look forward...
```

Input text (with PDF artifacts):

{text}

Cleaned AND formatted text (Markdown added, artifacts fixed):"""

    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model='gpt-5-2025-08-07',
                messages=[
                    {"role": "system", "content": "You are an expert at cleaning up PDF-extracted text. You fix paragraph breaks and hyphenation without changing any content."},
                    {"role": "user", "content": prompt}
                ],
                temperature=TEMPERATURE,
                max_tokens=16000
            )

            cleaned = response.choices[0].message.content.strip()
            logger.info(f"  ✓ Chapter {chapter_num} cleaned and formatted (before: {len(text)}, after: {len(cleaned)} chars)")
            return cleaned

        except Exception as e:
            logger.error(f"  Cleaning attempt {attempt + 1} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
            else:
                logger.error(f"  Failed to clean Chapter {chapter_num}, returning original")
                return text

    return text


def process_chapter(client, chapter_file: Path):
    """Process a single chapter"""
    chapter_num = int(chapter_file.stem.split('_')[1])

    # Read chapter
    text = chapter_file.read_text(encoding='utf-8')

    # Extract title and content
    lines = text.split('\n', 1)
    title = lines[0] if lines else f"Chapter {chapter_num}"
    content = lines[1] if len(lines) > 1 else text

    logger.info(f"\nProcessing Chapter {chapter_num}: {title}")
    logger.info(f"  Original length: {len(content)} chars")

    # Clean and format content
    cleaned_content = clean_and_format_chapter(client, content, chapter_num)

    # Save cleaned chapter
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    output_file = PROCESSED_DIR / chapter_file.name
    output_file.write_text(f"{title}\n\n{cleaned_content}", encoding='utf-8')

    logger.info(f"  ✓ Saved to: {output_file.name}")


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

    # Initialize client
    logger.info("Initializing Azure OpenAI client...")
    client = init_client()

    # Get chapter files
    chapter_files = sorted(CHAPTERS_DIR.glob('chapter_*.txt'))

    if max_chapters:
        chapter_files = chapter_files[:max_chapters]

    logger.info(f"Found {len(chapter_files)} chapters to process\n")

    # Process each chapter
    for chapter_file in chapter_files:
        process_chapter(client, chapter_file)
        time.sleep(1)  # Rate limiting

    logger.info("\n" + "="*60)
    logger.info("All chapters preprocessed successfully!")
    logger.info(f"Cleaned chapters saved to: {PROCESSED_DIR}")
    logger.info("="*60)


if __name__ == '__main__':
    main()
