#!/usr/bin/env python3
"""
Restructure the project to support multiple books
"""
from pathlib import Path
import shutil

# Create book's index.html (chapter list)
book_index_html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Next Level - 章节列表</title>
    <link rel="stylesheet" href="../../css/style.css">
</head>
<body>
    <div class="container">
        <a href="../../" class="back-link">← 返回书籍列表</a>

        <header>
            <h1>Next Level</h1>
            <p class="subtitle">Your Guide to Kicking Ass, Feeling Great, and Crushing Goals Through Menopause and Beyond</p>
            <p class="author">by Stacy T. Sims, PhD & Selene Yeager</p>
        </header>

        <div id="chapters-list">
            <!-- Chapters will be loaded here by JavaScript -->
        </div>
    </div>

    <script src="../../js/main.js"></script>
    <script>
        // Update loadChapters to use correct path
        async function loadChapters() {
            try {
                const response = await fetch('data/chapters.json');
                const chapters = await response.json();
                const container = document.getElementById('chapters-list');

                chapters.forEach(chapter => {
                    const card = createChapterCard(chapter);
                    container.appendChild(card);
                });
            } catch (error) {
                console.error('Error loading chapters:', error);
                document.getElementById('chapters-list').innerHTML =
                    '<p>加载章节列表失败，请稍后再试。</p>';
            }
        }

        loadChapters();
    </script>
</body>
</html>
'''

# Write book index
book_index_path = Path('docs/books/next-level/index.html')
book_index_path.write_text(book_index_html, encoding='utf-8')
print(f'✓ Created {book_index_path}')

# Update chapter HTML files to fix paths
chapters_dir = Path('docs/books/next-level/chapters')
if chapters_dir.exists():
    for chapter_file in chapters_dir.glob('chapter_*.html'):
        content = chapter_file.read_text(encoding='utf-8')

        # Update CSS and JS paths
        content = content.replace('href="../css/style.css"', 'href="../../../css/style.css"')
        content = content.replace('src="../audio/', 'src="../audio/')
        content = content.replace('href="../index.html"', 'href="../"')

        chapter_file.write_text(content, encoding='utf-8')

    print(f'✓ Updated {len(list(chapters_dir.glob("chapter_*.html")))} chapter files')

print('\n✅ Restructuring complete!')
print('\nNew structure:')
print('docs/')
print('├── index.html              # Book list')
print('├── books/')
print('│   └── next-level/')
print('│       ├── index.html      # Chapter list')
print('│       ├── chapters/       # Chapter pages')
print('│       ├── data/           # chapters.json')
print('│       └── audio/          # Audio files')
print('├── css/')
print('└── js/')
