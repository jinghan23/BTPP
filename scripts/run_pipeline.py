#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Run the book translation pipeline with options
"""

import argparse
from pathlib import Path
from pipeline import BookPipeline, logger


def main():
    parser = argparse.ArgumentParser(description='Book Translation Pipeline')
    parser.add_argument('--pdf', type=str, help='Path to PDF file (optional, will use first PDF in books/)')
    parser.add_argument('--max-chapters', type=int, default=None, help='Maximum number of chapters to process (default: all)')
    parser.add_argument('--test', action='store_true', help='Test mode: only process first 2 chapters')
    parser.add_argument('--skip-audio', action='store_true', help='Skip audio generation')

    args = parser.parse_args()

    # Find PDF
    if args.pdf:
        pdf_path = Path(args.pdf)
    else:
        books_dir = Path('books')
        pdf_files = list(books_dir.glob('*.pdf'))
        if not pdf_files:
            logger.error("No PDF files found in 'books/' directory")
            return
        pdf_path = pdf_files[0]

    if not pdf_path.exists():
        logger.error(f"PDF file not found: {pdf_path}")
        return

    logger.info(f"Processing: {pdf_path.name}")

    # Initialize pipeline
    pipeline = BookPipeline(str(pdf_path))

    # Extract and split
    text = pipeline.extract_text_from_pdf()
    pipeline.split_into_chapters(text)

    # Limit chapters if requested
    max_chapters = 2 if args.test else args.max_chapters
    if max_chapters:
        original_count = len(pipeline.chapters)
        pipeline.chapters = pipeline.chapters[:max_chapters]
        logger.info(f"Limited to {len(pipeline.chapters)} chapters (out of {original_count})")

    # Process chapters
    logger.info(f"Processing {len(pipeline.chapters)} chapters...")
    for i, chapter in enumerate(pipeline.chapters, 1):
        logger.info(f"\n{'='*60}")
        logger.info(f"Chapter {i}/{len(pipeline.chapters)}: {chapter.title}")
        logger.info(f"{'='*60}")

        # Translate
        chapter.translation = pipeline.translate_chapter(chapter)

        # Generate summary
        chapter.summary = pipeline.generate_summary(chapter)

        # Generate audio (unless skipped)
        if not args.skip_audio:
            chapter.audio_path = pipeline.generate_audio(chapter)

    # Export to JSON
    pipeline.export_to_json()

    logger.info("\n" + "="*60)
    logger.info("✓ Pipeline completed successfully!")
    logger.info("="*60)
    logger.info(f"\nProcessed: {len(pipeline.chapters)} chapters")
    logger.info(f"Translations: output/translations/")
    logger.info(f"Summaries: output/summaries/")
    logger.info(f"Audio: output/audio/")
    logger.info(f"Web data: web/data/book_data.json")


if __name__ == '__main__':
    main()
