import requests
from bs4 import BeautifulSoup
import execjs
import re
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class MangaHere:
    def __init__(self):
        self.name = "MangaHere"
        self.base_url = "http://www.mangahere.cc"
        self.logo = (
            "https://i.pinimg.com/564x/51/08/62/51086247ed16ff8abae2df0bb06448e4.jpg"
        )
        self.class_path = "MANGA.MangaHere"

    def fetch_manga_info(self, manga_id):
        manga_info = {
            "id": manga_id,
            "title": "",
            "description": "",
            "headers": {"Referer": self.base_url},
            "image": "",
            "genres": [],
            "status": "UNKNOWN",
            "rating": None,
            "authors": [],
            "chapters": [],
        }
        try:
            response = requests.get(
                f"{self.base_url}/manga/{manga_id}", headers={"cookie": "isAdult=1"}
            )
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            manga_info["title"] = soup.select_one(
                "span.detail-info-right-title-font"
            ).text.strip()
            manga_info["description"] = soup.select_one(
                "div.detail-info-right > p.fullcontent"
            ).text.strip()
            manga_info["image"] = soup.select_one("div.detail-info-cover > img")["src"]
            manga_info["genres"] = [
                a["title"].strip()
                for a in soup.select("p.detail-info-right-tag-list > a")
            ]
            status_text = soup.select_one(
                "span.detail-info-right-title-tip"
            ).text.strip()
            manga_info["status"] = (
                "ONGOING"
                if status_text == "Ongoing"
                else "COMPLETED" if status_text == "Completed" else "UNKNOWN"
            )
            manga_info["rating"] = float(
                soup.select_one(
                    "span.detail-info-right-title-star > span:last-child"
                ).text.strip()
            )
            manga_info["authors"] = [
                a["title"] for a in soup.select("p.detail-info-right-say > a")
            ]
            print(soup.select("ul.detail-main-list > li"))
            manga_info["chapters"] = [
                {
                    "id": a["href"].split("/manga/")[1].replace(".html", ""),
                    "title": a.select_one("div > p.title3").text.strip(),
                    "releasedDate": a.select_one("div > p.title2").text.strip(),
                }
                for a in soup.select("ul.detail-main-list > li > a")
            ]

            return manga_info
        except Exception as e:
            raise Exception(f"Error fetching manga info:v {str(e)}")
        
    def fetch_chapter_pages(self, chapter_id):
        chapter_pages = []
        url = f"{self.base_url}/manga/{chapter_id}/1.html"
        
        try:
            response = requests.get(url, headers={"cookie": "isAdult=1"})
            response.raise_for_status()
            html = response.text
            soup = BeautifulSoup(html, 'html.parser')

            # Get total pages first
            page_elements = soup.select('select.mangaread-page option')
            if not page_elements:
                page_elements = soup.select('div.pager-list-left a:not([class]), div.pager-list-left span')
            
            if not page_elements:
                raise Exception("Could not determine number of pages")
                
            total_pages = max([
                int(el.text.strip()) 
                for el in page_elements 
                if el.text.strip().isdigit()
            ])
            
            logger.debug(f"Total pages found: {total_pages}")

            # Get chapter ID and key
            chapter_id_match = re.search(r'chapterid\s*=\s*(\d+)', html)
            if not chapter_id_match:
                raise Exception("Could not find chapter ID")
            chapter_num = chapter_id_match.group(1)
            s_key = self.extract_key(html)

            # Fetch all pages
            for page_num in range(1, total_pages + 1):
                page_url = f"{self.base_url}/chapterfun.ashx"
                params = {
                    'cid': chapter_num,
                    'page': page_num,
                    'key': s_key
                }
                headers = {
                    "Referer": url,
                    "X-Requested-With": "XMLHttpRequest",
                    "cookie": "isAdult=1"
                }
                
                response = requests.get(page_url, params=params, headers=headers)
                if not response.text:
                    continue
                    
                # Decode the response
                script = response.text.replace('eval', '')
                try:
                    ctx = execjs.compile(f"function getResult() {{ return {script} }}")
                    decoded_script = ctx.call("getResult")
                    
                    # Extract image URLs
                    base_url_match = re.search(r'pix\s*=\s*["\']([^"\']+)["\']', decoded_script)
                    image_paths_match = re.search(r'pvalue\s*=\s*\[(.*?)\]', decoded_script)
                    
                    if base_url_match and image_paths_match:
                        base_url = base_url_match.group(1)
                        image_paths = [p.strip('"\'') for p in image_paths_match.group(1).split(',')]
                        
                        # Only take the first image from each response
                        if image_paths and image_paths[0]:
                            img_path = image_paths[0]
                            img_url = f"https:{base_url}{img_path}" if not base_url.startswith('http') else f"{base_url}{img_path}"
                            chapter_pages.append({
                                "page": page_num,  # Using actual page number instead of index
                                "img": img_url,
                                "headerForImage": {
                                    "Referer": self.base_url
                                }
                            })
                except Exception as e:
                    logger.error(f"Error processing page {page_num}: {str(e)}")
                    continue

            if not chapter_pages:
                raise Exception("No pages found")
                
            # Ensure pages are in correct order
            chapter_pages.sort(key=lambda x: x["page"])
            logger.info(f"Successfully extracted {len(chapter_pages)} pages")
            return chapter_pages
            
        except Exception as e:
            logger.exception(f"Error fetching chapter pages: {str(e)}")
            raise Exception(f"Error fetching chapter pages: {str(e)}")
    
    def search(self, query, page=1):
        search_res = {"currentPage": page, "results": [], "hasNextPage": False}
        try:
            response = requests.get(f"{self.base_url}/search?title={query}&page={page}")
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            with open("search.html", "w",encoding='utf-8') as f:
                f.write(response.text)
            search_res["hasNextPage"] = (
                soup.select_one("div.pager-list-left > a.active + a").text.strip()
                != ">"
            )
            print(soup.select("div.container > div > div > ul > li"))
            search_res["results"] = [
                {
                    "id": a.select_one("a")["href"].split("/")[2],
                    "title": a.select_one("p.manga-list-4-item-title > a").text.strip(),
                    "headerForImage": {"Referer": self.base_url},
                    "image": a.select_one("a > img")["src"],
                    "description": a.select("p")[-1].text.strip(),
                    "status": (
                        "ONGOING"
                        if a.select_one(
                            "p.manga-list-4-show-tag-list-2 > a"
                        ).text.strip()
                        == "Ongoing"
                        else (
                            "COMPLETED"
                            if a.select_one(
                                "p.manga-list-4-show-tag-list-2 > a"
                            ).text.strip()
                            == "Completed"
                            else "UNKNOWN"
                        )
                    ),
                }
                for a in soup.select("div.container > div > div > ul > li")
            ]

            return search_res
        except Exception as e:
            raise Exception(f"Error searching manga: {str(e)}")

    def extract_key(self, html: str) -> str:
        try:
            start_idx = html.find('eval(function(p,a,c,k,e,d)')
            end_idx = html.find('</script>', start_idx)
            script = html[start_idx:end_idx].replace('eval', '')
            
            ctx = execjs.compile(f"function getResult() {{ return {script} }}")
            decoded_script = ctx.call("getResult")
            
            start_key = decoded_script.find("'")
            end_key = decoded_script.find(';')
            key_str = decoded_script[start_key:end_key]
            
            ctx = execjs.compile(f"function getKey() {{ return {key_str} }}")
            return ctx.call("getKey")
        except Exception as e:
            logger.error(f"Error extracting key: {str(e)}")
            return ''

