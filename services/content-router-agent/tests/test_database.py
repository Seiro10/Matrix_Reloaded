from dotenv import load_dotenv
load_dotenv()
import pytest
import tempfile
import os
import sys

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from database import ContentDatabase


class TestContentDatabase:

    def setup_method(self):
        """Set up test database"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.db = ContentDatabase(self.temp_db.name)

    def teardown_method(self):
        """Clean up test database"""
        os.unlink(self.temp_db.name)

    def test_init_db(self):
        """Test database initialization"""
        # Database should be created and initialized
        assert os.path.exists(self.temp_db.name)

    def test_add_and_search_article(self):
        """Test adding and searching for articles"""
        # Add test article
        success = self.db.add_article(
            site_id=1,
            url="https://example.com/test-article",
            title="Test Gaming Article",
            slug="test-gaming-article",
            content="This is a test article about gaming",
            keywords="gaming, test, article",
            meta_description="Test article description"
        )

        assert success

        # Search for similar content
        result = self.db.search_similar_content(1, "gaming")

        assert result is not None
        assert result["title"] == "Test Gaming Article"
        assert result["site_id"] == 1

    def test_search_no_results(self):
        """Test searching when no results exist"""
        result = self.db.search_similar_content(1, "nonexistent")
        assert result is None

    def test_get_related_articles(self):
        """Test getting related articles"""
        # Add multiple test articles FIRST
        self.db.add_article(1, "https://example.com/article1", "Gaming Review 1", "gaming-review-1", "Content",
                            "gaming, review")
        self.db.add_article(1, "https://example.com/article2", "Gaming Guide 2", "gaming-guide-2", "Content",
                            "gaming, guide")

        # Now test getting them
        related = self.db.get_related_articles(1, "gaming")
        assert len(related) >= 2
