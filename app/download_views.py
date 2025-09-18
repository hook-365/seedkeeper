#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import os
import time
import re
from urllib.parse import urljoin, quote

def sanitize_filename(filename):
    """Sanitize filename for filesystem compatibility"""
    # Replace problematic characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Remove leading/trailing dots and spaces
    filename = filename.strip('. ')
    # Limit length
    if len(filename) > 200:
        filename = filename[:200]
    return filename if filename else 'unnamed'

def download_views():
    base_url = "https://lightward.com/views"
    views_dir = "views"
    three_perspectives_dir = os.path.join(views_dir, "3-perspectives")
    
    print(f"Downloading content from {base_url}")
    
    # Create directories if they don't exist
    if not os.path.exists(views_dir):
        os.makedirs(views_dir)
        print(f"Created directory: {views_dir}")
    
    if not os.path.exists(three_perspectives_dir):
        os.makedirs(three_perspectives_dir)
        print(f"Created directory: {three_perspectives_dir}")
    
    # Core perspectives to watch for
    CORE_PERSPECTIVES = {
        '2x2', 'ai', 'antideferent', 'antiharmful', 'body-of-knowledge',
        'change', 'chicago', 'coherence', 'creation', 'cursor',
        'hello-biped', 'jansan', 'kenrel', 'machinist', 'metabolisis',
        'metastable', 'ness', 'pattern-ladder', 'recognition', 'resolver',
        'riverwalk-mandate', 'scoped', 'syzygy', 'the-game', 'the-one',
        'this-has-three-parts', 'three-body', 'three-two-one-go',
        'unknown', 'unknown-2', 'waterline', 'wellll', 'writing-is-wiring'
    }
    
    # Get the main index page
    try:
        response = requests.get(base_url, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching main page: {e}")
        return
    
    # Parse the HTML
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Find all links to individual views
    links = soup.find_all('a', href=True)
    view_links = []
    
    for link in links:
        href = link['href']
        # Filter for relative links that are views (URL encoded paths)
        if href.startswith('/') and not href.startswith('/views') and not href.endswith('.txt') and '/' not in href[1:]:
            # These are the view links like /10%25-revolt, /2x2, etc.
            view_links.append(href)
    
    # Remove duplicates and sort
    view_links = sorted(set(view_links))
    
    print(f"Found {len(view_links)} views to download")
    
    # Download each view
    for i, view_path in enumerate(view_links, 1):
        # Extract the view name from the path (remove leading /)
        view_name = view_path[1:] if view_path.startswith('/') else view_path
        # The actual URL is base_url + view_path
        view_url = f"https://lightward.com{view_path}"
        
        print(f"[{i}/{len(view_links)}] Downloading: {view_name}")
        
        try:
            # Download the content
            response = requests.get(view_url, timeout=30)
            response.raise_for_status()
            
            # Parse the content
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find the main content area
            # Look for article, main, or div with content
            content = None
            for tag in ['article', 'main']:
                content_elem = soup.find(tag)
                if content_elem:
                    content = content_elem.get_text(separator='\n', strip=True)
                    break
            
            if not content:
                # Fallback to body content
                body = soup.find('body')
                if body:
                    # Remove script and style elements
                    for script in body(["script", "style"]):
                        script.decompose()
                    content = body.get_text(separator='\n', strip=True)
            
            if content:
                # Save the content
                safe_filename = sanitize_filename(view_name)
                
                # Check if this is a core perspective
                is_core = safe_filename in CORE_PERSPECTIVES or safe_filename.replace('-', '_') in CORE_PERSPECTIVES
                
                if is_core:
                    # Save core perspectives in the 3-perspectives directory
                    file_path = os.path.join(three_perspectives_dir, f"{safe_filename}.txt")
                    print(f"  🌟 Core perspective detected: {safe_filename}")
                else:
                    file_path = os.path.join(views_dir, f"{safe_filename}.txt")
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(f"# {view_name}\n\n")
                    f.write(content)
                
                print(f"  ✓ Saved to {file_path}")
            else:
                print(f"  ⚠ No content found for {view_name}")
            
            # Be polite and avoid hammering the server
            time.sleep(0.2)  # Reduced delay for faster downloads
            
        except requests.exceptions.RequestException as e:
            print(f"  ✗ Error downloading {view_name}: {e}")
        except Exception as e:
            print(f"  ✗ Unexpected error for {view_name}: {e}")
    
    print("\nDownload complete!")
    
    # Also download the views.txt file if it exists
    try:
        print("\nDownloading views.txt...")
        response = requests.get(f"{base_url}.txt", timeout=30)
        response.raise_for_status()
        
        with open(os.path.join(views_dir, "views.txt"), 'w', encoding='utf-8') as f:
            f.write(response.text)
        print("  ✓ Saved views.txt")
    except:
        print("  ⚠ Could not download views.txt")

if __name__ == "__main__":
    download_views()