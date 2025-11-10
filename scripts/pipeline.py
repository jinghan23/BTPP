#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Book Translation & Publishing Pipeline

Automated pipeline for:
1. Extracting text from PDF books
2. Splitting into chapters
3. Translating to Chinese (loyal & fluent)
4. Generating chapter summaries
5. Creating audio files (OpenAI TTS)
6. Building web interface
"""

import os
import json
import re
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
import logging

import pdfplumber
from openai import OpenAI
from dotenv import load_dotenv
from tqdm import tqdm

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


@dataclass
class Chapter:
    """Represents a book chapter"""
    number: int
    title: str
    original_text: str
    translation: str = ""
    summary: str = ""
    audio_path: str = ""


class BookPipeline:
    """Main pipeline for book processing"""

    def __init__(self, pdf_path: str, book_title: str = None):
        self.pdf_path = Path(pdf_path)
        self.book_title = book_title or self.pdf_path.stem

        # Initialize Azure OpenAI client (internal endpoint)
        api_key = os.getenv('GPT_OPENAI_AK') or os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("No API key found. Set GPT_OPENAI_AK or OPENAI_API_KEY")

        api_version = os.getenv('AZURE_API_VERSION', 'preview')

        logger.info("Using Azure OpenAI API (internal endpoint)")

        # Use Azure OpenAI with internal endpoint (chat completions API)
        from openai import AzureOpenAI
        self.client = AzureOpenAI(
            azure_endpoint="https://search.bytedance.net/gpt/openapi/online/v2/crawl/openai/deployments/gpt_openapi",
            api_key=api_key,
            api_version=api_version,
            timeout=1200,
            max_retries=3
        )

        # TTS is not supported on internal Azure endpoint, set to None
        self.tts_client = None

        # Model settings
        self.translation_model = os.getenv('TRANSLATION_MODEL', 'gpt-5-2025-08-07')
        self.summary_model = os.getenv('SUMMARY_MODEL', 'gpt-5-2025-08-07')
        self.tts_model = os.getenv('TTS_MODEL', 'tts-1')
        self.tts_voice = os.getenv('TTS_VOICE', 'nova')
        self.temperature = float(os.getenv('TEMPERATURE', '0.3'))
        self.max_retries = int(os.getenv('MAX_RETRIES', '3'))

        # Output directories
        self.output_dir = Path('output')
        self.chapters_dir = self.output_dir / 'chapters'
        self.translations_dir = self.output_dir / 'translations'
        self.summaries_dir = self.output_dir / 'summaries'
        self.audio_dir = self.output_dir / 'audio'

        # Create directories
        for dir_path in [self.chapters_dir, self.translations_dir,
                        self.summaries_dir, self.audio_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

        self.chapters: List[Chapter] = []

    def extract_text_from_pdf(self) -> str:
        """Extract all text from PDF"""
        logger.info(f"Extracting text from: {self.pdf_path}")

        full_text = []
        with pdfplumber.open(self.pdf_path) as pdf:
            logger.info(f"Total pages: {len(pdf.pages)}")
            for page_num, page in enumerate(tqdm(pdf.pages, desc="Extracting pages"), 1):
                text = page.extract_text()
                if text:
                    full_text.append(text)

        combined_text = "\n\n".join(full_text)
        logger.info(f"Extracted {len(combined_text)} characters")
        return combined_text

    def split_into_chapters(self, text: str) -> List[Chapter]:
        """Split text into chapters using improved pattern matching"""
        logger.info("Splitting text into chapters...")

        # More specific chapter patterns - look for chapter markers with substantial titles
        patterns = [
            r'\n\s*(Chapter\s+\d+[:\s]+[A-Z].{10,100})\n',  # Chapter 1: Long Title
            r'\n\s*(CHAPTER\s+\d+[:\s]+[A-Z].{10,100})\n',  # CHAPTER 1: LONG TITLE
            r'\n\s*(\d+\n[A-Z][A-Z\s]{10,100})\n',  # Multi-line: number then CAPS TITLE
            r'\n\s*(PART\s+\d+\n.{10,100})\n',  # PART 1 with title
            r'\n\s*(\d+[:\.]?\s+[A-Z][A-Z\s\']{15,100})\n',  # 1: LONG CAPS TITLE or 1. LONG CAPS TITLE
        ]

        # Try each pattern
        chapter_matches = []
        for pattern in patterns:
            matches = list(re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE))
            # Filter matches that look like real chapters (longer titles, uppercase)
            filtered_matches = []
            for m in matches:
                title = m.group(1).strip()
                # Skip if it's just a number with URL or short text
                if ('http' not in title.lower() and
                    'www' not in title.lower() and
                    len(title) > 20 and
                    not title.startswith('Zone ')):  # Skip training zones
                    filtered_matches.append(m)

            if len(filtered_matches) > 3:  # Need at least 4 chapters
                chapter_matches = filtered_matches
                logger.info(f"Found {len(filtered_matches)} chapters using pattern: {pattern}")
                break

        if not chapter_matches:
            logger.warning("No chapter markers found. Creating single chapter.")
            self.chapters = [Chapter(
                number=1,
                title=self.book_title,
                original_text=text
            )]
            return self.chapters

        # Extract chapters
        chapters = []
        for i, match in enumerate(chapter_matches):
            chapter_num = i + 1
            chapter_title = match.group(1).strip()

            # Get chapter text
            start_pos = match.end()
            end_pos = chapter_matches[i + 1].start() if i + 1 < len(chapter_matches) else len(text)
            chapter_text = text[start_pos:end_pos].strip()

            # Skip very short chapters (likely false positives)
            if len(chapter_text) < 500:
                continue

            chapters.append(Chapter(
                number=chapter_num,
                title=chapter_title,
                original_text=chapter_text
            ))

        self.chapters = chapters
        logger.info(f"Split into {len(chapters)} chapters")

        # Save original chapters
        for chapter in chapters:
            chapter_file = self.chapters_dir / f"chapter_{chapter.number:02d}.txt"
            chapter_file.write_text(
                f"{chapter.title}\n\n{chapter.original_text}",
                encoding='utf-8'
            )

        return chapters

    def translate_chapter(self, chapter: Chapter) -> str:
        """Translate a chapter to Chinese by splitting into manageable chunks"""
        logger.info(f"Translating Chapter {chapter.number}: {chapter.title}")

        # Split text into chunks (3000 chars each to avoid token limits)
        text = chapter.original_text
        chunk_size = 3000
        chunks = []

        i = 0
        while i < len(text):
            end = min(i + chunk_size, len(text))
            chunk = text[i:end]

            # Try to break at paragraph boundaries if not at end
            if end < len(text):
                last_newline = chunk.rfind('\n\n')
                if last_newline > len(chunk) * 0.7:  # At least 70% through
                    chunk = chunk[:last_newline]
                    end = i + last_newline

            chunks.append(chunk)
            i = end

        logger.info(f"Split into {len(chunks)} chunks for translation")

        translations = []
        for idx, chunk in enumerate(chunks):
            logger.info(f"Translating chunk {idx + 1}/{len(chunks)}...")

            prompt = f"""You are a professional translator working on a book translation project for educational and personal study purposes.

Task: Translate the following English text to Chinese (Simplified).

Requirements:
1. **Accuracy**: Stay faithful to the original meaning and tone
2. **Fluency**: Use natural, idiomatic Chinese
3. **Completeness**: Translate ALL text, do not summarize or skip content
4. **Format**: Preserve paragraph structure

Text to translate (Part {idx + 1} of {len(chunks)}):

{chunk}

Chinese translation:"""

            # Retry logic for each chunk
            chunk_translation = ""
            for attempt in range(self.max_retries):
                try:
                    response = self.client.chat.completions.create(
                        model=self.translation_model,
                        messages=[
                            {"role": "system", "content": "You are a professional literary translator specializing in English to Chinese translation."},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=self.temperature,
                        max_tokens=16000
                    )

                    chunk_translation = response.choices[0].message.content.strip()
                    logger.info(f"✓ Chunk {idx + 1} translated ({len(chunk_translation)} chars)")
                    break  # Success, exit retry loop

                except Exception as e:
                    logger.error(f"Chunk {idx + 1} translation attempt {attempt + 1} failed: {e}")
                    if attempt < self.max_retries - 1:
                        time.sleep(2 ** attempt)  # Exponential backoff
                    else:
                        logger.error(f"Failed to translate chunk {idx + 1} after {self.max_retries} attempts")
                        chunk_translation = f"[Translation failed for chunk {idx + 1}]"

            translations.append(chunk_translation)
            time.sleep(1)  # Rate limiting between chunks

        # Combine all translations
        full_translation = "\n\n".join(translations)

        # Save translation
        trans_file = self.translations_dir / f"chapter_{chapter.number:02d}_cn.txt"
        trans_file.write_text(
            f"{chapter.title}\n\n{full_translation}",
            encoding='utf-8'
        )

        logger.info(f"✓ Translated Chapter {chapter.number} ({len(full_translation)} chars total)")
        return full_translation

    def generate_summary(self, chapter: Chapter) -> str:
        """Generate a compact summary of the chapter"""
        logger.info(f"Generating summary for Chapter {chapter.number}")

        # Use translation if available, otherwise original
        text_to_summarize = chapter.translation if chapter.translation else chapter.original_text

        prompt = f"""Please provide a concise summary of this chapter in Chinese (2-3 paragraphs).

Focus on:
- Main ideas and key points
- Important concepts or lessons
- Practical takeaways

Chapter: {chapter.title}

Text:
{text_to_summarize[:3000]}...

Summary (in Chinese):"""

        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.summary_model,
                    messages=[
                        {"role": "system", "content": "You are an expert at creating concise, insightful chapter summaries in Chinese."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=self.temperature,
                    max_tokens=1000
                )

                summary = response.choices[0].message.content.strip()

                # Save summary
                summary_file = self.summaries_dir / f"chapter_{chapter.number:02d}_summary.txt"
                summary_file.write_text(summary, encoding='utf-8')

                logger.info(f"✓ Generated summary for Chapter {chapter.number}")
                return summary

            except Exception as e:
                logger.error(f"Summary attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"Failed to generate summary for Chapter {chapter.number}")
                    return ""

        return ""

    def generate_audio(self, chapter: Chapter) -> str:
        """Generate audio file for chapter using OpenAI TTS"""
        logger.info(f"Generating audio for Chapter {chapter.number}")

        if not chapter.translation:
            logger.warning(f"No translation available for Chapter {chapter.number}, skipping audio")
            return ""

        if not self.tts_client:
            logger.warning(f"No TTS client available (OpenRouter doesn't support TTS), skipping audio for Chapter {chapter.number}")
            return ""

        audio_file = self.audio_dir / f"chapter_{chapter.number:02d}.mp3"

        # Prepare text (limit to ~4096 chars for TTS)
        text_for_audio = chapter.translation[:4000] if len(chapter.translation) > 4000 else chapter.translation

        for attempt in range(self.max_retries):
            try:
                response = self.tts_client.audio.speech.create(
                    model=self.tts_model,
                    voice=self.tts_voice,
                    input=text_for_audio
                )

                # Save audio file
                response.stream_to_file(audio_file)

                logger.info(f"✓ Generated audio for Chapter {chapter.number}: {audio_file.name}")
                return f"audio/{audio_file.name}"

            except Exception as e:
                logger.error(f"Audio generation attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"Failed to generate audio for Chapter {chapter.number}")
                    return ""

        return ""

    def process_all_chapters(self):
        """Process all chapters: translate, summarize, and generate audio"""
        logger.info(f"Processing {len(self.chapters)} chapters...")

        for chapter in tqdm(self.chapters, desc="Processing chapters"):
            # Translate
            chapter.translation = self.translate_chapter(chapter)
            time.sleep(1)  # Rate limiting

            # Generate summary
            chapter.summary = self.generate_summary(chapter)
            time.sleep(1)

            # Generate audio
            chapter.audio_path = self.generate_audio(chapter)
            time.sleep(1)

        logger.info("✓ All chapters processed!")

    def export_to_json(self) -> str:
        """Export all chapter data to JSON for web interface"""
        logger.info("Exporting data to JSON...")

        data = {
            "book_title": self.book_title,
            "total_chapters": len(self.chapters),
            "chapters": [
                {
                    "number": ch.number,
                    "title": ch.title,
                    "original": ch.original_text[:500] + "...",  # Truncate for web
                    "translation": ch.translation,
                    "summary": ch.summary,
                    "audio": ch.audio_path
                }
                for ch in self.chapters
            ]
        }

        json_file = Path('web/data/book_data.json')
        json_file.parent.mkdir(parents=True, exist_ok=True)

        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"✓ Exported to: {json_file}")
        return str(json_file)

    def run(self):
        """Run the complete pipeline"""
        logger.info("=" * 60)
        logger.info("Starting Book Translation Pipeline")
        logger.info("=" * 60)

        # Step 1: Extract text
        text = self.extract_text_from_pdf()

        # Step 2: Split into chapters
        self.split_into_chapters(text)

        # Step 3-5: Process chapters
        self.process_all_chapters()

        # Step 6: Export to JSON
        self.export_to_json()

        logger.info("=" * 60)
        logger.info("Pipeline completed successfully!")
        logger.info("=" * 60)


def main():
    """Main entry point"""
    # Find PDF in books directory
    books_dir = Path('books')
    pdf_files = list(books_dir.glob('*.pdf'))

    if not pdf_files:
        logger.error("No PDF files found in 'books/' directory")
        return

    # Use first PDF found
    pdf_path = pdf_files[0]
    logger.info(f"Processing: {pdf_path.name}")

    # Run pipeline
    pipeline = BookPipeline(str(pdf_path))
    pipeline.run()


if __name__ == '__main__':
    main()
