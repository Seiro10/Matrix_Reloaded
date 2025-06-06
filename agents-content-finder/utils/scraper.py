# utils/scraper.py

from bs4 import BeautifulSoup
import re


def clean_html_text(html: str, min_words: int = 15) -> str:
    """
    Nettoie le HTML en préservant le contenu principal d'article
    mais en supprimant les éléments parasites
    """
    soup = BeautifulSoup(html, "html.parser")

    # Étape 1: Trouve le contenu principal
    main_content = find_main_content(soup)

    if not main_content:
        # Fallback: utilise tout le body mais nettoie plus agressivement
        main_content = soup.find('body') or soup

    # Étape 2: Supprime les éléments parasites du contenu principal
    remove_unwanted_elements(main_content)

    # Étape 3: Extrait et nettoie le texte
    text = main_content.get_text(separator="\n", strip=True)

    # Étape 4: Nettoie le texte ligne par ligne
    cleaned_text = clean_text_lines(text, min_words)

    return cleaned_text


def find_main_content(soup):
    """
    Trouve le conteneur de contenu principal avec plusieurs stratégies
    """
    # Stratégie 1: Sélecteurs de contenu principal spécifiques
    content_selectors = [
        'article',
        '[role="main"]',
        'main',
        '.entry-content',
        '.post-content',
        '.article-content',
        '.content-main',
        '.single-content',
        '#content article',
        '.post-body',
        '.entry-body'
    ]

    for selector in content_selectors:
        element = soup.select_one(selector)
        if element and len(element.get_text(strip=True)) > 500:
            return element

    # Stratégie 2: Trouve l'élément avec le plus de paragraphes
    candidates = soup.find_all(['div', 'section', 'article'])
    best_candidate = None
    best_score = 0

    for candidate in candidates:
        # Compte les paragraphes significatifs
        paragraphs = candidate.find_all('p')
        significant_p = [p for p in paragraphs if len(p.get_text(strip=True)) > 50]

        score = len(significant_p)

        # Bonus pour certaines classes/ids
        if candidate.get('class'):
            classes = ' '.join(candidate.get('class', []))
            if any(word in classes for word in ['content', 'article', 'post', 'main']):
                score += 5

        if candidate.get('id'):
            if any(word in candidate['id'] for word in ['content', 'article', 'post', 'main']):
                score += 5

        if score > best_score:
            best_score = score
            best_candidate = candidate

    return best_candidate


def remove_unwanted_elements(content):
    """
    Supprime les éléments parasites du contenu
    """
    # Éléments à supprimer complètement
    unwanted_tags = [
        'script', 'style', 'noscript', 'iframe', 'embed', 'object',
        'nav', 'header', 'footer', 'aside'
    ]

    for tag in unwanted_tags:
        for element in content.find_all(tag):
            element.decompose()

    # Classes/IDs parasites à supprimer
    unwanted_selectors = [
        # Publicités
        '.ad', '.ads', '.advertisement', '.adsbygoogle', '.justads-insert',
        '[class*="ad-"]', '[id*="ad-"]', '[class*="advertisement"]',

        # Navigation et UI
        '.nav', '.navigation', '.navbar', '.menu', '.sidebar',
        '.breadcrumb', '.breadcrumbs', '.pagination',

        # Social et partage
        '.social', '.share', '.sharing', '.social-share', '.share-buttons',

        # Commentaires
        '.comments', '.comment', '.comment-form',

        # Newsletter et formulaires
        '.newsletter', '.subscription', '.subscribe', '.signup',

        # Widgets et sidebar
        '.widget', '.sidebar', '.related', '.related-posts',

        # Footer
        '.footer', '.site-footer',

        # Boutons et actions
        '.button', '.btn', '.cta', '.call-to-action'
    ]

    for selector in unwanted_selectors:
        for element in content.select(selector):
            element.decompose()


def clean_text_lines(text: str, min_words: int) -> str:
    """
    Nettoie le texte ligne par ligne
    """
    # Phrases parasites à supprimer
    unwanted_phrases = [
        # Navigation
        'Skip to content', 'Menu', 'Home', 'Contact', 'About',
        'Rechercher', 'Search', 'Login', 'Sign in', 'Register',

        # Actions
        'Read more', 'Continue reading', 'Lire la suite', 'Voir plus',
        'Subscribe', 'Follow', 'Share', 'Like', 'Comment',

        # Social media
        'Facebook', 'Twitter', 'Instagram', 'LinkedIn', 'YouTube',
        'Follow us', 'Suivez-nous', 'Partager', 'J\'aime',

        # Footer/legal
        'Privacy Policy', 'Terms of Service', 'Copyright', 'All rights reserved',
        'Politique de confidentialité', 'Mentions légales',

        # Newsletter
        'Subscribe to newsletter', 'Enter your email', 'Newsletter',
        'S\'abonner', 'Votre email', 'Inscription',

        # Dates isolées
        'Published', 'Updated', 'Publié', 'Mis à jour',

        # Publicité
        'Advertisement', 'Sponsored', 'Publicité', 'Sponsorisé'
    ]

    # Nettoie les espaces multiples et lignes vides
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r'[ \t]+', ' ', text)

    lines = text.split('\n')
    cleaned_lines = []

    for line in lines:
        line = line.strip()

        # Ignore les lignes trop courtes
        words = line.split()
        if len(words) < min_words:
            continue

        # Ignore les lignes contenant des phrases parasites
        if any(phrase.lower() in line.lower() for phrase in unwanted_phrases):
            continue

        # Ignore les lignes qui sont principalement des liens
        if line.count('http') > 2:
            continue

        # Ignore les lignes de navigation numérique
        if re.match(r'^[\d\s\-\|\.]+$', line):
            continue

        # Ignore les lignes avec beaucoup de majuscules (souvent du spam)
        if len([c for c in line if c.isupper()]) > len(line) * 0.5:
            continue

        cleaned_lines.append(line)

    return '\n'.join(cleaned_lines)


def extract_structure_tags(html: str) -> str:
    """
    Extrait la structure HTML simplifiée sans classes, IDs et attributs
    """
    soup = BeautifulSoup(html, "html.parser")

    # Trouve le contenu principal
    main_content = find_main_content(soup)
    if not main_content:
        main_content = soup

    # Supprime les éléments parasites
    remove_unwanted_elements(main_content)

    # Récupère les éléments de structure importants
    structure_elements = main_content.find_all([
        "h1", "h2", "h3", "h4", "h5", "h6",
        "p", "ul", "ol", "li", "blockquote"
    ])

    structure = []
    for element in structure_elements:
        # Clone l'élément pour ne pas modifier l'original
        clean_element = soup.new_tag(element.name)
        clean_element.string = element.get_text(strip=True)

        # Ajoute seulement si le contenu est significatif
        text_content = element.get_text(strip=True)
        if len(text_content) > 10:
            structure.append(str(clean_element))

    return '\n'.join(structure[:30])  # Limite à 30 éléments