import time, random, os, cv2, numpy as np


def _human_scroll(page):
    """Scroll down to bottom then back up like a human."""
    # get total page height
    total_height = page.evaluate("document.body.scrollHeight")
    current = 0
    # scroll down in chunks until bottom
    while current < total_height:
        step = random.randint(200, 500)
        page.evaluate(f"window.scrollBy(0, {step})")
        current += step
        time.sleep(random.uniform(0.3, 0.9))
        # re-check height in case page loaded more content
        total_height = page.evaluate("document.body.scrollHeight")
    time.sleep(random.uniform(0.8, 1.5))
    # scroll back up in chunks
    while current > 0:
        step = random.randint(150, 400)
        page.evaluate(f"window.scrollBy(0, -{step})")
        current -= step
        time.sleep(random.uniform(0.2, 0.6))


TEMPLATE_OK = os.path.join(os.path.dirname(__file__), 'src', 'ok.png')

def _find_and_click_ok(page, timeout=30):
    """Take screenshots and use OpenCV template matching to find and click ok.png."""
    template = cv2.imread(TEMPLATE_OK, cv2.IMREAD_COLOR)
    if template is None:
        print("   [journy] ⚠️  src/ok.png not found")
        return False
    th, tw = template.shape[:2]
    deadline = time.time() + timeout
    while time.time() < deadline:
        # screenshot as numpy array
        png = page.screenshot()
        arr = np.frombuffer(png, np.uint8)
        screen = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        if max_val >= 0.85:
            cx = max_loc[0] + tw // 2
            cy = max_loc[1] + th // 2
            print(f"   [journy] ✅ ok.png found (conf={max_val:.2f}) clicking ({cx},{cy})")
            page.mouse.click(cx, cy)
            return True
        time.sleep(1)
    print("   [journy] ⚠️  ok.png not matched within timeout")
    return False


def journy_func(page):
    """Task for 'Just a moment...' title (Cloudflare challenge)."""
    print("   [journy] waiting 10s...")
    time.sleep(10)
    # # dump all elements
    # elements = page.query_selector_all('*')
    # print(f"   [journy] {len(elements)} elements on page")
    # for el in elements[:30]:
    #     try:
    #         tag = el.evaluate("e => e.tagName")
    #         txt = (el.inner_text() or '').strip()[:60].replace('\n', ' ')
    #         print(f"      <{tag}> {txt}")
    #     except Exception:
    #         pass
    _find_and_click_ok(page)


def error_502(page):
    """Task for 502 error — reload and retry scroll."""
    print("   [task] 502 error: reloading...")
    try:
        page.reload(wait_until='networkidle', timeout=30000)
        print("   [task] 502 reloaded, scrolling...")
        _human_scroll(page)
    except Exception as e:
        print(f"   [task] 502 reload failed: {e}")


def statewins(page):
    """Task for Statewins title."""
    print("   [task] statewins: scrolling...")
    _human_scroll(page)
    print("   [task] statewins: done")


# ── title → task mapping ──
TASKS = {
    "statewins": statewins,
    "error 502": error_502,
    "eloniai": lambda page: _human_scroll(page),
    "just a moment": journy_func,
    "...": journy_func,
}


def run(title: str, page):
    """Run the matching task for the given title (case-insensitive substring match)."""
    title_lower = title.lower()
    for key, fn in TASKS.items():
        if key in title_lower:
            fn(page)
            return True
    return False
