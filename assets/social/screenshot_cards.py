"""
Screenshot all social cards into PNG files using Selenium + headless Chrome.
Selenium 4.x Selenium Manager auto-downloads the matching ChromeDriver.
"""
import os
import sys
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

SOCIAL_DIR = Path(r"C:\Users\Josep\Documents\smart-pick-pro-pd\assets\social")
OUT_DIR = SOCIAL_DIR / "png"
OUT_DIR.mkdir(exist_ok=True)

CARDS = [
    ("ig_slide_1_hook.html",     1080, 1080, "ig_slide_1_hook"),
    ("ig_slide_2_gold_wins.html",1080, 1080, "ig_slide_2_gold_wins"),
    ("ig_slide_3_more_wins.html",1080, 1080, "ig_slide_3_more_wins"),
    ("ig_slide_4_cta.html",      1080, 1080, "ig_slide_4_cta"),
    ("twitter_x_card.html",      1200,  675, "twitter_x_card"),
    ("facebook_card.html",       1200,  630, "facebook_card"),
    ("stories_tiktok.html",      1080, 1920, "stories_tiktok"),
]

def make_driver(width, height):
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--force-device-scale-factor=1")
    opts.add_argument(f"--window-size={width},{height}")
    # Hide automation flags so fonts/rendering are clean
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    driver = webdriver.Chrome(options=opts)
    driver.set_window_size(width, height)
    return driver

def screenshot_card(html_file, width, height, out_name):
    path = SOCIAL_DIR / html_file
    if not path.exists():
        print(f"  SKIP (not found): {html_file}")
        return False
    url = path.as_uri()
    driver = make_driver(width, height)
    try:
        driver.get(url)
        # Wait for fonts/animations to settle
        time.sleep(2)
        out_path = OUT_DIR / f"{out_name}.png"
        driver.save_screenshot(str(out_path))
        size = out_path.stat().st_size
        print(f"  SAVED: {out_path.name}  ({width}x{height})  {size//1024} KB")
        return True
    except Exception as e:
        print(f"  ERROR: {html_file} -> {e}")
        return False
    finally:
        driver.quit()

def main():
    print(f"Output dir: {OUT_DIR}\n")
    ok = 0
    for html_file, w, h, name in CARDS:
        print(f"Screenshotting {html_file} ...")
        if screenshot_card(html_file, w, h, name):
            ok += 1
    print(f"\nDone: {ok}/{len(CARDS)} screenshots saved to {OUT_DIR}")

if __name__ == "__main__":
    main()
