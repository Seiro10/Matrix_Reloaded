from typing import List
from team.journalists_team import Journalist


def distribute_headlines_to_journalists(journalists: List[Journalist], headlines: List[str]) -> List[Journalist]:
    """
    Distributes headlines evenly among journalists.
    Each journalist gets assigned specific headlines to cover.
    """
    if not headlines:
        return journalists

    num_journalists = len(journalists)
    if num_journalists == 0:
        return journalists

    # Calculate how many headlines each journalist should get
    headlines_per_journalist = len(headlines) // num_journalists
    extra_headlines = len(headlines) % num_journalists

    updated_journalists = []
    start_idx = 0

    for i, journalist in enumerate(journalists):
        # Calculate how many headlines this journalist gets
        num_headlines = headlines_per_journalist
        if i < extra_headlines:
            num_headlines += 1

        # Assign headlines to this journalist
        end_idx = start_idx + num_headlines
        assigned_headlines = headlines[start_idx:end_idx]

        # Create updated journalist with assigned headlines
        updated_journalist = Journalist(
            organization=journalist.organization,
            full_name=journalist.full_name,
            nickname=journalist.nickname,
            job_title=journalist.job_title,
            about=journalist.about,
            assigned_headlines=assigned_headlines
        )

        updated_journalists.append(updated_journalist)
        start_idx = end_idx

    return updated_journalists