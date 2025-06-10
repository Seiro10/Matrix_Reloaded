import json
import sys
import os
from pathlib import Path

# Get absolute paths
project_root = os.path.abspath('.')
router_src = os.path.join(project_root, 'services', 'content-router-agent', 'src')

print(f"Project root: {project_root}")
print(f"Router src path: {router_src}")
print(f"Router src exists: {os.path.exists(router_src)}")

# Add to Python path
if router_src not in sys.path:
    sys.path.insert(0, router_src)

print("Python path:", sys.path[:3])  # Show first 3 paths


def test_model_compatibility():
    """Test if ContentFinderOutput can parse your JSON"""

    try:
        # Import with explicit module path
        from models import ContentFinderOutput
        print("✅ Successfully imported ContentFinderOutput")
    except ImportError as e:
        print(f"❌ Import failed: {e}")

        # Debug: check what's in the router src directory
        print(f"Files in router src: {os.listdir(router_src)}")
        return False

    # Path to test data
    test_file = os.path.join('services', 'agents-content-finder', 'test.json')

    if not os.path.exists(test_file):
        print(f"❌ Test file not found: {test_file}")
        return False

    print(f"✅ Found test file: {test_file}")

    try:
        with open(test_file, 'r', encoding='utf-8') as f:
            test_data = json.load(f)

        print("📄 Loaded test data with keywords:", list(test_data.keys()))

        # Test model parsing
        content_output = ContentFinderOutput(keywords_data=test_data)

        print("✅ Model parsing successful!")
        print(f"🎯 Primary keyword: '{content_output.keyword}'")
        print(f"📊 Similar keywords count: {len(content_output.similar_keywords)}")
        print(f"🔍 SERP top results count: {len(content_output.serp_analysis.top_results)}")
        print(f"❓ People also ask count: {len(content_output.serp_analysis.people_also_ask)}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("🚀 Starting compatibility test...")
    success = test_model_compatibility()
    if success:
        print("🎉 All tests passed!")
    else:
        print("💥 Tests failed!")