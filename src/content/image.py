import uuid
from pathlib import Path

import httpx
import openai


def generate_image(prompt: str, save_dir: str, client: openai.OpenAI) -> str:
    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        quality="standard",
        n=1,
    )
    image_url = response.data[0].url
    image_data = httpx.get(image_url).content
    Path(save_dir).mkdir(parents=True, exist_ok=True)
    filepath = Path(save_dir) / f"{uuid.uuid4()}.png"
    filepath.write_bytes(image_data)
    return str(filepath)
