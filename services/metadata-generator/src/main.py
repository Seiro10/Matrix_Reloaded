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

        return {
            "keyword": row.get("KW", ""),
            "competition": row.get("competition", ""),
            "site": row.get("Site", ""),
            "language": row.get("language", "FR"),  # Default to FR if not provided
            "confidence": float(row.get("confidence", 0)),
            "monthly_searches": row.get("monthly_searches", 0),
            "people_also_ask": row.get("people_also_ask", "").split("; ") if row.get("people_also_ask") else [],
            "forum": row.get("forum", "").split("; ") if row.get("forum") else [],
            # Top competitors data
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
    except Exception as e:
        logger.error(f"Error parsing CSV: {e}")
        raise ValueError(f"Invalid CSV format: {str(e)}")


def generate_metadata(input_data: Dict[str, Any], llm) -> MetadataOutput:
    """
    Generate metadata using LLM based on input data
    """
    keyword = input_data.get("keyword", "")
    language = input_data.get("language", "FR")
    competitors = input_data.get("competitors", [])
    people_also_ask = input_data.get("people_also_ask", [])
    forum = input_data.get("forum", [])

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

    # Create prompt for Claude
    system_prompt = f"""You are a SEO metadata expert that analyzes content and creates optimal metadata for new articles.
Your task is to analyze the information about a keyword and its top-ranking competitors to generate optimal metadata for a new article.
You should produce metadata in the language indicated (default: French).

Current language setting: {language}

Generate the following fields:
1. url: A clean, SEO-friendly URL path (without domain) based on the main keyword and type of content
2. main_kw: The primary focus keyword for the article
3. secondary_kws: 2-3 important related keywords to include in the content
4. meta_description: An engaging meta description of exactly 150-160 characters that includes the main keyword
5. post_type: Determine if this should be an "Affiliate", "News", or "Guide" type of article
6. headlines: 5-7 compelling headlines (H2) that should be included in the article based on competitor analysis

Respond with ONLY a valid JSON object containing these fields.
"""

    human_prompt = f"""Here's the content to analyze:

Main Keyword: {keyword}
Language: {language}

Top Competitors:
{competitors_info}

People Also Ask:
{paa_text}

Related Forum Topics:
{forum_text}

Based on this data, generate the metadata JSON as instructed.
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

        return MetadataOutput(**metadata_dict)

    except Exception as e:
        logger.error(f"Error generating metadata: {e}")
        # Return basic metadata as fallback
        return MetadataOutput(
            url=f"/{keyword.lower().replace(' ', '-')}",
            main_kw=keyword,
            secondary_kws=[],
            meta_description=f"Découvrez tout sur {keyword} dans notre article complet.",
            post_type="Guide",
            headlines=["Introduction", "Qu'est-ce que " + keyword, "Conclusion"],
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

        # Prepare payload in CopywriterRequest format that matches your server.py
        payload = {
            "metadata": metadata.dict(),
            "keyword_data": {
                "keyword": original_data.get("keyword", ""),
                "competition": original_data.get("competition", ""),
                "site": original_data.get("site", ""),
                "language": original_data.get("language", "FR"),
                "confidence": original_data.get("confidence", 0),
                "monthly_searches": original_data.get("monthly_searches", 0),
                "people_also_ask": original_data.get("people_also_ask", []),
                "forum": original_data.get("forum", []),
                "competitors": original_data.get("competitors", [])
            },
            "session_metadata": {
                "source": "metadata_generator",
                "timestamp": datetime.now().isoformat(),
                "csv_file": original_csv_path
            }
        }

        # Send POST request to copywriter agent using the correct endpoint
        response = requests.post(
            f"{COPYWRITER_AGENT_URL}/copywriter",  # Fixed endpoint name
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=120  # Longer timeout for content generation
        )

        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ Successfully forwarded to copywriter")
            return {
                "success": True,
                "message": "Successfully forwarded to copywriter agent",
                "copywriter_response": result,
                "article_id": result.get("wordpress_post_id"),  # Changed from article_id to wordpress_post_id
                "content": result.get("content", ""),
                "status": result.get("status", "success")  # Use status from copywriter response
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

    except requests.exceptions.Timeout:
        logger.error(f"❌ Timeout calling copywriter agent")
        return {
            "success": False,
            "message": "Timeout calling copywriter agent",
            "copywriter_response": None,
            "error": "Request timeout",
            "status": "timeout"
        }

    except requests.exceptions.ConnectionError:
        logger.error(f"❌ Connection error calling copywriter agent")
        return {
            "success": False,
            "message": "Could not connect to copywriter agent",
            "copywriter_response": None,
            "error": "Connection error",
            "status": "connection_error"
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