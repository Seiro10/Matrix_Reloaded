import os
import openai
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()


def update_block_if_needed(block, subject, additional_content):
    """Update a single block if needed - EXACT logic from views2.py"""
    title = block['title']
    content_html = "\n".join([str(e) for e in block['content']])
    title_text = title.get_text() if title else "Sans titre"

    prompt = [
        {
            "role": "system",
            "content": """
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
"""
        },
        {
            "role": "user",
            "content": f"""
Sujet : {subject}
Titre : {title_text}

Contenu HTML :
{content_html}

Contenu additionnel :
{additional_content}

Évalue cette section et mets-la à jour si besoin.
"""
        }
    ]

    try:
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=prompt,
            temperature=0.4,
            max_tokens=1800
        )
        result = response.choices[0].message.content.strip()
        print(f"[GPT] Bloc '{title_text}' ➤ {result[:80]}...")

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
            print("[WARNING] Réponse inattendue du modèle.")
            return block

    except Exception as e:
        print(f"[ERROR] GPT block update failed: {e}")
        return block


def diagnose_missing_sections(memory):
    """Diagnose missing sections - EXACT format from views2.py"""
    prompt = [
        {
            "role": "system",
            "content": """
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
"""
        },
        {
            "role": "user",
            "content": f"""
Sujet : {memory['subject']}

Article HTML :
{memory['original_html']}

Contenu additionnel :
{memory['additional_content']}
"""
        }
    ]

    try:
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        res = client.chat.completions.create(model="gpt-4o", messages=prompt, max_tokens=1000)
        memory["diagnostic"] = res.choices[0].message.content.strip()
    except Exception as e:
        print(f"[ERROR] GPT diagnostic failed: {e}")
        memory["diagnostic"] = ""


def generate_sections(memory):
    """Generate new sections - EXACT format from views2.py"""
    prompt = [
        {
            "role": "system",
            "content": """
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
"""
        },
        {
            "role": "user",
            "content": f"""
Sujet : {memory['subject']}

Sections à créer :
{memory['diagnostic']}

Contenu additionnel :
{memory['additional_content']}
"""
        }
    ]

    try:
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        res = client.chat.completions.create(
            model="gpt-4o",
            messages=prompt,
            max_tokens=3000,
            temperature=1,
            top_p=0.95,
            frequency_penalty=0.5,
            presence_penalty=0.8
        )
        memory["generated_sections"] = res.choices[0].message.content.strip()
    except Exception as e:
        print(f"[ERROR] GPT section generation failed: {e}")
        memory["generated_sections"] = ""


def merge_final_article(memory):
    """Merge everything into final article - EXACT logic from views2.py"""
    prompt = [
        {
            "role": "system",
            "content": """
### ROLE
You are a senior French web editor specialized in video game journalism.

### GOAL
Your job is to **merge new information into an existing article** (already revised) without duplicating ideas.  
You must analyze the original structure and enrich it with **new content**, especially by **injecting generated paragraphs directly into existing sections** when relevant.

### GUIDELINES
- Use the updated article as the foundation.
- Carefully read the generated sections. If a generated section fits an existing section's topic, **integrate the new content as extra paragraphs inside that section.**
- Do not repeat or rephrase what is already covered.
- Respect logical flow, tone, and style of the original article.
- You may slightly rewrite paragraphs if it helps integrate the new information more smoothly.
- Update all references to years (e.g., 2024) to reflect the current year (2025) if the content is meant to be up to date.

### STYLE RULES
- Write in fluent, direct **French**.
- Avoid fluff, clichés, and redundant transitions.
- Never use names, brands, or YouTube references.
- Short paragraphs (3 lines max.), without long dashes.
- Never exceed three lines per paragraph. Cut long ideas into several shorter blocks.

### TECHNICAL LIMITATIONS
- Use only the following HTML tags: <h2>, <h3>, <p>, <ul>, <li>, <strong>, <em>, <blockquote>, <img>, <a>
- Do NOT use <html>, <body>, <head>, <style> or inline styles.
- Do not return any explanation or comment.

### OUTPUT
Return only clean, merged HTML. No headers, no extra output, without long dashes.
"""
        },
        {
            "role": "user",
            "content": f"""
Sujet : {memory['subject']}

Article révisé :
{memory['reconstructed_html']}

Nouvelles sections générées à intégrer :
{memory['generated_sections']}
"""
        }
    ]

    try:
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=prompt,
            max_tokens=8000,
            temperature=0.5
        )
        final_html = response.choices[0].message.content.strip()
        memory["final_article"] = final_html
        print("[DEBUG] ✅ Fusion intelligente terminée")
        return memory

    except Exception as e:
        print(f"[ERROR] ❌ GPT merge failed: {e}")
        memory["final_article"] = memory["reconstructed_html"] + "\n\n" + memory["generated_sections"]
        return memory