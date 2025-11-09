# Book Translation Pipeline

自动化翻译书籍并生成网站的完整流程工具。

## 功能特性

- **PDF 章节提取**: 基于目录自动提取并分割章节
- **AI 翻译**: 使用 GPT-5 进行高质量中文翻译
- **章节摘要**: 自动生成简洁的章节摘要
- **音频生成**: 使用 OpenAI TTS 生成中文朗读音频
- **网站发布**: 生成带音频播放器的静态网站

## 快速开始

### 1. 环境配置

```bash
# 创建 conda 环境
conda create -n translate python=3.10 -y
conda activate translate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置 API Key

创建 `.env` 文件并添加以下配置：

```bash
GPT_OPENAI_AK=your_translation_api_key
TTS_API_KEY=your_tts_api_key

TRANSLATION_MODEL=gpt-5-2025-08-07
TTS_MODEL=tts-1-hd
TTS_VOICE=nova
TTS_QPM=5
```

### 3. 处理流程

```bash
# 步骤 1: 从 PDF 提取章节
python extract_chapters_by_toc.py

# 步骤 2: 翻译所有章节（包含摘要生成）
python run_translation_pipeline.py

# 步骤 3: 生成音频文件
python generate_audio_batch.py 1 20  # 生成章节 1-20 的音频

# 步骤 4: 生成网站数据
python generate_website_data.py
```

## 项目结构

```
book_pipeline/
├── books/                    # PDF 源文件
├── output/
│   ├── chapters/            # 提取的原文章节
│   ├── translations/        # 中文翻译 (.md)
│   ├── summaries/           # 章节摘要 (.txt)
│   └── audio/               # 音频文件 (.mp3)
├── web/
│   ├── data/chapters.json   # 网站数据
│   └── index.html           # 网站首页
├── scripts/                 # 测试和工具脚本
└── [核心脚本]
```

## 核心脚本说明

| 脚本 | 功能 |
|------|------|
| `extract_chapters_by_toc.py` | 从 PDF 提取章节文本 |
| `run_translation_pipeline.py` | 翻译章节并生成摘要 |
| `generate_audio_chunked.py` | 为单个章节生成音频 |
| `generate_audio_batch.py` | 批量生成多个章节的音频 |
| `generate_website_data.py` | 生成网站 JSON 数据 |

## 技术细节

- **翻译分块**: 智能边界检测（段落 → 句子 → 单词），避免文本截断
- **音频分块**: 按段落分割，单个分块最大 4000 字符
- **音频合并**: 自动将多个音频片段合并为完整文件
- **速率限制**: 自动处理 API 速率限制 (QPM)

## License

MIT
