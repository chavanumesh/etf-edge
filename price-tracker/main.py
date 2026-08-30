"""
Price & Offer Tracker
----------------------
Reads a list of product URLs from products.txt, checks current price,
compares to target price, and emails you an alert if the price drops.

Run manually with:  python main.py
Runs automatically every 6 hours via GitHub Actions (see .github/workflows/tracker.yml)
"""

import os
import re
import json
import sqlite3
import smtplib
from email.mime.text import MIMEText

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import google.generativeai as genai

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(SCRIPT_DIR, "tracker.db")
PRODUCTS_FILE = os.path.join(SCRIPT_DIR, "products.txt")


# ---------------------------------------------------------------------------
# Step 1: Database setup
# ---------------------------------------------------------------------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            title TEXT,
            last_price REAL,
            target_price REAL
        )
    """)
    conn.commit()
    conn.close()


def get_or_create_product(url: str, target_price: float, title: str, price: float):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT last_price FROM products WHERE url = ?", (url,))
    row = cursor.fetchone()

    if row is None:
        cursor.execute(
            "INSERT INTO products (url, title, last_price, target_price) VALUES (?, ?, ?, ?)",
            (url, title, price, target_price),
        )
        previous_price = None
    else:
        previous_price = row[0]
        cursor.execute(
            "UPDATE products SET last_price = ?, title = ? WHERE url = ?",
            (price, title, url),
        )

    conn.commit()
    conn.close()
    return previous_price


# ---------------------------------------------------------------------------
# Step 2: Extract product info from the target URL
# ---------------------------------------------------------------------------
def clean_url(url: str) -> str:
    """Removes tracking parameters from incoming links."""
    return url.split("?")[0]


def extract_product_identity(url: str) -> dict:
    """Renders page via Playwright and extracts baseline metadata."""
    clean_target = clean_url(url)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = context.new_page()
        page.goto(clean_target, wait_until="domcontentloaded", timeout=60000)
        html = page.content()
        browser.close()

    soup = BeautifulSoup(html, "html.parser")

    title, price, currency = None, None, None
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            if isinstance(data, dict) and data.get("@type") in ["Product", "IndividualProduct"]:
                title = data.get("name")
                offers = data.get("offers", {})
                if isinstance(offers, list) and len(offers) > 0:
                    offers = offers[0]
                price = offers.get("price")
                currency = offers.get("priceCurrency")
                break
        except Exception:
            continue

    if not title:
        og_title = soup.find("meta", property="og:title")
        title = og_title["content"] if og_title else "Unknown Item"

    return {
        "title": title,
        "price": float(price) if price else 0.0,
        "currency": currency or "INR",
        "url": clean_target,
        "html": html,
    }


# ---------------------------------------------------------------------------
# Step 3: Use Gemini free tier to find hidden bank/card offers
# ---------------------------------------------------------------------------
def parse_hidden_offers(html_content: str) -> list:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel("gemini-1.5-flash")
    prompt = f"""
    Analyze the following HTML text and extract any bank offers, card discounts, coupon codes,
    or cashback offers. Return ONLY a valid JSON array of strings containing the offer details.

    HTML Snippet:
    {html_content[:4000]}
    """
    try:
        response = model.generate_content(prompt)
        return json.loads(response.text)
    except Exception:
        return ["No special offers detected"]


# ---------------------------------------------------------------------------
# Step 4: Search competitor sites for the same product
# ---------------------------------------------------------------------------
def find_competitor_prices(product_title: str) -> list:
    query = f'"{product_title[:30]}" site:amazon.in OR site:flipkart.com OR site:croma.com'
    search_url = f"https://html.duckduckgo.com/html/?q={query}"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        response = requests.get(search_url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        results = []
        for link in soup.find_all("a", class_="result__url", limit=3):
            results.append(link["href"])
        return results
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Step 5: Send email alert via Gmail
# ---------------------------------------------------------------------------
def send_gmail_alert(subject: str, message: str):
    gmail_address = os.environ["GMAIL_ADDRESS"]
    gmail_app_password = os.environ["GMAIL_APP_PASSWORD"]

    msg = MIMEText(message)
    msg["Subject"] = subject
    msg["From"] = gmail_address
    msg["To"] = gmail_address

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_address, gmail_app_password)
        server.sendmail(gmail_address, gmail_address, msg.as_string())


# ---------------------------------------------------------------------------
# Step 6: Read product list (url, target_price per line)
# ---------------------------------------------------------------------------
def read_products_file():
    products = []
    if not os.path.exists(PRODUCTS_FILE):
        return products

    with open(PRODUCTS_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(",")
            url = parts[0].strip()
            target_price = float(parts[1].strip()) if len(parts) > 1 else 0.0
            products.append((url, target_price))
    return products


# ---------------------------------------------------------------------------
# Main routine
# ---------------------------------------------------------------------------
def main():
    init_db()
    products = read_products_file()

    if not products:
        print("No products found in products.txt. Add at least one URL to track.")
        return

    for url, target_price in products:
        print(f"Checking: {url}")
        try:
            info = extract_product_identity(url)
        except Exception as e:
            print(f"  Failed to fetch {url}: {e}")
            continue

        offers = parse_hidden_offers(info["html"])
        competitors = find_competitor_prices(info["title"])
        previous_price = get_or_create_product(url, target_price, info["title"], info["price"])

        price_dropped = target_price and info["price"] > 0 and info["price"] <= target_price
        price_changed = previous_price is not None and info["price"] != previous_price

        if price_dropped or price_changed:
            message = (
                f"Product: {info['title']}\n"
                f"Current Price: {info['currency']} {info['price']}\n"
                f"Previous Price: {previous_price}\n"
                f"Target Price: {target_price}\n\n"
                f"Offers found: {', '.join(offers)}\n\n"
                f"Competitor links:\n" + "\n".join(competitors) + "\n\n"
                f"Link: {info['url']}"
            )
            subject = "Price Drop Alert 🔔" if price_dropped else "Price Changed"
            send_gmail_alert(subject, message)
            print("  Alert sent.")
        else:
            print(f"  No alert needed. Current price: {info['price']}")


if __name__ == "__main__":
    main()
