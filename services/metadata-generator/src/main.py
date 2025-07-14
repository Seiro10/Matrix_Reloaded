"""
Metadata Generator Agent - Processes router data to generate article metadata
"""

import os
import json
import logging
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import csv
import io
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
import requests
import uuid

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Ensure directories exist
os.makedirs("logs", exist_ok=True)
os.makedirs("temp", exist_ok=True)

# Constants
COPYWRITER_AGENT_URL = os.getenv("COPYWRITER_AGENT_URL", "http://localhost:8083")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


# Models
class MetadataOutput(BaseModel):
    """Output metadata structure"""
    url: str = Field(description="Best possible URL based on competitor and SERP info")
    main_kw: str = Field(description="Main keyword")
    secondary_kws: List[str] = Field(description="Secondary keywords (max 3)")
    meta_description: str = Field(description="Meta description (160 chars max)")
    post_type: str = Field(description="Type of post (Affiliate, News, or Guide)")
    headlines: List[str] = Field(description="List of headlines based on competitor content")
    language: str = Field(description="Content language (e.g., FR, EN)")


class MetadataResponse(BaseModel):
    """API response model"""
    success: bool
    session_id: str
    message: str
    metadata: Optional[MetadataOutput] = None
    error: Optional[str] = None
    # Add copywriter response fields
    copywriter_response: Optional[Dict[str, Any]] = None
    article_id: Optional[str] = None
    content: Optional[str] = None
    status: Optional[str] = None


# Initialize FastAPI app
app = FastAPI(
    title="Metadata Generator Agent",
    description="Generates metadata for articles based on content analysis",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Initialize LLM
def get_llm():
    return ChatAnthropic(
        model="claude-3-5-sonnet-20241022",
        temperature=0.2,
        anthropic_api_key=ANTHROPIC_API_KEY,
    )


def parse_csv_input(file_content: bytes) -> Dict[str, Any]:
    """
    Parse CSV input file from router agent
    """
    try:
        # Read CSV content
        csv_text = file_content.decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(csv_text))
        row = next(csv_reader)  # We only need the first row

        # DEBUG: Print all CSV headers and values
        print(f"🔍 CSV Headers: {list(row.keys())}")
        print(f"🔍 CSV post_type value: '{row.get('post_type', 'NOT_FOUND')}'")

        # ADD DEBUG PRINT FOR BANNER IMAGE
        banner_image = row.get("banner_image", "")
        if banner_image:
            print(f"🖼️  Banner image path received in metadata agent: {banner_image}")
        else:
            print("⚠️  No banner image found in CSV")

        # ADD DEBUG PRINT FOR ORIGINAL POST URL
        original_post_url = row.get("original_post_url", "")
        if original_post_url:
            print(f"🔗 Original post URL received in metadata agent: {original_post_url}")
        else:
            print("⚠️  No original post URL found in CSV")

        parsed_data = {
            "keyword": row.get("KW", ""),
            "competition": row.get("competition", ""),
            "site": row.get("Site", ""),
            "language": row.get("language", "FR"),  # Default to FR if not provided
            "post_type": row.get("post_type", ""),
            "confidence": float(row.get("confidence", 0)),
            "monthly_searches": row.get("monthly_searches", 0),
            # Make these optional for news articles
            "people_also_ask": row.get("people_also_ask", "").split("; ") if row.get("people_also_ask") else [],
            "forum": row.get("forum", "").split("; ") if row.get("forum") else [],
            "banner_image": banner_image,
            "original_post_url": original_post_url,
            # Top competitors data - also make optional
            "competitors": [
                {
                    "position": row.get(f"position{i}", ""),
                    "title": row.get(f"title{i}", ""),
                    "url": row.get(f"url{i}", ""),
                    "snippet": row.get(f"snippet{i}", ""),
                    "content": row.get(f"content{i}", ""),
                    "structure": row.get(f"structure{i}", ""),
                    "headlines": row.get(f"headlines{i}", "").split("; ") if row.get(f"headlines{i}") else [],
                    "metadescription": row.get(f"metadescription{i}", ""),
                }
                for i in range(1, 4)  # Get data for top 3 competitors
                if row.get(f"url{i}")  # Only include if URL exists
            ]
        }

        print(f"🔍 Parsed post_type: '{parsed_data['post_type']}'")
        print(f"🔍 Parsed original_post_url: '{parsed_data['original_post_url']}'")  # ADD DEBUG LOG
        return parsed_data

    except Exception as e:
        logger.error(f"Error parsing CSV: {e}")
        raise ValueError(f"Invalid CSV format: {str(e)}")


def generate_metadata(input_data: Dict[str, Any], llm) -> MetadataOutput:
    """
    Generate metadata using LLM based on input data
    """
    keyword = input_data.get("keyword", "")
    language = input_data.get("language", "FR")
    post_type_from_input = input_data.get("post_type", "").strip()  # ADD STRIP TO REMOVE WHITESPACE

    # DEBUG: Print the post_type we received
    print(f"🏷️  Received post_type from input: '{post_type_from_input}'")

    competitors = input_data.get("competitors", [])
    people_also_ask = input_data.get("people_also_ask", [])
    forum = input_data.get("forum", [])

    # For news articles, we have richer content from the RSS feed
    source_content = ""
    if competitors and len(competitors) > 0:
        source_content = competitors[0].get("content", "")

    # Prepare competitor data for prompt
    competitors_info = ""
    for i, comp in enumerate(competitors):
        comp_headlines = "\n".join([f"- {h}" for h in comp.get("headlines", [])])
        competitors_info += f"""
Competitor {i + 1}:
- Title: {comp.get('title', '')}
- URL: {comp.get('url', '')}
- Position: {comp.get('position', '')}
- Meta Description: {comp.get('metadescription', '')}
- Headlines: 
{comp_headlines}
"""

    # Prepare people also ask data
    paa_text = "\n".join([f"- {q}" for q in people_also_ask])

    # Prepare forum data
    forum_text = "\n".join([f"- {f}" for f in forum])

    # MODIFY SYSTEM PROMPT BASED ON POST TYPE
    if post_type_from_input == "News":
        print(f"🏷️  Using NEWS-specific prompt")
        keyword_instruction = """1. url: Create a clean URL from the news title
2. main_kw: Leave as empty string ""
3. secondary_kws: Leave as empty array []"""
        content_type_instruction = "- This is a NEWS article from RSS feed"
        post_type_instruction = "5. post_type: MUST BE EXACTLY: News"
    elif post_type_from_input:
        print(f"🏷️  Using FORCED post_type: {post_type_from_input}")
        keyword_instruction = """1. url: A clean, SEO-friendly URL path
2. main_kw: The primary focus keyword
3. secondary_kws: 2-3 related keywords"""
        content_type_instruction = f"- FORCED CONTENT TYPE: {post_type_from_input} (DO NOT CHANGE THIS)"
        post_type_instruction = f"5. post_type: MUST BE EXACTLY: {post_type_from_input}"
    else:
        print("🏷️  No post_type provided, using LLM detection")
        keyword_instruction = """1. url: A clean, SEO-friendly URL path
2. main_kw: The primary focus keyword
3. secondary_kws: 2-3 related keywords"""
        content_type_instruction = """- If source_content is provided, this is likely a NEWS article
    - If competitors show product comparisons/reviews, this might be AFFILIATE content
    - Otherwise, it's likely a GUIDE article"""
        post_type_instruction = '5. post_type: "News", "Affiliate", or "Guide" based on content analysis'

    system_prompt = f"""You are a SEO metadata expert that analyzes content and creates optimal metadata for new articles.

    Your task is to analyze the information about a keyword and its top-ranking competitors to generate optimal metadata for a new article.

    IMPORTANT: Content type determination:
    {content_type_instruction}

    Language detection:
    - Analyze the keyword and content to determine language
    - Common languages: FR (French), EN (English), ES (Spanish), etc.

    Generate the following fields:
    {keyword_instruction}
    4. meta_description: 150-160 characters including main keyword
    {post_type_instruction}
    6. headlines: 5-7 headlines based on content type and competitors
    7. language: Auto-detected language code

    Respond with ONLY a valid JSON object containing these fields.
    """

    # Build human prompt conditionally
    content_type_line = f"Content Type (REQUIRED): {post_type_from_input}" if post_type_from_input else ""
    content_type_reminder = f"IMPORTANT: Use post_type = {post_type_from_input}" if post_type_from_input else "Pay special attention to content type detection."

    human_prompt = f"""Here's the content to analyze:

    Main Keyword: {keyword}
    Language Setting: {language}
    {content_type_line}
    Full Content: {source_content[:1000] if source_content else "None"}

    Top Competitors:
    {competitors_info}

    People Also Ask:
    {paa_text}

    Related Forum Topics:
    {forum_text}

    Based on this data, generate the metadata JSON. {content_type_reminder}
    """

    try:
        # Call Claude
        response = llm.invoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
        )

        # Extract JSON from response
        content = response.content
        print(f"🤖 LLM Raw response preview: {content[:200]}...")

        # Find JSON in the response (in case Claude adds extra text)
        try:
            # Try to parse the entire content as JSON first
            metadata_dict = json.loads(content)
        except json.JSONDecodeError:
            # If that fails, try to extract JSON using a simple heuristic
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            if start_idx != -1 and end_idx != 0:
                json_str = content[start_idx:end_idx]
                metadata_dict = json.loads(json_str)
            else:
                raise ValueError("Could not extract valid JSON from LLM response")

        print(f"🤖 LLM detected post_type: '{metadata_dict.get('post_type', 'NOT_FOUND')}'")

        # FORCE POST_TYPE IF PROVIDED FROM INPUT - THIS IS THE CRITICAL PART
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

        # Validate metadata fields
        if "meta_description" in metadata_dict and len(metadata_dict["meta_description"]) > 160:
            metadata_dict["meta_description"] = metadata_dict["meta_description"][:157] + "..."

        # Ensure URL doesn't have domain
        if "url" in metadata_dict:
            url = metadata_dict["url"]
            if url.startswith("http"):
                # Extract just the path
                from urllib.parse import urlparse
                parsed = urlparse(url)
                metadata_dict["url"] = parsed.path
            # Ensure URL starts with /
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
        return final_metadata

    except Exception as e:
        logger.error(f"Error generating metadata: {e}")
        # Return basic metadata as fallback with proper handling for News
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
            headlines=["Introduction", "Contenu principal", "Conclusion"],
            language=language
        )


def forward_to_copywriter(metadata: MetadataOutput, original_csv_path: str) -> Dict[str, Any]:
    """
    Forward the metadata and original CSV data to the copywriter agent
    """
    try:
        logger.info(f"📤 Sending data to copywriter at {COPYWRITER_AGENT_URL}")

        # Read and parse the original CSV to get all the data
        with open(original_csv_path, 'rb') as f:
            csv_content = f.read()

        original_data = parse_csv_input(csv_content)

        # Prepare payload in CopywriterRequest format
        payload = {
            "metadata": metadata.dict(),
            "keyword_data": {
                "keyword": original_data.get("keyword", ""),
                "competition": original_data.get("competition", ""),
                "site": original_data.get("site", ""),
                "language": original_data.get("language", "FR"),
                "post_type": original_data.get("post_type", ""),
                "confidence": original_data.get("confidence", 0),
                "monthly_searches": original_data.get("monthly_searches", 0),
                "people_also_ask": original_data.get("people_also_ask", []),
                "forum": original_data.get("forum", []),
                "competitors": original_data.get("competitors", []),
                "banner_image": original_data.get("banner_image", ""),  # Banner image
                "original_post_url": original_data.get("original_post_url", ""),  # ADD THIS LINE
                "source_content": original_data.get("source_content", "")  # RSS content
            },
            "session_metadata": {
                "source": "metadata_generator",
                "timestamp": datetime.now().isoformat(),
                "csv_file": original_csv_path
            }
        }

        # DETERMINE WHICH ENDPOINT TO USE BASED ON POST TYPE
        if metadata.post_type == "News":
            endpoint = "/copywriter-news"  # Use news endpoint for News type
            logger.info(f" Using NEWS endpoint for post_type: {metadata.post_type}")
        else:
            endpoint = "/copywriter"  # Use regular endpoint for Affiliate/Guide
            logger.info(f" Using REGULAR endpoint for post_type: {metadata.post_type}")

        # Send POST request to appropriate endpoint
        response = requests.post(
            f"{COPYWRITER_AGENT_URL}{endpoint}",  # Dynamic endpoint
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=120
        )

        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ Successfully forwarded to copywriter")
            return {
                "success": True,
                "message": f"Successfully forwarded to copywriter agent ({endpoint})",
                "copywriter_response": result,
                "article_id": result.get("wordpress_post_id"),
                "content": result.get("content", ""),
                "status": result.get("status", "success")
            }
        else:
            logger.error(f"❌ Copywriter agent returned error: {response.status_code}")
            logger.error(f"Response text: {response.text}")
            return {
                "success": False,
                "message": f"Copywriter agent error: HTTP {response.status_code}",
                "copywriter_response": None,
                "error": response.text,
                "status": "failed"
            }

    except Exception as e:
        logger.error(f"❌ Error forwarding to copywriter: {e}")
        return {
            "success": False,
            "message": f"Error forwarding to copywriter: {str(e)}",
            "copywriter_response": None,
            "error": str(e),
            "status": "error"
        }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "metadata-generator-agent",
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/generate-metadata", response_model=MetadataResponse)
async def generate_metadata_endpoint(
        file: UploadFile = File(...),
        background_tasks: BackgroundTasks = None,
        llm: ChatAnthropic = Depends(get_llm)
):
    """
    Generate metadata from uploaded CSV file and forward to copywriter
    """
    session_id = f"metadata_{str(uuid.uuid4())[:8]}"

    try:
        # Read file content
        content = await file.read()

        # Save file to temp directory
        file_path = os.path.join("temp", f"{session_id}_{file.filename}")
        with open(file_path, "wb") as f:
            f.write(content)

        # Parse CSV
        input_data = parse_csv_input(content)
        keyword = input_data.get('keyword', 'unknown')
        logger.info(f"🔄 Processing metadata for keyword: {keyword}")

        # Generate metadata
        metadata = generate_metadata(input_data, llm)
        logger.info(f"✅ Generated metadata for: {keyword}")

        # Forward to copywriter
        logger.info(f"📤 Forwarding to copywriter for: {keyword}")
        copywriter_response = forward_to_copywriter(metadata, file_path)

        # Prepare response based on copywriter success
        if copywriter_response.get("success"):
            return MetadataResponse(
                success=True,
                session_id=session_id,
                message=f"Metadata generated and article created successfully for keyword: {keyword}",
                metadata=metadata,
                copywriter_response=copywriter_response.get("copywriter_response"),
                article_id=copywriter_response.get("article_id"),
                content=copywriter_response.get("content"),
                status=copywriter_response.get("status", "completed")
            )
        else:
            # Metadata generation succeeded but copywriter failed
            return MetadataResponse(
                success=False,  # Overall process failed
                session_id=session_id,
                message=f"Metadata generated but copywriter failed for keyword: {keyword}",
                metadata=metadata,
                error=copywriter_response.get("error", "Copywriter agent error"),
                copywriter_response=copywriter_response.get("copywriter_response"),
                status=copywriter_response.get("status", "failed")
            )

    except Exception as e:
        logger.error(f"❌ Error processing request: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "session_id": session_id,
                "message": "Error generating metadata",
                "error": str(e),
                "status": "error"
            }
        )

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8084))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        log_level="info"
    )