import time, random


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
}


def run(title: str, page):
    """Run the matching task for the given title (case-insensitive substring match)."""
    title_lower = title.lower()
    for key, fn in TASKS.items():
        if key in title_lower:
            fn(page)
            return True
    return False
