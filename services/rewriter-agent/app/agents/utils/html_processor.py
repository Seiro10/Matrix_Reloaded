from bs4 import BeautifulSoup, Tag


class HTMLProcessor:
    """HTML processing utilities with EXACT logic from Django views"""

    def load_html_file(self, filepath):
        """Load HTML content from file"""
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()

    def extract_html_blocks(self, html_content):
        """Extract HTML blocks from content - EXACT logic from utils.py"""
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
            'wp-block-shortcode',
            'wp-block-embed-youtube',  # Add YouTube embeds
            'rll-youtube-player'       # Add RLL YouTube players
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

                # Contenu classique + media elements
                elif elem.name in ['p', 'ul', 'ol', 'img', 'blockquote', 'figure', 'iframe']:
                    current_block.append(elem)

        if current_block:
            blocks.append({'title': current_title, 'content': current_block})

        print(f"[DEBUG] {len(blocks)} blocs extraits (avec blocs spéciaux)")
        return blocks

    def reconstruct_blocks(self, blocks):
        """Reconstruct HTML from blocks - EXACT logic from utils.py"""
        html = ""
        for block in blocks:
            if block['title']:
                html += str(block['title']) + "\n"
            for elem in block['content']:
                html += str(elem) + "\n"
        return html

    def strip_duplicate_title_and_featured_image(self, html):
        """Remove duplicate titles and featured images - EXACT logic from utils.py but preserve content images"""
        soup = BeautifulSoup(html, 'html.parser')

        # Supprimer H1
        h1 = soup.find('h1')
        if h1:
            print("[CLEAN] 🔠 H1 supprimé :", h1.text.strip()[:60])
            h1.decompose()

        # Supprimer SEULEMENT img principale (wp-post-image class) - PAS les autres images
        main_img = soup.find('img', class_="wp-post-image")
        if main_img:
            print("[CLEAN] 🖼️ Image principale (wp-post-image) supprimée")
            main_img.decompose()
        else:
            print("[CLEAN] ℹ️ Aucune image wp-post-image trouvée à supprimer")

        return str(soup)

    def simplify_youtube_embeds(self, soup):
        """Simplify YouTube embeds - EXACT logic from utils.py"""
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

    def restore_youtube_iframes_from_rll_div(self, soup):
        """Restore YouTube iframes from RLL divs - EXACT logic from utils.py"""
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

    def clean_all_images(self, soup):
        """Clean and optimize all images - EXACT logic from utils.py but preserve content images"""
        restored = 0
        removed_svg = 0
        removed_empty_p = 0
        removed_duplicates = 0

        seen_srcs = set()

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

        # 2. Supprimer les <img> encore en SVG (placeholder) - SAUF si elles ont du contenu utile
        for img in soup.find_all("img"):
            if img.get("src", "").startswith("data:image/svg+xml"):
                # Vérifier si l'image a un alt text utile ou d'autres attributs importants
                alt_text = img.get("alt", "")
                if not alt_text or alt_text.lower() in ["", "image", "photo"]:
                    parent = img.parent
                    img.decompose()
                    removed_svg += 1
                    # Supprimer <p> vide laissé derrière
                    if parent and parent.name == "p" and not parent.text.strip() and len(parent.find_all()) == 0:
                        parent.decompose()
                        removed_empty_p += 1
                else:
                    print(f"[CLEAN] ℹ️ Garde l'image SVG avec alt='{alt_text}'")

        # 3. Collecter tous les src dans les <figure> ou <picture> MAIS ne pas supprimer les doublons de contenu
        for figure in soup.find_all(["figure", "picture"]):
            for img in figure.find_all("img"):
                if img.get("src"):
                    seen_srcs.add(img["src"])

        # 4. SKIP - Ne pas supprimer les images en double car elles peuvent être du contenu important
        # Cette logique était trop agressive et supprimait des images de contenu importantes

        print(f"[DEBUG] ✅ {restored} images restaurées depuis lazy-src")
        print(f"[DEBUG] 🗑️ {removed_svg} SVG placeholders supprimés")
        print(f"[DEBUG] 🧼 {removed_empty_p} <p> vides supprimés")
        print(f"[DEBUG] ℹ️ Conservation des images de contenu (pas de suppression de doublons)")

        return soup

    def clean_all_content(self, html_content):
        """Apply all cleaning operations to HTML content - EXACT pipeline from Django utils.py"""
        soup = BeautifulSoup(html_content, 'html.parser')

        # Step 1: Clean images first (restore lazy loading, remove duplicates, etc.)
        soup = self.clean_all_images(soup)
        print("[DEBUG] ✅ Images cleaned")

        # Step 2: Simplify YouTube embeds (convert complex embeds to simple iframes)
        soup = self.simplify_youtube_embeds(soup)
        print("[DEBUG] ✅ YouTube embeds simplified")

        # Step 3: Restore YouTube iframes from RLL divs
        soup = self.restore_youtube_iframes_from_rll_div(soup)
        print("[DEBUG] ✅ YouTube iframes restored from RLL")

        # Step 4: Strip duplicate title and featured image (this should be last)
        cleaned_html = self.strip_duplicate_title_and_featured_image(str(soup))
        print("[DEBUG] ✅ Duplicate title and featured image stripped")

        return cleaned_html