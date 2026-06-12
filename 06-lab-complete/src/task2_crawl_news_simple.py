"""
Task 2 — Crawl bài báo (Alternative: Dùng requests thay vì Crawl4AI)

Vì Playwright download browser rất lâu, tôi tạo phiên bản backup dùng requests + BeautifulSoup.
Nhanh hơn nhưng kết quả có thể không đầy đủ bằng Crawl4AI.
"""

import json
import requests
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup

DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "news"
URLS_FILE = DATA_DIR / "urls_to_crawl.txt"


def load_urls_from_file():
    """Load URLs from file."""
    if not URLS_FILE.exists():
        print(f"Khong tim thay file: {URLS_FILE}")
        return []

    urls = []
    with open(URLS_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                urls.append(line)
    return urls


def crawl_article_simple(url: str) -> dict:
    """
    Crawl bài báo dùng requests + BeautifulSoup (không cần browser).
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'html.parser')

    # Extract title
    title = soup.find('title')
    title = title.get_text().strip() if title else "Unknown Title"

    # Extract article content (try common selectors)
    content = ""

    # Try common article content selectors
    article_selectors = [
        'article',
        '.article-content',
        '.content-detail',
        '.fck_detail',
        '.detail-content',
        'div[itemprop="articleBody"]'
    ]

    for selector in article_selectors:
        article_div = soup.select_one(selector)
        if article_div:
            # Get all paragraphs
            paragraphs = article_div.find_all(['p', 'h2', 'h3'])
            content = '\n\n'.join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])
            if content:
                break

    # Fallback: get all paragraphs
    if not content:
        paragraphs = soup.find_all('p')
        content = '\n\n'.join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])

    return {
        "url": url,
        "title": title,
        "date_crawled": datetime.now().isoformat(),
        "content_markdown": content,
        "word_count": len(content.split()) if content else 0,
        "method": "requests+beautifulsoup"
    }


def crawl_all_simple():
    """Crawl all articles using simple method."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    urls = load_urls_from_file()

    if not urls:
        print("\nChua co URLs de crawl!")
        print(f"Them URLs vao file: {URLS_FILE}")
        return

    print("=" * 60)
    print(f"Task 2: Crawl {len(urls)} bai bao (Simple Method)")
    print("=" * 60)

    success_count = 0
    for i, url in enumerate(urls, 1):
        print(f"\n[{i}/{len(urls)}] Crawling: {url}")
        try:
            article = crawl_article_simple(url)

            # Save JSON
            filename = f"article_{i:02d}.json"
            filepath = DATA_DIR / filename
            filepath.write_text(json.dumps(article, ensure_ascii=False, indent=2), encoding='utf-8')

            # Safe print for Windows console
            safe_title = article['title'][:60].encode('ascii', 'ignore').decode('ascii')
            print(f"  Title: {safe_title}... (len={len(article['title'])})")
            print(f"  Words: {article['word_count']:,}")
            print(f"  Saved: {filepath.name}")
            success_count += 1
        except Exception as e:
            print(f"  Error: {str(e)[:100]}")

    print("\n" + "=" * 60)
    print(f"HOAN THANH! Crawled {success_count}/{len(urls)} bai bao")
    print(f"Output: {DATA_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    crawl_all_simple()
