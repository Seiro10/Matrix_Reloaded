import os
import logging
from bs4 import BeautifulSoup
from langchain_anthropic import ChatAnthropic

logger = logging.getLogger(__name__)


def update_block_if_needed(block, subject, additional_content):
    """Update a single block if needed"""
    title = block['title']
    content_html = "\n".join([str(e) for e in block['content']])
    title_text = title.get_text() if title else "Sans titre"

    prompt = f"""
### ROLE
You're a French world-class copywriter specializing in video games. Your job is to update and improve article sections based on additional content provided.

### GOAL
- Identify if a section is:
  - VALID (still accurate and aligned with the additional content)
  - TO BE UPDATED (partially outdated or missing context)
  - OUTDATED (no longer valid and must be rewritten)

### VERIFICATION STRATEGY
- Compare the section line by line to the additional content.
- If the section mentions features/events/patches that the additional content contradicts or no longer includes, flag it.
- If a minor fix is needed, rewrite only the outdated parts.

### INSTRUCTIONS
- If VALID → respond `STATUS: VALID` and explain briefly why.
- If TO BE UPDATED → respond `STATUS: TO BE UPDATED` and give a corrected version (HTML).
- If OUTDATED → respond `STATUS: OUTDATED` and give a rewritten version (HTML).
- Use <p>, <ul>, <li>, <strong>, <em>, etc. No <div>, no inline styles.
- No brands, names or YouTube references.
- Write in French.

### TECHNICAL LIMITATIONS
- Never use long dashes (—). Replace them with a comma, semicolon or period, depending on the context.
- Never exceed three lines per paragraph. Cut long ideas into several shorter blocks.

Sujet : {subject}
Titre : {title_text}

Contenu HTML :
{content_html}

Contenu additionnel :
{additional_content}

Évalue cette section et mets-la à jour si besoin.
"""

    try:
        llm = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            temperature=0.4,
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )

        logger.info(f"[GPT-BLOCK] Calling Claude for block: {title_text}")
        response = llm.invoke(prompt)
        result = response.content.strip()

        if result.startswith("STATUS: VALID"):
            return block

        elif result.startswith("STATUS: TO BE UPDATED") or result.startswith("STATUS: OUTDATED"):
            html_start = result.split("\n", 1)[1].strip()
            soup = BeautifulSoup(html_start, "html.parser")
            updated_block = {
                "title": title,
                "content": list(soup.contents)
            }
            return updated_block

        else:
            logger.warning(f"[GPT-BLOCK] Unexpected response format: {title_text}")
            return block

    except Exception as e:
        logger.error(f"[GPT-BLOCK] ❌ Error processing block '{title_text}': {e}")
        return block


def diagnose_missing_sections(memory):
    prompt = f"""
### ROLE
Tu es un éditeur de contenu. Ton rôle est d'analyser un article déjà rédigé et du contenu additionnel afin d'identifier les sujets pertinents qui ne sont pas encore couverts.

### GOAL
Génère entre 1 et 3 nouvelles sections pertinentes à ajouter à l'article. Chaque section doit avoir :
- Un titre sous forme de balise <h2>
- Une courte description en une phrase (maximum 25 mots) résumant le contenu attendu

### GUIDELINES
- Ne suggère pas de doublons : les thèmes déjà traités dans l'article ne doivent pas être répétés.
- Priorise les apports d'expérience ou d'angle personnel non couverts.
- Reste simple et informatif : ne génère pas de contenu ou de paragraphe.

### TECHNICAL LIMITATIONS
- Utilise uniquement les balises HTML suivantes : <h2>, <p>
- Ne génère rien d'autre (pas d'explication ou de commentaire)
- N'utilise jamais de tirets longs (—). Remplace-les par une virgule, un point-virgule ou un point selon le contexte.
- Ne dépasse jamais trois lignes par paragraphe. Coupe les idées longues en plusieurs blocs plus courts.

Sujet : {memory['subject']}

Article HTML :
{memory['original_html']}

Contenu additionnel :
{memory['additional_content']}
"""

    try:
        llm = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            temperature=0.5,
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )

        logger.info("[GPT-DIAGNOSTIC] Calling Claude...")
        response = llm.invoke(prompt)
        memory["diagnostic"] = response.content.strip()

    except Exception as e:
        logger.error(f"[GPT-DIAGNOSTIC] ❌ Error: {e}")
        memory["diagnostic"] = ""


def generate_sections(memory):
    prompt = f"""
### ROLE
Tu es un joueur passionné qui partage ses avis et expériences sur les jeux vidéo de manière naturelle, mais claire.

### GOAL
Écrire des paragraphes immersifs et personnels en français (100 mots minimum), à partir de ton expérience de jeu.

### GUIDELINES
- Utilise la première personne : partage tes ressentis, tes doutes, tes frustrations ou tes moments marquants.
- Adopte un ton naturel, humain : comme si tu écrivais à un ami joueur, sans jargon marketing ni langue de bois.
- Évite les textes trop lisses ou trop formels : garde un peu d'hésitation, de spontanéité.
- Reste fluide : phrases simples, quelques respirations, mais pas trop relâché.
- Tu peux inclure des interjections ou des remarques personnelles (ex. : "honnêtement, j'étais paumé", "franchement, j'ai galéré"), mais modérément.

### STYLE
- Naturel > structuré
- Ton personnel, mais pas familier ou vulgaire
- Un peu de style rédactionnel, sans être encyclopédique
- Fragments de phrases ou contradictions légères bienvenus

### TECHNICAL LIMITATIONS
- HTML only: <h2>, <h3>, <p>, <ul>, <li>, <strong>, <em>, <blockquote>, <img>, <a>
- Une seule section par titre
- N'utilise jamais de tirets longs (—). Remplace-les par une virgule, un point-virgule ou un point selon le contexte.
- Ne dépasse jamais trois lignes par paragraphe. Coupe les idées longues en plusieurs blocs plus courts.

Sujet : {memory['subject']}

Sections à créer :
{memory['diagnostic']}

Contenu additionnel :
{memory['additional_content']}
"""

    try:
        llm = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            temperature=1.0,
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )

        logger.info("[GPT-GENERATE] Calling Claude...")
        response = llm.invoke(prompt)
        memory["generated_sections"] = response.content.strip()

    except Exception as e:
        logger.error(f"[GPT-GENERATE] ❌ Error: {e}")
        memory["generated_sections"] = ""


# --- FUSION STRUCTURÉE (remplace merge_final_article) ---


def split_into_sections(html):
    soup = BeautifulSoup(html, "html.parser")
    sections = []
    current_title = None
    current_content = []

    for elem in soup.find_all(recursive=False):
        if elem.name == "h2":
            if current_title:
                sections.append({"title": current_title, "content": current_content})
            current_title = elem
            current_content = []
        elif current_title:
            current_content.append(elem)

    if current_title:
        sections.append({"title": current_title, "content": current_content})

    return sections


def parse_generated_sections(generated_html):
    soup = BeautifulSoup(generated_html, "html.parser")
    sections = []
    current_title = None
    current_content = []

    for elem in soup.find_all(recursive=False):
        if elem.name == "h2":
            if current_title:
                sections.append({"title": current_title, "content": current_content})
            current_title = elem
            current_content = []
        elif current_title:
            current_content.append(elem)

    if current_title:
        sections.append({"title": current_title, "content": current_content})

    return sections


def reconstruct_blocks(sections):
    html = ""
    for section in sections:
        if section['title']:
            html += str(section['title']) + "\n"
        for elem in section['content']:
            html += str(elem) + "\n"
    return html


def merge_final_article_structured(memory):
    logger.info("[MERGE] Fusion structurée des sections générées...")

    try:
        existing_sections = split_into_sections(memory["reconstructed_html"])
        generated_sections = parse_generated_sections(memory["generated_sections"])

        existing_titles = [s["title"].get_text(strip=True) for s in existing_sections]

        from difflib import get_close_matches

        for gen_sec in generated_sections:
            gen_title = gen_sec["title"].get_text(strip=True)
            match = get_close_matches(gen_title, existing_titles, n=1, cutoff=0.6)

            if match:
                matched_title = match[0]
                for sec in existing_sections:
                    if sec["title"].get_text(strip=True) == matched_title:
                        logger.info(f"[MERGE] ➕ Injecté dans : {matched_title}")
                        sec["content"].extend(gen_sec["content"])
                        break
            else:
                logger.info(f"[MERGE] 🆕 Nouvelle section : {gen_title}")
                existing_sections.append(gen_sec)

        merged_html = reconstruct_blocks(existing_sections)
        memory["final_article"] = merged_html
        logger.info(f"[MERGE] ✅ Fusion terminée : {len(merged_html)} caractères")

        return memory

    except Exception as e:
        logger.error(f"[MERGE] ❌ Erreur fusion : {e}")
        memory["final_article"] = memory["reconstructed_html"] + "\n\n" + memory["generated_sections"]
        return memory
