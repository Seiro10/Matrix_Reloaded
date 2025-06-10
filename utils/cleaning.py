from bs4 import BeautifulSoup
from bs4 import BeautifulSoup
from .file_io import log_debug
from bs4 import BeautifulSoup


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
            iframe['allow'] = "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
            iframe['allowfullscreen'] = True
            iframe['referrerpolicy'] = "strict-origin-when-cross-origin"
            div.replace_with(iframe)
            count += 1
    print(f"[DEBUG] ✅ {count} iframes restaurés depuis <div.rll-youtube-player>")
    return soup


def clean_all_images(soup):
    from bs4 import Tag

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
            if parent.name == "p" and not parent.text.strip() and len(parent.find_all()) == 0:
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
            if parent.name == "p" and not parent.text.strip() and len(parent.find_all()) == 0:
                parent.decompose()
                removed_empty_p += 1

    print(f"[DEBUG] ✅ {restored} images restaurées depuis lazy-src")
    print(f"[DEBUG] 🗑️ {removed_svg} SVG placeholders supprimés")
    print(f"[DEBUG] 🧼 {removed_empty_p} <p> vides supprimés")
    print(f"[DEBUG] 🧽 {removed_duplicates} images dupliquées supprimées")

    return soup


def remove_useless_tags(soup):
    for tag in soup.find_all(["noscript", "script", "style"]):
        tag.decompose()
    return soup


def clean_html_for_processing(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    soup = restore_youtube_iframes_from_rll_div(soup)
    soup = simplify_youtube_embeds(soup)
    soup = clean_all_images(soup)
    return str(soup)


# Fonction utilisée avant publication : complète (restauration des iframes)
def clean_html_for_publication(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    soup = simplify_youtube_embeds(soup)
    soup = clean_all_images(soup)
    soup = restore_youtube_iframes_from_rll_div(soup)
    return str(soup)

def clean_transcript(text: str) -> str:
    lines = text.split("\n")
    cleaned = [line.strip() for line in lines if line.strip()]
    return "\n".join(cleaned)
