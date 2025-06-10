from typing import List, Dict, Any

def extract_urls_per_kw(input_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extrait les 3 premières URLs organiques et forums par mot-clé.
    Retourne un état compatible avec le graphe LangGraph.
    """
    results = []

    for kw_data in input_data:
        kw = kw_data.get("keyword", "UNKNOWN")
        organic = kw_data.get("organic_results", [])[:3]
        forums = kw_data.get("forum", [])[:3]

        base = {
            "Kw name": kw,
            "Competition": kw_data.get("competition", "UNKNOWN"),
            "People also ask": kw_data.get("people_also_ask", []),
            "people_also_search_for": kw_data.get("people_also_search_for", [])
        }

        print(f"\n🔍 [KW] {kw}")
        print(f"  ↪ Organic: {len(organic)} | Forums: {len(forums)}")

        for res in organic:
            url_entry = {
                **base,
                "Position": res.get("position", "N/A"),
                "Title": res.get("title", ""),
                "URL": res.get("url", ""),
                "Type": "organic"
            }
            print(f"    ✅ [ORG] {url_entry['URL']}")
            results.append(url_entry)

        for i, url in enumerate(forums):
            url_entry = {
                **base,
                "Position": f"forum_{i+1}",
                "Title": "",
                "URL": url,
                "Type": "forum"
            }
            print(f"    ✅ [FORUM] {url}")
            results.append(url_entry)

    print(f"\n📦 Total URLs to process: {len(results)}\n")
    return {
        "urls_to_process": results
    }
