
from dotenv import load_dotenv
load_dotenv()

import json
import os
import httpx
import re
import asyncio
from typing import Dict, Any


CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_API_KEY = os.getenv("ANTHROPIC_API_KEY")


def save_results_to_json(keyword_data: dict, output_dir="output", filename="results.json"):
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, filename)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(keyword_data, f, ensure_ascii=False, indent=2)

    print(f"[✅] Résultats sauvegardés dans : {output_path}")


async def send_to_claude_direct_api(data: dict) -> dict:
    """Direct API call to Claude with comprehensive error handling"""

    # First, let's check what we're working with
    print(f"[DEBUG] Data type: {type(data)}")
    print(f"[DEBUG] Data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")

    # Convert data to string to check size
    try:
        data_str = json.dumps(data, indent=2, ensure_ascii=False)
        data_size = len(data_str)
        print(f"[DEBUG] Data size: {data_size} characters")

        # If data is too large, use local cleaning
        if data_size > 15000:  # Conservative limit
            print(f"[WARNING] ⚠️ Data too large ({data_size} chars), using local cleaning")
            return clean_data_locally(data)

    except Exception as e:
        print(f"[ERROR] ❌ Cannot serialize data: {e}")
        return clean_data_locally(data)

    CLAUDE_API_KEY = os.getenv("ANTHROPIC_API_KEY")

    if not CLAUDE_API_KEY:
        print("[ERROR] ❌ ANTHROPIC_API_KEY not found")
        return clean_data_locally(data)

    headers = {
        "Content-Type": "application/json",
        "x-api-key": CLAUDE_API_KEY,
        "anthropic-version": "2023-06-01"
    }

    # Shorter, more focused prompt
    system_prompt = (
        "Clean this JSON data by removing special characters like \\xa0, \\u200b, etc. "
        "Fix spacing issues. Return only the cleaned JSON with the same structure."
    )

    # Limit the data we send
    if data_size > 8000:
        data_str = data_str[:8000] + "\n...(truncated)"

    user_prompt = f"Clean this JSON:\n\n```json\n{data_str}\n```"

    payload = {
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 4000,
        "temperature": 0.1,  # Lower temperature for more consistent output
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}]
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            print("[DEBUG] 🔄 Sending request to Claude...")

            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload
            )

            print(f"[DEBUG] 📊 Response status: {response.status_code}")

            if response.status_code != 200:
                error_text = response.text
                print(f"[ERROR] ❌ API Error {response.status_code}: {error_text[:500]}")
                return clean_data_locally(data)

            response_data = response.json()
            raw_content = response_data["content"][0]["text"].strip()

            print(f"[DEBUG] 📝 Raw response length: {len(raw_content)}")
            print(f"[DEBUG] 📝 Raw response preview: {raw_content[:200]}...")

            # More robust JSON extraction
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', raw_content, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find JSON without code blocks
                json_str = re.sub(r'^[^{]*', '', raw_content)
                json_str = re.sub(r'[^}]*$', '', json_str)

            # Clean up common issues
            json_str = json_str.replace('–', '-').replace('—', '-')

            try:
                cleaned_data = json.loads(json_str)
                print("[DEBUG] ✅ Successfully parsed Claude response")
                return cleaned_data
            except json.JSONDecodeError as e:
                print(f"[ERROR] ❌ JSON parse error: {e}")
                print(f"[DEBUG] Problematic JSON: {json_str[:500]}...")
                return clean_data_locally(data)

    except Exception as e:
        print(f"[ERROR] ❌ Request failed: {type(e).__name__}: {e}")
        return clean_data_locally(data)