import os
import time
import csv
import io
import requests
from PIL import Image
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager

# === KONFIGURASI ===
CSV_FILE = "laptops_all_indonesia_fixed_v7.csv"  # nama file dataset
OUTPUT_DIR = "gambar_laptop"                     # folder penyimpanan
WAIT_TIME = 4                                    # waktu tunggu
MAX_RETRY = 2                                    # jumlah percobaan ulang

# === SETUP SELENIUM CHROME ===
options = Options()
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

# === FUNGSI ===
def save_as_jpg(url, filename):
    """Download dan ubah gambar ke JPG"""
    try:
        resp = requests.get(url, timeout=10)
        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        if not filename.lower().endswith(".jpg"):
            filename = filename.rsplit(".", 1)[0] + ".jpg"
        img.save(filename, "JPEG", quality=92)
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
        # Klik thumbnail pertama 2x agar panel kanan terbuka
        actions = ActionChains(driver)
        actions.move_to_element(thumbnails[0]).click().perform()
        time.sleep(2)
        actions.click(thumbnails[0]).perform()
        time.sleep(WAIT_TIME + 1)

        # Scroll sedikit biar panel kanan kelihatan
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
        time.sleep(1)

        # Ambil gambar besar yang bukan base64
        big_images = driver.find_elements(By.XPATH, "//img[contains(@class,'n3VNCb') and not(contains(@src,'data:image'))]")
        for img in big_images:
            src = img.get_attribute("src")
            if src and src.startswith("http"):
                return src
    except Exception:
        return None
    return None


def get_bing_image(query):
    """Fallback ambil gambar dari Bing"""
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


# === PROSES UTAMA ===
with open(CSV_FILE, newline='', encoding='utf-8') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        brand = str(row.get("brand", "")).strip()
        model = str(row.get("model", "")).strip()
        query = f"{brand} {model}"

        safe_name = f"{brand}_{model}".replace("/", "_").replace(" ", "_")
        filename = os.path.join(OUTPUT_DIR, f"{safe_name}.jpg")

        # Skip kalau sudah ada
        if os.path.exists(filename):
            print(f"⏭️ Lewati (sudah ada): {filename}")
            continue

        print(f"\n🔍 Mencari: {query}")

        img_url = None
        for attempt in range(MAX_RETRY):
            img_url = get_google_image(query)
            if img_url:
                break
            print(f"⚠️ Google gagal (percobaan {attempt+1}), coba lagi...")
            time.sleep(2)

        if not img_url:
            print(f"⚠️ Google gagal total, coba Bing...")
            img_url = get_bing_image(query)

        if img_url:
            save_as_jpg(img_url, filename)
        else:
            print(f"🚫 Tidak ditemukan gambar untuk {query}")

driver.quit()
print("\n✅ Proses download selesai seluruhnya.")