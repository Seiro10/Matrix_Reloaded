import requests
from urllib.parse import urlparse
from app.config import settings


class WordPressClient:
    """WordPress API client adapted from your original code"""

    def __init__(self):
        self.base_url = settings.wordpress_base_url

    def get_jwt_token(self, username, password):
        """Get JWT token for WordPress authentication"""
        auth_url = f"{self.base_url}/wp-json/jwt-auth/v1/token"
        payload = {
            "username": username,
            "password": password
        }

        try:
            print(f"[DEBUG] Requête POST vers {auth_url} avec user={username}")
            res = requests.post(auth_url, json=payload)
            res.raise_for_status()
            token = res.json().get("token")
            print("[DEBUG] ✅ Token JWT récupéré avec succès.")
            return token
        except Exception as e:
            print(f"[ERROR] ❌ Échec de récupération du token JWT : {e}")
            if 'res' in locals():
                print(f"[DEBUG] ↪ Statut HTTP : {res.status_code}")
                print(f"[DEBUG] ↪ Réponse brute : {res.text}")
            return None

    def extract_slug_from_url(self, url):
        """Extract slug from WordPress URL"""
        path = urlparse(url).path
        parts = [p for p in path.strip("/").split("/") if p]
        return parts[-1] if parts else None

    def get_post_id_from_slug(self, slug, jwt_token):
        """Get WordPress post ID from slug"""
        try:
            api_url = f"{self.base_url}/wp-json/wp/v2/posts?slug={slug}"
            headers = {
                "Authorization": f"Bearer {jwt_token}"
            }
            res = requests.get(api_url, headers=headers)
            res.raise_for_status()
            posts = res.json()
            if posts:
                return posts[0]['id']
            else:
                print(f"[ERROR] Aucun article trouvé avec le slug : {slug}")
                return None
        except Exception as e:
            print(f"[ERROR] Récupération ID article échouée : {e}")
            return None

    def update_wordpress_article(self, post_id, html_txt_file, jwt_token):
        """Update WordPress article with new content"""
        update_url = f"{self.base_url}/wp-json/wp/v2/posts/{post_id}"

        try:
            with open(html_txt_file, "r", encoding="utf-8") as f:
                html_content = f.read()
        except Exception as e:
            print(f"[ERROR] ❌ Lecture du fichier HTML échouée : {e}")
            return False

        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json"
        }

        payload = {
            "content": html_content,
            "status": "private"
        }

        print(f"[DEBUG] 🔄 Envoi de la mise à jour vers {update_url}")
        print(f"[DEBUG] Payload size: {len(html_content)} caractères")

        try:
            res = requests.post(update_url, headers=headers, json=payload)
            res.raise_for_status()
            print(f"[✅] Article {post_id} mis à jour avec succès.")
            return True
        except Exception as e:
            print(f"[ERROR] ❌ Échec de la mise à jour de l'article : {e}")
            print(f"[DEBUG] ↪ Status: {res.status_code}")
            print(f"[DEBUG] ↪ Response: {res.text}")
            return False