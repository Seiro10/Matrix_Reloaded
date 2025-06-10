from dotenv import load_dotenv
load_dotenv()
import pytest
from unittest.mock import patch, MagicMock
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agent import site_selection_node, content_analysis_node, routing_decision_node, create_content_router_agent
from models import RouterState, ContentFinderOutput, SimilarKeyword, SERPAnalysis


class TestAgent:

    def setup_method(self):
        """Set up test data"""
        from models import ContentFinderOutput, SimilarKeyword, SERPAnalysis, TopResult

        # Crée un TopResult conforme au modèle
        top_result = TopResult(
            url="https://example.com/best-gaming-mouse",
            title="Best Gaming Mouse 2025",
            meta_description="Top gaming mice",
            content="Gaming mouse content",
            content_structure=["h1", "h2"],
            publication_date="2025-01-01"
        )

        # SERPAnalysis avec people_also_ask comme List[str]
        serp_analysis = SERPAnalysis(
            top_results=[top_result],
            people_also_ask=["Which mouse is best for gaming?", "What DPI for gaming?"]  # Simple strings
        )

        similar_keyword = SimilarKeyword(
            keyword="souris gaming",
            monthly_searches=1000,
            competition="low"
        )

        self.test_input = ContentFinderOutput(
            keyword="meilleure souris gamer",
            similar_keywords=[similar_keyword],
            serp_analysis=serp_analysis
        )

    @patch('tools.analyze_keyword_for_site_selection')  # Au lieu de 'agent.analyze_keyword_for_site_selection'
    def test_site_selection_node(self, mock_analyze):
        """Test site selection node"""
        mock_analyze.invoke.return_value = {
            "recommended_niche": "gaming",
            "confidence": 0.8,
            "analysis_details": {"matched_indicators": ["gaming", "souris"]}
        }
        # ... reste du test

        state = {
            "input_data": self.test_input,
            "selected_site": None,
            "existing_content": None,
            "routing_decision": None,
            "confidence_score": None,
            "internal_linking_suggestions": None,
            "reasoning": None,
            "output_payload": None
        }

        result = site_selection_node(state)

        assert result["selected_site"]["niche"] == "gaming"
        assert result["confidence_score"] == 0.8
        assert result["selected_site"]["name"] == "Gaming Hub"

    @patch('agent.generate_internal_links')
    @patch('agent.check_existing_content')
    @patch('agent.fetch_sitemap_content')
    def test_content_analysis_node(self, mock_sitemap, mock_content, mock_links):
        """Test content analysis node"""
        mock_sitemap.invoke.return_value = ["https://example.com/page1", "https://example.com/page2"]
        mock_content.invoke.return_value = {
            "content_found": False,
            "source": None,
            "content": None,
            "confidence": 0.0,
            "reason": "No content found"
        }
        mock_links.invoke.return_value = ["Link 1", "Link 2"]

        state = {
            "input_data": self.test_input,
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
            "existing_content": None,
            "routing_decision": None,
            "confidence_score": 1,
            "internal_linking_suggestions": None,
            "reasoning": None,
            "output_payload": None
        }

        result = content_analysis_node(state)

        assert result["existing_content"]["content_found"] == False
        assert len(result["internal_linking_suggestions"]) == 2

    def test_routing_decision_node_copywriter(self):
        """Test routing decision for copywriter"""
        state = {
            "input_data": self.test_input,
            "selected_site": {"site_id": 1, "name": "Gaming Hub"},
            "existing_content": {
                "content_found": False,
                "confidence": 0.0,
                "reason": "No content found"
            },
            "routing_decision": "copywriter",
            "confidence_score": 1,
            "internal_linking_suggestions": ["Link 1"],
            "reasoning": None,
            "output_payload": None
        }

        result = routing_decision_node(state)

        assert result["routing_decision"] == "copywriter"
        assert result["output_payload"]["agent_target"] == "copywriter"
        assert "No similar content found" in result["reasoning"]

    def test_routing_decision_node_rewriter(self):
        """Test routing decision for rewriter"""
        state = {
            "input_data": self.test_input,
            "selected_site": {"site_id": 1, "name": "Gaming Hub"},
            "existing_content": {
                "content_found": True,
                "confidence": 0.9,
                "reason": "Found similar content",
                "content": {"url": "https://example.com/existing"}
            },
            "routing_decision": None,
            "confidence_score": 0.9,
            "internal_linking_suggestions": ["Link 1"],
            "reasoning": None,
            "output_payload": None
        }

        result = routing_decision_node(state)

        assert result["routing_decision"] == "rewriter"
        assert result["output_payload"]["agent_target"] == "rewriter"
        assert "Similar content found" in result["reasoning"]

    def test_create_content_router_agent(self):
        """Test agent creation"""
        agent = create_content_router_agent()

        assert agent is not None
        # Test that the agent has the expected structure
        assert hasattr(agent, 'invoke')
        assert hasattr(agent, 'stream')
