import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse


def load_html_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def extract_html_blocks(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')

    if not soup.body:
        print("[DEBUG] Pas de <body> trouvé dans le HTML")
    else:
        print("[DEBUG] <body> trouvé ✅")

    blocks = []
    current_block = []
    current_title = None

    content_tags = [
        'p', 'ul', 'ol', 'img', 'figure', 'blockquote',
        'div', 'section', 'a', 'strong', 'em', 'mark', 'iframe'
    ]
    keep_classes = [
        'wp-block-quote',
        'cg-box-layout-eleven',
        'wp-block-shortcode'
    ]

    content_root = soup.find('article') or soup

    for elem in content_root.descendants:
        if not getattr(elem, 'name', None):
            continue

        # Titres : on découpe
        if elem.name in ['h1', 'h2', 'h3']:
            if current_block:
                blocks.append({'title': current_title, 'content': current_block})
                current_block = []
            current_title = elem

        # Contenu riche
        elif elem.name in content_tags:
            # Garde les div/section spécifiques (affiliate, shortcode, citation, etc.)
            cls = elem.get('class', [])
            if isinstance(cls, str):
                cls = [cls]
            if any(c for c in cls if c in keep_classes):
                current_block.append(elem)

            # Contenu classique
            elif elem.name in ['p', 'ul', 'ol', 'img', 'blockquote', 'figure']:
                current_block.append(elem)

    if current_block:
        blocks.append({'title': current_title, 'content': current_block})

    print(f"[DEBUG] {len(blocks)} blocs extraits (avec blocs spéciaux)")
    return blocks


def reconstruct_blocks(blocks):
    html = ""
    for block in blocks:
        if block['title']:
            html += str(block['title']) + "\n"
        for elem in block['content']:
            html += str(elem) + "\n"
    return html


def strip_duplicate_title_and_featured_image(html):
    soup = BeautifulSoup(html, 'html.parser')

    # Supprimer H1
    h1 = soup.find('h1')
    if h1:
        print("[CLEAN] 🔠 H1 supprimé :", h1.text.strip()[:60])
        h1.decompose()

    # Supprimer img principale (souvent wp-post-image)
    main_img = soup.find('img', class_="wp-post-image")
    if main_img:
        print("[CLEAN] 🖼️ Image principale supprimée")
        main_img.decompose()
    else:
        print("[CLEAN] ℹ️ Aucune image wp-post-image trouvée à supprimer")

    return str(soup)


def simplify_youtube_embeds(soup):
    count = 0
    for figure in soup.find_all("figure", class_="wp-block-embed-youtube"):
        noscript = figure.find("noscript")
        if noscript:
            iframe = noscript.find("iframe")
            if iframe:
                figure.replace_with(iframe)
                count += 1
    print(f"[DEBUG] ✅ {count} blocs YouTube nettoyés (remplacés par <iframe>)")
    return soup


def restore_youtube_iframes_from_rll_div(soup):
    count = 0
    for div in soup.find_all("div", class_="rll-youtube-player"):
        video_id = div.get("data-id")
        if video_id:
            iframe = soup.new_tag("iframe", width="800", height="450")
            iframe['src'] = f"https://www.youtube.com/embed/{video_id}?feature=oembed"
            iframe['title'] = div.get("data-alt", "Vidéo YouTube")
            iframe['frameborder'] = "0"
            iframe[
                'allow'] = "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
            iframe['allowfullscreen'] = True
            iframe['referrerpolicy'] = "strict-origin-when-cross-origin"
            div.replace_with(iframe)
            count += 1
    print(f"[DEBUG] ✅ {count} iframes restaurés depuis <div.rll-youtube-player>")
    return soup


def clean_all_images(soup):
    restored = 0
    removed_svg = 0
    removed_empty_p = 0

    # 1. Restaurer les vraies images à partir des balises lazy
    for img in soup.find_all("img"):
        if img.get("src", "").startswith("data:image/svg+xml"):
            if img.get("data-lazy-src"):
                img["src"] = img["data-lazy-src"]
                restored += 1
            elif img.get("data-lazy-srcset"):
                srcset = img["data-lazy-srcset"].split(",")[0]
                img["src"] = srcset.strip().split(" ")[0]
                restored += 1

    # 2. Supprimer les <img> encore en SVG (placeholder)
    for img in soup.find_all("img"):
        if img.get("src", "").startswith("data:image/svg+xml"):
            parent = img.parent
            img.decompose()
            removed_svg += 1
            # Supprimer <p> vide laissé derrière
            if parent and parent.name == "p" and not parent.text.strip() and len(parent.find_all()) == 0:
                parent.decompose()
                removed_empty_p += 1

    # 3. Restaurer <img> manquant dans <picture> si nécessaire
    picture_restored = 0
    for picture in soup.find_all("picture"):
        has_img = picture.find("img")
        if not has_img:
            source = picture.find("source")
            src = ""

            # Récupération depuis data-lazy-srcset ou srcset
            if source and source.get("data-lazy-srcset"):
                srcset = source["data-lazy-srcset"]
                src = srcset.split(",")[0].split(" ")[0].strip()
            elif source and source.get("srcset"):
                srcset = source["srcset"]
                src = srcset.split(",")[0].split(" ")[0].strip()

            if src:
                img_tag = soup.new_tag("img", src=src)
                img_tag["alt"] = picture.get("alt", "")
                picture.append(img_tag)
                picture_restored += 1

    if picture_restored:
        print(f"[DEBUG] 🧩 {picture_restored} <img> restaurés dans <picture> manquants")

    print(f"[DEBUG] ✅ {restored} images restaurées depuis lazy-src")
    print(f"[DEBUG] 🗑️ {removed_svg} SVG placeholders supprimés")
    print(f"[DEBUG] 🧼 {removed_empty_p} <p> vides supprimés")
    print(f"[DEBUG] ℹ️ Conservation des images de contenu")

    return soup


# AUTHENTICATION JWT TOKEN
def get_jwt_token(username, password):
    auth_url = "https://stuffgaming.fr/wp-json/jwt-auth/v1/token"
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


# WORDPRESS API
def extract_slug_from_url(url):
    path = urlparse(url).path
    parts = [p for p in path.strip("/").split("/") if p]
    return parts[-1] if parts else None


def get_post_id_from_slug(slug, jwt_token):
    try:
        api_url = f"https://stuffgaming.fr/wp-json/wp/v2/posts?slug={slug}"
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


def update_wordpress_article(post_id, html_txt_file, jwt_token):
    update_url = f"https://stuffgaming.fr/wp-json/wp/v2/posts/{post_id}"

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
        if 'res' in locals():
            print(f"[DEBUG] ↪ Status: {res.status_code}")
            print(f"[DEBUG] ↪ Response: {res.text}")
        return False