import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional


class MangaPill:
    def __init__(self):
        self.name = "MangaPill"
        self.base_url = "https://mangapill.com"
        self.logo = "https://scontent-man2-1.xx.fbcdn.net/v/t39.30808-6/300819578_399903675586699_2357525969702348451_n.png?_nc_cat=100&ccb=1-7&_nc_sid=09cbfe&_nc_ohc=Md2cQ4wRNWwAX-_U0fz&_nc_ht=scontent-man2-1.xx&oh=00_AfCJjAYDk9bsndz8uyNG-GdFIYcPvdIzbHnetHGzf1pVSw&oe=63BDD131"
        self.class_path = "MANGA.MangaPill"
        self.headers = {
            "User-Agent": "Mozilla/5.0",
        }

    def _get_request(self, url: str) -> str:
        response = requests.get(f"{self.base_url}{url}", headers=self.headers)
        response.raise_for_status()
        return response.text

    def search(self, query: str) -> Dict:
        try:
            query = requests.utils.quote(query)
            html_data = self._get_request(f"/search?q={query}")
            soup = BeautifulSoup(html_data, "html.parser")

            results = []
            for el in soup.select("div.container div.my-3.justify-end > div"):
                link = el.select_one("a")
                img = el.select_one("a img")
                results.append(
                    {
                        "id": link["href"].split("/manga/")[1] if link else "",
                        "title": (
                            el.select_one("div > a > div").text.strip()
                            if el.select_one("div > a > div")
                            else ""
                        ),
                        "image": img["data-src"] if img else "",
                        "headerForImage": {
                            "Referer": self.base_url
                        },
                    }
                )

            return {"results": results}
        except requests.HTTPError as e:
            raise ValueError(f"HTTP Error: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error: {str(e)}")

    def fetch_manga_info(self, manga_id: str) -> Dict:
        manga_info = {
            "id": manga_id,
            "title": "",
        }
        try:
            html_data = self._get_request(f"/manga/{manga_id}")
            soup = BeautifulSoup(html_data, "html.parser")

            manga_info["title"] = soup.select_one(
                "div.container div.my-3 div.flex-col div.mb-3 h1"
            ).text.strip()
            
            # Get cover image
            cover_img = soup.select_one("div.container div.my-3 div.flex-row img")
            if cover_img and cover_img.has_attr("data-src"):
                manga_info["cover"] = cover_img["data-src"]
            elif cover_img and cover_img.has_attr("src"):
                manga_info["cover"] = cover_img["src"]
                
            manga_info["description"] = " ".join(
                soup.select_one(
                    "p.text-sm.text--secondary"
                ).text.split("\n")
            ).strip()
            manga_info["releaseDate"] = (
                soup.select_one(
                    'div.grid.grid-cols-1.gap-3.mb-3 div:nth-child(3) div'
                ).text.strip()
            )
            manga_info["genres"] = [
                genre.strip()
                for genre in soup.select_one(
                    'div.container div.my-3 div.flex-col div.mb-3:contains("Genres")'
                ).text.split("\n")
                if genre.strip() and genre != "Genres"
            ]

            manga_info["chapters"] = [
                {
                    "id": el["href"].split("/chapters/")[1] if el else "",
                    "title": el.text.strip(),
                    "chapter": (
                        el.text.split("Chapter ")[1] if "Chapter " in el.text else ""
                    ),
                }
                for el in soup.select(
                    "div.container div.border-border div#chapters div.grid-cols-1 a"
                )
            ]

            return manga_info
        except requests.HTTPError as e:
            raise ValueError(f"HTTP Error: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error: {str(e)}")

    def fetch_chapter_pages(self, chapter_id: str) -> List[Dict]:
        try:
            html_data = self._get_request(f"/chapters/{chapter_id}")
            soup = BeautifulSoup(html_data, "html.parser")

            pages = [
                {
                    "img": el.select_one("div picture img")["data-src"],
                    "page": (
                            el.select_one("div[data-summary] > div").text.split(
                                "page "
                            )[1].split("/")[0]
                        if el.select_one("div[data-summary] > div")
                        else 0
                    ),
                    "headerForImage": {
                        "Referer": self.base_url
                    },
                }
                for el in soup.select("chapter-page")
            ]

            return pages
        except requests.HTTPError as e:
            raise ValueError(f"HTTP Error: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error: {str(e)}")

