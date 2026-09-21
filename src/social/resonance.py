from src.models import Agent


def interest_overlap(a: Agent, b: Agent) -> float:
    shared = set(a.interests) & set(b.interests)
    if not shared:
        return 0.0
    score = sum(min(a.interests[k], b.interests[k]) for k in shared)
    max_possible = sum(max(a.interests[k], b.interests[k]) for k in shared)
    return score / max_possible if max_possible > 0 else 0.0


def aesthetic_compat(a: Agent, b: Agent) -> float:
    palette_match = 1.0 if a.aesthetic.palette == b.aesthetic.palette else 0.3
    comp_match = 1.0 if a.aesthetic.composition == b.aesthetic.composition else 0.3
    return (palette_match + comp_match) / 2


def personality_compat(a: Agent, b: Agent) -> float:
    energy_diff = abs(a.personality.energy - b.personality.energy)
    valence_diff = abs(a.personality.valence - b.personality.valence)
    return 1.0 - (energy_diff + valence_diff) / 2


def resonance_score(viewer: Agent, poster: Agent) -> float:
    return (
        interest_overlap(viewer, poster) * 0.5
        + aesthetic_compat(viewer, poster) * 0.3
        + personality_compat(viewer, poster) * 0.2
    )


def like_threshold(agent: Agent) -> float:
    return round(0.7 - agent.personality.energy * 0.4, 3)


def comment_threshold(agent: Agent) -> float:
    return round(like_threshold(agent) + 0.15, 3)
