import cloudinary
import cloudinary.uploader
import httpx

_GRAPH_BASE = "https://graph.facebook.com/v18.0"


class CloudinaryUploader:
    def upload(self, image_path: str) -> str:
        result = cloudinary.uploader.upload(image_path, folder="agent-instagram")
        return result["secure_url"]


class InstagramClient:
    def __init__(self, ig_user_id: str, access_token: str):
        self._user_id = ig_user_id
        self._token = access_token

    def post(self, image_url: str, caption: str) -> str:
        with httpx.Client() as http:
            container_resp = http.post(
                f"{_GRAPH_BASE}/{self._user_id}/media",
                params={
                    "image_url": image_url,
                    "caption": caption,
                    "access_token": self._token,
                },
            )
            if container_resp.status_code != 200:
                raise RuntimeError(f"container creation failed: {container_resp.json()}")
            creation_id = container_resp.json()["id"]

            publish_resp = http.post(
                f"{_GRAPH_BASE}/{self._user_id}/media_publish",
                params={
                    "creation_id": creation_id,
                    "access_token": self._token,
                },
            )
            if publish_resp.status_code != 200:
                raise RuntimeError(f"publish failed: {publish_resp.json()}")
            return publish_resp.json()["id"]
