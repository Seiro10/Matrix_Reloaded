"""Website configuration for destination mapping"""

WEBSITE_DESTINATIONS = {
    "League of Legends": "Stuffgaming",
    "IGN Gaming": "Stuffgaming",
    "Test Gaming Site": "Stuffgaming",
    # Ajouter d'autres mappings ici au fur et à mesure
    "Valorant": "Stuffgaming",
    "TFT": "Stuffgaming",
    "Wild Rift": "Stuffgaming",
}

def get_destination_website(source_website: str) -> str:
    """Get the destination website for a source website"""
    return WEBSITE_DESTINATIONS.get(source_website, "Stuffgaming")