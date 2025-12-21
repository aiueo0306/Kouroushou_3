from feedgen.feed import FeedGenerator
from datetime import datetime, timezone
import os
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.mhlw.go.jp/stf/kinnkyuuhininnyaku.html"


# ==================================================
# RSS生成（UTF-8 BOM付きで保存：Windows文字化け対策）
# GUIDはURLのみ（要望どおり）
# ==================================================
def generate_rss(items, output_path):
    fg = FeedGenerator()
    fg.title("緊急避妊薬（更新）")
    fg.link(href=BASE_URL)
    fg.description("厚生労働省「緊急避妊薬」ページ内リンク一覧")
    fg.language("ja")

    now_utc = datetime.now(timezone.utc)  # 日付が無いので共通の取得時刻を使う

    for item in items:
        entry = fg.add_entry()
        entry.title(item["title"])
        entry.link(href=item["link"])
        entry.description(item["description"])

        # ✅ GUID：URLのみ
        entry.guid(item["link"], permalink=False)

        # ✅ pubDate：日付が無いので取得時刻
        entry.pubDate(now_utc)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    rss_text = fg.rss_str(pretty=True).decode("utf-8")
    with open(output_path, "w", encoding="utf-8-sig", newline="\n") as f:
        f.write(rss_text)


# ==================================================
# div.l-contentMain 内の li を全部対象に href を拾う
# ==================================================
def fetch_items_all_li_links():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "ja-JP,ja;q=0.9",
    }

    r = requests.get(BASE_URL, headers=headers, timeout=30)
    r.raise_for_status()

    # 厚労省ページはUTF-8想定で固定（誤判定回避）
    html = r.content.decode("utf-8", errors="replace")
    soup = BeautifulSoup(html, "html.parser")

    items = []
    seen = set()  # URL単位で重複排除

    content = soup.select_one("div.l-contentMain")
    if not content:
        return items

    for li in content.select("li"):
        a = li.select_one("a[href]")
        if not a:
            continue

        title = " ".join(a.get_text(" ", strip=True).split())
        href = a.get("href")
        link = urljoin(BASE_URL, href)

        if not title:
            title = link  # 保険：テキストが空ならURLをタイトルに

        if link in seen:
            continue
        seen.add(link)

        items.append(
            {
                "title": title,
                "link": link,
                "description": title,
            }
        )

    return items


# ==================================================
# メイン処理
# ==================================================
if __name__ == "__main__":
    print("▶ ページHTMLを取得中（requests）...")

    try:
        items = fetch_items_all_li_links()
    except Exception as e:
        print("⚠ 取得に失敗しました:", e)
        raise SystemExit(1)

    print(f"▶ 抽出件数: {len(items)}")
    if not items:
        print("⚠ 対象の li/a[href] が見つかりませんでした。")

    rss_path = "rss_output/kinnkyuuhininnyaku.xml"
    generate_rss(items, rss_path)

    print("\n✅ RSSフィード生成完了！")
    print(f"📄 保存先: {rss_path}")
