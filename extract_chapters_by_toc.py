#!/usr/bin/env python3
"""
Extract chapters based on the Table of Contents
"""

import pdfplumber
import re
from pathlib import Path

# Chapter titles from TOC
CHAPTERS = [
    "The Stats. The Stigma. The Silence.",
    "The Science of the Menopause Transition",
    "Hormones and Symptoms Explained",
    "Menopausal Hormone Therapy, Adaptogens, and Other Interventions",
    "Kick Up Your Cardio",
    "Now's the Time to Lift Heavy Sh*t!",
    "Get a Jump on Menopausal Strength Losses",
    "Gut Health for Athletic Glory",
    "Eat Enough!",
    "Fueling for the Menopause Transition",
    "Nail Your Nutrition Timing",
    "How to Hydrate",
    "Sleep Well and Recover Right",
    "Stability, Mobility, and Core Strength: Keep Your Foundation Strong",
    "Motivation and the Mental Game: Your Mind Matters",
    "Keep Your Skeleton Strong",
    "Strategies for Exercising Through the Transition",
    "Supplements: What You Need and What You Don't",
    "Pulling It All Together",
]

def find_chapter_pages(pdf_path):
    """Find the starting page for each chapter"""
    chapter_pages = {}

    with pdfplumber.open(pdf_path) as pdf:
        print(f"Scanning {len(pdf.pages)} pages for chapter markers...")

        # Skip first 10 pages (TOC and front matter)
        for page_num in range(10, len(pdf.pages)):
            page = pdf.pages[page_num]
            text = page.extract_text()
            if not text:
                continue

            lines = text.split('\n')[:10]
            first_line = lines[0].strip() if lines else ''

            # Check if first line is a chapter number (1-19)
            if re.match(r'^\d{1,2}$', first_line):
                chapter_num = int(first_line)
                if 1 <= chapter_num <= 19 and chapter_num not in chapter_pages:
                    # Verify it looks like a chapter by checking for uppercase text in the title line
                    # (second line, or second+third if title wraps)
                    title_lines = ' '.join(lines[1:3])  # Just the title line(s), not subtitle
                    uppercase_count = sum(1 for c in title_lines if c.isupper())
                    total_letters = sum(1 for c in title_lines if c.isalpha())

                    # If more than 25% of letters are uppercase, it's likely a chapter title
                    if total_letters > 0 and uppercase_count / total_letters > 0.25:
                        chapter_pages[chapter_num] = page_num
                        chapter_title = CHAPTERS[chapter_num - 1] if chapter_num <= len(CHAPTERS) else "Unknown"
                        print(f"Found Chapter {chapter_num}: {chapter_title} on page {page_num + 1}")

    return chapter_pages

def extract_chapters(pdf_path, output_dir):
    """Extract chapters based on found page numbers"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    chapter_pages = find_chapter_pages(pdf_path)

    # Sort chapter pages
    sorted_chapters = sorted(chapter_pages.items())

    with pdfplumber.open(pdf_path) as pdf:
        for i, (chapter_num, start_page) in enumerate(sorted_chapters):
            # Determine end page (start of next chapter or end of book)
            if i + 1 < len(sorted_chapters):
                end_page = sorted_chapters[i + 1][1]
            else:
                end_page = len(pdf.pages)

            # Extract text from this chapter
            chapter_text = []
            for page_num in range(start_page, end_page):
                text = pdf.pages[page_num].extract_text()
                if text:
                    chapter_text.append(text)

            combined_text = "\n\n".join(chapter_text)

            # Save chapter
            chapter_file = output_dir / f"chapter_{chapter_num:02d}.txt"
            chapter_title = CHAPTERS[chapter_num - 1]

            with open(chapter_file, 'w', encoding='utf-8') as f:
                f.write(f"{chapter_num}. {chapter_title}\n\n")
                f.write(combined_text)

            print(f"Saved Chapter {chapter_num}: {len(combined_text)} chars ({end_page - start_page} pages)")

if __name__ == '__main__':
    pdf_path = 'books/Next Level Your Guide to Kicking Ass, Feeling G... (Z-Library).pdf'
    output_dir = 'output/chapters'

    print("Extracting chapters based on TOC...")
    extract_chapters(pdf_path, output_dir)
    print("\nDone!")
