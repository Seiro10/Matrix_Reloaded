# test_integration.py
import json
from src.models import ContentFinderOutput
from src.agent import process_content_finder_output
import asyncio

# Load your JSON data
with open('test.json', 'r', encoding='utf-8') as f:
    test_data = json.load(f)

# Create ContentFinderOutput
content_finder_output = ContentFinderOutput(keywords_data=test_data)

# Test the router
async def test_router():
    result = await process_content_finder_output(content_finder_output)
    print("Router Result:", result)

if __name__ == "__main__":
    asyncio.run(test_router())