#!/usr/bin/env python3
"""
Test different endpoint combinations to find correct ElevenLabs TTS path
"""

import os
from openai import AzureOpenAI
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

test_text = '测试'
api_key = os.getenv('TTS_API_KEY')

# Different endpoint variations to try
base_urls = [
    'https://search.bytedance.net',
    'https://bytedance.net',
]

paths = [
    '/gpt/openapi/online/v2/multimodal/openai/deployments/gpt_openapi',
    '/multimodal/openapi/online/v2/crawl/openai/deployments/gpt_openapi',
    '/gpt/multimodal/online/v2/crawl/openai/deployments/gpt_openapi',
    '/openapi/multimodal/online/v2/crawl/openai/deployments/gpt_openapi',
    '/gpt/openapi/multimodal/v2/crawl/openai/deployments/gpt_openapi',
    '/gpt/openapi/online/multimodal/crawl/openai/deployments/gpt_openapi',
]

# Model variations
models = ['elevenlabs', 'tts-elevenlabs', 'eleven_labs', 'elevenlabs-tts']

# Voice variations
voices = ['nova', 'alloy', 'echo', 'fable', 'onyx', 'shimmer']

print("Testing ElevenLabs TTS endpoints...")
print("=" * 70)

endpoint_count = 0
for base_url in base_urls:
    for path in paths:
        endpoint = base_url + path
        endpoint_count += 1

        print(f"\n[{endpoint_count}] Testing: {endpoint}")

        try:
            client = AzureOpenAI(
                azure_endpoint=endpoint,
                api_key=api_key,
                api_version='preview',
                timeout=20
            )

            # Try first model with first voice
            response = client.audio.speech.create(
                model=models[0],
                voice=voices[0],
                input=test_text
            )

            output_file = Path('test_elevenlabs.mp3')
            response.stream_to_file(output_file)

            file_size = output_file.stat().st_size / 1024
            print(f"  ✓ SUCCESS!")
            print(f"  ✓ Endpoint: {endpoint}")
            print(f"  ✓ Model: {models[0]}")
            print(f"  ✓ Voice: {voices[0]}")
            print(f"  ✓ File size: {file_size:.2f} KB")
            print("\n" + "=" * 70)
            print("FOUND WORKING CONFIGURATION!")
            print("=" * 70)
            exit(0)

        except Exception as e:
            error_msg = str(e)
            if '404' in error_msg:
                print(f"  ✗ 404 Not Found")
            elif '403' in error_msg:
                print(f"  ✗ 403 Forbidden")
                # Print more details for 403
                if 'multimodal' in error_msg.lower():
                    print(f"     Still needs multimodal cluster")
            elif 'Unauthorized' in error_msg:
                print(f"  ✗ Unauthorized")
            else:
                print(f"  ✗ {error_msg[:150]}")

print("\n" + "=" * 70)
print("No working endpoint found.")
print("=" * 70)
print("\nSuggestions:")
print("1. Check if you have access to the multimodal cluster")
print("2. Verify your API key has multimodal/elevenlabs permissions")
print("3. Contact the platform team for the correct endpoint")
print("4. Check if there's a different API key for multimodal services")
