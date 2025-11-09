#!/usr/bin/env python3
"""
Translation Pipeline using TOC-extracted chapters
"""

import os
import sys
import time
import re
from pathlib import Path
from openai import AzureOpenAI
from dotenv import load_dotenv
import logging

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
CHAPTERS_DIR = Path('output/chapters_processed')  # Use preprocessed chapters with Markdown
TRANSLATIONS_DIR = Path('output/translations')
SUMMARIES_DIR = Path('output/summaries')
CHUNK_SIZE = 3000
MAX_RETRIES = 3
TEMPERATURE = 1.0

# Create output directories
TRANSLATIONS_DIR.mkdir(parents=True, exist_ok=True)
SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)


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


def translate_chapter(client, chapter_num: int, chapter_text: str) -> str:
    """Translate a chapter by splitting into chunks"""
    logger.info(f"Translating Chapter {chapter_num}...")

    # Split into chunks with smart boundary detection
    chunks = []
    i = 0
    while i < len(chapter_text):
        end = min(i + CHUNK_SIZE, len(chapter_text))
        chunk = chapter_text[i:end]

        # Try to break at safe boundaries if not at the end
        if end < len(chapter_text):
            # First try paragraph boundary
            last_para = chunk.rfind('\n\n')
            if last_para > len(chunk) * 0.6:
                chunk = chunk[:last_para]
                end = i + last_para
            else:
                # Try sentence boundary (period, question mark, exclamation)
                last_sentence = max(
                    chunk.rfind('. '),
                    chunk.rfind('! '),
                    chunk.rfind('? '),
                    chunk.rfind('.\n')
                )
                if last_sentence > len(chunk) * 0.5:
                    # Include the period
                    chunk = chunk[:last_sentence + 1]
                    end = i + last_sentence + 1
                else:
                    # Last resort: break at word boundary (space)
                    last_space = chunk.rfind(' ')
                    if last_space > len(chunk) * 0.7:
                        chunk = chunk[:last_space]
                        end = i + last_space

        chunks.append(chunk.strip())
        i = end

    logger.info(f"  Split into {len(chunks)} chunks")

    # Translate each chunk
    translations = []
    for idx, chunk in enumerate(chunks):
        logger.info(f"  Translating chunk {idx + 1}/{len(chunks)}...")

        prompt = f"""You are a professional translator working on a book translation project for educational and personal study purposes.

Task: Translate the following English text to Chinese (Simplified).

Requirements:
1. **Accuracy**: Stay faithful to the original meaning and tone
2. **Fluency**: Use natural, idiomatic Chinese
3. **Completeness**: Translate ALL text, do not summarize or skip content
4. **Preserve Markdown formatting**: Keep all # ## * symbols exactly as they are
5. Only translate the text content, do NOT translate or modify Markdown symbols

Text to translate (Part {idx + 1} of {len(chunks)}):

{chunk}

Chinese translation:"""

        for attempt in range(MAX_RETRIES):
            try:
                response = client.chat.completions.create(
                    model='gpt-5-2025-08-07',
                    messages=[
                        {"role": "system", "content": "You are a professional literary translator specializing in English to Chinese translation."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=TEMPERATURE,
                    max_tokens=16000
                )

                chunk_translation = response.choices[0].message.content.strip()
                translations.append(chunk_translation)
                logger.info(f"    ✓ Chunk {idx + 1} translated ({len(chunk_translation)} chars)")
                break

            except Exception as e:
                logger.error(f"    Chunk {idx + 1} attempt {attempt + 1} failed: {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
                else:
                    translations.append(f"[Translation failed for chunk {idx + 1}]")

        time.sleep(1)  # Rate limiting

    # Combine translations
    full_translation = "\n\n".join(translations)
    logger.info(f"  ✓ Chapter {chapter_num} translated ({len(full_translation)} chars total)")

    return full_translation


def format_markdown_with_gpt(client, text: str, chapter_num: int) -> str:
    """Use GPT-5 to intelligently add Markdown formatting"""
    logger.info(f"Formatting Chapter {chapter_num} with Markdown...")

    prompt = f"""Please add proper Markdown formatting to this Chinese translated book chapter.

Requirements:
1. Main chapter title → Use `# Title` (H1)
2. Chapter subtitle/tagline (短语或口号) → Use `*subtitle*` (italic)
3. Section headings (小标题) → Use `## Heading` (H2)
4. Keep all paragraph text unchanged
5. Preserve all line breaks and spacing
6. Do NOT change any Chinese text content, ONLY add Markdown formatting symbols

Example format:
```
# 1. Chapter Title

## 副标题

*章节口号或主旨。*

正文段落...

## 第一个小节标题

正文段落...

## 第二个小节标题

正文段落...
```

Text to format:

{text}

Formatted Markdown (Chinese text unchanged, only add # ## * symbols):"""

    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model='gpt-5-2025-08-07',
                messages=[
                    {"role": "system", "content": "You are an expert at formatting Chinese text with Markdown for readability. You only add formatting symbols, never change the actual text content."},
                    {"role": "user", "content": prompt}
                ],
                temperature=TEMPERATURE,  # Use model default
                max_tokens=16000
            )

            formatted = response.choices[0].message.content.strip()
            logger.info(f"  ✓ Markdown formatting applied")
            return formatted

        except Exception as e:
            logger.error(f"  Formatting attempt {attempt + 1} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
            else:
                logger.error(f"  Failed to format Chapter {chapter_num}, returning original")
                return text

    return text


def generate_summary(client, chapter_num: int, translation: str) -> str:
    """Generate summary of the translated chapter"""
    logger.info(f"Generating summary for Chapter {chapter_num}...")

    # Use first 3000 chars of translation
    text_to_summarize = translation[:3000]

    prompt = f"""Summarize this Chinese chapter in 2-3 paragraphs (in Chinese).

Focus on:
- Main ideas and key points
- Important concepts or lessons
- Practical takeaways

Text:
{text_to_summarize}

Summary (in Chinese):"""

    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model='gpt-5-2025-08-07',
                messages=[
                    {"role": "system", "content": "You are an expert at creating concise, insightful chapter summaries."},
                    {"role": "user", "content": prompt}
                ],
                temperature=TEMPERATURE,
                max_tokens=2000
            )

            summary = response.choices[0].message.content.strip()
            logger.info(f"  ✓ Summary generated for Chapter {chapter_num}")
            return summary

        except Exception as e:
            logger.error(f"  Summary attempt {attempt + 1} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
            else:
                return ""

    return ""


def process_chapter(client, chapter_file: Path):
    """Process a single chapter: translate and summarize"""
    chapter_num = int(chapter_file.stem.split('_')[1])

    # Read chapter
    text = chapter_file.read_text(encoding='utf-8')

    # Extract title and content
    lines = text.split('\n', 1)
    title = lines[0] if lines else f"Chapter {chapter_num}"
    content = lines[1] if len(lines) > 1 else text

    logger.info(f"\n{'='*60}")
    logger.info(f"Processing Chapter {chapter_num}: {title}")
    logger.info(f"{'='*60}")

    # Translate (Markdown formatting already in source, will be preserved)
    translation = translate_chapter(client, chapter_num, content)

    # Save translation (already has Markdown from preprocessing)
    trans_file = TRANSLATIONS_DIR / f"chapter_{chapter_num:02d}_cn.md"
    trans_file.write_text(f"{title}\n\n{translation}", encoding='utf-8')

    time.sleep(1)

    # Generate summary
    summary = generate_summary(client, chapter_num, translation)

    # Save summary
    if summary:
        summary_file = SUMMARIES_DIR / f"chapter_{chapter_num:02d}_summary.txt"
        summary_file.write_text(summary, encoding='utf-8')

    time.sleep(1)

    logger.info(f"✓ Chapter {chapter_num} complete!")


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

    logger.info(f"Found {len(chapter_files)} chapters to process")

    # Process each chapter
    for chapter_file in chapter_files:
        process_chapter(client, chapter_file)

    logger.info("\n" + "="*60)
    logger.info("All chapters processed successfully!")
    logger.info("="*60)


if __name__ == '__main__':
    main()
