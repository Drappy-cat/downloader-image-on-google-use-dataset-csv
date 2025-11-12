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
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# === CONFIG ===
CSV_FILE = "laptops_all_indonesia_fixed_v7.csv"
OUTPUT_DIR = "gambar_laptop_v8_fixed"
FAILED_JSON = "failed_downloads.json"
WAIT_TIME = 5
MAX_IMAGES = 3
os.makedirs(OUTPUT_DIR, exist_ok=True)

# === SANITIZE FILE NAME ===
def safe_filename(name):
    return "".join(c if c.isalnum() or c in (" ", "_", "-") else "_" for c in name).strip()

# === LOAD MODEL ===
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = models.resnet50(pretrained=True).to(device)
model.eval()
LABELS = requests.get("https://raw.githubusercontent.com/pytorch/hub/master/imagenet_classes.txt").text.splitlines()
preprocess = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485,0.456,0.406], std=[0.229,0.224,0.225]),
])

def is_laptop(img_bytes):
    try:
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        inp = preprocess(img).unsqueeze(0).to(device)
        with torch.no_grad(): preds = model(inp)
        top5 = [LABELS[i] for i in preds[0].topk(5).indices]
        return any(k in str(top5).lower() for k in ["laptop","notebook","macbook","computer"])
    except: return False

# === SELENIUM SETUP ===
def start_browser():
    opts = Options()
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--headless=new")
    opts.add_argument("window-size=1280,1024")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)

driver = start_browser()

def restart_browser():
    global driver
    try: driver.quit()
    except: pass
    driver = start_browser()

# === IMAGE SEARCHERS ===
def google_images(q):
    driver.get(f"https://www.google.com/search?q={q}+laptop&tbm=isch")
    time.sleep(WAIT_TIME)
    urls=[]
    for el in driver.find_elements(By.CSS_SELECTOR,"img.Q4LuWd")[:MAX_IMAGES]:
        try:
            el.click(); time.sleep(WAIT_TIME)
            srcs=driver.find_elements(By.CSS_SELECTOR,"img.n3VNCb")
            for s in srcs:
                u=s.get_attribute("src")
                if u and u.startswith("http"): urls.append(u); break
        except: continue
    return urls

def bing_images(q):
    driver.get(f"https://www.bing.com/images/search?q={q}+laptop")
    time.sleep(WAIT_TIME)
    return [i.get_attribute("src") for i in driver.find_elements(By.CSS_SELECTOR,"img.mimg")[:MAX_IMAGES] if i.get_attribute("src")]

def duckduckgo_images(q):
    driver.get(f"https://duckduckgo.com/?q={q}+laptop&iax=images&ia=images")
    time.sleep(WAIT_TIME)
    return [i.get_attribute("src") for i in driver.find_elements(By.CSS_SELECTOR,"img.tile--img__img")[:MAX_IMAGES] if i.get_attribute("src")]

# === SAVE IMAGE ===
def save_image(url, fname):
    try:
        r=requests.get(url,timeout=10)
        if not r.ok: return False
        if not is_laptop(r.content): return False
        img=Image.open(io.BytesIO(r.content)).convert("RGB")
        img.save(fname,"JPEG",quality=90)
        return True
    except: return False

# === MAIN PROCESS ===
searchers=[("Google",google_images),("Bing",bing_images),("DuckDuckGo",duckduckgo_images)]
failed=[]

if os.path.exists(FAILED_JSON):
    with open(FAILED_JSON,"r",encoding="utf-8") as f:
        try: failed=json.load(f)
        except: failed=[]

with open(CSV_FILE,encoding="utf-8") as f:
    reader=csv.DictReader(f)
    for row in reader:
        q=f"{row.get('brand','')} {row.get('model','')}".strip()
        fname=os.path.join(OUTPUT_DIR,safe_filename(q)+".jpg")
        if os.path.exists(fname): continue
        print(f"\n🔍 Memproses: {q}")
        ok=False
        for name,func in searchers:
            try: urls=func(q)
            except Exception:
                restart_browser()
                urls=[]
            for i,u in enumerate(urls[:MAX_IMAGES]):
                print(f"   🔁 {name} percobaan {i+1}")
                if save_image(u,fname):
                    print(f"✅ {fname} tersimpan dari {name}")
                    ok=True; break
            if ok: break
        if not ok:
            failed.append(q)
            print(f"❌ Gagal total untuk {q}")
        if len(failed)%10==0:
            with open(FAILED_JSON,"w",encoding="utf-8") as f: json.dump(failed,f,indent=2)

# === RETRY FAILED ===
if failed:
    print("\n🔁 Re-download gambar gagal...")
    retry=[]
    for q in failed:
        fname=os.path.join(OUTPUT_DIR,safe_filename(q)+".jpg")
        ok=False
        for name,func in searchers:
            try: urls=func(q)
            except Exception:
                restart_browser(); urls=[]
            for i,u in enumerate(urls[:MAX_IMAGES]):
                if save_image(u,fname):
                    ok=True; break
            if ok: break
        if not ok: retry.append(q)
    with open(FAILED_JSON,"w",encoding="utf-8") as f: json.dump(retry,f,indent=2)
    print(f"📄 Masih gagal: {len(retry)}")
else:
    print("✅ Semua gambar berhasil diunduh.")

driver.quit()
print("🎉 Selesai.")