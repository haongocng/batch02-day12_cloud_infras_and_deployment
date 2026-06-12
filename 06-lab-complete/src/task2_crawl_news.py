"""
Task 2 — Crawl bài báo về nghệ sĩ liên quan tới ma tuý.

Hướng dẫn:
    1. Crawl tối thiểu 5 bài báo từ các trang tin tức Việt Nam.
    2. Sử dụng Crawl4AI hoặc thư viện crawling tương tự.
    3. Lưu output vào data/landing/news/
    4. Mỗi bài lưu 1 file JSON với metadata (url, title, date_crawled, content).

Cài đặt:
    pip install crawl4ai
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "news"
URLS_FILE = DATA_DIR / "urls_to_crawl.txt"


def setup_directory():
    """Tạo thư mục data/landing/news/ nếu chưa có."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_urls_from_file() -> list[str]:
    """
    Đọc URLs từ file urls_to_crawl.txt

    Returns:
        List of URLs (bỏ qua dòng trống và comment)
    """
    if not URLS_FILE.exists():
        print(f"Khong tim thay file: {URLS_FILE}")
        print("Tao file urls_to_crawl.txt va them URLs vao")
        return []

    urls = []
    with open(URLS_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Bỏ qua dòng trống và comment
            if line and not line.startswith('#'):
                urls.append(line)

    return urls


# Đọc URLs từ file
ARTICLE_URLS = load_urls_from_file()


async def crawl_article(url: str) -> dict:
    """
    Crawl một bài báo và trả về dict chứa metadata + content.

    Returns:
        {
            "url": str,
            "title": str,
            "date_crawled": str (ISO format),
            "content_markdown": str
        }
    """
    from crawl4ai import AsyncWebCrawler

    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=url)

        # Extract title from metadata hoặc từ content
        title = result.metadata.get("title", "Unknown Title")
        if title == "Unknown Title" and hasattr(result, 'html'):
            # Fallback: extract từ HTML nếu cần
            import re
            title_match = re.search(r'<title>(.*?)</title>', result.html)
            if title_match:
                title = title_match.group(1)

        return {
            "url": url,
            "title": title,
            "date_crawled": datetime.now().isoformat(),
            "content_markdown": result.markdown,
            "word_count": len(result.markdown.split()) if result.markdown else 0,
        }


async def crawl_all():
    """Crawl toàn bộ bài báo trong ARTICLE_URLS."""
    setup_directory()

    print("=" * 60)
    print(f"Task 2: Crawl {len(ARTICLE_URLS)} bài báo")
    print("=" * 60)

    success_count = 0
    for i, url in enumerate(ARTICLE_URLS, 1):
        print(f"\n[{i}/{len(ARTICLE_URLS)}] Crawling: {url}")
        try:
            article = await crawl_article(url)

            # Lưu file JSON
            filename = f"article_{i:02d}.json"
            filepath = DATA_DIR / filename
            filepath.write_text(json.dumps(article, ensure_ascii=False, indent=2), encoding='utf-8')

            print(f"  Title: {article['title'][:60]}...")
            print(f"  Words: {article['word_count']:,}")
            print(f"  Saved: {filepath.name}")
            success_count += 1
        except Exception as e:
            # Avoid encoding errors on Windows console
            error_msg = str(e).encode('ascii', 'ignore').decode('ascii')
            print(f"  Error: {error_msg[:200]}")

    print("\n" + "=" * 60)
    print(f"HOAN THANH! Crawled {success_count}/{len(ARTICLE_URLS)} bai bao")
    print(f"Output: {DATA_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    if not ARTICLE_URLS:
        print("\nChua co URLs de crawl!")
        print(f"Them URLs vao file: {URLS_FILE}")
        print("Moi URL 1 dong, bo qua dong trong va dong bat dau bang #")
        print("\nVi du noi dung file:")
        print("  https://vnexpress.net/bai-bao-1.html")
        print("  https://tuoitre.vn/bai-bao-2.html")
        print("  # Comment nay se bi bo qua")
        print("  https://thanhnien.vn/bai-bao-3.html")
    else:
        print(f"\nDoc duoc {len(ARTICLE_URLS)} URLs tu {URLS_FILE}")
        asyncio.run(crawl_all())
