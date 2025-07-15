import json
import re
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_anthropic import ChatAnthropic


def generate_news_node(state):
    llm = ChatAnthropic(model="claude-3-5-sonnet-20241022", temperature=0.4, max_tokens=2000)

    headlines = state.get("headlines", [])
    post_type = state.get("post_type", "News")
    headlines_text = "\n".join([f"- {headline}" for headline in headlines])

    system_msg = SystemMessage(content=f"""
    ## ROLE:
    You are a tech journalist specialized in gaming, writing for a French tech blog. Your job is to craft short, clear, impactful news pieces in French, based on the provided source material.

    ### CRITICAL: RESPONSE FORMAT
    You MUST respond with a valid JSON object following this exact structure:
    {state['report_structure']}

    ### WRITING STYLE:
    - Journalistic, professional, dynamic tone
    - Neutral and informative (not personal review style)
    - Short paragraphs (max 2-3 sentences per paragraph)
    - Clear, simple, accessible language
    - Bullet lists allowed but concise

    ### FORMATTING WITHIN JSON TEXT FIELDS:
    You may include:
    - **Bullet Lists**:
    ```
    "paragraph": "Intro text.\\n\\nKey points:\\n- Point 1\\n- Point 2\\n- Point 3\\n\\nConclusion."
    ```
    - **Pros/Cons** if relevant:
    ```
    "paragraph": "Description.\\n\\n**Pros:**\\n- ✅ Positive point 1\\n- ✅ Positive point 2\\n\\n**Cons:**\\n- ❌ Negative point 1"
    ```

    ### HEADLINES:
    You must use these headlines but you have the right to delete some to avoid repetitions in the content:
    {headlines_text}

    ### JSON VALIDATION:
    - Escape all quotes with \\"
    - No trailing commas
    - All strings must be properly closed
    - Return ONLY the JSON object, no markdown wrappers
    """)

    human_msg = HumanMessage(content=f"""
    Write a short news piece based on the following information:

    CRITICAL: respond ONLY with a valid JSON object following this structure:
    {json.dumps(state['report_structure'], indent=2, ensure_ascii=False)}

    Headlines to include:
    {headlines_text}

    Source content:
    {state.get('source_content', '')}

    Reminders:
    1. Keep it short: this is a news snippet, not a long article.
    2. You may use lists or pros/cons but keep it concise.
    3. Use \\n for line breaks inside JSON strings.
    4. Escape quotes with \\"
    5. Do NOT include any markdown code blocks around the JSON.
    """)

    response = llm.invoke([system_msg, human_msg])
    content = response.content.strip()

    # Remove any markdown artifacts
    content = re.sub(r'^```json\s*', '', content)
    content = re.sub(r'\s*```$', '', content)

    try:
        parsed_article = json.loads(content)
        print("[DEBUG] ✅ Successfully parsed JSON from generate_news_node")
        return {"article": parsed_article, "headlines": headlines, "post_type": post_type}
    except json.JSONDecodeError as e:
        print(f"[ERROR] ❌ JSON decode error in generate_news_node: {e}")
        print(f"[DEBUG] Raw content preview: {content[:300]}...")

        # Use the existing fix_json_content function
        from writing.writer_nodes import fix_json_content
        fixed_content = fix_json_content(content)
        try:
            parsed_article = json.loads(fixed_content)
            print("[DEBUG] ✅ Successfully parsed fixed JSON")
            return {"article": parsed_article, "headlines": headlines, "post_type": post_type}
        except:
            print("[DEBUG] ❌ Could not fix JSON, returning raw content")
            return {"article": content, "headlines": headlines, "post_type": post_type}