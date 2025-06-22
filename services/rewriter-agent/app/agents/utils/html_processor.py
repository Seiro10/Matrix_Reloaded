from bs4 import BeautifulSoup, Tag, NavigableString


class HTMLProcessor:
    """HTML processing utilities with EXACT logic from Django utils.py"""

    def load_html_file(self, filepath):
        """Load HTML content from file"""
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()

    def extract_html_blocks(self, html_content):
        """Extract HTML blocks - EXACT COPY from update_app/utils.py"""
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

    def reconstruct_blocks(self, blocks):
        """Reconstruct HTML from blocks - EXACT COPY from update_app/utils.py"""
        html = ""
        for block in blocks:
            if block['title']:
                html += str(block['title']) + "\n"
            for elem in block['content']:
                html += str(elem) + "\n"
        return html

    def strip_duplicate_title_and_featured_image(self, html):
        """Remove duplicate titles and featured images - EXACT COPY from utils.py"""
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

    def simplify_youtube_embeds(self, soup):
        """Simplify YouTube embeds - EXACT COPY from utils.py"""
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
        """Restore YouTube iframes from RLL divs - EXACT COPY from utils.py"""
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
        """Clean and optimize all images - EXACT COPY from utils.py with content preservation"""
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

        # 4. 🔧 Restaurer <img> manquant dans <picture> si nécessaire
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
        print(f"[DEBUG] ℹ️ Conservation des images de contenu (pas de suppression de doublons)")

        return soup

    def clean_all_content(self, html_content):
        """Apply all cleaning operations to HTML content"""
        soup = BeautifulSoup(html_content, 'html.parser')

        # Step 1: Clean images first
        soup = self.clean_all_images(soup)
        print("[DEBUG] ✅ Images cleaned")

        # Step 2: Simplify YouTube embeds
        soup = self.simplify_youtube_embeds(soup)
        print("[DEBUG] ✅ YouTube embeds simplified")

        # Step 3: Restore YouTube iframes from RLL divs
        soup = self.restore_youtube_iframes_from_rll_div(soup)
        print("[DEBUG] ✅ YouTube iframes restored from RLL")

        # Step 4: Strip duplicate title and featured image
        cleaned_html = self.strip_duplicate_title_and_featured_image(str(soup))
        print("[DEBUG] ✅ Duplicate title and featured image stripped")

        return cleaned_html