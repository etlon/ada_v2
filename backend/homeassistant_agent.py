import os
import aiohttp
from dotenv import load_dotenv

load_dotenv()


class HomeAssistantAgent:
    def __init__(self):
        self.base_url = os.getenv("HA_URL", "").rstrip("/")
        self.token = os.getenv("HA_TOKEN", "")
        self.entities = {}  # Cache: entity_id -> state dict

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    @property
    def configured(self):
        return bool(self.base_url and self.token)

    async def _request(self, method, path, json=None):
        """Make an authenticated request to the HA API."""
        if not self.configured:
            return {"error": "Home Assistant not configured. Set HA_URL and HA_TOKEN in .env"}
        url = f"{self.base_url}/api{path}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(method, url, headers=self._headers(), json=json, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        text = await resp.text()
                        return {"error": f"HTTP {resp.status}: {text}"}
        except aiohttp.ClientError as e:
            return {"error": f"Connection error: {e}"}

    async def get_states(self):
        """Fetch all entity states and cache them."""
        result = await self._request("GET", "/states")
        if isinstance(result, list):
            self.entities = {e["entity_id"]: e for e in result}
            return result
        return result

    async def list_entities(self, domain=None):
        """List entities, optionally filtered by domain (light, cover, switch, etc.)."""
        if not self.entities:
            await self.get_states()

        if not domain:
            # No domain filter — return a domain summary instead of all entities
            domains = {}
            for eid in self.entities:
                d = eid.split(".")[0]
                domains[d] = domains.get(d, 0) + 1
            return {"summary": domains}

        entities = []
        for eid, state in self.entities.items():
            if not eid.startswith(f"{domain}."):
                continue
            entities.append({
                "entity_id": eid,
                "state": state.get("state"),
                "friendly_name": state.get("attributes", {}).get("friendly_name", eid),
            })
        return entities

    async def get_entity_state(self, entity_id):
        """Get the current state of a specific entity."""
        result = await self._request("GET", f"/states/{entity_id}")
        if "error" not in result:
            self.entities[entity_id] = result
            return {
                "entity_id": entity_id,
                "state": result.get("state"),
                "friendly_name": result.get("attributes", {}).get("friendly_name", entity_id),
                "attributes": result.get("attributes", {}),
            }
        return result

    async def call_service(self, domain, service, entity_id, **kwargs):
        """Call a Home Assistant service on an entity."""
        data = {"entity_id": entity_id}
        data.update(kwargs)
        result = await self._request("POST", f"/services/{domain}/{service}", json=data)
        if isinstance(result, list):
            # HA returns a list of changed states on success
            for s in result:
                self.entities[s["entity_id"]] = s
            return {"success": True, "entity_id": entity_id, "service": f"{domain}.{service}"}
        return result

    async def turn_on(self, entity_id, **kwargs):
        domain = entity_id.split(".")[0]
        return await self.call_service(domain, "turn_on", entity_id, **kwargs)

    async def turn_off(self, entity_id, **kwargs):
        domain = entity_id.split(".")[0]
        return await self.call_service(domain, "turn_off", entity_id, **kwargs)

    async def toggle(self, entity_id):
        domain = entity_id.split(".")[0]
        return await self.call_service(domain, "toggle", entity_id)

    async def set_cover_position(self, entity_id, position):
        return await self.call_service("cover", "set_cover_position", entity_id, position=position)

    async def open_cover(self, entity_id):
        return await self.call_service("cover", "open_cover", entity_id)

    async def close_cover(self, entity_id):
        return await self.call_service("cover", "close_cover", entity_id)

    def resolve_entity(self, name_or_id):
        """Resolve a friendly name or entity_id to an entity_id."""
        # Direct match
        if name_or_id in self.entities:
            return name_or_id

        # Search by friendly name (case-insensitive)
        name_lower = name_or_id.lower()
        for eid, state in self.entities.items():
            friendly = state.get("attributes", {}).get("friendly_name", "")
            if friendly.lower() == name_lower:
                return eid
            if name_lower in friendly.lower():
                return eid

        return None
