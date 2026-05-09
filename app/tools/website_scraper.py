from bs4 import BeautifulSoup
import httpx


class WebsiteScraper:
    async def scrape(self, url: str | None) -> dict:
        if not url:
            return {"available": False, "summary": "No website supplied."}
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            title = soup.title.string.strip() if soup.title and soup.title.string else ""
            description = ""
            meta = soup.find("meta", attrs={"name": "description"})
            if meta and meta.get("content"):
                description = str(meta["content"]).strip()
            headings = [h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2"])[:8]]
            return {
                "available": True,
                "title": title,
                "description": description,
                "headings": headings,
                "summary": " ".join([title, description, *headings])[:1800],
            }
        except Exception as exc:
            return {"available": False, "summary": f"Website scrape failed: {exc}"}
