#!/usr/bin/env python3
"""
Add Markdown formatting to translated chapters for better readability
"""

import re
from pathlib import Path


def format_chapter_markdown(text: str) -> str:
    """
    Add Markdown formatting to chapter text:
    - Format chapter title
    - Format subtitle (italicized phrase after title)
    - Format section headings (short standalone lines)
    """
    lines = text.split('\n')
    formatted_lines = []

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Skip empty lines
        if not stripped:
            formatted_lines.append(line)
            i += 1
            continue

        # Chapter title pattern: "1. Title" or just number
        if i == 0 and re.match(r'^\d+\.\s+.+', stripped):
            # Main chapter title
            formatted_lines.append(f'# {stripped}')
            i += 1
            continue

        # Chapter number alone
        if i < 3 and re.match(r'^\d+$', stripped):
            formatted_lines.append(line)
            i += 1
            continue

        # Chapter title in Chinese (short, no punctuation at end, appears early)
        if i < 5 and len(stripped) < 30 and not stripped.endswith(('。', '！', '？', '，', '；')):
            # Check if it looks like a title (mostly short, impactful)
            formatted_lines.append(f'## {stripped}')
            i += 1
            continue

        # Subtitle/tagline after chapter title (appears within first 10 lines, ends with punctuation)
        if i < 10 and len(stripped) < 50 and (stripped.endswith(('。', '！', '？')) or '，' in stripped):
            # Likely a subtitle/tagline
            formatted_lines.append(f'*{stripped}*\n')
            i += 1
            continue

        # Section headings: short lines (< 20 chars), no ending punctuation, not all caps
        # Preceded and followed by blank lines or paragraphs
        if (len(stripped) < 20 and
            not stripped.endswith(('。', '！', '？', '，', '；', '：', '、')) and
            i > 10):  # After initial title area

            # Check if previous line is empty or a paragraph
            prev_empty = i == 0 or not lines[i-1].strip()
            # Check if next line is empty or starts a new paragraph
            next_empty = i == len(lines)-1 or not lines[i+1].strip()

            if prev_empty or next_empty:
                # This is likely a section heading
                formatted_lines.append(f'\n## {stripped}\n')
                i += 1
                continue

        # Regular paragraph
        formatted_lines.append(line)
        i += 1

    return '\n'.join(formatted_lines)


def process_translation_file(file_path: Path):
    """Process a translation file to add Markdown formatting"""
    print(f'Processing: {file_path.name}')

    # Read content
    content = file_path.read_text(encoding='utf-8')

    # Format with Markdown
    formatted = format_chapter_markdown(content)

    # Save to new file with _formatted suffix
    output_path = file_path.parent / f'{file_path.stem}_formatted.md'
    output_path.write_text(formatted, encoding='utf-8')

    print(f'  ✓ Saved to: {output_path.name}')


def main():
    """Process all translation files"""
    translations_dir = Path('output/translations')

    # Find all Chinese translation files
    files = sorted(translations_dir.glob('chapter_*_cn.txt'))

    if not files:
        print('No translation files found')
        return

    print(f'Found {len(files)} translation files\n')

    for file_path in files:
        process_translation_file(file_path)

    print('\n✓ All files formatted!')


if __name__ == '__main__':
    main()
