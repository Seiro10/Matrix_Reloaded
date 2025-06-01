import os
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()


async def test_anthropic_api():
    """
    Test Anthropic API connection with minimal payload
    """
    CLAUDE_API_KEY = os.getenv("ANTHROPIC_API_KEY")

    if not CLAUDE_API_KEY:
        print("❌ ANTHROPIC_API_KEY not found in environment")
        return False

    print(f"✅ API Key found: {CLAUDE_API_KEY[:10]}...")

    headers = {
        "Content-Type": "application/json",
        "x-api-key": CLAUDE_API_KEY,
        "anthropic-version": "2023-06-01"
    }

    # Minimal test payload
    payload = {
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 100,
        "messages": [
            {
                "role": "user",
                "content": "Hello, respond with just 'API working'"
            }
        ]
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            print("🔄 Testing API connection...")
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload
            )

            print(f"📊 Status Code: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                content = data["content"][0]["text"]
                print(f"✅ API Response: {content}")
                return True
            else:
                print(f"❌ Error Response: {response.text}")
                return False

    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return False


if __name__ == "__main__":
    print("=== Testing Anthropic API Connection ===\n")

    # Test basic connection
    result = asyncio.run(test_anthropic_api())

    if not result:
        print("\n=== Testing Different Models ===")
        asyncio.run(test_with_different_models())

    print("\n=== Test Complete ===")