import openai
from bs4 import BeautifulSoup

def update_block_if_needed(block, subject, transcript_text):
    import openai
    from bs4 import BeautifulSoup

    title = block['title']
    content_html = "\n".join([str(e) for e in block['content']])
    title_text = title.get_text() if title else "Sans titre"

    include_temporality = any(
        keyword in (subject + title_text).lower()
        for keyword in ["saison", "patch", "année", "2024", "2023", "version"]
    )

    prompt = [
        {
            "role": "system",
            "content": f"""
### RÔLE
Tu es un rédacteur expert en jeux vidéo, spécialisé dans la mise à jour d'articles à partir de transcripts YouTube récents. Tu travailles en français et ton objectif est d'analyser et mettre à jour les sections d'article de façon précise et fiable.

### OBJECTIF
- Identifier si une section est :
  - ✅ VALIDE (encore correcte)
  - ✏️ À METTRE À JOUR (partiellement incorrecte)
  - ❌ OBSOLÈTE (totalement dépassée)

### STRATÉGIE D’ÉVALUATION
- Compare le contenu HTML ligne par ligne au transcript.
- Si une information est dépassée, incomplète ou absente du transcript, corrige-la.
- Si la section est correcte mais améliorable, propose une mise à jour partielle.

### INSTRUCTIONS
- Si VALIDE → réponds `STATUS: VALID` + une justification.
- Si À METTRE À JOUR ou OBSOLÈTE → réponds `STATUS: TO BE UPDATED` ou `STATUS: OUTDATED` + version corrigée en HTML.
- Utilise une écriture claire, concise, factuelle.
- Structure le HTML avec uniquement ces balises : <p>, <ul>, <li>, <strong>, <em>, <blockquote>. Pas de <div>, pas de styles inline.

### LIMITES
- Ne fais **aucune mention temporelle** (saison, patch, année, aujourd’hui, récemment, etc.) sauf si le sujet ou le titre y font référence.
- INCLUDE_TEMPORALITY = {"true" if include_temporality else "false"}
- Ne mentionne aucune marque, créateur ou chaîne.
- N’invente jamais d’information absente du transcript.
- Rédige uniquement en français.
"""
        },
        {
            "role": "user",
            "content": f"""
Sujet : {subject}
Titre de la section : {title_text}

Contenu HTML :
{content_html}

Transcript vidéo :
{transcript_text}

Évalue et réécris la section selon les règles ci-dessus.
"""
        }
    ]

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=prompt,
            temperature=0.4,
            max_tokens=20000
        )

        answer = response.choices[0].message.content.strip()
        print(f"[GPT] Bloc '{title_text}' →\n{answer[:400]}...\n")

        if answer.startswith("STATUS: VALID"):
            return block

        elif answer.startswith("STATUS: TO BE UPDATED") or answer.startswith("STATUS: OUTDATED"):
            try:
                updated_html = answer.split('\n', 1)[1].strip()
                soup = BeautifulSoup(updated_html, "html.parser")
                updated_block = {
                    "title": title,
                    "content": list(soup.contents)
                }
                return updated_block
            except Exception as e:
                print(f"[PARSE ERROR] {e}")
                return block

        else:
            print(f"[WARNING] Réponse inattendue : {answer}")
            return block

    except Exception as e:
        print(f"[GPT ERROR] {e}")
        return block
