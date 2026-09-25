import anthropic

from src.content.quality import generate_quality_score
from src.db.repository import AgentRepo, PostRepo
from src.instagram.client import CloudinaryUploader, InstagramClient


def run_bridge_tick(
    db_path: str,
    anthropic_client: anthropic.Anthropic,
    ig_client: InstagramClient | None,
    threshold: float = 0.7,
) -> int:
    post_repo = PostRepo(db_path)
    agent_repo = AgentRepo(db_path)
    unscored = post_repo.get_unscored()
    published = 0

    for post in unscored:
        agent = agent_repo.get(post.agent_id)
        if agent is None:
            continue
        score = generate_quality_score(post, agent, anthropic_client)
        post_repo.update_quality_score(post.id, score)

        if ig_client is None or score < threshold:
            continue

        try:
            uploader = CloudinaryUploader()
            image_url = uploader.upload(post.image_path)
            caption = post.caption if "🤖 AI agent" in post.caption else f"{post.caption} 🤖 AI agent"
            ig_post_id = ig_client.post(image_url=image_url, caption=caption)
            post_repo.update_ig_post_id(post.id, ig_post_id)
            published += 1
        except Exception as e:
            print(f"[bridge] 게시 실패 post={post.id}: {e}")

    return published
