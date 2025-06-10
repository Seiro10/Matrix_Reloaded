from dotenv import load_dotenv
load_dotenv()
import sys
import os
import pytest
from unittest.mock import patch, MagicMock

# Add src directory to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from models import SimilarKeyword, SERPAnalysis, SiteInfo
from config import WEBSITES
from tools import analyze_keyword_for_site_selection, fetch_sitemap_content, check_existing_content


class TestTools:

    def test_analyze_keyword_for_site_selection_gaming(self):
        """Test keyword analysis for gaming niche"""
        keyword = "meilleure souris gamer"
        similar_keywords = [
            {"keyword": "souris gaming", "monthly_searches": 1000, "competition": "low"}
        ]

        result = analyze_keyword_for_site_selection.invoke({
            "keyword": keyword,
            "similar_keywords": similar_keywords
        })

        assert result["recommended_niche"] == "gaming"
        assert result["confidence"] > 0.5
        assert "gaming" in result["scores"]

    def test_analyze_keyword_for_site_selection_marketing(self):
        """Test keyword analysis for marketing niche"""
        keyword = "stratégie marketing digital"
        similar_keywords = [
            {"keyword": "seo marketing", "monthly_searches": 800, "competition": "medium"}
        ]

        result = analyze_keyword_for_site_selection.invoke({
            "keyword": keyword,
            "similar_keywords": similar_keywords
        })

        assert result["recommended_niche"] == "marketing"
        assert result["confidence"] > 0.5

    @patch('tools.requests.get')
    def test_fetch_sitemap_content_success(self, mock_get):
        """Test successful sitemap fetching"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = '''<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>https://example.com/article1</loc></url>
            <url><loc>https://example.com/article2</loc></url>
        </urlset>'''
        mock_get.return_value = mock_response

        result = fetch_sitemap_content.invoke("https://example.com/sitemap.xml")

        assert len(result) == 2
        assert "https://example.com/article1" in result
        assert "https://example.com/article2" in result

    @patch('tools.requests.get')
    def test_fetch_sitemap_content_failure(self, mock_get):
        """Test failed sitemap fetching"""
        mock_get.side_effect = Exception("Network error")

        result = fetch_sitemap_content.invoke("https://example.com/sitemap.xml")

        assert result == []
