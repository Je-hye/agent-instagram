import base64
import uuid
from pathlib import Path

import openai


def generate_image(prompt: str, save_dir: str, client: openai.OpenAI) -> str:
    response = client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        size="1024x1024",
        quality="standard",
        n=1,
    )
    image_data = base64.b64decode(response.data[0].b64_json)
    Path(save_dir).mkdir(parents=True, exist_ok=True)
    filepath = Path(save_dir) / f"{uuid.uuid4()}.png"
    filepath.write_bytes(image_data)
    return str(filepath)
