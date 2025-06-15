"""
Fixed csv_utils.py to match rewriter agent expected format
"""

import csv
import os
import logging
from typing import Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


def create_copywriter_csv(
        keyword: str,
        keyword_data: Dict[str, Any],
        site_info: Dict[str, Any],
        confidence: float,
        output_dir: str = "./output"
) -> str:
    """
    Create CSV file for Copywriter Agent with comprehensive SERP data

    Args:
        keyword: Target keyword
        keyword_data: Full keyword data from ContentFinderOutput
        site_info: Selected site information
        confidence: Routing confidence score
        output_dir: Directory to save CSV files

    Returns:
        Path to created CSV file
    """

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Generate filename
    safe_keyword = "".join(c for c in keyword if c.isalnum() or c in (' ', '-', '_')).strip()
    safe_keyword = safe_keyword.replace(' ', '_')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"copywriter_{safe_keyword}_{timestamp}.csv"
    filepath = os.path.join(output_dir, filename)

    try:
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)

            # Write header
            header = [
                'KW', 'competition', 'Site', 'confidence', 'monthly_searches',
                'people_also_ask', 'forum',
                'position1', 'title1', 'url1', 'snippet1', 'content1', 'structure1', 'headlines1', 'metadescription1',
                'position2', 'title2', 'url2', 'snippet2', 'content2', 'structure2', 'headlines2', 'metadescription2',
                'position3', 'title3', 'url3', 'snippet3', 'content3', 'structure3', 'headlines3', 'metadescription3'
            ]
            writer.writerow(header)

            # Prepare data
            organic_results = keyword_data.get('organic_results', [])
            people_also_ask = '; '.join(keyword_data.get('people_also_ask', []))
            forum_links = '; '.join(keyword_data.get('forum', []))

            # Prepare SERP results (up to 3)
            serp_data = {}
            for i in range(1, 4):  # positions 1-3
                if i <= len(organic_results):
                    result = organic_results[i - 1]
                    serp_data[f'position{i}'] = result.get('position', i)
                    serp_data[f'title{i}'] = result.get('title', '')
                    serp_data[f'url{i}'] = result.get('url', '')
                    serp_data[f'snippet{i}'] = result.get('snippet', '')
                    serp_data[f'content{i}'] = result.get('content', '')
                    serp_data[f'structure{i}'] = result.get('structure', '')
                    serp_data[f'headlines{i}'] = '; '.join(result.get('headlines', []))
                    serp_data[f'metadescription{i}'] = result.get('metadescription', '')
                else:
                    # Empty data for missing results
                    serp_data[f'position{i}'] = ''
                    serp_data[f'title{i}'] = ''
                    serp_data[f'url{i}'] = ''
                    serp_data[f'snippet{i}'] = ''
                    serp_data[f'content{i}'] = ''
                    serp_data[f'structure{i}'] = ''
                    serp_data[f'headlines{i}'] = ''
                    serp_data[f'metadescription{i}'] = ''

            # Write data row
            row = [
                keyword,
                keyword_data.get('competition', 'UNKNOWN'),
                site_info.get('name', ''),
                f"{confidence:.2f}",
                keyword_data.get('monthly_searches', 0),
                people_also_ask,
                forum_links,
                serp_data['position1'], serp_data['title1'], serp_data['url1'],
                serp_data['snippet1'], serp_data['content1'], serp_data['structure1'],
                serp_data['headlines1'], serp_data['metadescription1'],
                serp_data['position2'], serp_data['title2'], serp_data['url2'],
                serp_data['snippet2'], serp_data['content2'], serp_data['structure2'],
                serp_data['headlines2'], serp_data['metadescription2'],
                serp_data['position3'], serp_data['title3'], serp_data['url3'],
                serp_data['snippet3'], serp_data['content3'], serp_data['structure3'],
                serp_data['headlines3'], serp_data['metadescription3']
            ]
            writer.writerow(row)

        logger.info(f"✅ Created copywriter CSV: {filepath}")
        return filepath

    except Exception as e:
        logger.error(f"❌ Error creating copywriter CSV: {e}")
        return None


def create_rewriter_csv(
        existing_content_url: str,
        keyword: str,
        keyword_data: Dict[str, Any],
        site_info: Dict[str, Any],
        confidence: float,
        output_dir: str = "./output"
) -> str:
    """
    Create CSV file for Rewriter Agent with existing content URL + SERP data
    Format must match exactly what rewriter agent expects

    Args:
        existing_content_url: URL of content to rewrite
        keyword: Target keyword
        keyword_data: Full keyword data from ContentFinderOutput
        site_info: Selected site information
        confidence: Routing confidence score
        output_dir: Directory to save CSV files

    Returns:
        Path to created CSV file
    """

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Generate filename
    safe_keyword = "".join(c for c in keyword if c.isalnum() or c in (' ', '-', '_')).strip()
    safe_keyword = safe_keyword.replace(' ', '_')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"rewriter_{safe_keyword}_{timestamp}.csv"
    filepath = os.path.join(output_dir, filename)

    try:
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)

            # IMPORTANT: Header must match exactly what rewriter agent expects
            # Based on rewriter_agent_main.py parse_csv_input function
            header = [
                'Url',  # Note: Capital U - this is what rewriter expects
                'KW',
                'competition',
                'Site',
                'confidence',
                'monthly_searches',
                'people_also_ask',
                'forum',
                'position1', 'title1', 'url1', 'snippet1', 'content1', 'structure1', 'headlines1', 'metadescription1',
                'position2', 'title2', 'url2', 'snippet2', 'content2', 'structure2', 'headlines2', 'metadescription2',
                'position3', 'title3', 'url3', 'snippet3', 'content3', 'structure3', 'headlines3', 'metadescription3'
            ]
            writer.writerow(header)

            # Prepare competitor data from organic results
            organic_results = keyword_data.get('organic_results', [])
            people_also_ask = '; '.join(keyword_data.get('people_also_ask', []))
            forum_links = '; '.join(keyword_data.get('forum', []))

            # Create competitor data that matches CompetitorData model
            competitors_data = {}
            for i in range(1, 4):  # positions 1-3
                if i <= len(organic_results):
                    result = organic_results[i - 1]

                    # Process headlines - convert from list to semicolon-separated string
                    headlines = result.get('headlines', [])
                    if isinstance(headlines, list):
                        headlines_str = '; '.join(headlines)
                    else:
                        headlines_str = str(headlines) if headlines else ''

                    competitors_data[f'position{i}'] = result.get('position', i)
                    competitors_data[f'title{i}'] = result.get('title', '')
                    competitors_data[f'url{i}'] = result.get('url', '')
                    competitors_data[f'snippet{i}'] = result.get('snippet', '')
                    competitors_data[f'content{i}'] = result.get('content', '')
                    competitors_data[f'structure{i}'] = result.get('structure', '')
                    competitors_data[f'headlines{i}'] = headlines_str
                    competitors_data[f'metadescription{i}'] = result.get('metadescription', '')
                else:
                    # Empty data for missing results
                    competitors_data[f'position{i}'] = ''
                    competitors_data[f'title{i}'] = ''
                    competitors_data[f'url{i}'] = ''
                    competitors_data[f'snippet{i}'] = ''
                    competitors_data[f'content{i}'] = ''
                    competitors_data[f'structure{i}'] = ''
                    competitors_data[f'headlines{i}'] = ''
                    competitors_data[f'metadescription{i}'] = ''

            # Write data row - IMPORTANT: First column is URL for rewriter
            row = [
                existing_content_url,  # Must be first for rewriter agent
                keyword,
                keyword_data.get('competition', 'UNKNOWN'),
                site_info.get('name', ''),
                f"{confidence:.2f}",
                keyword_data.get('monthly_searches', 0),
                people_also_ask,
                forum_links,
                # Competitor 1
                competitors_data['position1'], competitors_data['title1'], competitors_data['url1'],
                competitors_data['snippet1'], competitors_data['content1'], competitors_data['structure1'],
                competitors_data['headlines1'], competitors_data['metadescription1'],
                # Competitor 2
                competitors_data['position2'], competitors_data['title2'], competitors_data['url2'],
                competitors_data['snippet2'], competitors_data['content2'], competitors_data['structure2'],
                competitors_data['headlines2'], competitors_data['metadescription2'],
                # Competitor 3
                competitors_data['position3'], competitors_data['title3'], competitors_data['url3'],
                competitors_data['snippet3'], competitors_data['content3'], competitors_data['structure3'],
                competitors_data['headlines3'], competitors_data['metadescription3']
            ]
            writer.writerow(row)

        logger.info(f"✅ Created rewriter CSV: {filepath}")
        logger.info(f"   📄 URL to rewrite: {existing_content_url}")
        logger.info(f"   🎯 Keyword: {keyword}")
        logger.info(f"   🏢 Site: {site_info.get('name', 'Unknown')}")
        return filepath

    except Exception as e:
        logger.error(f"❌ Error creating rewriter CSV: {e}")
        return None


def extract_existing_content_url(existing_content: Dict[str, Any]) -> str:
    """
    Extract the best URL from existing content analysis

    Args:
        existing_content: Existing content analysis results

    Returns:
        URL of content to rewrite
    """

    if not existing_content or not existing_content.get('content_found'):
        return "No existing content found"

    source = existing_content.get('source')
    content = existing_content.get('content')

    if source == 'wordpress_api' and content:
        # WordPress API content has direct URL
        return content.get('url', 'WordPress content - no URL found')

    elif source == 'database' and content:
        # Database content has direct URL
        return content.get('url', 'Database content - no URL')

    elif source == 'sitemap' and content:
        # Sitemap content - get best match URL
        best_match = content.get('best_match', {})
        return best_match.get('url', 'Sitemap match - no URL')

    return "Content found but no URL available"


def get_keyword_data_from_content_finder(content_finder_output, primary_keyword: str) -> Dict[str, Any]:
    """
    Extract keyword data for the primary keyword from ContentFinderOutput
    Format for CSV generation

    Args:
        content_finder_output: ContentFinderOutput object
        primary_keyword: The primary keyword to extract data for

    Returns:
        Dictionary with keyword data formatted for CSV
    """

    keywords_data = content_finder_output.keywords_data

    if primary_keyword in keywords_data:
        keyword_obj = keywords_data[primary_keyword]
        return {
            'keyword': keyword_obj.keyword or primary_keyword,
            'competition': keyword_obj.competition,
            'monthly_searches': keyword_obj.monthly_searches,
            'people_also_ask': keyword_obj.people_also_ask,
            'forum': keyword_obj.forum,
            'organic_results': [
                {
                    'position': result.position,
                    'title': result.title,
                    'url': result.url,
                    'snippet': result.snippet,
                    'content': result.content or '',
                    'structure': result.structure or '',
                    'headlines': result.headlines or [],
                    'metadescription': result.metadescription or ''
                }
                for result in keyword_obj.organic_results
            ]
        }

    # Fallback if keyword not found
    return {
        'keyword': primary_keyword,
        'competition': 'UNKNOWN',
        'monthly_searches': 0,
        'people_also_ask': [],
        'forum': [],
        'organic_results': []
    }


def validate_rewriter_csv(csv_file_path: str) -> bool:
    """
    Validate that CSV file has the correct format for rewriter agent

    Args:
        csv_file_path: Path to CSV file to validate

    Returns:
        True if valid, False otherwise
    """
    try:
        with open(csv_file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            row = next(reader)

            # Check required fields match rewriter expectations
            required_fields = ['Url', 'KW', 'competition', 'Site', 'confidence']

            for field in required_fields:
                if field not in row:
                    logger.error(f"❌ Missing required field in CSV: {field}")
                    return False

            # Check that URL field is not empty
            if not row.get('Url') or row['Url'] == 'No existing content found':
                logger.warning(f"⚠️ CSV has no valid URL for rewriting: {row.get('Url')}")
                return False

            logger.info(f"✅ CSV validation passed")
            return True

    except Exception as e:
        logger.error(f"❌ Error validating CSV: {e}")
        return False