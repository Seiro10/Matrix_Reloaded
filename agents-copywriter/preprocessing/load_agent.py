from utils.html_loader import get_article_html_from_url
from utils.transcript import extract_video_id, get_transcript_supadata

class LoadAgent:
    def load(self, article_url: str, transcript_url: str) -> tuple[str, str]:
        html = get_article_html_from_url(article_url)
        video_id = extract_video_id(transcript_url)
        transcript = get_transcript_supadata(video_id)
        return html, transcript
