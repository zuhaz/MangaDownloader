import tkinter as tk
from tkinter import filedialog, ttk
import customtkinter
import requests
import os
import time
import threading
from PIL import Image, ImageDraw
import shutil
from io import BytesIO
import urllib.request
import subprocess
import sys
from providers.manga.mangapill import MangaPill
from providers.manga.mangapark import Mangapark
from providers.manga.mangahere import MangaHere

total_chapters_cache = {}
PROVIDERS = {}
last_downloaded_file = None
last_downloaded_dir = None

# Initialize the root window
root = customtkinter.CTk()
root.title("Manga Downloader powered by Mangafit")
customtkinter.set_appearance_mode("dark") 
customtkinter.set_default_color_theme("blue")
root.geometry("1100x800")
root.minsize(1000, 750)

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller exe"""
    try:
        base_path = sys._MEIPASS  # when bundled by PyInstaller
    except Exception:
        base_path = os.path.abspath(".")  # when running normally
    return os.path.join(base_path, relative_path)


try:
    # Set custom icon for the application window
    icon_path = resource_path("assets/logo.ico")  # Use .ico format for Windows
    root.iconbitmap(icon_path)
except Exception as e:
    print(f"Could not load icon: {str(e)}")

# Modern color scheme
COLORS = {
    "bg_primary": "#1A1A1A",
    "bg_secondary": "#222222",
    "bg_tertiary": "#2B2B2B",
    "accent": "#4F6BFF",  # Modern blue accent
    "accent_hover": "#3A56E8",
    "text_primary": "#FFFFFF",
    "text_secondary": "#DDDDDD",
    "text_tertiary": "#AAAAAA",
    "error": "#FF5252",
    "success": "#4CAF50"
}

# Available formats for download (will add more)
formats = ['.cbz', '.pdf', '.png'] 

# Function to filter out illegal characters from file names
def filter_path(path):
    illegal_chars = ["\\", "/", ":", "*", "?", "\"", "<", ">", "|"]
    for char in illegal_chars:
        path = path.replace(char, "")
    return path

# Function to download manga chapter images
def download_chapter_images(chapter_id, provider_name, progress_var, status_label, manga_title=""):
    try:
        provider = PROVIDERS[provider_name]
        
        # Create temp directory if it doesn't exist
        temp_dir = os.path.join("temp", f"{filter_path(manga_title)}_Chapter_{chapter_id}")
        if not os.path.exists("temp"):
            os.makedirs("temp")
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
        
        # Get chapter pages
        pages = provider.fetch_chapter_pages(chapter_id)
        total_pages = len(pages)
        
        status_label.configure(text=f"Downloading {total_pages} pages...")
        
        # Download each page
        for i, page in enumerate(pages):
            try:
                page_num = page.get("page", i+1)
                img_url = page.get("img")
                headers = page.get("headerForImage", {})
                
                # Download image
                response = requests.get(img_url, headers=headers)
                response.raise_for_status()
                
                # Save image
                img = Image.open(BytesIO(response.content))
                img.save(os.path.join(temp_dir, f"{page_num}.png"))
                
                # Update progress
                progress_var.set(int((i+1) / total_pages * 100))
                status_label.configure(text=f"Downloaded page {i+1}/{total_pages}")
                root.update_idletasks()
                
            except Exception as e:
                print(f"Error downloading page {i+1}: {str(e)}")
                continue
        
        return temp_dir, total_pages
    
    except Exception as e:
        status_label.configure(text=f"Error: {str(e)}")
        return None, 0

# Function to convert downloaded images to selected format
def convert_to_format(temp_dir, output_path, format_type, manga_title, chapter_id, status_label):
    try:
        # Ensure the output directory exists
        if not os.path.exists(output_path):
            os.makedirs(output_path)
            
        # Create a safe filename
        safe_manga_title = filter_path(manga_title)
        safe_chapter_id = filter_path(str(chapter_id))
        output_file = os.path.join(output_path, f"{safe_manga_title}_Chapter_{safe_chapter_id}{format_type}")
        
        # Get all images in the temp directory
        image_files = os.listdir(temp_dir)
        image_files = [f for f in image_files if f.endswith('.png')]
        
        # Check if there are any images
        if not image_files:
            status_label.configure(text="No images found to convert")
            return False, None
            
        image_files.sort(key=lambda x: int(x.split('.')[0]))  # Sort numerically
        
        status_label.configure(text=f"Converting to {format_type}...")
        
        if format_type == ".pdf":
            try:
                # Convert to PDF
                images = []
                for img_file in image_files:
                    img_path = os.path.join(temp_dir, img_file)
                    img = Image.open(img_path)
                    if img.mode == 'RGBA':
                        img = img.convert('RGB')
                    images.append(img)
                
                if images:
                    # Make sure the path isn't too long
                    if len(output_file) > 240:  # Windows has 260 char path limit
                        short_title = safe_manga_title[:20] if len(safe_manga_title) > 20 else safe_manga_title
                        output_file = os.path.join(output_path, f"{short_title}_Ch_{safe_chapter_id}{format_type}")
                    
                    # Save the PDF
                    images[0].save(
                        output_file, 
                        "PDF", 
                        resolution=100.0, 
                        save_all=True, 
                        append_images=images[1:]
                    )
            except Exception as pdf_error:
                status_label.configure(text=f"PDF conversion error: {str(pdf_error)}")
                return False, None
        
        elif format_type == ".cbz":
            # Create zip and rename to CBZ
            zip_file = os.path.join(output_path, f"{safe_manga_title}_Chapter_{safe_chapter_id}")
            
            # Make sure the path isn't too long
            if len(zip_file) > 240:  # Windows has 260 char path limit
                short_title = safe_manga_title[:20] if len(safe_manga_title) > 20 else safe_manga_title
                zip_file = os.path.join(output_path, f"{short_title}_Ch_{safe_chapter_id}")
                output_file = f"{zip_file}.cbz"
                
            try:
                shutil.make_archive(zip_file, "zip", temp_dir)
                
                # Rename to CBZ
                if os.path.exists(output_file):
                    os.remove(output_file)
                os.rename(f"{zip_file}.zip", output_file)
            except Exception as zip_error:
                status_label.configure(text=f"CBZ creation error: {str(zip_error)}")
                return False, None
        
        elif format_type == ".png":
            # Create a subfolder for the PNGs
            png_folder = os.path.join(output_path, f"{safe_manga_title}_Chapter_{safe_chapter_id}")
            
            # Make sure the path isn't too long
            if len(png_folder) > 240:  # Windows has 260 char path limit
                short_title = safe_manga_title[:20] if len(safe_manga_title) > 20 else safe_manga_title
                png_folder = os.path.join(output_path, f"{short_title}_Ch_{safe_chapter_id}")
                
            if not os.path.exists(png_folder):
                os.makedirs(png_folder)
                
            # Just copy all PNG files to the destination folder
            try:
                for img_file in image_files:
                    src = os.path.join(temp_dir, img_file)
                    dst = os.path.join(png_folder, img_file)
                    shutil.copy(src, dst)
                output_file = png_folder  # For opening folder later
            except Exception as png_error:
                status_label.configure(text=f"PNG copy error: {str(png_error)}")
                return False, None
        
        # Clean up temp directory
        try:
            shutil.rmtree(temp_dir)
        except Exception as cleanup_error:
            print(f"Warning: Could not clean up temp directory: {str(cleanup_error)}")
        
        # Create "Open File" and "Open Folder" buttons
        status_label.configure(text=f"Successfully saved to {output_file}")
        
        # Store the output file path and directory for the open buttons
        global last_downloaded_file, last_downloaded_dir
        last_downloaded_file = output_file
        last_downloaded_dir = output_path
        
        # Show the open buttons
        show_open_buttons()
        
        return True, output_file
    
    except Exception as e:
        status_label.configure(text=f"Error converting: {str(e)}")
        print(f"Conversion error: {str(e)}")
        return False, None

# Function to handle manga search
def search_manga():
    query = search_entry.get().strip()
    provider_name = provider_dropdown.get()
    
    if not query:
        status_label.configure(text="Please enter a search term")
        return
    
    # Clear previous results
    results_listbox.delete(0, tk.END)
    chapters_listbox.delete(0, tk.END)
    status_label.configure(text=f"Searching for '{query}' on {provider_name}...")
    
    def perform_search():
        try:
            provider = PROVIDERS[provider_name]
            search_results = provider.search(query)
            
            # Store results for later use
            if isinstance(search_results, dict) and "results" in search_results:
                results = search_results["results"]
            else:
                results = search_results
            
            if not results:
                status_label.configure(text=f"No results found for '{query}'")
                return
            
            # Display results in listbox
            for i, result in enumerate(results):
                title = result.get("title", "Unknown")
                results_listbox.insert(tk.END, title)
            
            # Store results data
            results_listbox.results_data = results
            status_label.configure(text=f"Found {len(results)} results")
        
        except Exception as e:
            status_label.configure(text=f"Search error: {str(e)}")
    
    # Run search in a separate thread
    search_thread = threading.Thread(target=perform_search)
    search_thread.daemon = True
    search_thread.start()

# Function to handle manga selection from search results
def on_manga_selected(event):
    selected_idx = results_listbox.curselection()
    if not selected_idx:
        return
    
    selected_idx = selected_idx[0]
    if not hasattr(results_listbox, 'results_data') or selected_idx >= len(results_listbox.results_data):
        return
    
    manga_data = results_listbox.results_data[selected_idx]
    manga_id = manga_data.get("id", "")
    
    # Debug: Print manga data from search results
    print(f"Selected manga data: {manga_data}")
    
    if not manga_id:
        status_label.configure(text="Invalid manga selection")
        return
    
    # Clear previous chapters
    chapters_listbox.delete(0, tk.END)
    
    provider_name = provider_dropdown.get()
    status_label.configure(text=f"Fetching chapters for {manga_data.get('title', 'Unknown')}...")
    
    # If we already have an image URL in search results, store it for backup
    if "image" in manga_data and manga_data["image"]:
        # Store the image URL from search results in case the manga info doesn't have one
        chapters_listbox.search_result_cover = manga_data["image"]
        print(f"Found image URL in search results: {manga_data['image']}")
    
    def fetch_chapters():
        try:
            provider = PROVIDERS[provider_name]
            manga_info = provider.fetch_manga_info(manga_id)
            
            # Debug: Print manga info
            print(f"Manga info keys: {manga_info.keys()}")
            
            if not manga_info or "chapters" not in manga_info:
                status_label.configure(text="No chapters found")
                return
            
            chapters = manga_info["chapters"]
            if not chapters:
                status_label.configure(text="No chapters available")
                return
            
            # Store all chapters for searching/filtering
            chapters_listbox.all_chapters = chapters
            chapters_listbox.manga_title = manga_info.get("title", "Unknown Manga")
            chapters_listbox.manga_id = manga_id
            
            # If manga_info doesn't have a cover/image but we have one from search results, add it
            if ("cover" not in manga_info or not manga_info["cover"]) and \
               ("image" not in manga_info or not manga_info["image"]) and \
               hasattr(chapters_listbox, 'search_result_cover'):
                manga_info["image"] = chapters_listbox.search_result_cover
                print(f"Using image from search results: {manga_info['image']}")
            
            # Display chapters in listbox
            display_chapters(chapters)
            
            # Update manga info panel
            update_manga_info_panel(manga_info)
            
            status_label.configure(text=f"Found {len(chapters)} chapters")
        
        except Exception as e:
            status_label.configure(text=f"Error fetching chapters: {str(e)}")
            print(f"Error in fetch_chapters: {str(e)}")
    
    # Run chapter fetch in a separate thread
    chapter_thread = threading.Thread(target=fetch_chapters)
    chapter_thread.daemon = True
    chapter_thread.start()

# Function to calculate appropriate image size based on window width
def calculate_image_size():
    # Use a fixed small size instead of dynamic resizing
    return (100, 150)

# Update load_manga_cover to use a fixed size
def load_manga_cover(image_url, max_size=None):
    """Load manga cover image from URL and resize it"""
    # Use a fixed size for better performance
    max_size = (100, 150)
        
    try:
        if not image_url:
            print("No image URL provided")
            return None
            
        print(f"Loading image from: {image_url}")
        
        # Determine appropriate referer based on URL
        referer = "https://mangapill.com"  # Default referer
        if "mangapill" in image_url:
            referer = "https://mangapill.com"
        elif "mangapark" in image_url:
            referer = "https://mangapark.net"
        elif "mangahere" in image_url:
            referer = "https://www.mangahere.cc"
        
        # Get current provider to use as referer
        provider_name = provider_dropdown.get()
        if provider_name in PROVIDERS and hasattr(PROVIDERS[provider_name], "base_url"):
            referer = PROVIDERS[provider_name].base_url
        
        print(f"Using referer: {referer}")
        
        # Try with requests first (handles more headers/redirects)
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Referer": referer,
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
            }
            response = requests.get(image_url, headers=headers)
            response.raise_for_status()
            image_data = response.content
            print(f"Successfully downloaded image with requests: {len(image_data)} bytes")
        except Exception as e:
            print(f"Requests failed, trying urlopen with custom headers: {str(e)}")
            # Fallback to urlopen with custom headers
            try:
                req = urllib.request.Request(
                    image_url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                        "Referer": referer
                    }
                )
                response = urllib.request.urlopen(req)
                image_data = response.read()
                print(f"Successfully downloaded image with urllib: {len(image_data)} bytes")
            except Exception as e2:
                print(f"Both download methods failed: {str(e2)}")
                raise e2
        
        # Convert to PIL Image
        img = Image.open(BytesIO(image_data))
        print(f"Image opened: {img.format}, {img.size}, {img.mode}")
        
        # Resize image while maintaining aspect ratio
        img.thumbnail(max_size)
        print(f"Image resized to: {img.size}")
        
        # Convert to CTkImage for customtkinter
        photo_img = customtkinter.CTkImage(light_image=img, dark_image=img, size=img.size)
        print(f"Successfully created CTkImage")
        return photo_img
    except Exception as e:
        print(f"Error loading image: {str(e)}")
        # Try to create a placeholder image
        try:
            placeholder_size = max_size
            placeholder = Image.new('RGB', placeholder_size, color=(50, 50, 50))
            draw = ImageDraw.Draw(placeholder)
            text_y = placeholder_size[1] // 2 - 10
            draw.text((10, text_y), "No Image", fill=(200, 200, 200))
            photo_img = customtkinter.CTkImage(light_image=placeholder, dark_image=placeholder, size=placeholder_size)
            print("Created placeholder image")
            return photo_img
        except Exception as e2:
            print(f"Failed to create placeholder: {str(e2)}")
            return None

def update_manga_info_panel(manga_info):
    """Update the manga info panel with details and cover image"""
    manga_title_label.configure(text=manga_info.get("title", "Unknown Title"))
    
    # Load and display cover image if available - check different field names used by providers
    cover_url = None
    for field in ["cover", "image", "img", "thumbnail", "coverImage"]:
        if field in manga_info and manga_info[field]:
            cover_url = manga_info[field]
            print(f"Found cover URL in field '{field}': {cover_url}")
            break
    
    # Skip URLs from removed providers
    if cover_url and ("manganato" in cover_url or "chapmanganato" in cover_url or "vyvymanga" in cover_url):
        print(f"Skipping image from removed provider: {cover_url}")
        cover_url = None
    
    # Store the cover URL for later use
    if cover_url:
        manga_cover_label.cover_url = cover_url
    
    # Calculate appropriate text wrapping based on window width
    window_width = root.winfo_width()
    wrap_length = max(300, window_width - 350)  # Adjust wrapping based on window size
    manga_desc_label.configure(wraplength=wrap_length)
    manga_title_label.configure(wraplength=wrap_length)
    manga_info_label.configure(wraplength=wrap_length)
    
    if cover_url:
        # Ensure URL is absolute
        if cover_url.startswith("//"):
            cover_url = "https:" + cover_url
            print(f"Fixed relative URL: {cover_url}")
        elif cover_url.startswith("/"):
            provider_name = provider_dropdown.get()
            provider = PROVIDERS.get(provider_name)
            if provider and hasattr(provider, "base_url"):
                cover_url = provider.base_url + cover_url
                print(f"Added base URL: {cover_url}")
        
        # Use fixed image size for better performance
        photo_img = load_manga_cover(cover_url)
        if photo_img:
            manga_cover_label.configure(image=photo_img)
            manga_cover_label.image = photo_img  # Keep a reference
            
            # Use grid layout for better responsiveness
            manga_cover_label.grid(row=0, column=0, rowspan=3, padx=5, pady=5, sticky="nw")
            manga_title_label.grid(row=0, column=1, padx=5, pady=(5, 3), sticky="nw")
            manga_desc_label.grid(row=1, column=1, padx=5, pady=3, sticky="nw")
            manga_info_label.grid(row=2, column=1, padx=5, pady=(3, 5), sticky="nw")
        else:
            # If image loading failed, revert to original layout
            print("Image loading failed, reverting to original layout")
            manga_cover_label.grid_forget()
            manga_title_label.grid(row=0, column=0, columnspan=2, padx=5, pady=(5, 3), sticky="nw")
            manga_desc_label.grid(row=1, column=0, columnspan=2, padx=5, pady=3, sticky="nw")
            manga_info_label.grid(row=2, column=0, columnspan=2, padx=5, pady=(3, 5), sticky="nw")
    else:
        # No cover URL, use original layout
        print("No cover URL found in manga_info")
        manga_cover_label.grid_forget()
        manga_title_label.grid(row=0, column=0, columnspan=2, padx=5, pady=(5, 3), sticky="nw")
        manga_desc_label.grid(row=1, column=0, columnspan=2, padx=5, pady=3, sticky="nw")
        manga_info_label.grid(row=2, column=0, columnspan=2, padx=5, pady=(3, 5), sticky="nw")
    
    # Update description if available
    description = manga_info.get("description", "No description available")
    if len(description) > 300:
        description = description[:300] + "..."
    manga_desc_label.configure(text=description)
    
    # Update other info
    info_text = f"Status: {manga_info.get('status', 'Unknown')}\n"
    
    if "genres" in manga_info and manga_info["genres"]:
        genres = ", ".join(manga_info["genres"][:5])  # Show first 5 genres
        if len(manga_info["genres"]) > 5:
            genres += "..."
        info_text += f"Genres: {genres}\n"
    
    if "authors" in manga_info and manga_info["authors"]:
        authors = ", ".join(manga_info["authors"])
        info_text += f"Authors: {authors}"
    
    manga_info_label.configure(text=info_text)

def display_chapters(chapters):
    """Display chapters in the listbox with formatting"""
    chapters_listbox.delete(0, tk.END)
    
    for chapter in chapters:
        chapter_title = chapter.get("title", "")
        chapter_num = chapter.get("chapter", "")
        
        if chapter_num:
            try:
                # For numeric sorting
                chapter["chapter_num"] = float(chapter_num)
            except:
                chapter["chapter_num"] = 0
                
            display_text = f"Chapter {chapter_num} - {chapter_title}"
        else:
            display_text = chapter_title
            chapter["chapter_num"] = 0
        
        chapters_listbox.insert(tk.END, display_text)

def filter_chapters():
    """Filter chapters based on search text"""
    if not hasattr(chapters_listbox, 'all_chapters'):
        return
    
    search_text = chapter_search_entry.get().lower()
    
    if not search_text:
        # If search is empty, show all chapters
        display_chapters(chapters_listbox.all_chapters)
        return
    
    # Filter chapters based on search text
    filtered_chapters = []
    for chapter in chapters_listbox.all_chapters:
        chapter_title = chapter.get("title", "").lower()
        chapter_num = str(chapter.get("chapter", "")).lower()
        
        if search_text in chapter_title or search_text in chapter_num:
            filtered_chapters.append(chapter)
    
    # Display filtered chapters
    display_chapters(filtered_chapters)
    status_label.configure(text=f"Found {len(filtered_chapters)} matching chapters")

def sort_chapters():
    """Sort chapters based on selected sort option"""
    if not hasattr(chapters_listbox, 'all_chapters'):
        return
    
    sort_option = sort_var.get()
    
    # Get the currently displayed chapters (which might be filtered)
    displayed_chapters = []
    for i in range(chapters_listbox.size()):
        display_text = chapters_listbox.get(i)
        for chapter in chapters_listbox.all_chapters:
            chapter_title = chapter.get("title", "")
            chapter_num = chapter.get("chapter", "")
            
            if chapter_num:
                if f"Chapter {chapter_num} - {chapter_title}" == display_text:
                    displayed_chapters.append(chapter)
                    break
            elif chapter_title == display_text:
                displayed_chapters.append(chapter)
                break
    
    if not displayed_chapters:
        displayed_chapters = chapters_listbox.all_chapters.copy()
    
    # Sort the displayed chapters
    if sort_option == "Newest First":
        displayed_chapters.sort(key=lambda x: float(x.get("chapter_num", 0) or 0), reverse=True)
    elif sort_option == "Oldest First":
        displayed_chapters.sort(key=lambda x: float(x.get("chapter_num", 0) or 0))
    
    # Display sorted chapters
    display_chapters(displayed_chapters)

# Function to download selected chapter
def download_selected_chapter():
    # Clear any existing progress bars
    clear_progress_bars()
    
    selected_idx = chapters_listbox.curselection()
    if not selected_idx:
        status_label.configure(text="Please select a chapter to download")
        play_sound("error")
        return
    
    # Get all chapters (filtered or not)
    all_displayed_chapters = []
    for i in range(chapters_listbox.size()):
        # Find the corresponding chapter from all_chapters
        display_text = chapters_listbox.get(i)
        for chapter in chapters_listbox.all_chapters:
            chapter_title = chapter.get("title", "")
            chapter_num = chapter.get("chapter", "")
            
            if chapter_num:
                if f"Chapter {chapter_num} - {chapter_title}" == display_text:
                    all_displayed_chapters.append(chapter)
                    break
            elif chapter_title == display_text:
                all_displayed_chapters.append(chapter)
                break
    
    if not all_displayed_chapters:
        status_label.configure(text="Error finding chapter data")
        play_sound("error")
        return
        
    selected_idx = selected_idx[0]
    if selected_idx >= len(all_displayed_chapters):
        status_label.configure(text="Invalid chapter selection")
        play_sound("error")
        return
        
    # Get chapter data
    chapter = all_displayed_chapters[selected_idx]
    chapter_id = chapter.get("id", "")
    
    if not chapter_id:
        status_label.configure(text="Invalid chapter ID")
        play_sound("error")
        return
    
    # Get download path
    download_path = download_folder_entry.get()
    if not download_path:
        status_label.configure(text="Please select a download folder")
        play_sound("error")
        return
    
    # Get selected format
    format_type = format_dropdown.get()
    
    # Get manga title
    manga_title = getattr(chapters_listbox, 'manga_title', "Unknown Manga")
    
    # Disable download button during download
    download_button.configure(state="disabled")
    batch_download_button.configure(state="disabled")
    
    # Hide open buttons if they were visible
    hide_open_buttons()
    
    # Play start sound
    play_sound("start")
    
    def perform_download():
        try:
            provider_name = provider_dropdown.get()
            
            # Download images
            status_label.configure(text=f"Downloading chapter...")
            progress_var.set(0)
            # Show progress frame and progress bar
            progress_frame.pack(fill=tk.X, padx=5, pady=2)
            
            # Add a label for the progress bar
            progress_label = customtkinter.CTkLabel(
                progress_frame,
                text="Chapter Progress:",
                anchor="w",
                text_color=COLORS["text_primary"],
                font=("Arial", 11)
            )
            progress_label.pack(fill=tk.X, padx=5, pady=(2, 0), anchor="w")
            
            progress_bar.pack(fill=tk.X, padx=5, pady=(0, 5))
            
            temp_dir, total_pages = download_chapter_images(chapter_id, provider_name, progress_var, status_label, manga_title)
            
            if not temp_dir or total_pages == 0:
                status_label.configure(text="Download failed")
                download_button.configure(state="normal")
                batch_download_button.configure(state="normal")
                # Clear progress bars when failed
                clear_progress_bars()
                play_sound("error")
                return
            
            # Convert to selected format and get the output file path
            success, output_file = convert_to_format(temp_dir, download_path, format_type, manga_title, chapter_id, status_label)
            
            # Clear progress bars when done
            clear_progress_bars()
            
            # Enable download button
            download_button.configure(state="normal")
            batch_download_button.configure(state="normal")
            
            # Play completion sound
            play_sound("complete")
        
        except Exception as e:
            status_label.configure(text=f"Download error: {str(e)}")
            download_button.configure(state="normal")
            batch_download_button.configure(state="normal")
            # Clear progress bars on error
            clear_progress_bars()
            # Play error sound
            play_sound("error")
    
    # Run download in a separate thread
    download_thread = threading.Thread(target=perform_download)
    download_thread.daemon = True
    download_thread.start()

# Function to download multiple chapters in batch
def download_batch_chapters():
    # Clear any existing progress bars
    clear_progress_bars()
    
    selected_indices = chapters_listbox.curselection()
    if not selected_indices:
        status_label.configure(text="Please select chapters to download")
        play_sound("error")
        return
    
    # Get download path
    download_path = download_folder_entry.get()
    if not download_path:
        status_label.configure(text="Please select a download folder")
        play_sound("error")
        return
    
    # Get selected format
    format_type = format_dropdown.get()
    
    # Get manga title
    manga_title = getattr(chapters_listbox, 'manga_title', "Unknown Manga")
    
    # Get all displayed chapters
    all_displayed_chapters = []
    for i in range(chapters_listbox.size()):
        # Find the corresponding chapter from all_chapters
        display_text = chapters_listbox.get(i)
        for chapter in chapters_listbox.all_chapters:
            chapter_title = chapter.get("title", "")
            chapter_num = chapter.get("chapter", "")
            
            if chapter_num:
                if f"Chapter {chapter_num} - {chapter_title}" == display_text:
                    all_displayed_chapters.append(chapter)
                    break
            elif chapter_title == display_text:
                all_displayed_chapters.append(chapter)
                break
    
    if not all_displayed_chapters:
        status_label.configure(text="Error finding chapter data")
        play_sound("error")
        return
    
    # Get selected chapters
    selected_chapters = []
    for idx in selected_indices:
        if idx < len(all_displayed_chapters):
            selected_chapters.append(all_displayed_chapters[idx])
    
    if not selected_chapters:
        status_label.configure(text="No valid chapters selected")
        play_sound("error")
        return
    
    # Disable download buttons during download
    download_button.configure(state="disabled")
    batch_download_button.configure(state="disabled")
    
    # Hide open buttons if they were visible
    hide_open_buttons()
    
    # Play start sound
    play_sound("start")
    
    # Create a progress bar for overall progress
    total_progress = len(selected_chapters)
    batch_progress_var = tk.IntVar(value=0)
    
    # Make sure progress frame is visible
    if not progress_frame.winfo_ismapped():
        progress_frame.pack(fill=tk.X, padx=5, pady=2)
    
    # Create batch progress frame
    batch_progress_frame = customtkinter.CTkFrame(progress_frame, fg_color=COLORS["bg_primary"])
    batch_progress_frame.pack(fill=tk.X, padx=0, pady=2)
    
    # Add a label for the batch progress bar
    batch_progress_label = customtkinter.CTkLabel(
        batch_progress_frame,
        text=f"Batch Progress: 0/{total_progress}",
        anchor="w",
        text_color=COLORS["text_primary"],
        font=("Arial", 11)
    )
    batch_progress_label.pack(fill=tk.X, padx=5, pady=(2, 0), anchor="w")
    
    batch_progress_bar = ttk.Progressbar(
        batch_progress_frame,
        orient="horizontal",
        length=400,
        mode="determinate",
        variable=batch_progress_var,
        maximum=total_progress
    )
    batch_progress_bar.pack(fill=tk.X, padx=5, pady=(0, 5))
    
    def perform_batch_download():
        provider_name = provider_dropdown.get()
        completed = 0
        failed = 0
        last_successful_file = None
        
        for i, chapter in enumerate(selected_chapters):
            try:
                chapter_id = chapter.get("id", "")
                if not chapter_id:
                    print(f"Invalid chapter ID for chapter {i}")
                    failed += 1
                    continue
                
                # Update status
                chapter_num = chapter.get("chapter", i+1)
                status_label.configure(text=f"Downloading chapter {chapter_num} ({i+1}/{len(selected_chapters)})")
                
                # Download chapter
                progress_var.set(0)
                # Show progress frame if not already visible
                if not progress_frame.winfo_ismapped():
                    progress_frame.pack(fill=tk.X, padx=5, pady=2)
                
                # Add a label for the chapter progress bar if not already added
                if not any(isinstance(widget, customtkinter.CTkLabel) and widget.cget("text") == "Chapter Progress:" 
                          for widget in progress_frame.winfo_children()):
                    progress_label = customtkinter.CTkLabel(
                        progress_frame,
                        text="Chapter Progress:",
                        anchor="w",
                        text_color=COLORS["text_primary"],
                        font=("Arial", 11)
                    )
                    progress_label.pack(fill=tk.X, padx=5, pady=(2, 0), anchor="w")
                
                progress_bar.pack(fill=tk.X, padx=5, pady=(0, 5))
                
                temp_dir, total_pages = download_chapter_images(chapter_id, provider_name, progress_var, status_label, manga_title)
                
                if not temp_dir or total_pages == 0:
                    print(f"Download failed for chapter {chapter_num}")
                    failed += 1
                    continue
                
                # Convert to selected format and get output file path
                success, output_file = convert_to_format(temp_dir, download_path, format_type, manga_title, chapter_id, status_label)
                if success:
                    completed += 1
                    last_successful_file = output_file
                else:
                    failed += 1
                
                # Update batch progress
                batch_progress_var.set(i + 1)
                batch_progress_label.configure(text=f"Batch Progress: {i+1}/{total_progress} (Completed: {completed}, Failed: {failed})")
                
                # Small delay to prevent overwhelming the server
                time.sleep(1)
                
            except Exception as e:
                print(f"Error downloading chapter: {str(e)}")
                failed += 1
        
        # Clear all progress bars
        clear_progress_bars()
        
        # Enable download buttons
        download_button.configure(state="normal")
        batch_download_button.configure(state="normal")
        
        # Update status
        status_label.configure(text=f"Batch download complete. Completed: {completed}, Failed: {failed}")
        
        # Set the last downloaded file and directory for open buttons
        if last_successful_file:
            global last_downloaded_file, last_downloaded_dir
            last_downloaded_file = last_successful_file
            last_downloaded_dir = download_path
            show_open_buttons()
        
        # Play completion sound
        play_sound("complete")
    
    # Run batch download in a separate thread
    batch_thread = threading.Thread(target=perform_batch_download)
    batch_thread.daemon = True
    batch_thread.start()

# Function to browse for download folder
def browse_folder():
    folder = filedialog.askdirectory()
    if folder:
        download_folder_var.set(folder)

# Create main frame
main_frame = customtkinter.CTkFrame(root, fg_color=COLORS["bg_primary"])
main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

# Create and configure UI elements
# Top bar with provider dropdown
top_bar = customtkinter.CTkFrame(main_frame, fg_color=COLORS["bg_primary"])
top_bar.pack(fill=tk.X, padx=5, pady=5)

provider_label = customtkinter.CTkLabel(top_bar, text="Provider:", font=("Arial", 14), text_color=COLORS["text_primary"])
provider_label.pack(side=tk.LEFT, padx=(0, 5))

provider_var = tk.StringVar()
provider_dropdown = customtkinter.CTkOptionMenu(
    top_bar, 
    variable=provider_var,
    values=["MangaPill", "MangaPark", "MangaHere"],
    fg_color=COLORS["bg_tertiary"], 
    text_color=COLORS["text_primary"],
    bg_color=COLORS["bg_primary"],
    button_color=COLORS["bg_tertiary"],
    dropdown_fg_color=COLORS["bg_tertiary"],
    dropdown_hover_color=COLORS["accent"],
    width=150,
    font=("Arial", 13)
)
provider_dropdown.pack(side=tk.LEFT, padx=5)
provider_dropdown.set("MangaPill")

# Add GitHub link to top right
credit_frame = customtkinter.CTkFrame(top_bar, fg_color="transparent")
credit_frame.pack(side=tk.RIGHT, padx=10)

credit_label = customtkinter.CTkLabel(
    credit_frame,
    text="Made by:",
    text_color=COLORS["text_tertiary"],
    font=("Arial", 12)
)
credit_label.pack(side=tk.LEFT, padx=(0, 5))

def open_github():
    import webbrowser
    webbrowser.open("https://github.com/zuhaz")

github_link = customtkinter.CTkButton(
    credit_frame,
    text="github.com/zuhaz",
    command=open_github,
    fg_color="transparent",
    hover_color=COLORS["bg_tertiary"],
    text_color=COLORS["accent"],
    font=("Arial", 12, "underline"),
    height=25,
    corner_radius=8,
    width=0
)
github_link.pack(side=tk.LEFT)

# Search section
search_frame = customtkinter.CTkFrame(main_frame, fg_color=COLORS["bg_primary"])
search_frame.pack(fill=tk.X, padx=5, pady=(0, 5))

search_label = customtkinter.CTkLabel(search_frame, text="Search Manga:", font=("Arial", 14), text_color=COLORS["text_primary"])
search_label.pack(side=tk.LEFT, padx=(0, 5))

search_entry = customtkinter.CTkEntry(
    search_frame, 
    width=400,
    fg_color=COLORS["bg_secondary"],
    border_width=1,
    border_color=COLORS["bg_tertiary"],
    placeholder_text="Enter manga title",
    placeholder_text_color=COLORS["text_tertiary"],
    font=("Arial", 13),
    height=35,
    corner_radius=8
)
search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

search_button = customtkinter.CTkButton(
    search_frame, 
    text="Search", 
    command=search_manga,
    fg_color=COLORS["accent"],
    hover_color=COLORS["accent_hover"],
    width=100,
    font=("Arial", 13, "bold"),
    height=35,
    corner_radius=8
)
search_button.pack(side=tk.RIGHT, padx=5)

# Create a paned window to divide the interface
paned_window = tk.PanedWindow(main_frame, orient=tk.HORIZONTAL, bg=COLORS["bg_primary"], sashwidth=4, sashrelief="raised")
paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

# Set minimum sizes for panels to ensure they don't get too small
min_left_width = 250
min_right_width = 500

# Left panel for search results
left_panel = customtkinter.CTkFrame(paned_window, fg_color=COLORS["bg_primary"])
left_panel.grid_propagate(False)  # Prevent panel from shrinking
paned_window.add(left_panel, stretch="always", minsize=min_left_width)

# Right panel for manga details and chapters
right_panel = customtkinter.CTkFrame(paned_window, fg_color=COLORS["bg_primary"])
right_panel.grid_propagate(False)  # Prevent panel from shrinking
paned_window.add(right_panel, stretch="always", minsize=min_right_width)

# Results section
results_label = customtkinter.CTkLabel(left_panel, text="Search Results:", anchor="w", font=("Arial", 14, "bold"), text_color=COLORS["text_primary"])
results_label.pack(fill=tk.X, padx=3, pady=3)

results_frame = customtkinter.CTkFrame(left_panel, fg_color=COLORS["bg_primary"])
results_frame.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)

results_listbox = tk.Listbox(
    results_frame, 
    height=10, 
    width=30,
    bg=COLORS["bg_secondary"],
    fg=COLORS["text_primary"],
    selectbackground=COLORS["accent"],
    font=("Arial", 12),
    relief="flat",
    borderwidth=0,
    highlightthickness=0,
    activestyle="none"
)
results_scrollbar = ttk.Scrollbar(results_frame, command=results_listbox.yview, style="TScrollbar")
results_listbox.configure(yscrollcommand=results_scrollbar.set)
results_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
results_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
results_listbox.bind("<<ListboxSelect>>", on_manga_selected)

# Manga info section - make it responsive
manga_info_frame = customtkinter.CTkFrame(right_panel, fg_color=COLORS["bg_secondary"], corner_radius=8)
manga_info_frame.pack(fill=tk.X, padx=5, pady=5)
manga_info_frame.grid_columnconfigure(1, weight=1)  # Make text column expandable

# Create label for manga cover with a default empty image
manga_cover_label = customtkinter.CTkLabel(manga_info_frame, text="", image=None)

# Create text labels using grid instead of pack
manga_title_label = customtkinter.CTkLabel(
    manga_info_frame, 
    text="Select a manga", 
    font=("Arial", 18, "bold"),
    anchor="w",
    text_color=COLORS["text_primary"],
    wraplength=550  # Allow title to wrap if needed
)
manga_title_label.grid(row=0, column=0, columnspan=2, padx=5, pady=(5, 3), sticky="nw")

manga_desc_label = customtkinter.CTkLabel(
    manga_info_frame, 
    text="", 
    wraplength=550,
    justify="left",
    anchor="w",
    font=("Arial", 12),
    text_color=COLORS["text_secondary"]
)
manga_desc_label.grid(row=1, column=0, columnspan=2, padx=5, pady=3, sticky="nw")

manga_info_label = customtkinter.CTkLabel(
    manga_info_frame, 
    text="", 
    justify="left",
    anchor="w",
    font=("Arial", 12),
    text_color=COLORS["text_tertiary"],
    wraplength=550  # Allow info to wrap if needed
)
manga_info_label.grid(row=2, column=0, columnspan=2, padx=5, pady=(3, 5), sticky="nw")

# Chapters section with search and sort options
chapters_control_frame = customtkinter.CTkFrame(right_panel, fg_color=COLORS["bg_primary"])
chapters_control_frame.pack(fill=tk.X, padx=5, pady=(5, 3))

chapters_label = customtkinter.CTkLabel(
    chapters_control_frame, 
    text="Chapters:", 
    anchor="w", 
    font=("Arial", 14, "bold"),
    text_color=COLORS["text_primary"]
)
chapters_label.pack(side=tk.LEFT, padx=5)

# Chapter search
chapter_search_entry = customtkinter.CTkEntry(
    chapters_control_frame,
    width=180,
    fg_color=COLORS["bg_secondary"],
    border_width=1,
    border_color=COLORS["bg_tertiary"],
    placeholder_text="Search chapters",
    placeholder_text_color=COLORS["text_tertiary"],
    font=("Arial", 12),
    height=30,
    corner_radius=8
)
chapter_search_entry.pack(side=tk.LEFT, padx=10)
chapter_search_entry.bind("<KeyRelease>", lambda e: filter_chapters())

# Chapter sort options
sort_var = tk.StringVar(value="Newest First")
sort_dropdown = customtkinter.CTkOptionMenu(
    chapters_control_frame,
    variable=sort_var,
    values=["Newest First", "Oldest First"],
    command=lambda x: sort_chapters(),
    fg_color=COLORS["bg_tertiary"],
    text_color=COLORS["text_primary"],
    bg_color=COLORS["bg_primary"],
    button_color=COLORS["bg_tertiary"],
    dropdown_fg_color=COLORS["bg_tertiary"],
    dropdown_hover_color=COLORS["accent"],
    width=120,
    font=("Arial", 12),
    corner_radius=8
)
sort_dropdown.pack(side=tk.RIGHT, padx=5)

sort_label = customtkinter.CTkLabel(chapters_control_frame, text="Sort:", font=("Arial", 12), text_color=COLORS["text_primary"])
sort_label.pack(side=tk.RIGHT, padx=5)

# Chapters listbox
chapters_frame = customtkinter.CTkFrame(right_panel, fg_color=COLORS["bg_primary"])
chapters_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=3)

chapters_listbox = tk.Listbox(
    chapters_frame, 
    height=10, 
    width=50,
    bg=COLORS["bg_secondary"],
    fg=COLORS["text_primary"],
    selectbackground=COLORS["accent"],
    font=("Arial", 12),
    relief="flat",
    borderwidth=0,
    highlightthickness=0,
    activestyle="none",
    selectmode=tk.EXTENDED  # Allow multiple selections for batch download
)
chapters_scrollbar = ttk.Scrollbar(chapters_frame, command=chapters_listbox.yview, style="TScrollbar")
chapters_listbox.configure(yscrollcommand=chapters_scrollbar.set)
chapters_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
chapters_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
# Bind selection event to update button visibility
# Function to update button visibility based on selection
def update_button_visibility(*args):
    selected_indices = chapters_listbox.curselection()
    if not selected_indices:
        # No selection - hide both buttons
        download_button.pack_forget()
        batch_download_button.pack_forget()
    elif len(selected_indices) == 1:
        # Single selection - show only single download button
        batch_download_button.pack_forget()
        download_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2, pady=3)
    else:
        # Multiple selection - show only batch download button
        download_button.pack_forget()
        batch_download_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2, pady=3)

chapters_listbox.bind("<<ListboxSelect>>", update_button_visibility)

# Add instructions for multiple selection
selection_help_label = customtkinter.CTkLabel(
    right_panel,
    text="Tip: Hold Ctrl/Shift to select multiple chapters for batch download",
    text_color=COLORS["text_tertiary"],
    font=("Arial", 10)
)
selection_help_label.pack(fill=tk.X, padx=5, pady=2)

# Download options frame
download_options_frame = customtkinter.CTkFrame(main_frame, fg_color=COLORS["bg_secondary"], corner_radius=8)
download_options_frame.pack(fill=tk.X, padx=5, pady=(5, 0))

format_label = customtkinter.CTkLabel(download_options_frame, text="Format:", font=("Arial", 14), text_color=COLORS["text_primary"])
format_label.pack(side=tk.LEFT, padx=5, pady=5)

format_dropdown = customtkinter.CTkOptionMenu(
    download_options_frame, 
    values=formats,
    fg_color=COLORS["bg_tertiary"], 
    text_color=COLORS["text_primary"],
    bg_color=COLORS["bg_secondary"],
    button_color=COLORS["bg_tertiary"],
    dropdown_fg_color=COLORS["bg_tertiary"],
    dropdown_hover_color=COLORS["accent"],
    width=80,
    font=("Arial", 13),
    corner_radius=8
)
format_dropdown.pack(side=tk.LEFT, padx=5, pady=5)
format_dropdown.set(".cbz")

download_folder_label = customtkinter.CTkLabel(download_options_frame, text="Download Folder:", font=("Arial", 14), text_color=COLORS["text_primary"])
download_folder_label.pack(side=tk.LEFT, padx=(10, 5), pady=5)

download_folder_var = tk.StringVar()
download_folder_entry = customtkinter.CTkEntry(
    download_options_frame, 
    textvariable=download_folder_var,
    width=350,
    fg_color=COLORS["bg_tertiary"],
    border_width=1,
    border_color=COLORS["bg_tertiary"],
    state="readonly",
    font=("Arial", 12),
    height=30,
    corner_radius=8
)
download_folder_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)

browse_button = customtkinter.CTkButton(
    download_options_frame, 
    text="Browse", 
    command=browse_folder,
    fg_color=COLORS["accent"],
    hover_color=COLORS["accent_hover"],
    width=80,
    font=("Arial", 13),
    height=30,
    corner_radius=8
)
browse_button.pack(side=tk.RIGHT, padx=5, pady=5)

# Bottom frame for download button and status
bottom_frame = customtkinter.CTkFrame(main_frame, fg_color=COLORS["bg_primary"])
bottom_frame.pack(fill=tk.X, padx=5, pady=5)

# Download buttons frame
buttons_frame = customtkinter.CTkFrame(bottom_frame, fg_color=COLORS["bg_primary"])
buttons_frame.pack(fill=tk.X, padx=0, pady=0)

# Single chapter download button
download_button = customtkinter.CTkButton(
    buttons_frame, 
    text="Download Selected Chapter", 
    command=download_selected_chapter,
    fg_color=COLORS["accent"],
    hover_color=COLORS["accent_hover"],
    height=35,
    font=("Arial", 13, "bold"),
    corner_radius=8
)
# Make the single download button visible by default
download_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2, pady=3)

# Batch download button
batch_download_button = customtkinter.CTkButton(
    buttons_frame,
    text="Batch Download Selected",
    command=download_batch_chapters,
    fg_color=COLORS["accent"],
    hover_color=COLORS["accent_hover"],
    height=35,
    font=("Arial", 13, "bold"),
    corner_radius=8
)
# Initially hidden - will be shown when multiple chapters are selected

# Progress bar frame to better manage progress bars - initially hidden
progress_frame = customtkinter.CTkFrame(bottom_frame, fg_color=COLORS["bg_primary"])
# Don't pack it initially - only show when needed

# Chapter progress bar
progress_var = tk.IntVar()
progress_bar = ttk.Progressbar(
    progress_frame, 
    orient="horizontal", 
    length=400, 
    mode="determinate",
    variable=progress_var
)

# Style the progress bar
style = ttk.Style()
style.theme_use("clam")
style.configure("Horizontal.TProgressbar", 
                troughcolor=COLORS["bg_secondary"], 
                background=COLORS["accent"],
                thickness=10)

# Configure scrollbar colors for dark theme
style.configure("TScrollbar", 
                background=COLORS["bg_tertiary"],
                troughcolor=COLORS["bg_primary"], 
                bordercolor=COLORS["bg_primary"],
                arrowcolor=COLORS["text_tertiary"],
                borderwidth=0,
                relief="flat")

# Status label
status_label = customtkinter.CTkLabel(
    bottom_frame, 
    text="Ready", 
    text_color=COLORS["text_tertiary"],
    font=("Arial", 12)
)
status_label.pack(fill=tk.X, padx=5, pady=3)

# Create a frame for the open buttons (initially hidden)
open_buttons_frame = customtkinter.CTkFrame(bottom_frame, fg_color=COLORS["bg_primary"], corner_radius=8)
# Center the buttons in the frame
open_buttons_frame.grid_columnconfigure(0, weight=1)
open_buttons_frame.grid_columnconfigure(1, weight=1)

# Function to open downloaded file
def open_downloaded_file():
    global last_downloaded_file
    if last_downloaded_file and os.path.exists(last_downloaded_file):
        try:
            # Use the default application to open the file
            if os.name == 'nt':  # Windows
                os.startfile(last_downloaded_file)
            elif os.name == 'posix':  # macOS and Linux
                subprocess.call(('xdg-open' if os.name == 'posix' else 'open', last_downloaded_file))
            status_label.configure(text=f"Opened file: {os.path.basename(last_downloaded_file)}")
        except Exception as e:
            status_label.configure(text=f"Error opening file: {str(e)}")
    else:
        status_label.configure(text="No file to open")

# Create open file and open folder buttons (initially hidden)
open_file_button = customtkinter.CTkButton(
    open_buttons_frame,
    text="📄 Open File",
    command=open_downloaded_file,
    fg_color=COLORS["bg_tertiary"],
    hover_color=COLORS["accent"],
    height=35,
    font=("Arial", 12, "bold"),
    corner_radius=8,
    width=150
)

# Function to open download folder
def open_download_folder():
    global last_downloaded_dir
    if last_downloaded_dir and os.path.exists(last_downloaded_dir):
        try:
            # Open the folder in file explorer
            if os.name == 'nt':  # Windows
                os.startfile(last_downloaded_dir)
            elif os.name == 'posix':  # macOS and Linux
                subprocess.call(('xdg-open' if os.name == 'posix' else 'open', last_downloaded_dir))
            status_label.configure(text=f"Opened folder: {last_downloaded_dir}")
        except Exception as e:
            status_label.configure(text=f"Error opening folder: {str(e)}")
    else:
        status_label.configure(text="No folder to open")

open_folder_button = customtkinter.CTkButton(
    open_buttons_frame,
    text="📁 Open Folder",
    command=open_download_folder,
    fg_color=COLORS["bg_tertiary"],
    hover_color=COLORS["accent"],
    height=35,
    font=("Arial", 12, "bold"),
    corner_radius=8,
    width=150
)

# Initialize providers
PROVIDERS = {
    "MangaPill": MangaPill(),
    "MangaPark": Mangapark(),
    "MangaHere": MangaHere()
}

# Add a function to handle window resize
def on_window_resize(event):
    # Only handle resize events for the main window
    if event.widget == root:
        # Calculate new widths based on window size
        window_width = event.width
        left_width = max(min_left_width, int(window_width * 0.3))
        right_width = max(min_right_width, int(window_width * 0.7))
        
        # Update paned window sizes
        paned_window.paneconfigure(left_panel, minsize=left_width)
        paned_window.paneconfigure(right_panel, minsize=right_width)
        
        # Update text wrapping for manga description
        wrap_length = max(300, window_width - 350)
        manga_desc_label.configure(wraplength=wrap_length)
        manga_title_label.configure(wraplength=wrap_length)
        manga_info_label.configure(wraplength=wrap_length)
        
        # We don't need to reload images on resize anymore since we use fixed size

# Add a delay to resize handling to prevent too many updates
def debounce_resize(func, delay=250):
    """Debounce the resize event to prevent too many updates"""
    timer = None
    def debounced(*args, **kwargs):
        nonlocal timer
        if timer is not None:
            root.after_cancel(timer)
        timer = root.after(delay, lambda: func(*args, **kwargs))
    return debounced

# Replace direct binding with debounced version
root.unbind("<Configure>")
root.bind("<Configure>", debounce_resize(on_window_resize))


# Add sound effects for download actions
def play_sound(sound_type):
    try:
        import winsound
        if sound_type == "start":
            winsound.Beep(1000, 100)  # 1000 Hz for 100 ms
        elif sound_type == "complete":
            winsound.Beep(1500, 100)  # 1500 Hz for 100 ms
            time.sleep(0.1)
            winsound.Beep(1500, 100)
        elif sound_type == "error":
            winsound.Beep(500, 300)  # 500 Hz for 300 ms
    except:
        # If winsound is not available, silently fail
        pass

# Function to show open buttons after download
def show_open_buttons():
    # Show the buttons frame first
    open_buttons_frame.pack(fill=tk.X, padx=5, pady=5)
    
    # Use grid for better alignment
    open_file_button.grid(row=0, column=0, padx=10, pady=8, sticky="e")
    open_folder_button.grid(row=0, column=1, padx=10, pady=8, sticky="w")

# Function to hide open buttons
def hide_open_buttons():
    open_file_button.grid_forget()
    open_folder_button.grid_forget()
    open_buttons_frame.pack_forget()

# Function to clear all progress bars and reset the progress frame
def clear_progress_bars():
    # Remove any existing widgets in the progress frame
    for widget in progress_frame.winfo_children():
        widget.destroy()
    
    # Recreate the main progress bar
    global progress_bar, progress_label
    
    # Create a label for the progress bar
    progress_label = customtkinter.CTkLabel(
        progress_frame,
        text="Chapter Progress:",
        anchor="w",
        text_color=COLORS["text_primary"],
        font=("Arial", 11)
    )
    
    progress_bar = ttk.Progressbar(
        progress_frame, 
        orient="horizontal", 
        length=400, 
        mode="determinate",
        variable=progress_var
    )
    
    # Hide the progress frame
    progress_frame.pack_forget()

# Start the app
if __name__ == "__main__":
    root.mainloop()