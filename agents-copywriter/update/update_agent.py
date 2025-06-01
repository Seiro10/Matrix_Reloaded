from utils.html_blocks import extract_html_blocks, reconstruct_blocks
from utils.update_eval import update_block_if_needed

class UpdateAgent:
    def update(self, html: str, subject: str, transcript: str) -> str:
        print("[UPDATE] 🧩 Découpage HTML en blocs...")
        blocks = extract_html_blocks(html)

        updated_blocks = []
        for block in blocks:
            title = block['title'].get_text() if block['title'] else "Sans titre"
            print(f"[UPDATE] 🔍 Bloc: {title}")
            updated_block = update_block_if_needed(block, subject, transcript)
            updated_blocks.append(updated_block)

        html_rebuilt = reconstruct_blocks(updated_blocks)
        print(f"[UPDATE] ✅ Article reconstruit ({len(html_rebuilt)} caractères)")
        return html_rebuilt
