import os
import io
import time
import csv
import json
import requests
from PIL import Image
import torch
from torchvision import models, transforms
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# === KONFIGURASI ===
CSV_FILE = "laptops_all_indonesia_fixed_v7.csv"
OUTPUT_DIR = "gambar_laptop_v8"
FAILED_JSON = "failed_downloads.json"
WAIT_TIME = 4
MAX_IMAGES_PER_SOURCE = 3

os.makedirs(OUTPUT_DIR, exist_ok=True)

# === LOAD MODEL DETEKSI LAPTOP ===
print("🧠 Memuat model deteksi laptop (ResNet50, pretrained ImageNet)...")
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model_cnn = models.resnet50(pretrained=True).to(device)
model_cnn.eval()

LABELS_URL = "https://raw.githubusercontent.com/pytorch/hub/master/imagenet_classes.txt"
LABELS = requests.get(LABELS_URL).text.splitlines()

preprocess = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406],
                         std=[0.229, 0.224, 0.225]),
])

def is_laptop_image(img_bytes):
    """Cek apakah gambar termasuk kategori laptop"""
    try:
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        input_tensor = preprocess(img).unsqueeze(0).to(device)
        with torch.no_grad():
            outputs = model_cnn(input_tensor)
            _, indices = torch.sort(outputs, descending=True)
            top5 = [LABELS[idx] for idx in indices[0][:5]]
        if any(word in str(top5).lower() for word in
               ["laptop", "notebook", "computer", "keyboard", "display", "monitor", "macbook"]):
            return True
        return False
    except Exception:
        return False


# === SETUP SELENIUM ===
options = Options()
options.add_argument("start-maximized")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)


def save_as_jpg(url, filename):
    """Download dan simpan gambar ke format JPG"""
    try:
        r = requests.get(url, timeout=10)
        if not is_laptop_image(r.content):
            print(f"🚫 {os.path.basename(filename)} dilewati (bukan laptop)")
            return False
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        filename = filename.rsplit(".", 1)[0] + ".jpg"
        img.save(filename, "JPEG", quality=90)
        print(f"✅ {os.path.basename(filename)} tersimpan.")
        return True
    except Exception as e:
        print(f"⚠️ Gagal menyimpan {filename}: {e}")
        return False


# === MESIN PENCARI ===
def get_google_images(query, max_images=3):
    search_url = f"https://www.google.com/search?q={query}+laptop&tbm=isch"
    driver.get(search_url)
    time.sleep(WAIT_TIME)
    thumbs = driver.find_elements(By.CSS_SELECTOR, "img.Q4LuWd, img.YQ4gaf, img.rg_i")
    results = []
    for idx, thumb in enumerate(thumbs[:max_images]):
        try:
            thumb.click()
            time.sleep(WAIT_TIME)
            srcs = driver.find_elements(By.CSS_SELECTOR, "img.n3VNCb")
            for s in srcs:
                url = s.get_attribute("src")
                if url and url.startswith("http") and "data:image" not in url:
                    results.append(url)
                    break
        except Exception:
            continue
    return results

def get_bing_images(query, max_images=3):
    url = f"https://www.bing.com/images/search?q={query}+laptop"
    driver.get(url)
    time.sleep(WAIT_TIME)
    results = []
    try:
        imgs = driver.find_elements(By.CSS_SELECTOR, "img.mimg")
        for i in imgs[:max_images]:
            src = i.get_attribute("src")
            if src and src.startswith("http"):
                results.append(src)
    except Exception:
        pass
    return results

def get_duckduckgo_images(query, max_images=3):
    url = f"https://duckduckgo.com/?q={query}+laptop&iax=images&ia=images"
    driver.get(url)
    time.sleep(WAIT_TIME)
    results = []
    try:
        imgs = driver.find_elements(By.CSS_SELECTOR, "img.tile--img__img")
        for i in imgs[:max_images]:
            src = i.get_attribute("src")
            if src and src.startswith("http"):
                results.append(src)
    except Exception:
        pass
    return results


# === PROSES DOWNLOAD DENGAN MULTI-SOURCE ===
def process_product(query, filename):
    """Coba download dari Google, Bing, DuckDuckGo"""
    searchers = [
        ("Google", get_google_images),
        ("Bing", get_bing_images),
        ("DuckDuckGo", get_duckduckgo_images)
    ]

    for name, func in searchers:
        print(f"🔍 Mencoba sumber: {name}")
        urls = func(query, MAX_IMAGES_PER_SOURCE)
        if not urls:
            print(f"⚠️ Tidak ada hasil dari {name}")
            continue

        for idx, url in enumerate(urls, 1):
            print(f"   🔁 Percobaan gambar ke-{idx}/{MAX_IMAGES_PER_SOURCE} ({name}) ...")
            if save_as_jpg(url, filename):
                return True
            time.sleep(1)

    return False


# === UTAMA ===
failed = []
if os.path.exists(FAILED_JSON):
    with open(FAILED_JSON, "r", encoding="utf-8") as f:
        try:
            failed = json.load(f)
        except Exception:
            failed = []

with open(CSV_FILE, newline='', encoding='utf-8') as csvfile:
    reader = csv.DictReader(csvfile)
    count = 0

    for row in reader:
        brand = str(row.get("brand", "")).strip()
        model = str(row.get("model", "")).strip()
        query = f"{brand} {model}"
        safe_name = f"{brand}_{model}".replace("/", "_").replace(" ", "_")
        filename = os.path.join(OUTPUT_DIR, f"{safe_name}.jpg")

        if os.path.exists(filename):
            print(f"⏭️ Lewati (sudah ada): {filename}")
            continue

        print(f"\n🔍 Memproses: {query}")
        ok = process_product(query, filename)
        if not ok:
            print(f"❌ Gagal total untuk {query}")
            failed.append(query)

        count += 1
        if count % 10 == 0:
            with open(FAILED_JSON, "w", encoding="utf-8") as f:
                json.dump(failed, f, indent=2)
            print(f"💾 Progress disimpan ({count} produk).")

# === COBA ULANG UNTUK YANG GAGAL ===
if failed:
    print("\n🔁 Mencoba ulang download gambar yang gagal...")
    still_failed = []
    for query in failed:
        safe_name = query.replace("/", "_").replace(" ", "_")
        filename = os.path.join(OUTPUT_DIR, f"{safe_name}.jpg")
        ok = process_product(query, filename)
        if not ok:
            still_failed.append(query)

    with open(FAILED_JSON, "w", encoding="utf-8") as f:
        json.dump(still_failed, f, indent=2)

    print(f"\n📄 {len(still_failed)} produk masih gagal. Daftar disimpan di {FAILED_JSON}")
else:
    print("\n✅ Semua gambar berhasil diunduh.")

driver.quit()
print("\n🎉 Selesai! Semua proses multi-source berhasil dijalankan.")