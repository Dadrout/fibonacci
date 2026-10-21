import httpx
import asyncio
from uuid import uuid4
import logging
import json

from app.core.config import settings

logger = logging.getLogger(__name__)

class RunwareService:
    def __init__(self):
        self.api_key = settings.RUNWARE_API_KEY
        self.base_url = "https://api.runware.ai/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    async def _send_request(self, payload: dict | list):
        if not self.api_key:
            logger.warning("RUNWARE_API_KEY is not configured. Skipping Runware image generation.")
            return {"data": []}

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(f"{self.base_url}/tasks", headers=self.headers, json=payload)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"Runware API request failed with status {e.response.status_code}: {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"An unexpected error occurred while calling Runware API: {e}", exc_info=True)
                raise

    async def generate_images_from_prompts(self, prompts: list[str]) -> list[str]:
        """
        Generates multiple images from a list of prompts in a single batch request.
        """
        logger.info(f"🎨 Generating {len(prompts)} images with Runware in a single batch...")
        
        tasks_payload: list[dict] = []
        uuid_to_index: dict[str, int] = {}
        for idx, prompt in enumerate(prompts):
            task_uuid = str(uuid4())
            uuid_to_index[task_uuid] = idx
            tasks_payload.append({
                "taskType": "imageInference",
                "taskUUID": task_uuid,
                "model": "rundiffusion:130@100",
                "positivePrompt": prompt,
                "width": 1280,
                "height": 720,
                "steps": 33,
                "CFGScale": 3,
                "scheduler": "Euler Beta",
                "outputFormat": "JPEG",
                "numberResults": 1,
                "outputType": ["URL"],
                "includeCost": True,
            })

        try:
            logger.info(f"Sending payload to Runware: {json.dumps(tasks_payload, indent=2)}")
            response_data = await self._send_request(tasks_payload)
            
            if response_data.get("errors"):
                logger.error(f"Runware API returned errors for batch request: {response_data['errors']}")
                # Continue processing even if some images fail
            
            results = response_data.get("data", [])

            ordered_images: list[str | None] = [None] * len(prompts)
            for item in results:
                task_uuid = item.get("taskUUID")
                img_url = item.get("imageURL")
                if task_uuid in uuid_to_index and img_url:
                    ordered_images[uuid_to_index[task_uuid]] = img_url

            successful_images = [url for url in ordered_images if url]

            logger.info(
                f"Successfully generated {len(successful_images)} out of {len(prompts)} images with Runware, order preserved.")
            return successful_images

        except Exception:
            return []

    def generate_images_from_prompts_sync(self, prompts: list[str]) -> list[str]:
        try:
            return asyncio.run(self.generate_images_from_prompts(prompts))
        except RuntimeError:
            logger.warning("Runware sync wrapper hit an active event loop. Returning no images.")
            return []

runware_service = RunwareService()
