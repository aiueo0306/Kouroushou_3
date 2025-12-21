from feedgen.feed import FeedGenerator
from datetime import datetime, timezone
import os
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.mhlw.go.jp/stf/shingi/indexshingi.html"


# ==================================================
# RSS生成（UTF-8 BOM付きで保存：Windows文字化け対策）
# GUIDは URL + 更新日（同一URLでも更新日が変われば別アイテム扱いになりやすい）
# ==================================================
def generate_rss(items, output_path):
    fg = FeedGenerator()
    fg.title("審議会・研究会等（NEW）")
    fg.link(href=BASE_URL)
    fg.description("厚生労働省 審議会・研究会等のNEW更新のみ")
    fg.language("ja")

    for item in items:
        entry = fg.add_entry()
        entry.title(item["title"])
        entry.link(href=item["link"])
        entry.description(item["description"])

        # ✅ GUID：URLだけだと既読固定になりがちなので「URL#日付」にする
        # pubdateが無い場合はURLのみ（保険）
        if item.get("pubdate"):
            guid = f'{item["link"]}#{item["pubdate"]}'
        else:
            guid = item["link"]
        entry.guid(guid, permalink=False)

        # ✅ pubDate：ページ側の更新日を優先
        if item.get("pubdate"):
            # time datetime="YYYY-MM-DD" を UTC の 00:00 として扱う
            dt = datetime.fromisoformat(item["pubdate"]).replace(tzinfo=timezone.utc)
            entry.pubDate(dt)
        else:
            entry.pubDate(datetime.now(timezone.utc))

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # FeedGeneratorはUTF-8 bytesを返す → BOM付きで保存（メモ帳でも文字化けしない）
    rss_text = fg.rss_str(pretty=True).decode("utf-8")
    with open(output_path, "w", encoding="utf-8-sig", newline="\n") as f:
        f.write(rss_text)


# ==================================================
# NEW項目取得（span.m-listLink__link 単位で正確判定）
# ==================================================
def fetch_items_new_only():
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
    seen = set()  # 「URL#日付」で重複排除する

    # ★ 重要：span.m-listLink__link 単位で NEW 判定
    for span in soup.select("span.m-listLink__link"):

        # この span 自体に NEW アイコンがあるか？
        if not span.select_one(".m-icnNew, .toggleIcnNew"):
            continue

        a = span.select_one("a[href]")
        if not a:
            continue

        title = " ".join(a.get_text(" ", strip=True).split())
        link = urljoin(BASE_URL, a.get("href"))

        # 更新日（<time datetime="YYYY-MM-DD">）
        time_tag = span.select_one("time[datetime]")
        pubdate = time_tag["datetime"] if time_tag else None

        description = title
        if pubdate:
            description = f"{title}（更新日: {pubdate}）"

        # ✅ 重複排除：GUIDに合わせて URL#pubdate をキーにする
        key = f"{link}#{pubdate}" if pubdate else link
        if key in seen:
            continue
        seen.add(key)

        items.append({
            "title": title,
            "link": link,
            "description": description,
            "pubdate": pubdate,  # "YYYY-MM-DD" or None
        })

    return items


# ==================================================
# メイン処理
# ==================================================
if __name__ == "__main__":
    print("▶ ページHTMLを取得中（requests）...")

    try:
        items = fetch_items_new_only()
    except Exception as e:
        print("⚠ 取得に失敗しました:", e)
        raise SystemExit(1)

    print(f"▶ NEW抽出件数: {len(items)}")
    if not items:
        print("⚠ NEWに該当する項目がありませんでした。")

    rss_path = "rss_output/shingi_new.xml"
    generate_rss(items, rss_path)

    print("\n✅ RSSフィード生成完了！")
    print(f"📄 保存先: {rss_path}")
