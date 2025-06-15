"""
Rewriter Agent - LangGraph-based Article Updating System
Processes CSV data from Router Agent to update existing WordPress articles
"""

import os
import sys
import csv
import requests
import logging
from typing import Dict, List, Any, Optional, Literal
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
import json
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Anthropic LLM
llm = ChatAnthropic(
    model="claude-3-5-sonnet-20241022",
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    temperature=0.3
)

# Import models
from .models import (
    CompetitorData,
    RewriterInput,
    ArticleContent,
    RewritingStrategy,
    RewriterState
)


class WordPressAPI:
    """WordPress API handler for authentication and content management"""

    def __init__(self):
        self.base_url = os.getenv("WORDPRESS_API_URL", "")
        self.username = os.getenv("WORDPRESS_USERNAME", "")
        self.password = os.getenv("WORDPRESS_PASSWORD", "")
        self.token = None

    def authenticate(self) -> bool:
        """Authenticate with WordPress using JWT"""
        auth_url = f"{self.base_url}/jwt-auth/v1/token"
        payload = {
            "username": self.username,
            "password": self.password
        }

        try:
            response = requests.post(auth_url, json=payload, timeout=30)
            response.raise_for_status()
            self.token = response.json().get("token")
            logger.info("✅ WordPress authentication successful")
            return True
        except Exception as e:
            logger.error(f"❌ WordPress authentication failed: {e}")
            return False

    def get_article_by_url(self, article_url: str) -> Optional[ArticleContent]:
        """Fetch article content by URL"""
        try:
            # Extract slug from URL
            slug = urlparse(article_url).path.strip('/').split('/')[-1]

            # Search for post by slug
            search_url = f"{self.base_url}/wp/v2/posts"
            headers = {"Authorization": f"Bearer {self.token}"}
            params = {"slug": slug, "per_page": 1}

            response = requests.get(search_url, headers=headers, params=params, timeout=30)
            response.raise_for_status()

            posts = response.json()
            if not posts:
                logger.error(f"No article found for URL: {article_url}")
                return None

            post = posts[0]

            return ArticleContent(
                id=post["id"],
                title=post["title"]["rendered"],
                content=post["content"]["rendered"],
                slug=post["slug"],
                meta_description=post.get("excerpt", {}).get("rendered", ""),
                featured_image=post.get("featured_image_url"),
                tags=[tag["name"] for tag in post.get("_embedded", {}).get("wp:term", [[]])[1]],
                categories=[cat["name"] for cat in post.get("_embedded", {}).get("wp:term", [[]])[0]]
            )

        except Exception as e:
            logger.error(f"❌ Error fetching article: {e}")
            return None

    def update_article(self, article_id: int, updated_content: str, title: str = None) -> bool:
        """Update article content via WordPress API"""
        try:
            update_url = f"{self.base_url}/wp/v2/posts/{article_id}"
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }

            payload = {
                "content": updated_content,
                "status": "private"  # Publish as private for review
            }

            if title:
                payload["title"] = title

            response = requests.post(update_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()

            logger.info(f"✅ Article {article_id} updated successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Error updating article: {e}")
            return False


def parse_csv_input(csv_file_path: str) -> RewriterInput:
    """Parse CSV input from Router Agent"""
    try:
        with open(csv_file_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            row = next(reader)  # Get first row

            # Parse competitor data
            competitors = []
            for i in range(1, 4):  # positions 1-3
                if row.get(f'title{i}'):
                    competitor = CompetitorData(
                        position=i,
                        title=row[f'title{i}'],
                        url=row[f'url{i}'],
                        snippet=row[f'snippet{i}'],
                        content=row[f'content{i}'],
                        structure=row[f'structure{i}'],
                        headlines=row[f'headlines{i}'].split(';') if row[f'headlines{i}'] else [],
                        metadescription=row[f'metadescription{i}']
                    )
                    competitors.append(competitor)

            return RewriterInput(
                keyword=row['KW'],
                competition=row['competition'],
                url_to_rewrite=row['Url'],  # Note: CSV uses 'Url' not 'url_to_rewrite'
                site=row['Site'],
                confidence=float(row['confidence']),
                monthly_searches=int(row['monthly_searches']),
                people_also_ask=row['people_also_ask'].split(';') if row['people_also_ask'] else [],
                forum=row['forum'].split(';') if row['forum'] else [],
                competitors=competitors
            )

    except Exception as e:
        logger.error(f"❌ Error parsing CSV: {e}")
        raise


# LangGraph Nodes
def fetch_original_article_node(state: RewriterState) -> RewriterState:
    """Node: Fetch original article from WordPress"""
    logger.info("🔄 Fetching original article from WordPress...")

    wp_api = WordPressAPI()
    if not wp_api.authenticate():
        state.errors.append("WordPress authentication failed")
        return state

    article = wp_api.get_article_by_url(state.input_data.url_to_rewrite)
    if not article:
        state.errors.append("Could not fetch original article")
        return state

    state.original_article = article
    logger.info(f"✅ Fetched article: {article.title}")
    return state


def analyze_competitors_node(state: RewriterState) -> RewriterState:
    """Node: Analyze competitor content for insights"""
    logger.info("🔄 Analyzing competitor content...")

    try:
        competitors = state.input_data.competitors
        insights = {
            "common_topics": [],
            "unique_angles": [],
            "content_gaps": [],
            "seo_opportunities": []
        }

        # Extract common topics from competitor headlines
        all_headlines = []
        for comp in competitors:
            all_headlines.extend(comp.headlines)

        # Simple keyword frequency analysis
        topic_frequency = {}
        for headline in all_headlines:
            words = headline.lower().split()
            for word in words:
                if len(word) > 3:  # Filter short words
                    topic_frequency[word] = topic_frequency.get(word, 0) + 1

        # Get top topics
        common_topics = sorted(topic_frequency.items(), key=lambda x: x[1], reverse=True)[:10]
        insights["common_topics"] = [topic[0] for topic in common_topics]

        # Analyze content structure patterns
        content_lengths = [len(comp.content) for comp in competitors if comp.content]
        if content_lengths:
            insights["avg_content_length"] = sum(content_lengths) / len(content_lengths)

        state.competitor_insights = insights
        logger.info(f"✅ Analyzed {len(competitors)} competitors")
        return state

    except Exception as e:
        logger.error(f"❌ Error analyzing competitors: {e}")
        state.errors.append(f"Competitor analysis failed: {str(e)}")
        return state


def generate_rewriting_strategy_node(state: RewriterState) -> RewriterState:
    """Node: Generate LLM-powered rewriting strategy"""
    logger.info("🔄 Generating rewriting strategy...")

    try:
        # Prepare context for LLM
        original_content = state.original_article.content
        competitor_insights = state.competitor_insights
        keyword = state.input_data.keyword
        people_also_ask = state.input_data.people_also_ask

        # Extract text content from HTML for analysis
        soup = BeautifulSoup(original_content, 'html.parser')
        text_content = soup.get_text()

        system_prompt = """You are an expert content strategist and SEO specialist. Your task is to analyze an existing article and create a strategic plan to update and improve it based on competitor analysis and search intent.

Your goal is to:
1. Identify sections that need updating or are outdated
2. Suggest new content to add based on competitor insights
3. Recommend SEO improvements
4. Maintain the original article's structure and tone

Be specific and actionable in your recommendations."""

        user_prompt = f"""
ORIGINAL ARTICLE ANALYSIS:
Title: {state.original_article.title}
Content Length: {len(text_content)} characters
Target Keyword: {keyword}

CURRENT CONTENT PREVIEW:
{text_content[:1000]}...

COMPETITOR INSIGHTS:
Common Topics: {', '.join(competitor_insights.get('common_topics', [])[:5])}
Average Competitor Content Length: {competitor_insights.get('avg_content_length', 0):.0f} characters

SEARCH INTENT (People Also Ask):
{chr(10).join(people_also_ask[:5])}

TOP COMPETITORS:
{chr(10).join([f"- {comp.title}: {comp.snippet}" for comp in state.input_data.competitors[:3]])}

Please provide a detailed rewriting strategy that will modernize this content while preserving its core value.
"""

        parser = PydanticOutputParser(pydantic_object=RewritingStrategy)

        messages = [
            SystemMessage(content=system_prompt + f"\n\n{parser.get_format_instructions()}"),
            HumanMessage(content=user_prompt)
        ]

        response = llm.invoke(messages)
        strategy = parser.parse(response.content)

        state.rewriting_strategy = strategy
        logger.info("✅ Rewriting strategy generated")
        return state

    except Exception as e:
        logger.error(f"❌ Error generating strategy: {e}")
        state.errors.append(f"Strategy generation failed: {str(e)}")
        return state


def rewrite_content_node(state: RewriterState) -> RewriterState:
    """Node: Execute content rewriting based on strategy"""
    logger.info("🔄 Rewriting content...")

    try:
        original_content = state.original_article.content
        strategy = state.rewriting_strategy
        keyword = state.input_data.keyword
        competitors = state.input_data.competitors

        # Prepare competitor content summaries
        competitor_summaries = []
        for comp in competitors:
            if comp.content:
                competitor_summaries.append(f"From {comp.title}: {comp.content[:300]}...")

        system_prompt = """You are an expert content rewriter specializing in article modernization. Your task is to update an existing HTML article while:

1. Preserving the original structure, HTML tags, and formatting
2. Keeping media elements (images, videos) intact
3. Updating outdated information with fresh insights
4. Improving SEO optimization
5. Maintaining the original tone and style

Return ONLY the updated HTML content, preserving all original HTML structure."""

        user_prompt = f"""
REWRITE THIS ARTICLE:

ORIGINAL HTML CONTENT:
{original_content}

REWRITING STRATEGY:
Sections to Update: {', '.join(strategy.sections_to_update)}
Content to Add: {strategy.content_to_add}
Outdated Elements: {', '.join(strategy.outdated_elements)}
SEO Improvements: {', '.join(strategy.seo_improvements)}

TARGET KEYWORD: {keyword}

COMPETITOR INSIGHTS FOR REFERENCE:
{chr(10).join(competitor_summaries[:3])}

PEOPLE ALSO ASK:
{chr(10).join(state.input_data.people_also_ask[:5])}

Please rewrite the article incorporating these improvements while maintaining all HTML structure, images, and formatting. Focus on making the content more current, comprehensive, and SEO-optimized.
"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]

        response = llm.invoke(messages)

        state.updated_content = response.content
        logger.info("✅ Content rewritten successfully")
        return state

    except Exception as e:
        logger.error(f"❌ Error rewriting content: {e}")
        state.errors.append(f"Content rewriting failed: {str(e)}")
        return state


def publish_updated_article_node(state: RewriterState) -> RewriterState:
    """Node: Publish updated article to WordPress"""
    logger.info("🔄 Publishing updated article...")

    try:
        wp_api = WordPressAPI()
        if not wp_api.authenticate():
            state.errors.append("WordPress authentication failed for publishing")
            return state

        success = wp_api.update_article(
            article_id=state.original_article.id,
            updated_content=state.updated_content,
            title=state.original_article.title
        )

        if success:
            state.wordpress_response = {
                "status": "success",
                "article_id": state.original_article.id,
                "updated_at": datetime.now().isoformat()
            }
            logger.info("✅ Article published successfully")
        else:
            state.errors.append("Failed to publish updated article")

        return state

    except Exception as e:
        logger.error(f"❌ Error publishing article: {e}")
        state.errors.append(f"Publishing failed: {str(e)}")
        return state


def create_rewriter_agent():
    """Create and configure the Rewriter Agent workflow"""
    logger.info("🚀 Creating Rewriter Agent...")

    # Create state graph
    workflow = StateGraph(RewriterState)

    # Add nodes
    workflow.add_node("fetch_article", fetch_original_article_node)
    workflow.add_node("analyze_competitors", analyze_competitors_node)
    workflow.add_node("generate_strategy", generate_rewriting_strategy_node)
    workflow.add_node("rewrite_content", rewrite_content_node)
    workflow.add_node("publish_article", publish_updated_article_node)

    # Define workflow edges
    workflow.add_edge(START, "fetch_article")
    workflow.add_edge("fetch_article", "analyze_competitors")
    workflow.add_edge("analyze_competitors", "generate_strategy")
    workflow.add_edge("generate_strategy", "rewrite_content")
    workflow.add_edge("rewrite_content", "publish_article")
    workflow.add_edge("publish_article", END)

    # Add error handling
    def should_continue(state: RewriterState) -> str:
        if state.errors:
            return END
        return "continue"

    # Compile with checkpointer
    checkpointer = MemorySaver()
    compiled_workflow = workflow.compile(checkpointer=checkpointer)

    logger.info("✅ Rewriter Agent created successfully")
    return compiled_workflow


async def process_rewriter_request(csv_file_path: str, output_dir: str = "./output") -> Dict[str, Any]:
    """Main function to process rewriter request"""
    try:
        # Parse input
        input_data = parse_csv_input(csv_file_path)
        logger.info(f"🎯 Processing rewrite request for: {input_data.keyword}")

        # Create agent
        agent = create_rewriter_agent()

        # Generate session ID
        session_id = f"rewriter_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        config = {"configurable": {"thread_id": session_id}}

        # Initialize state
        initial_state = RewriterState(input_data=input_data)

        # Execute workflow
        logger.info(f"🔄 Executing rewriter workflow (session: {session_id})")
        result = agent.invoke(initial_state, config=config)

        # Save results
        os.makedirs(output_dir, exist_ok=True)
        result_file = os.path.join(output_dir, f"rewriter_result_{session_id}.json")

        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump({
                "session_id": session_id,
                "keyword": input_data.keyword,
                "url_rewritten": input_data.url_to_rewrite,
                "success": len(result.errors) == 0,
                "errors": result.errors,
                "wordpress_response": result.wordpress_response,
                "strategy_applied": result.rewriting_strategy.dict() if result.rewriting_strategy else None,
                "timestamp": datetime.now().isoformat()
            }, indent=2, ensure_ascii=False)

        if result.errors:
            logger.error(f"❌ Rewriter workflow completed with errors: {result.errors}")
            return {
                "success": False,
                "errors": result.errors,
                "session_id": session_id
            }
        else:
            logger.info(f"✅ Rewriter workflow completed successfully")
            return {
                "success": True,
                "session_id": session_id,
                "article_id": result.original_article.id if result.original_article else None,
                "wordpress_response": result.wordpress_response,
                "result_file": result_file
            }

    except Exception as e:
        logger.error(f"❌ Error in rewriter process: {e}")
        return {
            "success": False,
            "error": str(e)
        }


if __name__ == "__main__":
    import asyncio

    # Example usage
    csv_file = "path/to/rewriter_input.csv"
    result = asyncio.run(process_rewriter_request(csv_file))
    print(f"Rewriter result: {result}")