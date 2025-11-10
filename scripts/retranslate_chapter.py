#!/usr/bin/env python3
"""
Re-translate a specific chapter to test fixes
"""

import sys
from pathlib import Path
from run_translation_pipeline import init_client, translate_chapter

CHAPTERS_DIR = Path('output/chapters_processed')
TRANSLATIONS_DIR = Path('output/translations')

def main():
    if len(sys.argv) < 2:
        print("Usage: python retranslate_chapter.py <chapter_num>")
        sys.exit(1)

    chapter_num = int(sys.argv[1])
    chapter_file = CHAPTERS_DIR / f'chapter_{chapter_num:02d}.txt'

    if not chapter_file.exists():
        print(f"Error: {chapter_file} not found")
        sys.exit(1)

    print(f"Re-translating Chapter {chapter_num}...\n")

    # Read chapter
    text = chapter_file.read_text(encoding='utf-8')
    lines = text.split('\n', 1)
    title = lines[0] if lines else f"Chapter {chapter_num}"
    content = lines[1] if len(lines) > 1 else text

    # Initialize client and translate
    client = init_client()
    translation = translate_chapter(client, chapter_num, content)

    # Save translation
    trans_file = TRANSLATIONS_DIR / f"chapter_{chapter_num:02d}_cn.md"
    trans_file.write_text(f"{title}\n\n{translation}", encoding='utf-8')

    print(f"\n✓ Chapter {chapter_num} re-translated!")
    print(f"  Output: {trans_file}")

if __name__ == '__main__':
    main()
