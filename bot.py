import os
import time
import csv
import io
import requests
from PIL import Image
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

# === KONFIGURASI ===
CSV_FILE = "laptops_all_indonesia_fixed_v7.csv"
OUTPUT_DIR = "gambar_laptop"
WAIT_TIME = 4
MAX_IMAGES = 1

# === SETUP WEBDRIVER ===
options = Options()
# Jalankan dengan tampilan agar klik berfungsi
# (kalau headless, klik sering gagal)
# options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("start-maximized")
options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
os.makedirs(OUTPUT_DIR, exist_ok=True)


def save_as_jpg(url, filename):
    """Download gambar dan ubah ke JPG"""
    try:
        resp = requests.get(url, timeout=10)
        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        if not filename.lower().endswith(".jpg"):
            filename = filename.rsplit(".", 1)[0] + ".jpg"
        img.save(filename, "JPEG", quality=90)
        print(f"✅ Gambar disimpan: {filename}")
    except Exception as e:
        print(f"⚠️ Gagal download {filename}: {e}")


def get_google_image(query):
    """Ambil gambar besar dari Google Images"""
    search_url = f"https://www.google.com/search?q={query}+laptop&tbm=isch"
    driver.get(search_url)
    time.sleep(WAIT_TIME)

    thumbnails = driver.find_elements(By.CSS_SELECTOR, "img.Q4LuWd, img.YQ4gaf, img.rg_i")
    if not thumbnails:
        return None

    try:
        thumbnails[0].click()  # klik gambar kecil pertama
        time.sleep(WAIT_TIME + 1)
        big_images = driver.find_elements(By.CSS_SELECTOR, "img.sFlh5c, img.n3VNCb")
        for img in big_images:
            src = img.get_attribute("src")
            if src and src.startswith("http"):
                return src
    except Exception:
        return None
    return None


def get_bing_image(query):
    """Fallback ke Bing"""
    search_url = f"https://www.bing.com/images/search?q={query}+laptop"
    driver.get(search_url)
    time.sleep(WAIT_TIME)

    try:
        thumbs = driver.find_elements(By.CSS_SELECTOR, "img.mimg")
        if not thumbs:
            return None
        thumbs[0].click()
        time.sleep(WAIT_TIME + 1)
        bigs = driver.find_elements(By.CSS_SELECTOR, "img.nofocus")
        for img in bigs:
            src = img.get_attribute("src")
            if src and src.startswith("http"):
                return src
    except Exception:
        return None
    return None


with open(CSV_FILE, newline='', encoding='utf-8') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        brand = str(row.get("brand", ""))
        model = str(row.get("model", ""))
        query = f"{brand} {model}"

        print(f"\n🔍 Mencari: {query}")
        img_url = get_google_image(query)

        if not img_url:
            print(f"⚠️ Google gagal, coba Bing...")
            img_url = get_bing_image(query)

        if img_url:
            safe_name = f"{brand}_{model}".replace("/", "_").replace(" ", "_")
            filename = os.path.join(OUTPUT_DIR, f"{safe_name}.jpg")
            save_as_jpg(img_url, filename)
        else:
            print(f"🚫 Tidak ditemukan gambar untuk {query}")

driver.quit()
print("\n✅ Proses selesai.")