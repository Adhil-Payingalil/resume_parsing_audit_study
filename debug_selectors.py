from playwright.sync_api import sync_playwright
import time
import os

# Constants
GREENHOUSE_URL = "https://my.greenhouse.io/jobs"
CONTEXT_DIR = "data/browser_context"

def debug_selectors():
    with sync_playwright() as p:
        # Launch browser
        if os.path.exists(CONTEXT_DIR):
            print(f"Loading context from {CONTEXT_DIR}")
            browser = p.chromium.launch_persistent_context(
                user_data_dir=CONTEXT_DIR,
                headless=False,
                args=['--no-sandbox', '--disable-blink-features=AutomationControlled']
            )
            page = browser.pages[0]
        else:
            print("Starting new browser")
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()

        print(f"Navigating to {GREENHOUSE_URL}")
        page.goto(GREENHOUSE_URL)
        page.wait_for_load_state('networkidle')
        
        print("Page loaded. Inspecting for location input...")
        
        # Selectors to test
        selectors = [
            "input[placeholder*='location' i]",
            "input[placeholder*='city' i]", 
            "input[placeholder*='where' i]",
            "input[placeholder*='Location']",
            "[class*='location'] input",
            "[data-testid*='location'] input",
            "input[type='text']:near(text=Location)",
            "input[type='search']",
            "#location",
            "[aria-label*='location' i]"
        ]
        
        found = False
        for s in selectors:
            try:
                el = page.query_selector(s)
                if el and el.is_visible():
                    print(f"✅ FOUND selector: {s}")
                    # Highlight it
                    el.evaluate("el => el.style.border = '5px solid red'")
                    found = True
                else:
                    print(f"❌ Not found/visible: {s}")
            except Exception as e:
                print(f"Error checking {s}: {e}")
                
        if not found:
            print("\nDumping page content to debug_page.html...")
            with open("debug_page.html", "w", encoding="utf-8") as f:
                f.write(page.content())
            print("Please check debug_page.html to see what the scraper sees.")
        
        print("\nKeeping browser open for 30 seconds...")
        time.sleep(30)
        browser.close()

if __name__ == "__main__":
    debug_selectors()
