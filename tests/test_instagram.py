import pytest
from unittest.mock import MagicMock, patch


def test_cloudinary_uploader_returns_url():
    with patch("cloudinary.uploader.upload") as mock_upload:
        mock_upload.return_value = {"secure_url": "https://res.cloudinary.com/test/image.png"}
        from src.instagram.client import CloudinaryUploader
        url = CloudinaryUploader().upload("images/test.png")
    assert url == "https://res.cloudinary.com/test/image.png"


def test_instagram_client_post_returns_ig_id():
    with patch("httpx.Client.post") as mock_post:
        mock_post.side_effect = [
            MagicMock(status_code=200, json=lambda: {"id": "container_123"}),
            MagicMock(status_code=200, json=lambda: {"id": "ig_post_456"}),
        ]
        from src.instagram.client import InstagramClient
        client = InstagramClient(ig_user_id="user1", access_token="token1")
        ig_id = client.post(
            image_url="https://example.com/img.png",
            caption="Test caption 🤖 AI agent",
        )
    assert ig_id == "ig_post_456"


def test_instagram_client_raises_on_container_error():
    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=400,
            json=lambda: {"error": {"message": "Invalid image"}},
        )
        from src.instagram.client import InstagramClient
        client = InstagramClient(ig_user_id="user1", access_token="token1")
        with pytest.raises(RuntimeError, match="container"):
            client.post(
                image_url="https://example.com/bad.png",
                caption="Test 🤖 AI agent",
            )


def test_instagram_client_raises_on_publish_error():
    with patch("httpx.Client.post") as mock_post:
        mock_post.side_effect = [
            MagicMock(status_code=200, json=lambda: {"id": "container_123"}),
            MagicMock(
                status_code=400,
                json=lambda: {"error": {"message": "Publish failed"}},
            ),
        ]
        from src.instagram.client import InstagramClient
        client = InstagramClient(ig_user_id="user1", access_token="token1")
        with pytest.raises(RuntimeError, match="publish"):
            client.post(
                image_url="https://example.com/img.png",
                caption="Test 🤖 AI agent",
            )


def test_cloudinary_uploader_uses_folder():
    with patch("cloudinary.uploader.upload") as mock_upload:
        mock_upload.return_value = {"secure_url": "https://res.cloudinary.com/test/image.png"}
        from src.instagram.client import CloudinaryUploader
        CloudinaryUploader().upload("images/test.png")
    mock_upload.assert_called_once_with("images/test.png", folder="agent-instagram")
