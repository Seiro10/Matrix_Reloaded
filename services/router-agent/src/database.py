import sqlite3
import json
import os
import sys
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
from contextlib import contextmanager

# Add src directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Change relative imports to absolute imports
from config import settings

logger = logging.getLogger(__name__)


class ContentDatabase:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or settings.db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_db()

    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()

    def init_db(self):
        """Initialize database tables and indexes"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Articles table
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS articles
                           (
                               id
                               INTEGER
                               PRIMARY
                               KEY,
                               site_id
                               INTEGER,
                               url
                               TEXT,
                               title
                               TEXT,
                               slug
                               TEXT,
                               content
                               TEXT,
                               keywords
                               TEXT,
                               meta_description
                               TEXT,
                               status
                               TEXT
                               DEFAULT
                               'published',
                               created_at
                               TIMESTAMP
                               DEFAULT
                               CURRENT_TIMESTAMP,
                               updated_at
                               TIMESTAMP
                               DEFAULT
                               CURRENT_TIMESTAMP,
                               UNIQUE
                           (
                               site_id,
                               slug
                           )
                               )
                           ''')

            # Indexes for performance
            cursor.execute('''
                           CREATE INDEX IF NOT EXISTS idx_site_keywords
                               ON articles(site_id, keywords)
                           ''')

            cursor.execute('''
                           CREATE INDEX IF NOT EXISTS idx_site_title
                               ON articles(site_id, title)
                           ''')

            cursor.execute('''
                           CREATE INDEX IF NOT EXISTS idx_site_slug
                               ON articles(site_id, slug)
                           ''')

            conn.commit()
            logger.info("Database initialized successfully")

    def search_similar_content(self, site_id: int, keyword: str) -> Optional[Dict]:
        """
        Search for similar content using keyword matching strategies

        Args:
            site_id: Website ID to search in
            keyword: Keyword to search for

        Returns:
            Dict with article details if found, None otherwise
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Multiple search strategies in order of precision
            search_strategies = [
                # Exact keyword match
                f'%{keyword}%',
                # Keyword with spaces replaced by wildcards
                f'%{keyword.replace(" ", "%")}%',
                # First two words of keyword
                f'%{" ".join(keyword.split()[:2])}%',
                # Individual words
                f'%{keyword.split()[0]}%' if keyword.split() else f'%{keyword}%'
            ]

            for i, pattern in enumerate(search_strategies):
                cursor.execute('''
                               SELECT *
                               FROM articles
                               WHERE site_id = ?
                                 AND (
                                   LOWER(title) LIKE LOWER(?) OR
                                   LOWER(keywords) LIKE LOWER(?) OR
                                   LOWER(slug) LIKE LOWER(?)
                                   )
                               ORDER BY updated_at DESC LIMIT 1
                               ''', (site_id, pattern, pattern, pattern))

                result = cursor.fetchone()
                if result:
                    logger.info(f"Found similar content using strategy {i + 1}: {pattern}")
                    return {
                        'id': result[0],
                        'site_id': result[1],
                        'url': result[2],
                        'title': result[3],
                        'slug': result[4],
                        'content': result[5],
                        'keywords': result[6],
                        'meta_description': result[7],
                        'status': result[8],
                        'similarity_reason': f'Matched pattern: {pattern}'
                    }

            logger.info(f"No similar content found for keyword: {keyword}")
            return None

    def get_articles_by_site(self, site_id: int, limit: int = 50) -> List[Dict]:
        """Get all articles for a specific site"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                           SELECT *
                           FROM articles
                           WHERE site_id = ?
                           ORDER BY updated_at DESC LIMIT ?
                           ''', (site_id, limit))

            results = cursor.fetchall()
            return [
                {
                    'id': row[0],
                    'site_id': row[1],
                    'url': row[2],
                    'title': row[3],
                    'slug': row[4],
                    'content': row[5],
                    'keywords': row[6],
                    'meta_description': row[7],
                    'status': row[8]
                }
                for row in results
            ]

    def insert_article(self, article_data: Dict) -> int:
        """Insert a new article record"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO articles 
                (site_id, url, title, slug, content, keywords, meta_description, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                article_data['site_id'],
                article_data['url'],
                article_data['title'],
                article_data['slug'],
                article_data['content'],
                article_data['keywords'],
                article_data['meta_description'],
                article_data.get('status', 'published')
            ))
            conn.commit()
            return cursor.lastrowid

    def add_article(self, site_id, url, title, slug, content, keywords, meta_description=None):
        """Alias for insert_article to match test expectations"""
        article_data = {
            'site_id': site_id,
            'url': url,
            'title': title,
            'slug': slug,
            'content': content,
            'keywords': keywords,
            'meta_description': meta_description or ""
        }
        return self.insert_article(article_data)

    def update_article(self, article_id: int, updates: Dict) -> bool:
        """Update an existing article"""
        if not updates:
            return False

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Build dynamic update query
            set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
            values = list(updates.values()) + [article_id]

            cursor.execute(f'''
                UPDATE articles 
                SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', values)

            conn.commit()
            return cursor.rowcount > 0

    def delete_article(self, article_id: int) -> bool:
        """Delete an article by ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM articles WHERE id = ?', (article_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_stats(self) -> Dict:
        """Get database statistics"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Total articles per site
            cursor.execute('''
                           SELECT site_id, COUNT(*) as article_count
                           FROM articles
                           GROUP BY site_id
                           ''')
            site_stats = dict(cursor.fetchall())

            # Total articles
            cursor.execute('SELECT COUNT(*) FROM articles')
            total_articles = cursor.fetchone()[0]

            return {
                'total_articles': total_articles,
                'articles_per_site': site_stats,
                'database_path': self.db_path
            }

    def get_related_articles(self, site_id: int, keywords: str, limit: int = 10) -> List[Dict]:
        """Get articles related to given keywords"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                           SELECT *
                           FROM articles
                           WHERE site_id = ?
                             AND (LOWER(keywords) LIKE LOWER(?) OR LOWER(title) LIKE LOWER(?))
                           ORDER BY updated_at DESC LIMIT ?
                           ''', (site_id, f'%{keywords}%', f'%{keywords}%', limit))

            results = cursor.fetchall()
            return [
                {
                    'id': row[0],
                    'site_id': row[1],
                    'url': row[2],
                    'title': row[3],
                    'slug': row[4],
                    'content': row[5],
                    'keywords': row[6],
                    'meta_description': row[7],
                    'status': row[8]
                }
                for row in results
            ]