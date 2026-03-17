import requests
import pandas as pd
import time
import re
import urllib3

from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


TELEGRAM_TOKEN = "YOUR_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID"

SEARCH_QUERY = "data analyst OR аналитик данных"
PER_PAGE = 20
PAGES = 3
MIN_SCORE = 2.0

SKILLS = {
    "python": 1.5,
    "sql": 1.7,
    "pandas": 1.3,
    "numpy": 0.8,
    "excel": 0.7,
    "git": 0.6,
    "github": 0.5,
    "tableau": 0.5,
    "superset": 0.5,
    "datalens": 0.5,
    "a b": 1.2,
    "ab test": 1.2,
    "статистика": 1.2,
    "метрики": 1.0,
}

GOOD_TITLES = [
    "data analyst",
    "аналитик данных",
    "product analyst",
    "продуктовый аналитик",
    "bi analyst",
    "bi аналитик",
    "web analyst",
    "web аналитик",
    "crm analyst",
    "crm аналитик"
]

sent_urls = set()

def clean(text):
    return re.sub(r'\W+', ' ', text.lower())

def skill_score(text):
    return sum(w for skill, w in SKILLS.items() if skill in text)

def title_score(title):
    t = clean(title)
    return 2 if any(x in t for x in GOOD_TITLES) else 0

def bonus_score(text):
    b = 0
    if "intern" in text or "стаж" in text:
        b += 1.5
    if "junior" in text:
        b += 1
    return b

def penalty_score(text):
    t = text.lower()
    p = 0
    if "1 год" in t or "1-3" in t or "2 года" in t:
        p += 0.5
    if "middle" in text:
        p += 2.0
    if "senior" in text:
        p += 3
    if "3 года" in text:
        p += 2
    return p

def stack_bonus(text):
    b = 0
    if "python" in text and "sql" in text:
        b += 1.5
    return b

def explain(text):
    reasons = []
    for s in SKILLS:
        if s in text:
            reasons.append(s)
    return ", ".join(reasons)

def get_vacancies():
    vac = []

    for page in range(PAGES):
        r = requests.get(
            "https://api.hh.ru/vacancies",
            params={"text": SEARCH_QUERY, "per_page": PER_PAGE, "page": page},
            verify=False
        )

        for item in r.json().get("items", []):
            snippet = item.get("snippet") or {}

            text = (
                (snippet.get("requirement") or "") +
                (snippet.get("responsibility") or "")
            )

            if not text.strip():
                continue

            vac.append({
                "title": item["name"],
                "url": item["alternate_url"],
                "text": text
            })

    return vac

def process(vacancies):
    res = []

    for v in vacancies:
        text = clean(v["text"])

        s = skill_score(text)
        t = title_score(v["title"])
        b = bonus_score(text)
        p = penalty_score(text)
        sb = stack_bonus(text)

        score = s + t + b + sb - p

        reason = explain(text)

        print(v["title"], score)

        if score >= MIN_SCORE:
            v["score"] = round(score, 2)
            v["reason"] = reason
            res.append(v)

    return sorted(res, key=lambda x: x["score"], reverse=True)

def save(results):
    wb = Workbook()
    ws = wb.active

    ws.append(["Название", "Score", "Причины", "Ссылка"])

    green = PatternFill(start_color="C6EFCE", fill_type="solid")
    yellow = PatternFill(start_color="FFEB9C", fill_type="solid")

    for r in results:
        ws.append([r["title"], r["score"], r["reason"], r["url"]])
        row = ws.max_row

        fill = green if r["score"] >= 5 else yellow

        for col in range(1, 5):
            ws.cell(row=row, column=col).fill = fill

    wb.save("hh_results.xlsx")
    print("✅ Excel готов")

def send(results):
    new = [r for r in results if r["url"] not in sent_urls]

    if not new:
        ("📭 Нет новых")
        return

    for r in new[:5]:
        data = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": f"{r['title']}\n📊 {r['score']}",
            "reply_markup": {
                "inline_keyboard": [[
                    {"text": "Открыть вакансию", "url": r["url"]}
                ]]
            }
        }

        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json=data
        )

        print("Telegram status:", resp.status_code)

        sent_urls.add(r["url"])

def main():
    while True:
        print("🔄 Поиск...")

        vac = get_vacancies()
        res = process(vac)

        save(res)
        send(res)

        print(f"✅ Готово | Всего: {len(vac)} | Подошло: {len(res)}")
        print("⏳ Ждём 10 минут\n")

        time.sleep(600)

if __name__ == "__main__":
    main()