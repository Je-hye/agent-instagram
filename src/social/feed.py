from src.db.repository import FollowRepo, PostRepo
from src.models import Post


def get_feed(agent_id: str, follow_repo: FollowRepo, post_repo: PostRepo,
             limit: int = 30) -> list[Post]:
    following = follow_repo.get_following(agent_id)
    return post_repo.get_feed(following, limit=limit)
