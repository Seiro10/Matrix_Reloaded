import json
import logging
from typing import List
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_anthropic import ChatAnthropic
from models.metadata_models import MetadataOutput, ParsedInputData

logger = logging.getLogger(__name__)


def generate_news_headlines(input_data: ParsedInputData, llm: ChatAnthropic) -> List[str]:
    """
    Generate 1-3 headlines specifically for news articles
    """
    source_content = input_data.source_content
    keyword = input_data.keyword
    language = input_data.language

    system_prompt = f"""You are a news headline expert. Generate 1-3 compelling headlines for a news article.

    Guidelines:
    - Write in {language}
    - Keep headlines short and punchy (max 60 characters each)
    - Focus on the main news angle
    - Use active voice
    - Include numbers or specific details when relevant
    - Make it engaging for gaming/tech audience

    Respond with ONLY a JSON array of headlines, like: ["Headline 1", "Headline 2"]
    """

    human_prompt = f"""Based on this news content, generate 1-3 headlines in {language}:

    Main Topic: {keyword}
    Full Content: {source_content[:800] if source_content else "None"}

    Generate headlines that capture the essence of this news story.
    """

    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ])

        content = response.content.strip()
        headlines = json.loads(content)

        # Ensure we have a list and limit to 3
        if isinstance(headlines, list):
            return headlines[:3]
        else:
            return [str(headlines)]

    except Exception as e:
        logger.error(f"Error generating news headlines: {e}")
        # Fallback headlines for news
        return [
            "Actualité gaming",
            "Nouveautés à découvrir",
            "Ce qu'il faut retenir"
        ]


def generate_regular_headlines(input_data: ParsedInputData, llm: ChatAnthropic) -> List[str]:
    """
    Generate 5-7 headlines for Affiliate/Guide articles
    """
    competitors = input_data.competitors
    people_also_ask = input_data.people_also_ask
    keyword = input_data.keyword
    language = input_data.language

    # Prepare competitor headlines
    all_competitor_headlines = []
    for comp in competitors:
        all_competitor_headlines.extend(comp.headlines)

    competitors_headlines_text = "\n".join([f"- {h}" for h in all_competitor_headlines])
    paa_text = "\n".join([f"- {q}" for q in people_also_ask])

    system_prompt = f"""You are an SEO content strategist. Generate 5-7 section headlines for a comprehensive article.

    Guidelines:
    - Write in {language}
    - Create headlines that cover the topic comprehensively
    - Include both informational and comparison-based headlines
    - Make them SEO-friendly and engaging
    - Consider user intent and search behavior
    - Vary headline types (how-to, best-of, comparison, etc.)

    Respond with ONLY a JSON array of headlines, like: ["Headline 1", "Headline 2", ...]
    """

    human_prompt = f"""Generate 5-7 headlines in {language} for an article about: {keyword}

    Competitor Headlines (for inspiration):
    {competitors_headlines_text}

    People Also Ask:
    {paa_text}

    Create headlines that would make a comprehensive article covering all aspects of this topic.
    """

    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ])

        content = response.content.strip()
        headlines = json.loads(content)

        # Ensure we have a list and limit to 7
        if isinstance(headlines, list):
            return headlines[:7]
        else:
            return [str(headlines)]

    except Exception as e:
        logger.error(f"Error generating regular headlines: {e}")
        # Fallback headlines based on post type
        if input_data.post_type == "Affiliate":
            return [
                "Les meilleures options",
                "Comparatif détaillé",
                "Guide d'achat",
                "Avantages et inconvénients",
                "Notre verdict"
            ]
        else:  # Guide
            return [
                "Introduction",
                "Étapes principales",
                "Conseils pratiques",
                "Erreurs à éviter",
                "Conclusion"
            ]


def generate_metadata(input_data: ParsedInputData, llm: ChatAnthropic) -> MetadataOutput:
    """
    Generate metadata using LLM based on input data
    """
    keyword = input_data.keyword
    language = input_data.language
    post_type_from_input = input_data.post_type.strip()

    # DEBUG: Print the post_type we received
    print(f"🏷️  Received post_type from input: '{post_type_from_input}'")

    # Generate headlines based on post type
    if post_type_from_input == "News":
        print(f"🏷️  Generating NEWS headlines (1-3)")
        headlines = generate_news_headlines(input_data, llm)
    else:
        print(f"🏷️  Generating REGULAR headlines (5-7)")
        headlines = generate_regular_headlines(input_data, llm)

    # Prepare competitor data for main metadata prompt
    competitors_info = ""
    for i, comp in enumerate(input_data.competitors):
        comp_headlines = "\n".join([f"- {h}" for h in comp.headlines])
        competitors_info += f"""
Competitor {i + 1}:
- Title: {comp.title}
- URL: {comp.url}
- Position: {comp.position}
- Meta Description: {comp.metadescription}
- Headlines: 
{comp_headlines}
"""

    # Prepare people also ask data
    paa_text = "\n".join([f"- {q}" for q in input_data.people_also_ask])

    # Prepare forum data
    forum_text = "\n".join([f"- {f}" for f in input_data.forum])

    # MODIFY SYSTEM PROMPT BASED ON POST TYPE
    if post_type_from_input == "News":
        print(f"🏷️  Using NEWS-specific prompt")
        keyword_instruction = """1. url: Create a clean URL from the news title
2. main_kw: Leave as empty string ""
3. secondary_kws: Leave as empty array []"""
        content_type_instruction = "- This is a NEWS article from RSS feed"
        post_type_instruction = "4. post_type: MUST BE EXACTLY: News"
    elif post_type_from_input:
        print(f"🏷️  Using FORCED post_type: {post_type_from_input}")
        keyword_instruction = """1. url: A clean, SEO-friendly URL path
2. main_kw: The primary focus keyword
3. secondary_kws: 2-3 related keywords"""
        content_type_instruction = f"- FORCED CONTENT TYPE: {post_type_from_input} (DO NOT CHANGE THIS)"
        post_type_instruction = f"4. post_type: MUST BE EXACTLY: {post_type_from_input}"
    else:
        print("🏷️  No post_type provided, using LLM detection")
        keyword_instruction = """1. url: A clean, SEO-friendly URL path
2. main_kw: The primary focus keyword
3. secondary_kws: 2-3 related keywords"""
        content_type_instruction = """- If source_content is provided, this is likely a NEWS article
    - If competitors show product comparisons/reviews, this might be AFFILIATE content
    - Otherwise, it's likely a GUIDE article"""
        post_type_instruction = '4. post_type: "News", "Affiliate", or "Guide" based on content analysis'

    system_prompt = f"""You are a SEO metadata expert that creates optimal metadata for articles.

    Your task is to generate metadata for a new article based on the provided information.

    IMPORTANT: Content type determination:
    {content_type_instruction}

    Language detection:
    - Analyze the keyword and content to determine language
    - Common languages: FR (French), EN (English), ES (Spanish), etc.

    Generate the following fields:
    {keyword_instruction}
    {post_type_instruction}
    5. meta_description: 150-160 characters including main keyword
    6. language: Auto-detected language code

    Headlines will be provided separately, so don't generate them.

    Respond with ONLY a valid JSON object containing these fields (without headlines).
    """

    # Build human prompt conditionally
    content_type_line = f"Content Type (REQUIRED): {post_type_from_input}" if post_type_from_input else ""
    content_type_reminder = f"IMPORTANT: Use post_type = {post_type_from_input}" if post_type_from_input else "Pay special attention to content type detection."

    human_prompt = f"""Here's the content to analyze:

    Main Keyword: {keyword}
    Language Setting: {language}
    {content_type_line}
    Full Content: {input_data.source_content[:1000] if input_data.source_content else "None"}

    Top Competitors:
    {competitors_info}

    People Also Ask:
    {paa_text}

    Related Forum Topics:
    {forum_text}

    Based on this data, generate the metadata JSON (without headlines). {content_type_reminder}
    """

    try:
        # Call Claude for main metadata
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ])

        # Extract JSON from response
        content = response.content
        print(f"🤖 LLM Raw response preview: {content[:200]}...")

        # Find JSON in the response
        try:
            metadata_dict = json.loads(content)
        except json.JSONDecodeError:
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            if start_idx != -1 and end_idx != 0:
                json_str = content[start_idx:end_idx]
                metadata_dict = json.loads(json_str)
            else:
                raise ValueError("Could not extract valid JSON from LLM response")

        print(f"🤖 LLM detected post_type: '{metadata_dict.get('post_type', 'NOT_FOUND')}'")

        # FORCE POST_TYPE IF PROVIDED FROM INPUT
        if post_type_from_input:
            original_post_type = metadata_dict.get("post_type", "")
            metadata_dict["post_type"] = post_type_from_input
            print(f"🏷️  FORCED post_type from '{original_post_type}' to '{post_type_from_input}'")

            # For News articles, ensure keywords are empty
            if post_type_from_input == "News":
                metadata_dict["main_kw"] = ""
                metadata_dict["secondary_kws"] = []
                print(f"🏷️  Cleared keywords for News article")
        else:
            print(f"🏷️  Using LLM detected post_type: '{metadata_dict.get('post_type', '')}'")

        # Add the generated headlines
        metadata_dict["headlines"] = headlines

        # Validate and clean metadata
        if "meta_description" in metadata_dict and len(metadata_dict["meta_description"]) > 160:
            metadata_dict["meta_description"] = metadata_dict["meta_description"][:157] + "..."

        # Ensure URL doesn't have domain
        if "url" in metadata_dict:
            url = metadata_dict["url"]
            if url.startswith("http"):
                from urllib.parse import urlparse
                parsed = urlparse(url)
                metadata_dict["url"] = parsed.path
            if not metadata_dict["url"].startswith("/"):
                metadata_dict["url"] = "/" + metadata_dict["url"]

        # Limit secondary keywords to 3
        if "secondary_kws" in metadata_dict and len(metadata_dict["secondary_kws"]) > 3:
            metadata_dict["secondary_kws"] = metadata_dict["secondary_kws"][:3]

        # Add language if not present
        if "language" not in metadata_dict:
            metadata_dict["language"] = language

        final_metadata = MetadataOutput(**metadata_dict)
        print(f"🏷️  Final metadata post_type: '{final_metadata.post_type}'")
        print(f"🏷️  Generated {len(final_metadata.headlines)} headlines")
        return final_metadata

    except Exception as e:
        logger.error(f"Error generating metadata: {e}")
        # Return basic metadata as fallback
        fallback_post_type = post_type_from_input or "Guide"
        fallback_main_kw = "" if post_type_from_input == "News" else keyword
        fallback_secondary_kws = [] if post_type_from_input == "News" else []

        print(f"🏷️  Using fallback post_type: '{fallback_post_type}'")
        return MetadataOutput(
            url=f"/{keyword.lower().replace(' ', '-')}",
            main_kw=fallback_main_kw,
            secondary_kws=fallback_secondary_kws,
            meta_description=f"Découvrez tout sur {keyword} dans notre article complet.",
            post_type=fallback_post_type,
            headlines=headlines,
            language=language
        )