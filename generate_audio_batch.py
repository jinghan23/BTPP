#!/usr/bin/env python3
"""
Batch generate audio for multiple chapters
"""

import sys
from pathlib import Path
from generate_audio_chunked import generate_chapter_audio, init_client

def main():
    """Generate audio for a range of chapters"""

    if len(sys.argv) < 2:
        print("Usage: python generate_audio_batch.py <start_chapter> [end_chapter]")
        print("Example: python generate_audio_batch.py 1 3")
        sys.exit(1)

    start_chapter = int(sys.argv[1])
    end_chapter = int(sys.argv[2]) if len(sys.argv) > 2 else start_chapter

    # Initialize client
    print("Initializing Azure OpenAI client...")
    client = init_client()

    print(f"\nGenerating audio for chapters {start_chapter} to {end_chapter}")
    print("=" * 70)

    for chapter_num in range(start_chapter, end_chapter + 1):
        try:
            generate_chapter_audio(client, chapter_num)
            print()
        except Exception as e:
            print(f"Error generating audio for chapter {chapter_num}: {e}")
            import traceback
            traceback.print_exc()
            continue

    print("=" * 70)
    print(f"Batch audio generation complete!")
    print(f"Processed chapters: {start_chapter} to {end_chapter}")

if __name__ == '__main__':
    main()
