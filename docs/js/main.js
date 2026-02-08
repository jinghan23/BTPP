// Load and display chapters
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

function createChapterCard(chapter) {
    const card = document.createElement('div');
    card.className = 'chapter-card';
    card.style.cursor = 'pointer';
    card.onclick = () => location.href = `chapters/chapter_${String(chapter.number).padStart(2, '0')}.html`;

    const number = document.createElement('div');
    number.className = 'chapter-number';
    number.textContent = `第 ${chapter.number} 章`;

    const title = document.createElement('div');
    title.className = 'chapter-title';
    title.textContent = chapter.title;

    const summary = document.createElement('div');
    summary.className = 'chapter-summary';
    summary.textContent = chapter.summary;

    const meta = document.createElement('div');
    meta.className = 'chapter-meta';

    if (chapter.hasAudio) {
        const audioIcon = document.createElement('span');
        audioIcon.textContent = '🔊 有音频';
        meta.appendChild(audioIcon);
    }

    const wordCount = document.createElement('span');
    wordCount.textContent = `📝 ${chapter.wordCount || 'N/A'} 字`;
    meta.appendChild(wordCount);

    card.appendChild(number);
    card.appendChild(title);
    card.appendChild(summary);
    card.appendChild(meta);

    return card;
}

// Load chapters when page loads
if (document.getElementById('chapters-list')) {
    loadChapters();
}
