from dotenv import load_dotenv
load_dotenv()
import sys
import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Add src directory to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from main import app
from models import ContentFinderOutput, SimilarKeyword, SERPAnalysis, TopResult


class TestMain:

    def setup_method(self):
        """Set up test client"""
        self.client = TestClient(app)

        self.test_payload = {
            "keyword": "meilleure souris gamer",
            "similar_keywords": [
                {"keyword": "souris gaming", "monthly_searches": 1000, "competition": "low"}
            ],
            "serp_analysis": {
                "top_results": [
                    {
                        "url": "https://example.com/best-gaming-mouse",
                        "title": "Best Gaming Mouse 2025",
                        "meta_description": "Top gaming mice",
                        "content": "Gaming mouse content",
                        "content_structure": ["h1", "h2"],
                        "publication_date": "2025-01-01"
                    }
                ],
                "people_also_ask": [
                    "Which mouse is best for gaming?",
                    "What DPI for gaming?"
                ]  # Simple strings, pas d'objets
            }
        }

    def test_health_check(self):  # Supprime async
        """Test health check endpoint"""
        response = self.client.get('/health')
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "content-router-agent"

    @patch('agent.process_content_finder_output')
    def test_route_content_success(self, mock_process):  # Supprime async et @pytest.mark.asyncio
        """Test successful routing"""
        mock_process.return_value = {
            "success": True,
            "routing_decision": "copywriter",
            "selected_site": {
                "site_id": 1,
                "name": "Gaming Hub",
                "domain": "gaminghub.fr",
                "niche": "gaming",
                "theme": "gaming-theme",
                "language": "fr",
                "sitemap_url": "https://gaminghub.fr/sitemap.xml",
                "wordpress_api_url": "https://gaminghub.fr/wp-json/wp/v2/"
            },
            "confidence_score": 0.8,
            "reasoning": "Test reasoning",
            "payload": {
                "agent_target": "copywriter",
                "keyword": "test",
                "site_config": {
                    "site_id": 1,
                    "name": "Gaming Hub",
                    "domain": "gaminghub.fr",
                    "niche": "gaming",
                    "theme": "gaming-theme",
                    "language": "fr",
                    "sitemap_url": "https://gaminghub.fr/sitemap.xml",
                    "wordpress_api_url": "https://gaminghub.fr/wp-json/wp/v2/"
                },
                "serp_analysis": {
                    "top_results": [],
                    "people_also_ask": []
                },
                "similar_keywords": [],
                "internal_linking_suggestions": [],
                "routing_metadata": {
                    "confidence_score": 0.8,
                    "timestamp": "2025-01-01T00:00:00"
                }
            },
            "internal_linking_suggestions": ["Link 1"]
        }

        response = self.client.post('/route', json=self.test_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True

    def test_route_content_no_data(self):  # Supprime async
        """Test routing with no JSON data"""
        response = self.client.post('/route')
        assert response.status_code == 422

    def test_route_content_invalid_data(self):  # Supprime async
        """Test routing with invalid JSON data"""
        invalid_payload = {"invalid": "data"}
        response = self.client.post('/route', json=invalid_payload)
        assert response.status_code == 422