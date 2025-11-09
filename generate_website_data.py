#!/usr/bin/env python3
"""
Generate website data (chapters.json and chapter HTML pages)
"""

import json
import os
from pathlib import Path
import markdown

# Directories
TRANSLATIONS_DIR = Path('output/translations')
SUMMARIES_DIR = Path('output/summaries')
AUDIO_DIR = Path('output/audio')
DOCS_DIR = Path('docs')
CHAPTERS_DIR = DOCS_DIR / 'chapters'
DATA_DIR = DOCS_DIR / 'data'

# Create directories
CHAPTERS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Chapter titles from TOC
CHAPTER_TITLES = {
    1: "The Stats. The Stigma. The Silence.",
    2: "The Science of the Menopause Transition",
    3: "Hormones and Symptoms Explained",
    4: "Menopausal Hormone Therapy, Adaptogens, and Other Interventions",
    5: "Kick Up Your Cardio",
    6: "Now's the Time to Lift Heavy Sh*t!",
    7: "Jump Around: The Power of Plyometrics",
    8: "The Estrogen Fix for Strength and Endurance",
    9: "Eat to Perform and Thrive",
    10: "Feast and Fast",
    11: "Stay Hydrated to Stay Cool, Strong, and Healthy",
    12: "Strategize Your Supplementation",
    13: "Your Body Composition Rx",
    14: "Train Your Brain",
    15: "Rest and Recovery",
    16: "Your Performance Care Network",
    17: "Periodize Your Life",
    18: "Sample Training Plans",
    19: "Recipes for Training and Recovery",
    20: "Epilogue: It's Just a Transition"
}

def get_summary(chapter_num):
    """Get chapter summary"""
    summary_file = SUMMARIES_DIR / f'chapter_{chapter_num:02d}_summary.txt'
    if summary_file.exists():
        summary = summary_file.read_text(encoding='utf-8').strip()
        # Return first 200 characters for preview
        return summary[:200] + '...' if len(summary) > 200 else summary
    return "暂无摘要"

def has_audio(chapter_num):
    """Check if chapter has full audio file"""
    full_audio = AUDIO_DIR / f'chapter_{chapter_num:02d}_full.mp3'
    return full_audio.exists()

def get_word_count(chapter_num):
    """Get word count for chapter"""
    trans_file = TRANSLATIONS_DIR / f'chapter_{chapter_num:02d}_cn.md'
    if trans_file.exists():
        text = trans_file.read_text(encoding='utf-8')
        # Count Chinese characters
        return sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    return 0

def generate_chapters_json():
    """Generate chapters.json with metadata"""
    chapters = []

    for chapter_num in range(1, 21):
        trans_file = TRANSLATIONS_DIR / f'chapter_{chapter_num:02d}_cn.md'

        if not trans_file.exists():
            continue

        chapter_data = {
            'number': chapter_num,
            'title': CHAPTER_TITLES.get(chapter_num, f'Chapter {chapter_num}'),
            'summary': get_summary(chapter_num),
            'hasAudio': has_audio(chapter_num),
            'wordCount': get_word_count(chapter_num),
            'file': f'chapter_{chapter_num:02d}.html'
        }

        chapters.append(chapter_data)

    # Save to JSON
    json_file = DATA_DIR / 'chapters.json'
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(chapters, f, ensure_ascii=False, indent=2)

    print(f'✓ Generated {json_file} with {len(chapters)} chapters')

def md_to_html(md_text):
    """Convert Markdown to HTML"""
    # Convert markdown to HTML
    html = markdown.markdown(md_text, extensions=['extra'])
    return html

def generate_chapter_html(chapter_num):
    """Generate HTML page for a chapter"""
    trans_file = TRANSLATIONS_DIR / f'chapter_{chapter_num:02d}_cn.md'

    if not trans_file.exists():
        return

    # Read translation
    content = trans_file.read_text(encoding='utf-8')

    # Convert to HTML
    content_html = md_to_html(content)

    # Get full audio file (only _full.mp3)
    full_audio = AUDIO_DIR / f'chapter_{chapter_num:02d}_full.mp3'
    audio_html = ''

    if full_audio.exists():
        audio_html = '<div class="audio-player">\n'
        audio_html += '<h3>🔊 章节音频</h3>\n'
        audio_html += '<audio controls>\n'
        audio_html += f'  <source src="../audio/{full_audio.name}" type="audio/mpeg">\n'
        audio_html += '  您的浏览器不支持音频播放。\n'
        audio_html += '</audio>\n'
        audio_html += '</div>\n'

    # Get summary
    summary_file = SUMMARIES_DIR / f'chapter_{chapter_num:02d}_summary.txt'
    summary_html = ''
    if summary_file.exists():
        summary_text = summary_file.read_text(encoding='utf-8')
        summary_html = f'''
<div class="chapter-summary-box">
<h3>📖 章节摘要</h3>
<p>{summary_text}</p>
</div>
'''

    # HTML template
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>第 {chapter_num} 章: {CHAPTER_TITLES.get(chapter_num, '')} - Next Level</title>
    <link rel="stylesheet" href="../css/style.css">
    <style>
        .chapter-summary-box {{
            background: #f0f8ff;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
            border-left: 4px solid #3498db;
        }}
        .chapter-summary-box h3 {{
            margin-top: 0;
            color: #2c3e50;
        }}
        .chapter-summary-box p {{
            line-height: 1.8;
            white-space: pre-wrap;
        }}
    </style>
</head>
<body>
    <div class="container chapter-detail">
        <a href="../index.html" class="back-link">← 返回目录</a>

        <div class="chapter-header">
            <h1>第 {chapter_num} 章: {CHAPTER_TITLES.get(chapter_num, '')}</h1>
        </div>

        {summary_html}

        {audio_html}

        <div class="chapter-content">
            {content_html}
        </div>

        <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd;">
            <a href="../index.html" class="back-link">← 返回目录</a>
        </div>
    </div>
</body>
</html>
'''

    # Save HTML
    html_file = CHAPTERS_DIR / f'chapter_{chapter_num:02d}.html'
    html_file.write_text(html, encoding='utf-8')

    print(f'✓ Generated {html_file.name}')

def main():
    """Main function"""
    print('Generating website data...\n')

    # Generate chapters.json
    generate_chapters_json()

    print('\nGenerating chapter HTML pages...')

    # Generate HTML for each chapter
    for chapter_num in range(1, 21):
        generate_chapter_html(chapter_num)

    print('\n✓ Website generation complete!')
    print(f'  Chapters JSON: {DATA_DIR / "chapters.json"}')
    print(f'  Chapter pages: {CHAPTERS_DIR}/')
    print(f'  Main page: {DOCS_DIR / "index.html"}')

if __name__ == '__main__':
    main()
