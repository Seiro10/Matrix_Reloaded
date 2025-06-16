from bs4 import BeautifulSoup, Tag


class HTMLProcessor:
    """HTML processing utilities adapted from your original code"""

    def load_html_file(self, filepath):
        """Load HTML content from file"""
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()

    def extract_html_blocks(self, html_content):
        """Extract HTML blocks from content"""
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
        """Reconstruct HTML from blocks"""
        html = ""
        for block in blocks:
            if block['title']:
                html += str(block['title']) + "\n"
            for elem in block['content']:
                html += str(elem) + "\n"
        return html

    def strip_duplicate_title_and_featured_image(self, html):
        """Remove duplicate titles and featured images"""
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

        return str(soup)

    def simplify_youtube_embeds(self, soup):
        """Simplify YouTube embeds"""
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
        """Restore YouTube iframes from RLL divs"""
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
        """Clean and optimize all images"""
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

        # 3. Collecter tous les src dans les <figure> ou <picture>
        for figure in soup.find_all(["figure", "picture"]):
            for img in figure.find_all("img"):
                if img.get("src"):
                    seen_srcs.add(img["src"])

        # 4. Supprimer les images en double hors figure/picture
        for img in soup.find_all("img"):
            src = img.get("src")
            if not src or src not in seen_srcs:
                continue
            if not img.find_parent(["figure", "picture"]):
                parent = img.parent
                img.decompose()
                removed_duplicates += 1
                # Supprimer <p> vide s'il ne reste rien
                if parent and parent.name == "p" and not parent.text.strip() and len(parent.find_all()) == 0:
                    parent.decompose()
                    removed_empty_p += 1

        print(f"[DEBUG] ✅ {restored} images restaurées depuis lazy-src")
        print(f"[DEBUG] 🗑️ {removed_svg} SVG placeholders supprimés")
        print(f"[DEBUG] 🧼 {removed_empty_p} <p> vides supprimés")
        print(f"[DEBUG] 🧽 {removed_duplicates} images dupliquées supprimées")

        return soup

    def clean_all_content(self, html_content):
        """Apply all cleaning operations to HTML content"""
        soup = BeautifulSoup(html_content, 'html.parser')

        # Apply all cleaning operations
        soup = self.clean_all_images(soup)
        soup = self.simplify_youtube_embeds(soup)
        soup = self.restore_youtube_iframes_from_rll_div(soup)

        # Strip duplicate title and featured image
        cleaned_html = self.strip_duplicate_title_and_featured_image(str(soup))

        return cleaned_html