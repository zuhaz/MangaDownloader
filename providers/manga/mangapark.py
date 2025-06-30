import requests
from bs4 import BeautifulSoup
import json
import re

class Mangapark:
    name = "Mangapark"
    base_url = "https://mangapark.net"
    logo = "https://raw.githubusercontent.com/tachiyomiorg/tachiyomi-extensions/repo/icon/tachiyomi-en.mangapark-v1.3.23.png"
    class_path = "MANGA.Mangapark"

    def __init__(self):
        self.client = requests.Session()

    def fetch_manga_info(self, manga_id: str, *args) -> dict:
        if not manga_id:
            raise ValueError("Manga ID cannot be empty")
        
        manga_info = {"id": manga_id, "title": ""}
        url = f"{self.base_url}/title/{manga_id}"

        try:
            response = self.client.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            with open("manga_info.html", "w", encoding="utf-8") as f:
                f.write(soup.prettify())
            manga_info["title"] = soup.select_one("h3.text-lg.font-bold > a").text if soup.select_one("h3.text-lg.font-bold > a") else "Unknown Title"
            manga_info["image"] = soup.select_one("img.w-full.not-prose.shadow-md")["src"] if soup.select_one("img.w-full.not-prose.shadow-md") else None
            # Extract description - simplest direct approach
            description_elem = soup.select_one("div.limit-html-p")
            if description_elem:
                manga_info["description"] = description_elem.text.strip()
            else:
                manga_info["description"] = "No description available"
            
            # Extract authors
            authors = []
            author_elements = soup.select("div.mt-2.text-sm.md\\:text-base.opacity-80 a")
            for author_elem in author_elements:
                authors.append(author_elem.text.strip())
            manga_info["authors"] = authors
            
            manga_info["genres"] = [
                genre.text
                for genre in soup.select(
                    "div.flex.items-center.flex-wrap span span:nth-child(1)"
                )
            ]
            manga_info["status"] = soup.select("span.font-bold.uppercase.text-success")[
                0
            ].text if soup.select("span.font-bold.uppercase.text-success") else soup.select_one(
                "div.space-y-2 span.font-bold.uppercase.text-warning"
            ).text.strip() 
            
            # Extract rating information
            manga_info["rating"] = {
                "score": None,
                "votes": None,
                "distribution": {}
            }
            
            # Try to find the rating score directly
            rating_elem = soup.select_one("span.font-bold.opacity-80.whitespace-nowrap")
            if rating_elem:
                rating_text = rating_elem.text.strip()
                if rating_text and rating_text[0].isdigit():
                    try:
                        manga_info["rating"]["score"] = float(rating_text)
                    except ValueError:
                        pass
            
            # Extract vote count
            votes_elem = soup.select_one("div.text-sm.opacity-80.whitespace-nowrap")
            if votes_elem:
                votes_text = votes_elem.text.strip()
                if votes_text:
                    votes_count = votes_text.split()[0]
                    manga_info["rating"]["votes"] = votes_count
            
            # Extract rating distribution
            rating_bars = soup.select("div.flex.items-center.text-xs.md\\:text-sm.space-x-2")
            for bar in rating_bars:
                stars_elem = bar.select_one("div.flex.items-center.font-mono.font-bold.opacity-80 span")
                if stars_elem:
                    stars = stars_elem.text.strip()
                    percentage_elem = bar.select_one("span.font-mono.opacity-80")
                    if percentage_elem:
                        percentage = percentage_elem.text.strip()
                        manga_info["rating"]["distribution"][stars] = percentage
            
            # If we couldn't find the score directly, try to calculate it from the width
            if manga_info["rating"]["score"] is None:
                score_width_elem = soup.select_one("div.absolute.top-0.bottom-0.left-0.overflow-hidden")
                if score_width_elem and "style" in score_width_elem.attrs:
                    style = score_width_elem["style"]
                    width_match = re.search(r'width:(\d+\.?\d*)%', style)
                    if width_match:
                        width_percentage = float(width_match.group(1))
                        # Calculate score out of 5
                        manga_info["rating"]["score"] = round((width_percentage / 100) * 5, 2)
            
            # Extract view statistics
            views_section = soup.select_one("div.mt-5.space-y-3:has(b.text-lg.font-bold:contains('Views'))")
            if views_section:
                views_data = {}
                view_spans = views_section.select("span.whitespace-nowrap")
                for span in view_spans:
                    text = span.text.strip()
                    if ":" in text:
                        key, value = text.split(":", 1)
                        views_data[key.strip()] = value.strip()
                    elif "Total" in text:
                        views_data["Total"] = text.replace("Total:", "").strip()
                    else:
                        # Handle format like "360 days: 207.6K"
                        parts = text.split()
                        if len(parts) >= 2 and parts[-1].isalpha() or parts[-1][-1].isalpha():
                            key = ' '.join(parts[:-1])
                            value = parts[-1]
                            views_data[key] = value
                manga_info["views"] = views_data
            
            # Extract reader statistics
            readers_section = soup.select_one("div.mt-5.space-y-3:has(b.text-lg.font-bold:contains('Readers'))")
            if readers_section:
                readers_data = {}
                reader_spans = readers_section.select("span.whitespace-nowrap")
                for span in reader_spans:
                    text = span.text.strip()
                    if len(text.split()) > 1:
                        key = ' '.join(text.split()[1:])  # Get everything after the first word
                        value = text.split()[0]
                        readers_data[key] = value
                manga_info["readers"] = readers_data
            
            # Extract language information
            lang_elem = soup.select_one("div.whitespace-nowrap.overflow-hidden")
            if lang_elem:
                lang_text = lang_elem.text.strip()
                # Clean up language info by removing emoji codes
                lang_text = re.sub(r'\uD83C[\uDDE6-\uDDFF]\uD83C[\uDDE6-\uDDFF]', '', lang_text)
                lang_text = re.sub(r'Tr From', 'Translated From', lang_text)
                manga_info["language"] = lang_text.strip()
            
            # Extract publication info
            pub_elem = soup.select_one("div:has(span.font-bold.uppercase.text-success)")
            if pub_elem:
                pub_text = pub_elem.text.strip()
                # Clean up the publication status text
                if ":" in pub_text:
                    pub_text = pub_text.split(":", 1)[1].strip()
                # Further clean up by removing any content after the status
                if pub_text:
                    status_words = ["Ongoing", "Completed", "Cancelled", "Hiatus"]
                    for status in status_words:
                        if status in pub_text:
                            pub_text = status
                            break
                manga_info["publication_status"] = pub_text
            
            chapters = []
            for chapter in soup.select(".px-2.py-2"):
                chapter_id = chapter.select_one("div.space-x-1 a")["href"].replace(
                    "/title/", ""
                )
                title = (
                    chapter.select_one("div.space-x-1 a").text
                    + ""
                    + chapter.select_one("div.space-x-1 span").text
                    if chapter.select_one("div.space-x-1 span").text.startswith(": ")
                    else chapter.select_one("div.space-x-1 a").text
                )
                release_data_element = (
                    chapter.select("div")[1].select("div")[-1].select_one("time")
                )
                release_date = release_data_element.select_one("span").text
                release_date_in_unix = release_data_element["data-time"]

                chapters.append(
                    {
                        "id": chapter_id,
                        "title": title,
                        "releaseDate": release_date,
                        "releaseDateUnix": release_date_in_unix,
                    }
                )

            manga_info["chapters"] = chapters

            return manga_info

        except Exception as e:
            raise Exception(f"Error fetching manga info: {str(e)}")

    def fetch_chapter_pages(self, chapter_id: str) -> list:
        if not chapter_id:
            raise ValueError("Chapter ID cannot be empty")
        
        url = f"{self.base_url}/title/{chapter_id}"
        try:
            response = self.client.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Find all script tags
            scripts = soup.find_all('script')
            pages = []
            page_number = 1
            
            # Look for image URLs in all script contents
            for script in scripts:
                if not script.string:
                    continue
                    
                # Try to parse as JSON if it looks like JSON data
                if script.get('type') == 'qwik/json' or script.string.strip().startswith('{'):
                    try:
                        data = json.loads(script.string)
                        # Recursively search for image URLs in the JSON data
                        def extract_images(obj):
                            if isinstance(obj, str) and obj.startswith('https://') and ('/media/' in obj or '/i0.wp.com/' in obj):
                                pages.append({
                                    "page": len(pages) + 1,
                                    "img": obj
                                })
                            elif isinstance(obj, dict):
                                for value in obj.values():
                                    extract_images(value)
                            elif isinstance(obj, list):
                                for item in obj:
                                    extract_images(item)
                                    
                        extract_images(data)
                    except json.JSONDecodeError:
                        continue
                
                # Also look for direct image URLs in script content
                if isinstance(script.string, str):
                    urls = re.findall(r'https://[^"\'\s]+?(?:/media/|/i0\.wp\.com/).+?\.(?:jpg|jpeg|png|gif|webp)', script.string)
                    for url in urls:
                        if url not in [p["img"] for p in pages]:
                            pages.append({
                                "page": len(pages) + 1,
                                "img": url
                            })
            
            if not pages:
                # Fallback: Look for image tags directly
                images = soup.select('img[src*="/media/"], img[src*="/i0.wp.com/"]')
                for img in images:
                    src = img.get('src')
                    if src and src not in [p["img"] for p in pages]:
                        pages.append({
                            "page": len(pages) + 1,
                            "img": src
                        })
            
            if not pages:
                raise Exception("No pages found")
                
            return sorted(pages, key=lambda x: x["page"])

        except Exception as e:
            raise Exception(f"Error fetching chapter pages: {str(e)}")

    def search(self, query: str, page: int = 1, *args) -> dict:
        if not query:
            raise ValueError("Search query cannot be empty")
        if page < 1:
            raise ValueError("Page number must be greater than 0")
        
        # URL encode the query parameter
        query = requests.utils.quote(query)
        url = f"{self.base_url}/search?word={query}&page={page}"

        try:
            response = self.client.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            results = []
            for item in soup.select("div.flex.border-b.border-b-base-200"):
                title_link = item.select_one("h3.font-bold a")
                if not title_link:
                    continue
                    
                manga_id = title_link["href"].replace("/title/", "")
                title = title_link.text.strip()
                
                # Get image URL
                image = item.select_one("img")
                image_url = image["src"] if image else None
                
                # Get additional info
                genres = [
                    span.text.strip() 
                    for span in item.select("div.flex.flex-wrap.text-xs span.whitespace-nowrap")
                    if span.text.strip()
                ]
                
                results.append({
                    "id": manga_id,
                    "title": title,
                    "image": image_url,
                    "genres": genres
                })

            return {
                "results": results,
                "hasNextPage": bool(soup.select_one("a[href*='page=" + str(page + 1) + "']"))
            }

        except Exception as e:
            raise Exception(f"Error searching manga: {str(e)}")
            
    def fetch_home_page(self, *args) -> BeautifulSoup:
        """
        Fetches the home page HTML and returns the BeautifulSoup object
        """
        url = f"{self.base_url}/"
        try:
            response = self.client.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            return soup
        except Exception as e:
            raise Exception(f"Error fetching home page: {str(e)}")
            

    
    def get_latest_releases(self) -> list:
        """
        Extracts latest manga releases from the home page
        """
        soup = self.fetch_home_page()
            
        latest_releases = []
        
        # Find the "Latest Releases" section
        latest_section = None
        for section in soup.find_all("div", class_="space-y-5"):
            title_elem = section.find("b", class_="text-base-content")
            if title_elem and "Latest Releases" in title_elem.text:
                latest_section = section
                break
        
        if not latest_section:
            return latest_releases
            
        # Extract manga items
        manga_items = latest_section.select("div.flex.border-b.border-b-base-200")
        
        for item in manga_items:
            try:
                # Extract manga ID and title
                title_link = item.select_one("h3.font-bold a")
                if not title_link:
                    continue
                    
                manga_id = title_link["href"].replace("/title/", "")
                title = title_link.text.strip()
                
                # Extract image
                image = item.select_one("img")
                image_url = image["src"] if image else None
                
                # Extract latest chapter
                chapter_link = item.select_one("div.flex.flex-nowrap.justify-between a")
                latest_chapter = {
                    "id": chapter_link["href"].replace("/title/", "") if chapter_link else None,
                    "title": chapter_link.text.strip() if chapter_link else None
                }
                
                # Extract release date
                time_elem = item.select_one("time")
                release_date = time_elem.select_one("span").text.strip() if time_elem and time_elem.select_one("span") else None
                release_date_unix = time_elem["data-time"] if time_elem and "data-time" in time_elem.attrs else None
                
                # Extract genres
                genres = [
                    span.text.strip() 
                    for span in item.select("div.flex.flex-wrap.text-xs span.whitespace-nowrap")
                    if span.text.strip()
                ]
                
                # Extract rating if available
                rating_elem = item.select_one("span.flex.flex-nowrap.items-center.text-yellow-500 span.font-bold")
                rating = rating_elem.text.strip() if rating_elem else None
                
                manga_data = {
                    "id": manga_id,
                    "title": title,
                    "image": image_url,
                    "latest_chapter": latest_chapter,
                    "release_date": release_date,
                    "release_date_unix": release_date_unix,
                    "genres": genres,
                    "rating": rating
                }
                
                latest_releases.append(manga_data)
                
            except Exception as e:
                # Skip items that can't be parsed properly
                continue
                
        return latest_releases
    
    def get_genres(self) -> list:
        """
        Extracts available genres from the home page
        """
        soup = self.fetch_home_page()
            
        genres = []
        
        # Find the genres section
        genres_section = None
        for section in soup.find_all("div", class_="w-full border border-base-200"):
            title_elem = section.find("b")
            if title_elem and "Genres" in title_elem.text:
                genres_section = section
                break
        
        if not genres_section:
            # Try to find genres from manga items
            genre_elements = soup.select("div.flex.flex-wrap.text-xs span.whitespace-nowrap")
            genres = list(set([elem.text.strip() for elem in genre_elements if elem.text.strip()]))
            return genres
            
        # If we found a dedicated genres section, extract from there
        genre_links = genres_section.select("a.link-hover")
        genres = [link.text.strip() for link in genre_links if link.text.strip()]
        
        return genres
    