import os
import logging
import requests
from typing import Dict, Any
from datetime import datetime
from models.metadata_models import MetadataOutput, ParsedInputData

logger = logging.getLogger(__name__)

COPYWRITER_AGENT_URL = os.getenv("COPYWRITER_AGENT_URL", "http://localhost:8083")


def forward_to_copywriter(metadata: MetadataOutput, input_data: ParsedInputData, csv_file_path: str) -> Dict[str, Any]:
    """
    Forward the metadata and original CSV data to the copywriter agent
    """
    try:
        logger.info(f"📤 Sending data to copywriter at {COPYWRITER_AGENT_URL}")

        # Prepare payload in CopywriterRequest format
        payload = {
            "metadata": metadata.dict(),
            "keyword_data": {
                "keyword": input_data.keyword,
                "competition": input_data.competition,
                "site": input_data.site,
                "language": input_data.language,
                "post_type": input_data.post_type,
                "confidence": input_data.confidence,
                "monthly_searches": input_data.monthly_searches,
                "people_also_ask": input_data.people_also_ask,
                "forum": input_data.forum,
                "competitors": [comp.dict() for comp in input_data.competitors],
                "banner_image": input_data.banner_image,
                "original_post_url": input_data.original_post_url,
                "source_content": input_data.source_content
            },
            "session_metadata": {
                "source": "metadata_generator",
                "timestamp": datetime.now().isoformat(),
                "csv_file": csv_file_path
            }
        }

        # DETERMINE WHICH ENDPOINT TO USE BASED ON POST TYPE
        if metadata.post_type == "News":
            endpoint = "/copywriter-news"  # Use news endpoint for News type
            logger.info(f"📰 Using NEWS endpoint for post_type: {metadata.post_type}")
        else:
            endpoint = "/copywriter"  # Use regular endpoint for Affiliate/Guide
            logger.info(f"📝 Using REGULAR endpoint for post_type: {metadata.post_type}")

        # Send POST request to appropriate endpoint
        response = requests.post(
            f"{COPYWRITER_AGENT_URL}{endpoint}",
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