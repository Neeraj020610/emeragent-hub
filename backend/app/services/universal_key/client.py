import time
import uuid
from typing import Any, Dict, List, Optional
import httpx

from app.schemas.universal_key import UniversalKeyValidateResponse


class EmergentProxyClient:
    """
    Official Emergent LiteLLM-compatible proxy client.
    Interacts with Emergent's OpenAI-compatible inference proxy:
    - Base URL: configured per account or default https://proxy.emergent.ai
    - Authorization: Bearer <EMERGENT_UNIVERSAL_KEY>
    - Endpoints: /v1/models, /v1/chat/completions
    """

    def __init__(self, default_base_url: str = "https://proxy.emergent.ai", timeout_seconds: float = 12.0):
        self.default_base_url = default_base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def _clean_base_url(self, raw_url: Optional[str]) -> str:
        url = (raw_url or self.default_base_url).strip().rstrip("/")
        if url.endswith("/v1"):
            url = url[:-3]
        return url

    async def validate_key(self, api_key: str, proxy_base_url: Optional[str] = None) -> UniversalKeyValidateResponse:
        """
        Safely validates a Universal API Key against the LiteLLM proxy using a lightweight test.
        Never persists or logs the raw API key.
        """
        base_url = self._clean_base_url(proxy_base_url)
        start_time = time.time()

        # Offline/Simulated test keys for deterministic testing without live proxy dependency
        clean_key = api_key.strip()
        if clean_key.startswith("emg_test_"):
            latency = int((time.time() - start_time) * 1000) + 12
            if "invalid" in clean_key:
                return UniversalKeyValidateResponse(
                    is_valid=False,
                    status_code=401,
                    message="Invalid Emergent Universal API Key (401 Unauthorized)",
                    latency_ms=latency,
                )
            if "credits" in clean_key:
                return UniversalKeyValidateResponse(
                    is_valid=False,
                    status_code=402,
                    message="Insufficient Emergent credits (402 Payment Required)",
                    latency_ms=latency,
                )
            if "forbidden" in clean_key or "ip_restricted" in clean_key:
                return UniversalKeyValidateResponse(
                    is_valid=False,
                    status_code=403,
                    message="IP restriction or access forbidden (403 Forbidden)",
                    latency_ms=latency,
                )
            if "ratelimit" in clean_key:
                return UniversalKeyValidateResponse(
                    is_valid=False,
                    status_code=429,
                    message="Rate limit reached on Emergent proxy (429 Too Many Requests)",
                    latency_ms=latency,
                )
            # Default valid test key
            return UniversalKeyValidateResponse(
                is_valid=True,
                status_code=200,
                message="Universal API Key successfully validated against Emergent proxy.",
                latency_ms=latency,
                models_available=["gpt-4o", "gpt-4o-mini", "claude-3-5-sonnet", "gemini-1.5-pro"],
            )

        # Real proxy call
        headers = {
            "Authorization": f"Bearer {clean_key}",
            "Content-Type": "application/json",
            "User-Agent": "EmergentCentralHub/1.0",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                # First try models endpoint
                resp = await client.get(f"{base_url}/v1/models", headers=headers)
                latency = int((time.time() - start_time) * 1000)

                if resp.status_code in (200, 201):
                    models_data = []
                    try:
                        data = resp.json()
                        if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
                            models_data = [m.get("id") for m in data["data"] if isinstance(m, dict) and "id" in m]
                    except Exception:
                        pass
                    return UniversalKeyValidateResponse(
                        is_valid=True,
                        status_code=resp.status_code,
                        message="Universal API Key successfully validated against Emergent proxy.",
                        latency_ms=latency,
                        models_available=models_data or ["gpt-4o-mini", "claude-3-5-sonnet"],
                    )
                
                # If models is 404 or unsupported, fallback to small 1-token test prompt
                if resp.status_code == 404:
                    test_payload = {
                        "model": "gpt-4o-mini",
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 1,
                    }
                    comp_resp = await client.post(f"{base_url}/v1/chat/completions", headers=headers, json=test_payload)
                    latency = int((time.time() - start_time) * 1000)
                    if comp_resp.status_code in (200, 201):
                        return UniversalKeyValidateResponse(
                            is_valid=True,
                            status_code=comp_resp.status_code,
                            message="Universal API Key successfully validated against Emergent proxy.",
                            latency_ms=latency,
                        )
                    resp = comp_resp

                # Specific HTTP status handling
                if resp.status_code == 401:
                    return UniversalKeyValidateResponse(
                        is_valid=False,
                        status_code=401,
                        message="Authentication failed: Invalid Emergent Universal API Key.",
                        latency_ms=latency,
                    )
                if resp.status_code == 402:
                    return UniversalKeyValidateResponse(
                        is_valid=False,
                        status_code=402,
                        message="Insufficient Emergent credits on account (402).",
                        latency_ms=latency,
                    )
                if resp.status_code == 403:
                    return UniversalKeyValidateResponse(
                        is_valid=False,
                        status_code=403,
                        message="Access denied: Check IP restrictions or workspace permissions (403).",
                        latency_ms=latency,
                    )
                if resp.status_code == 429:
                    return UniversalKeyValidateResponse(
                        is_valid=False,
                        status_code=429,
                        message="Rate limit reached on Emergent proxy (429).",
                        latency_ms=latency,
                    )

                return UniversalKeyValidateResponse(
                    is_valid=False,
                    status_code=resp.status_code,
                    message=f"Emergent proxy returned status {resp.status_code}: {resp.text[:200]}",
                    latency_ms=latency,
                )

        except httpx.ConnectTimeout:
            latency = int((time.time() - start_time) * 1000)
            return UniversalKeyValidateResponse(
                is_valid=False,
                status_code=504,
                message=f"Connection timed out reaching Emergent proxy at {base_url}",
                latency_ms=latency,
            )
        except httpx.ConnectError:
            latency = int((time.time() - start_time) * 1000)
            return UniversalKeyValidateResponse(
                is_valid=False,
                status_code=502,
                message=f"Network error: Unable to connect to Emergent proxy at {base_url}",
                latency_ms=latency,
            )
        except Exception as ex:
            latency = int((time.time() - start_time) * 1000)
            return UniversalKeyValidateResponse(
                is_valid=False,
                status_code=500,
                message=f"Proxy error: {str(ex)}",
                latency_ms=latency,
            )

    async def execute_chat(
        self,
        api_key: str,
        proxy_base_url: Optional[str],
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 500,
    ) -> Dict[str, Any]:
        """
        Executes an inference request through the LiteLLM proxy and returns parsed usage and content.
        """
        base_url = self._clean_base_url(proxy_base_url)
        start_time = time.time()
        clean_key = api_key.strip()

        # Simulated response for test keys
        if clean_key.startswith("emg_test_"):
            latency = int((time.time() - start_time) * 1000) + 45
            req_id = f"req-{uuid.uuid4().hex[:12]}"
            if "invalid" in clean_key:
                raise httpx.HTTPStatusError("Invalid API Key", request=None, response=httpx.Response(401))
            if "credits" in clean_key:
                raise httpx.HTTPStatusError("Insufficient credits", request=None, response=httpx.Response(402))
            
            prompt_tokens = sum(len(m.get("content", "").split()) for m in messages) + 10
            completion_tokens = 25
            total_tokens = prompt_tokens + completion_tokens
            cost = round(total_tokens * 0.0000015, 6)

            return {
                "request_id": req_id,
                "model": model,
                "content": f"[Emergent Proxy Response for {model}]: Request processed successfully via Universal API Key.",
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "cost": cost,
                "duration_ms": latency,
                "status": "SUCCESS",
            }

        headers = {
            "Authorization": f"Bearer {clean_key}",
            "Content-Type": "application/json",
            "User-Agent": "EmergentCentralHub/1.0",
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds * 2) as client:
            resp = await client.post(f"{base_url}/v1/chat/completions", headers=headers, json=payload)
            latency = int((time.time() - start_time) * 1000)

            if resp.status_code not in (200, 201):
                resp.raise_for_status()

            data = resp.json()
            req_id = data.get("id") or f"req-{uuid.uuid4().hex[:12]}"
            content = ""
            if "choices" in data and len(data["choices"]) > 0:
                content = data["choices"][0].get("message", {}).get("content", "")

            usage = data.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)
            
            # LiteLLM cost header or body if present
            cost = None
            if "cost" in data:
                try:
                    cost = float(data["cost"])
                except Exception:
                    pass
            elif "x-litellm-response-cost" in resp.headers:
                try:
                    cost = float(resp.headers["x-litellm-response-cost"])
                except Exception:
                    pass

            return {
                "request_id": req_id,
                "model": data.get("model", model),
                "content": content,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "cost": cost,
                "duration_ms": latency,
                "status": "SUCCESS",
            }

