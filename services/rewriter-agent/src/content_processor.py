import re
import html
import logging
from typing import List, Dict, Any, Optional, Tuple
from bs4 import BeautifulSoup, NavigableString, Tag
from urllib.parse import urlparse, urljoin
import statistics

logger = logging.getLogger(__name__)


class ContentProcessor:
    """Utility class for processing and analyzing HTML content"""

    @staticmethod
    def extract_text_content(html_content: str) -> str:
        """
        Extract clean text content from HTML

        Args:
            html_content: HTML string

        Returns:
            Clean text content
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()

            # Get text and clean it up
            text = soup.get_text()

            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)

            return text

        except Exception as e:
            logger.error(f"Error extracting text content: {e}")
            return ""

    @staticmethod
    def extract_heading_structure(html_content: str) -> List[Dict[str, Any]]:
        """
        Extract heading structure from HTML content

        Args:
            html_content: HTML string

        Returns:
            List of heading dictionaries with level, text, and position
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            headings = []

            for i, heading in enumerate(soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])):
                headings.append({
                    'level': int(heading.name[1]),
                    'text': heading.get_text().strip(),
                    'tag': heading.name,
                    'position': i,
                    'id': heading.get('id', ''),
                    'classes': heading.get('class', [])
                })

            return headings

        except Exception as e:
            logger.error(f"Error extracting heading structure: {e}")
            return []

    @staticmethod
    def count_words(text: str) -> int:
        """
        Count words in text content

        Args:
            text: Text content

        Returns:
            Word count
        """
        if not text:
            return 0

        # Remove extra whitespace and split by words
        words = re.findall(r'\b\w+\b', text.lower())
        return len(words)

    @staticmethod
    def calculate_keyword_density(text: str, keyword: str) -> float:
        """
        Calculate keyword density in text

        Args:
            text: Text content
            keyword: Target keyword

        Returns:
            Keyword density as percentage
        """
        if not text or not keyword:
            return 0.0

        text_lower = text.lower()
        keyword_lower = keyword.lower()

        # Count total words
        total_words = len(re.findall(r'\b\w+\b', text_lower))

        if total_words == 0:
            return 0.0

        # Count keyword occurrences (exact phrase)
        keyword_count = text_lower.count(keyword_lower)

        # Calculate density
        density = (keyword_count / total_words) * 100
        return round(density, 2)

    @staticmethod
    def extract_internal_links(html_content: str, base_domain: str) -> List[Dict[str, str]]:
        """
        Extract internal links from HTML content

        Args:
            html_content: HTML string
            base_domain: Base domain for internal link detection

        Returns:
            List of internal link dictionaries
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            internal_links = []

            for link in soup.find_all('a', href=True):
                href = link['href']
                text = link.get_text().strip()

                # Parse URL
                parsed = urlparse(href)

                # Check if internal link
                is_internal = (
                        not parsed.netloc or  # Relative link
                        base_domain in parsed.netloc  # Same domain
                )

                if is_internal and text:
                    internal_links.append({
                        'url': href,
                        'text': text,
                        'title': link.get('title', ''),
                        'target': link.get('target', '')
                    })

            return internal_links

        except Exception as e:
            logger.error(f"Error extracting internal links: {e}")
            return []

    @staticmethod
    def extract_media_elements(html_content: str) -> Dict[str, List[Dict[str, str]]]:
        """
        Extract media elements (images, videos) from HTML

        Args:
            html_content: HTML string

        Returns:
            Dictionary with images and videos lists
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            media = {'images': [], 'videos': [], 'iframes': []}

            # Extract images
            for img in soup.find_all('img'):
                media['images'].append({
                    'src': img.get('src', ''),
                    'alt': img.get('alt', ''),
                    'title': img.get('title', ''),
                    'width': img.get('width', ''),
                    'height': img.get('height', ''),
                    'classes': ' '.join(img.get('class', []))
                })

            # Extract videos
            for video in soup.find_all('video'):
                media['videos'].append({
                    'src': video.get('src', ''),
                    'poster': video.get('poster', ''),
                    'controls': video.has_attr('controls'),
                    'autoplay': video.has_attr('autoplay'),
                    'width': video.get('width', ''),
                    'height': video.get('height', '')
                })

            # Extract iframes (YouTube, etc.)
            for iframe in soup.find_all('iframe'):
                media['iframes'].append({
                    'src': iframe.get('src', ''),
                    'title': iframe.get('title', ''),
                    'width': iframe.get('width', ''),
                    'height': iframe.get('height', ''),
                    'frameborder': iframe.get('frameborder', ''),
                    'allowfullscreen': iframe.has_attr('allowfullscreen')
                })

            return media

        except Exception as e:
            logger.error(f"Error extracting media elements: {e}")
            return {'images': [], 'videos': [], 'iframes': []}

    @staticmethod
    def preserve_structure_tags(html_content: str) -> BeautifulSoup:
        """
        Create BeautifulSoup object while preserving important structural tags

        Args:
            html_content: HTML string

        Returns:
            BeautifulSoup object with preserved structure
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # Add markers to preserve important elements
            for element in soup.find_all(['figure', 'blockquote', 'table', 'ul', 'ol']):
                element['data-preserve'] = 'true'

            return soup

        except Exception as e:
            logger.error(f"Error preserving structure: {e}")
            return BeautifulSoup("", 'html.parser')

    @staticmethod
    def clean_html_content(html_content: str, preserve_media: bool = True) -> str:
        """
        Clean and normalize HTML content

        Args:
            html_content: Raw HTML content
            preserve_media: Whether to preserve media elements

        Returns:
            Cleaned HTML content
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # Remove unwanted tags
            unwanted_tags = ['script', 'style', 'noscript']
            if not preserve_media:
                unwanted_tags.extend(['img', 'video', 'iframe', 'embed', 'object'])

            for tag in soup(unwanted_tags):
                tag.decompose()

            # Clean up attributes
            allowed_attrs = {
                'a': ['href', 'title', 'target'],
                'img': ['src', 'alt', 'title', 'width', 'height', 'class'],
                'iframe': ['src', 'title', 'width', 'height', 'frameborder', 'allowfullscreen'],
                'blockquote': ['cite'],
                'table': ['class'],
                'td': ['colspan', 'rowspan'],
                'th': ['colspan', 'rowspan', 'scope']
            }

            for tag in soup.find_all():
                if tag.name in allowed_attrs:
                    # Keep only allowed attributes
                    attrs_to_keep = {}
                    for attr in allowed_attrs[tag.name]:
                        if tag.has_attr(attr):
                            attrs_to_keep[attr] = tag[attr]
                    tag.attrs = attrs_to_keep
                else:
                    # Remove all attributes for other tags
                    tag.attrs = {}

            # Clean up empty paragraphs
            for p in soup.find_all('p'):
                if not p.get_text().strip() and not p.find_all(['img', 'iframe', 'video']):
                    p.decompose()

            return str(soup)

        except Exception as e:
            logger.error(f"Error cleaning HTML content: {e}")
            return html_content

    @staticmethod
    def merge_content_blocks(original_soup: BeautifulSoup, new_content: str,
                             insertion_point: str = "after_last_p") -> str:
        """
        Merge new content into original HTML structure

        Args:
            original_soup: BeautifulSoup object of original content
            new_content: New HTML content to insert
            insertion_point: Where to insert ("after_last_p", "before_conclusion", "append")

        Returns:
            Merged HTML content
        """
        try:
            new_soup = BeautifulSoup(new_content, 'html.parser')

            if insertion_point == "after_last_p":
                # Find last paragraph
                paragraphs = original_soup.find_all('p')
                if paragraphs:
                    last_p = paragraphs[-1]
                    for element in new_soup.contents:
                        if isinstance(element, Tag):
                            last_p.insert_after(element)

            elif insertion_point == "before_conclusion":
                # Look for conclusion indicators
                conclusion_indicators = ['conclusion', 'summary', 'final', 'end']
                conclusion_element = None

                for heading in original_soup.find_all(['h2', 'h3', 'h4']):
                    heading_text = heading.get_text().lower()
                    if any(indicator in heading_text for indicator in conclusion_indicators):
                        conclusion_element = heading
                        break

                if conclusion_element:
                    for element in reversed(new_soup.contents):
                        if isinstance(element, Tag):
                            conclusion_element.insert_before(element)
                else:
                    # Fallback to append
                    for element in new_soup.contents:
                        if isinstance(element, Tag):
                            original_soup.append(element)

            elif insertion_point == "append":
                for element in new_soup.contents:
                    if isinstance(element, Tag):
                        original_soup.append(element)

            return str(original_soup)

        except Exception as e:
            logger.error(f"Error merging content blocks: {e}")
            return str(original_soup)

    @staticmethod
    def analyze_content_structure(html_content: str) -> Dict[str, Any]:
        """
        Analyze content structure and provide metrics

        Args:
            html_content: HTML content to analyze

        Returns:
            Dictionary with structure analysis
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            text_content = ContentProcessor.extract_text_content(html_content)
            headings = ContentProcessor.extract_heading_structure(html_content)
            media = ContentProcessor.extract_media_elements(html_content)

            # Calculate reading time (average 200 words per minute)
            word_count = ContentProcessor.count_words(text_content)
            reading_time = max(1, round(word_count / 200))

            # Analyze heading distribution
            heading_levels = [h['level'] for h in headings]
            heading_distribution = {}
            for level in range(1, 7):
                heading_distribution[f'h{level}'] = heading_levels.count(level)

            # Calculate paragraph count
            paragraphs = soup.find_all('p')
            paragraph_count = len([p for p in paragraphs if p.get_text().strip()])

            # Calculate average paragraph length
            paragraph_lengths = [len(p.get_text().split()) for p in paragraphs if p.get_text().strip()]
            avg_paragraph_length = round(statistics.mean(paragraph_lengths)) if paragraph_lengths else 0

            # Analyze content density
            sentences = re.split(r'[.!?]+', text_content)
            sentence_count = len([s for s in sentences if s.strip()])
            avg_sentence_length = round(word_count / sentence_count) if sentence_count > 0 else 0

            return {
                'word_count': word_count,
                'reading_time_minutes': reading_time,
                'paragraph_count': paragraph_count,
                'sentence_count': sentence_count,
                'heading_count': len(headings),
                'heading_distribution': heading_distribution,
                'avg_paragraph_length': avg_paragraph_length,
                'avg_sentence_length': avg_sentence_length,
                'image_count': len(media['images']),
                'video_count': len(media['videos']),
                'iframe_count': len(media['iframes']),
                'has_tables': len(soup.find_all('table')) > 0,
                'has_lists': len(soup.find_all(['ul', 'ol'])) > 0,
                'has_blockquotes': len(soup.find_all('blockquote')) > 0,
                'content_depth_score': len(headings) + len(media['images']) + len(media['videos'])
            }

        except Exception as e:
            logger.error(f"Error analyzing content structure: {e}")
            return {
                'word_count': 0,
                'reading_time_minutes': 0,
                'paragraph_count': 0,
                'sentence_count': 0,
                'heading_count': 0,
                'error': str(e)
            }


class CompetitorAnalyzer:
    """Analyzer for competitor content and insights"""

    @staticmethod
    def analyze_competitor_content(competitors: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze competitor content for insights

        Args:
            competitors: List of competitor data

        Returns:
            Dictionary with competitor analysis insights
        """
        try:
            if not competitors:
                return {'error': 'No competitor data provided'}

            insights = {
                'total_competitors': len(competitors),
                'common_topics': [],
                'content_gaps': [],
                'average_content_length': 0,
                'title_patterns': [],
                'meta_description_patterns': [],
                'heading_patterns': [],
                'content_themes': {}
            }

            # Analyze content lengths
            content_lengths = []
            all_headlines = []
            all_titles = []
            all_meta_descriptions = []

            for comp in competitors:
                # Content length analysis
                content = comp.get('content', '')
                if content:
                    word_count = ContentProcessor.count_words(content)
                    content_lengths.append(word_count)

                # Collect headlines
                headlines = comp.get('headlines', [])
                if isinstance(headlines, list):
                    all_headlines.extend(headlines)
                elif isinstance(headlines, str):
                    all_headlines.extend([h.strip() for h in headlines.split(';') if h.strip()])

                # Collect titles and meta descriptions
                title = comp.get('title', '')
                meta_desc = comp.get('metadescription', '')

                if title:
                    all_titles.append(title)
                if meta_desc:
                    all_meta_descriptions.append(meta_desc)

            # Calculate average content length
            if content_lengths:
                insights['average_content_length'] = round(statistics.mean(content_lengths))
                insights['content_length_range'] = {
                    'min': min(content_lengths),
                    'max': max(content_lengths),
                    'median': round(statistics.median(content_lengths))
                }

            # Analyze common topics from headlines
            insights['common_topics'] = CompetitorAnalyzer._extract_common_topics(all_headlines)

            # Analyze title patterns
            insights['title_patterns'] = CompetitorAnalyzer._analyze_title_patterns(all_titles)

            # Analyze meta description patterns
            insights['meta_description_patterns'] = CompetitorAnalyzer._analyze_meta_patterns(all_meta_descriptions)

            # Analyze heading patterns
            insights['heading_patterns'] = CompetitorAnalyzer._analyze_heading_patterns(all_headlines)

            return insights

        except Exception as e:
            logger.error(f"Error analyzing competitor content: {e}")
            return {'error': str(e)}

    @staticmethod
    def _extract_common_topics(headlines: List[str]) -> List[Dict[str, Any]]:
        """Extract common topics from headlines"""
        try:
            # Tokenize and count word frequency
            word_freq = {}
            stop_words = {
                'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have',
                'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
                'le', 'la', 'les', 'de', 'du', 'des', 'et', 'ou', 'pour', 'dans', 'sur'
            }

            for headline in headlines:
                words = re.findall(r'\b\w+\b', headline.lower())
                for word in words:
                    if len(word) > 3 and word not in stop_words:
                        word_freq[word] = word_freq.get(word, 0) + 1

            # Get top topics
            sorted_topics = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)

            return [
                {'topic': topic, 'frequency': freq}
                for topic, freq in sorted_topics[:15]  # Top 15 topics
            ]

        except Exception as e:
            logger.error(f"Error extracting common topics: {e}")
            return []

    @staticmethod
    def _analyze_title_patterns(titles: List[str]) -> Dict[str, Any]:
        """Analyze title patterns"""
        try:
            if not titles:
                return {}

            patterns = {
                'average_length': round(statistics.mean([len(title) for title in titles])),
                'contains_numbers': sum(1 for title in titles if re.search(r'\d', title)),
                'contains_questions': sum(1 for title in titles if '?' in title),
                'contains_lists': sum(
                    1 for title in titles if re.search(r'\b(\d+|\w+)\s+(top|best|ways|tips|methods)', title.lower())),
                'starts_with_how': sum(1 for title in titles if title.lower().startswith(('how', 'comment'))),
                'starts_with_what': sum(1 for title in titles if title.lower().startswith(('what', 'quel', 'quoi'))),
                'contains_year': sum(1 for title in titles if re.search(r'\b(202[0-9]|2030)\b', title))
            }

            # Convert counts to percentages
            total = len(titles)
            for key in patterns:
                if key != 'average_length':
                    patterns[key] = round((patterns[key] / total) * 100, 1)

            return patterns

        except Exception as e:
            logger.error(f"Error analyzing title patterns: {e}")
            return {}

    @staticmethod
    def _analyze_meta_patterns(meta_descriptions: List[str]) -> Dict[str, Any]:
        """Analyze meta description patterns"""
        try:
            if not meta_descriptions:
                return {}

            patterns = {
                'average_length': round(statistics.mean([len(meta) for meta in meta_descriptions])),
                'contains_cta': sum(1 for meta in meta_descriptions if
                                    re.search(r'\b(découvrez|apprenez|trouvez|voir|lire|cliquez)\b', meta.lower())),
                'contains_benefits': sum(1 for meta in meta_descriptions if
                                         re.search(r'\b(meilleur|gratuit|rapide|facile|simple|efficace)\b',
                                                   meta.lower())),
                'length_range': {
                    'min': min([len(meta) for meta in meta_descriptions]),
                    'max': max([len(meta) for meta in meta_descriptions])
                }
            }

            return patterns

        except Exception as e:
            logger.error(f"Error analyzing meta patterns: {e}")
            return {}

    @staticmethod
    def _analyze_heading_patterns(headlines: List[str]) -> Dict[str, Any]:
        """Analyze heading patterns"""
        try:
            if not headlines:
                return {}

            patterns = {
                'total_headlines': len(headlines),
                'average_length': round(statistics.mean([len(h) for h in headlines])),
                'question_headlines': sum(1 for h in headlines if '?' in h),
                'numbered_headlines': sum(1 for h in headlines if re.search(r'^\d+\.', h.strip())),
                'actionable_headlines': sum(
                    1 for h in headlines if re.search(r'\b(comment|how|guide|tutorial|étapes)\b', h.lower()))
            }

            return patterns

        except Exception as e:
            logger.error(f"Error analyzing heading patterns: {e}")
            return {}


class SEOAnalyzer:
    """SEO analysis utilities"""

    @staticmethod
    def analyze_seo_metrics(html_content: str, keyword: str, competitors: List[Dict[str, Any]] = None) -> Dict[
        str, Any]:
        """
        Analyze SEO metrics for content

        Args:
            html_content: HTML content to analyze
            keyword: Target keyword
            competitors: Optional competitor data for comparison

        Returns:
            Dictionary with SEO analysis
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            text_content = ContentProcessor.extract_text_content(html_content)

            seo_metrics = {
                'keyword_density': ContentProcessor.calculate_keyword_density(text_content, keyword),
                'title_optimization': SEOAnalyzer._analyze_title_seo(soup, keyword),
                'heading_optimization': SEOAnalyzer._analyze_heading_seo(soup, keyword),
                'content_optimization': SEOAnalyzer._analyze_content_seo(text_content, keyword),
                'image_optimization': SEOAnalyzer._analyze_image_seo(soup),
                'internal_linking': SEOAnalyzer._analyze_internal_linking(soup),
                'readability_score': SEOAnalyzer._calculate_readability(text_content),
                'content_length_score': SEOAnalyzer._score_content_length(text_content, competitors)
            }

            # Calculate overall SEO score
            seo_metrics['overall_score'] = SEOAnalyzer._calculate_overall_seo_score(seo_metrics)

            return seo_metrics

        except Exception as e:
            logger.error(f"Error analyzing SEO metrics: {e}")
            return {'error': str(e)}

    @staticmethod
    def _analyze_title_seo(soup: BeautifulSoup, keyword: str) -> Dict[str, Any]:
        """Analyze title SEO optimization"""
        try:
            title_tag = soup.find('title')
            if not title_tag:
                return {'score': 0, 'issues': ['No title tag found']}

            title_text = title_tag.get_text()
            issues = []
            score = 100

            # Check title length
            if len(title_text) < 30:
                issues.append('Title too short (< 30 characters)')
                score -= 20
            elif len(title_text) > 60:
                issues.append('Title too long (> 60 characters)')
                score -= 10

            # Check keyword presence
            if keyword.lower() not in title_text.lower():
                issues.append('Keyword not found in title')
                score -= 30

            return {
                'score': max(0, score),
                'length': len(title_text),
                'contains_keyword': keyword.lower() in title_text.lower(),
                'issues': issues
            }

        except Exception as e:
            return {'score': 0, 'error': str(e)}

    @staticmethod
    def _analyze_heading_seo(soup: BeautifulSoup, keyword: str) -> Dict[str, Any]:
        """Analyze heading SEO optimization"""
        try:
            headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])

            h1_count = len(soup.find_all('h1'))
            keyword_in_headings = sum(1 for h in headings if keyword.lower() in h.get_text().lower())

            issues = []
            score = 100

            # Check H1 count
            if h1_count == 0:
                issues.append('No H1 tag found')
                score -= 40
            elif h1_count > 1:
                issues.append('Multiple H1 tags found')
                score -= 20

            # Check keyword in headings
            if keyword_in_headings == 0:
                issues.append('Keyword not found in any heading')
                score -= 30

            return {
                'score': max(0, score),
                'h1_count': h1_count,
                'total_headings': len(headings),
                'keyword_in_headings': keyword_in_headings,
                'issues': issues
            }

        except Exception as e:
            return {'score': 0, 'error': str(e)}

    @staticmethod
    def _analyze_content_seo(text_content: str, keyword: str) -> Dict[str, Any]:
        """Analyze content SEO optimization"""
        try:
            word_count = ContentProcessor.count_words(text_content)
            keyword_density = ContentProcessor.calculate_keyword_density(text_content, keyword)

            issues = []
            score = 100

            # Check content length
            if word_count < 300:
                issues.append('Content too short (< 300 words)')
                score -= 30

            # Check keyword density
            if keyword_density == 0:
                issues.append('Keyword not found in content')
                score -= 40
            elif keyword_density > 3.0:
                issues.append('Keyword density too high (> 3%)')
                score -= 20
            elif keyword_density < 0.5:
                issues.append('Keyword density too low (< 0.5%)')
                score -= 10

            return {
                'score': max(0, score),
                'word_count': word_count,
                'keyword_density': keyword_density,
                'issues': issues
            }

        except Exception as e:
            return {'score': 0, 'error': str(e)}

    @staticmethod
    def _analyze_image_seo(soup: BeautifulSoup) -> Dict[str, Any]:
        """Analyze image SEO optimization"""
        try:
            images = soup.find_all('img')
            total_images = len(images)

            if total_images == 0:
                return {'score': 100, 'total_images': 0, 'issues': []}

            images_with_alt = sum(1 for img in images if img.get('alt'))
            images_with_title = sum(1 for img in images if img.get('title'))

            issues = []
            score = 100

            # Check alt text coverage
            alt_coverage = (images_with_alt / total_images) * 100
            if alt_coverage < 80:
                issues.append(f'Only {alt_coverage:.0f}% of images have alt text')
                score -= 20

            return {
                'score': max(0, score),
                'total_images': total_images,
                'images_with_alt': images_with_alt,
                'images_with_title': images_with_title,
                'alt_coverage': round(alt_coverage, 1),
                'issues': issues
            }

        except Exception as e:
            return {'score': 0, 'error': str(e)}

    @staticmethod
    def _analyze_internal_linking(soup: BeautifulSoup) -> Dict[str, Any]:
        """Analyze internal linking structure"""
        try:
            links = soup.find_all('a', href=True)
            internal_links = [link for link in links if
                              not link['href'].startswith(('http://', 'https://', 'mailto:', 'tel:'))]

            return {
                'total_links': len(links),
                'internal_links': len(internal_links),
                'external_links': len(links) - len(internal_links),
                'score': min(100, len(internal_links) * 10)  # 10 points per internal link, max 100
            }

        except Exception as e:
            return {'score': 0, 'error': str(e)}

    @staticmethod
    def _calculate_readability(text_content: str) -> Dict[str, Any]:
        """Calculate content readability score"""
        try:
            sentences = re.split(r'[.!?]+', text_content)
            sentence_count = len([s for s in sentences if s.strip()])

            words = re.findall(r'\b\w+\b', text_content)
            word_count = len(words)

            if sentence_count == 0:
                return {'score': 0, 'grade_level': 'Unknown'}

            # Simple readability calculation (Flesch-like)
            avg_sentence_length = word_count / sentence_count

            # Estimate syllables (rough approximation)
            syllable_count = sum(max(1, len(re.findall(r'[aeiouAEIOU]', word))) for word in words)
            avg_syllables_per_word = syllable_count / word_count if word_count > 0 else 0

            # Simplified Flesch Reading Ease score
            readability_score = 206.835 - (1.015 * avg_sentence_length) - (84.6 * avg_syllables_per_word)
            readability_score = max(0, min(100, readability_score))

            # Grade level interpretation
            if readability_score >= 90:
                grade_level = "Very Easy"
            elif readability_score >= 80:
                grade_level = "Easy"
            elif readability_score >= 70:
                grade_level = "Fairly Easy"
            elif readability_score >= 60:
                grade_level = "Standard"
            elif readability_score >= 50:
                grade_level = "Fairly Difficult"
            elif readability_score >= 30:
                grade_level = "Difficult"
            else:
                grade_level = "Very Difficult"

            return {
                'score': round(readability_score, 1),
                'grade_level': grade_level,
                'avg_sentence_length': round(avg_sentence_length, 1),
                'avg_syllables_per_word': round(avg_syllables_per_word, 1)
            }

        except Exception as e:
            return {'score': 0, 'error': str(e)}

    @staticmethod
    def _score_content_length(text_content: str, competitors: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Score content length against competitors"""
        try:
            word_count = ContentProcessor.count_words(text_content)

            if not competitors:
                # Basic scoring without competitor data
                if word_count >= 1000:
                    score = 100
                elif word_count >= 500:
                    score = 80
                elif word_count >= 300:
                    score = 60
                else:
                    score = 30

                return {'score': score, 'word_count': word_count, 'comparison': 'No competitor data'}

            # Calculate competitor average
            competitor_lengths = []
            for comp in competitors:
                content = comp.get('content', '')
                if content:
                    comp_word_count = ContentProcessor.count_words(content)
                    competitor_lengths.append(comp_word_count)

            if competitor_lengths:
                avg_competitor_length = statistics.mean(competitor_lengths)

                # Score based on comparison to competitors
                ratio = word_count / avg_competitor_length if avg_competitor_length > 0 else 1

                if ratio >= 1.2:  # 20% longer than average
                    score = 100
                elif ratio >= 1.0:  # Equal or longer
                    score = 90
                elif ratio >= 0.8:  # 80% of average
                    score = 70
                elif ratio >= 0.6:  # 60% of average
                    score = 50
                else:
                    score = 30

                return {
                    'score': score,
                    'word_count': word_count,
                    'competitor_average': round(avg_competitor_length),
                    'ratio': round(ratio, 2),
                    'comparison': f"{'Longer' if ratio > 1 else 'Shorter'} than competitors"
                }
            else:
                return {'score': 60, 'word_count': word_count, 'comparison': 'No valid competitor content'}

        except Exception as e:
            return {'score': 0, 'error': str(e)}

    @staticmethod
    def _calculate_overall_seo_score(seo_metrics: Dict[str, Any]) -> int:
        """Calculate overall SEO score from individual metrics"""
        try:
            weights = {
                'title_optimization': 0.2,
                'heading_optimization': 0.15,
                'content_optimization': 0.25,
                'image_optimization': 0.1,
                'internal_linking': 0.1,
                'readability_score': 0.1,
                'content_length_score': 0.1
            }

            total_score = 0
            total_weight = 0

            for metric, weight in weights.items():
                if metric in seo_metrics and isinstance(seo_metrics[metric], dict):
                    metric_score = seo_metrics[metric].get('score', 0)
                    total_score += metric_score * weight
                    total_weight += weight

            # Normalize to 0-100 scale
            overall_score = round(total_score / total_weight) if total_weight > 0 else 0

            return max(0, min(100, overall_score))

        except Exception as e:
            logger.error(f"Error calculating overall SEO score: {e}")
            return 0


# Export all classes and functions
__all__ = [
    'ContentProcessor',
    'CompetitorAnalyzer',
    'SEOAnalyzer'
]