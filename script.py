#!/usr/bin/env python3
"""
Simple test script to verify router-rewriter communication
"""

import requests
import json
import time


def test_rewriter_direct():
    """Test calling rewriter agent directly"""
    print("🧪 Testing Rewriter Agent Direct Call")
    print("=" * 50)

    # Create a test CSV content that matches rewriter expectations
    csv_content = """Url,KW,competition,Site,confidence,monthly_searches,people_also_ask,forum,position1,title1,url1,snippet1,content1,structure1,headlines1,metadescription1,position2,title2,url2,snippet2,content2,structure2,headlines2,metadescription2,position3,title3,url3,snippet3,content3,structure3,headlines3,metadescription3
https://stuffgaming.fr/final-fantasy-14-avis/,final fantasy 14,HIGH,Stuffgaming,0.95,1500,Qu'est-ce que Final Fantasy 14?;Est-ce que FF14 vaut le coup?,Forum reddit FF14;Discussion MMO,1,Guide Final Fantasy XIV 2024,https://example1.com,Guide complet pour débuter FF14,Contenu détaillé sur FF14,<h1>Guide FF14</h1>,Introduction;Gameplay;Conclusion,Guide complet Final Fantasy XIV,2,Test Final Fantasy XIV,https://example2.com,Notre test complet du MMO,Test approfondi du jeu,<h1>Test</h1>,Présentation;Avis;Note,Test Final Fantasy XIV 2024,3,FF14 débutant guide,https://example3.com,Guide pour nouveaux joueurs,Conseils pour débuter,<h1>Débutants</h1>,Premiers pas;Conseils;Astuces,Guide débutant FF14"""

    # Save to temp file
    import tempfile
    import os

    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
        f.write(csv_content)
        csv_file_path = f.name

    try:
        print(f"📄 Created test CSV: {csv_file_path}")

        # Call rewriter agent
        with open(csv_file_path, 'rb') as f:
            files = {'file': ('test_rewriter.csv', f, 'text/csv')}

            print("🔄 Calling Rewriter Agent...")
            response = requests.post(
                "http://localhost:8082/rewrite/csv",
                files=files,
                timeout=30
            )

        print(f"📊 Response Status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print("✅ Rewriter Agent Response:")
            print(f"   Success: {result.get('success')}")
            print(f"   Session ID: {result.get('session_id')}")
            print(f"   Message: {result.get('message')}")

            if result.get('session_id'):
                # Check status
                print(f"\n🔍 Checking rewriter status...")
                status_response = requests.get(
                    f"http://localhost:8082/rewrite/status/{result['session_id']}"
                )

                if status_response.status_code == 200:
                    status = status_response.json()
                    print(f"   Status: {status.get('status')}")
                    print(f"   Progress: {status.get('progress')}")
                else:
                    print(f"   ❌ Status check failed: {status_response.status_code}")

            return True
        else:
            print(f"❌ Rewriter call failed: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        # Cleanup
        try:
            os.unlink(csv_file_path)
        except:
            pass


def test_router_direct():
    """Test calling router agent directly"""
    print("\n🧪 Testing Router Agent Direct Call")
    print("=" * 50)

    # Test data that matches ContentFinderOutput format
    test_data = {
        "keywords_data": {
            "final fantasy 14": {
                "keyword": "final fantasy 14",
                "competition": "HIGH",
                "monthly_searches": 1500,
                "people_also_ask": [
                    "Qu'est-ce que Final Fantasy 14?",
                    "Est-ce que FF14 vaut le coup?"
                ],
                "people_also_search_for": [
                    "ffxiv guide",
                    "final fantasy mmo",
                    "ff14 débutant"
                ],
                "organic_results": [
                    {
                        "position": 1,
                        "title": "Guide Final Fantasy XIV 2024",
                        "url": "https://example1.com",
                        "snippet": "Guide complet pour débuter FF14",
                        "content": "Contenu détaillé sur FF14",
                        "structure": "<h1>Guide FF14</h1>",
                        "headlines": ["Introduction", "Gameplay", "Conclusion"],
                        "metadescription": "Guide complet Final Fantasy XIV"
                    }
                ],
                "forum": ["Forum reddit FF14"],
                "total_results_found": 156000
            }
        }
    }

    try:
        print("🔄 Calling Router Agent...")
        response = requests.post(
            "http://localhost:8080/route",
            json=test_data,
            timeout=60
        )

        print(f"📊 Response Status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print("✅ Router Agent Response:")
            print(f"   Success: {result.get('success')}")
            print(f"   Routing Decision: {result.get('routing_decision')}")
            print(f"   Selected Site: {result.get('selected_site', {}).get('name')}")
            print(f"   Confidence: {result.get('confidence_score', 0):.1%}")
            print(f"   CSV File: {result.get('csv_file')}")

            # Check if agent was called
            agent_response = result.get('agent_response')
            if agent_response:
                print(f"   Agent Called: {agent_response.get('success')}")
                if agent_response.get('session_id'):
                    print(f"   Agent Session: {agent_response.get('session_id')}")

            return True
        else:
            print(f"❌ Router call failed: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def check_agents_health():
    """Check health of all agents"""
    print("🏥 Checking Agent Health")
    print("=" * 30)

    agents = [
        ("Content Finder", "http://localhost:8000"),
        ("Router Agent", "http://localhost:8080"),
        ("Rewriter Agent", "http://localhost:8082")
    ]

    all_healthy = True

    for name, url in agents:
        try:
            response = requests.get(f"{url}/health", timeout=5)
            if response.status_code == 200:
                print(f"✅ {name}: HEALTHY")
            else:
                print(f"❌ {name}: UNHEALTHY ({response.status_code})")
                all_healthy = False
        except Exception as e:
            print(f"❌ {name}: UNREACHABLE ({e})")
            all_healthy = False

    return all_healthy


if __name__ == "__main__":
    print("🚀 Starting Agent Communication Tests")
    print("=" * 60)

    # Check health first
    if not check_agents_health():
        print("\n❌ Some agents are not healthy. Please check your setup.")
        exit(1)

    print("\n" + "=" * 60)

    # Test rewriter direct
    rewriter_ok = test_rewriter_direct()

    print("\n" + "=" * 60)

    # Test router (which should call rewriter)
    router_ok = test_router_direct()

    print("\n" + "=" * 60)
    print("📋 Test Results:")
    print(f"   Rewriter Direct: {'✅ PASS' if rewriter_ok else '❌ FAIL'}")
    print(f"   Router + Rewriter: {'✅ PASS' if router_ok else '❌ FAIL'}")

    if rewriter_ok and router_ok:
        print("\n🎉 All tests passed! Agent communication is working.")
    else:
        print("\n⚠️ Some tests failed. Check the logs above for details.")