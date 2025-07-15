import csv
import io
import logging
from typing import Dict, Any
from models.metadata_models import ParsedInputData, CompetitorData

logger = logging.getLogger(__name__)


def parse_csv_input(file_content: bytes) -> ParsedInputData:
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

        # Parse competitors data
        competitors = []
        for i in range(1, 4):  # Get data for top 3 competitors
            if row.get(f"url{i}"):  # Only include if URL exists
                competitor = CompetitorData(
                    position=row.get(f"position{i}", ""),
                    title=row.get(f"title{i}", ""),
                    url=row.get(f"url{i}", ""),
                    snippet=row.get(f"snippet{i}", ""),
                    content=row.get(f"content{i}", ""),
                    structure=row.get(f"structure{i}", ""),
                    headlines=row.get(f"headlines{i}", "").split("; ") if row.get(f"headlines{i}") else [],
                    metadescription=row.get(f"metadescription{i}", ""),
                )
                competitors.append(competitor)

        # Get source content (first competitor's content for news articles)
        source_content = ""
        if competitors and len(competitors) > 0:
            source_content = competitors[0].content

        parsed_data = ParsedInputData(
            keyword=row.get("KW", ""),
            competition=row.get("competition", ""),
            site=row.get("Site", ""),
            language=row.get("language", "FR"),
            post_type=row.get("post_type", ""),
            confidence=float(row.get("confidence", 0)),
            monthly_searches=int(row.get("monthly_searches", 0)) if row.get("monthly_searches") else 0,
            people_also_ask=row.get("people_also_ask", "").split("; ") if row.get("people_also_ask") else [],
            forum=row.get("forum", "").split("; ") if row.get("forum") else [],
            banner_image=banner_image,
            original_post_url=original_post_url,
            competitors=competitors,
            source_content=source_content
        )

        print(f"🔍 Parsed post_type: '{parsed_data.post_type}'")
        print(f"🔍 Parsed original_post_url: '{parsed_data.original_post_url}'")
        return parsed_data

    except Exception as e:
        logger.error(f"Error parsing CSV: {e}")
        raise ValueError(f"Invalid CSV format: {str(e)}")