from datetime import datetime

from augurai.models import RawItem
from augurai.sources.base import SourceContext, SourceError

URL = "https://registry.modelcontextprotocol.io/v0/servers"
META_KEY = "io.modelcontextprotocol.registry/official"
MAX_PAGES = 3


def _published(row: dict) -> datetime | None:
    stamp = (row.get("_meta") or {}).get(META_KEY, {}).get("publishedAt")
    if not stamp:
        return None
    return datetime.fromisoformat(stamp)


def _url(server: dict) -> str:
    repo = (server.get("repository") or {}).get("url")
    if repo:
        return repo
    remotes = server.get("remotes") or []
    if remotes and remotes[0].get("url"):
        return remotes[0]["url"]
    return f"https://registry.modelcontextprotocol.io/v0/servers?search={server['name']}"


class McpRegistrySource:
    name = "mcp-registry"
    required_env: tuple[str, ...] = ()

    def fetch(self, ctx: SourceContext) -> list[RawItem]:
        latest: dict[str, dict] = {}
        cursor: str | None = None
        for _ in range(MAX_PAGES):
            params: dict[str, str | int] = {"limit": 100}
            if cursor:
                params["cursor"] = cursor
            response = ctx.http.get(URL, params=params)
            response.raise_for_status()
            body = response.json()
            rows = body.get("servers")
            if not isinstance(rows, list):
                raise SourceError("unexpected payload: no servers list")
            for row in rows:
                name = row["server"]["name"]
                current = latest.get(name)
                if current is None or (_published(row) or datetime.min.astimezone()) >= (
                    _published(current) or datetime.min.astimezone()
                ):
                    latest[name] = row
            cursor = (body.get("metadata") or {}).get("nextCursor")
            if not cursor:
                break
        items: list[RawItem] = []
        for name, row in latest.items():
            server = row["server"]
            url = _url(server)
            items.append(
                RawItem(
                    id=RawItem.make_id(f"mcp:{name}"),
                    source=self.name,
                    kind="mcp",
                    title=server.get("title") or name,
                    url=url,
                    author=name.split("/")[0],
                    published=_published(row),
                    extra={
                        "server_name": name,
                        "owner": name.split("/")[0],
                        "description": server.get("description", ""),
                        "version": server.get("version"),
                    },
                )
            )
        return items
