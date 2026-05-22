# ── Standard library imports ──
import os, json, time, random, requests, argparse, platform, uuid, socket, sys, glob as _glob, shutil, atexit, subprocess

# Prevent Camoufox from auto-updating on startup
os.environ['CAMOUFOX_NO_UPDATE'] = '1'

# ── Version & banner ──
VERSION = "v6.6.6 codeany"
BANNER = f"""
  ███╗   ██╗ ██████╗ ██╗   ██╗ █████╗     ██████╗ ██╗███╗   ██╗
  ████╗  ██║██╔═══██╗██║   ██║██╔══██╗    ██╔══██╗██║████╗  ██║
  ██╔██╗ █ ║██║   █ ║██║   ██║███████║    ██║  ██║██║██╔██╗ ██║
  ██║╚██╗██║██║   ██║╚██╗ ██╔╝██╔══██║    ██║  ██║██║██║╚██╗██║
  ██║ ╚████║╚██████╔╝ ╚████╔╝ ██║  ██║    ██████╔╝██║██║ ╚████║
  ╚═╝  ╚═══╝ ╚═════╝   ╚═══╝  ╚═╝  ╚═╝   ╚═════╝ ╚═╝╚═╝  ╚═══╝
                                                    {VERSION}
"""
print(BANNER)

# ── Check / install Xvfb ──
if shutil.which('Xvfb') is None:
    print("[*] Xvfb not found, installing...")
    ret = subprocess.run(['sudo', 'apt-get', 'install', '-y', 'xvfb'], capture_output=True)
    if ret.returncode != 0:
        print(f"[!] Xvfb install failed:\n{ret.stderr.decode()}")
        sys.exit(1)
    print("[*] Xvfb installed ✅")
else:
    print(f"[*] Xvfb found: {shutil.which('Xvfb')}")

# ── Cleanup: remove Firefox temp profiles and cache left by Playwright ──
def _cleanup_tmp():
    """Delete all rust_mozprofile* and playwright* temp dirs created by this session."""
    import tempfile
    tmpdir = tempfile.gettempdir()
    for pattern in ('rust_mozprofile*', 'playwright*', '.com.google.Chrome*'):
        for path in _glob.glob(os.path.join(tmpdir, pattern)):
            try:
                shutil.rmtree(path, ignore_errors=True)
                print(f"[cleanup] removed {path}")
            except Exception:
                pass

atexit.register(_cleanup_tmp)

# ── Step 1: Generate a stable device fingerprint ──
def _device_id():
    """Stable device ID based on hostname + MAC."""
    mac = uuid.UUID(int=uuid.getnode()).hex[-12:]
    return f"{socket.gethostname()}-{mac}"

# Print device info for logging/debugging
print(f"[device]  id       : {_device_id()}")
print(f"[device]  hostname : {socket.gethostname()}")
print(f"[device]  os       : {platform.system()} {platform.release()} ({platform.machine()})")
print(f"[device]  python   : {platform.python_version()}")
print(f"[device]  cpu      : {platform.processor() or 'n/a'}")
try:
    # Optional: print RAM and CPU usage if psutil is available
    import psutil
    mem = psutil.virtual_memory()
    print(f"[device]  ram      : {mem.total // (1024**3)}GB total, {mem.percent}% used")
    print(f"[device]  cpu%     : {psutil.cpu_percent(interval=0.5)}%")
except ImportError:
    pass
print()

# ── Step 2: Parse CLI arguments ──
parser = argparse.ArgumentParser()
# -c allows pinning the Tor exit node to a specific country code
parser.add_argument('-c', metavar='COUNTRY', help='Use /ip/<country> endpoint and set exit IP (e.g. -c sw)')
args = parser.parse_args()

# ── Step 3: Import browser automation and user-agent pool ──
from camoufox.sync_api import Camoufox
from camoufox.addons import DefaultAddons
import task_action
from user_agnt import user_agent_list as _ua_pool

# ── Step 4: Build per-OS user-agent lists ──
# Filter the full UA pool into OS-specific buckets for realistic spoofing
_UA_FILTERS = {
    'windows': lambda ua: 'Windows NT' in ua and 'Android' not in ua,
    'macos':   lambda ua: 'Macintosh' in ua or 'Mac OS X' in ua,
    'linux':   lambda ua: ('X11' in ua or 'Linux' in ua) and 'Android' not in ua and 'Macintosh' not in ua,
}
USER_AGENTS = {
    os_key: [ua for ua in _ua_pool if fn(ua)] or _ua_pool
    for os_key, fn in _UA_FILTERS.items()
}
# import creep_session  # (disabled – fingerprint capture module)

# ── Step 5: Configuration constants ──
URL_2     = 'https://cryptyos.nl.eu.org/'   # primary target URL
URL_3     = 'https://cryptyos.eu.org/'      # warm-up URL visited first

# Tor proxy settings (read from env or use defaults)
TOR_HOST   = os.getenv('TOR_HOST',    '127.0.0.1')
SOCKS_PORT = int(os.getenv('SOCKS_PORT', '9050'))
API_PORT   = int(os.getenv('API_PORT',   '5000'))

PROXY     = f'socks5://{TOR_HOST}:{SOCKS_PORT}'
IP_API    = f'http://{TOR_HOST}:{API_PORT}/ip'        # get current exit IP
RESET_API = f'http://{TOR_HOST}:{API_PORT}/reset-ip'  # trigger IP rotation

# Remote endpoint to POST the session report to
REPORT_URL = os.getenv('REPORT_URL', 'https://f-api-s36l.onrender.com/api/v1/status')
# REPORT_URL = os.getenv('REPORT_URL', 'https://f-api-exb5.onrender.com/api/v1/status')

# ── Step 6: OS browser profiles (OS + window size combinations) ──
OS_PROFILES = [
    {'os': 'macos',   'window': (1440, 900)},
    {'os': 'macos',   'window': (1024, 768)},
    {'os': 'windows', 'window': (1366, 768)},
    {'os': 'windows', 'window': (1920, 1080)},
    {'os': 'windows', 'window': (1280, 800)},
    {'os': 'linux',   'window': (1280, 800)},
]

# Per-OS font lists used to spoof navigator.fonts
OS_FONTS = {
    'windows': ['Arial', 'Times New Roman', 'Georgia', 'Verdana', 'Trebuchet MS', 'Comic Sans MS', 'Impact', 'Courier New'],
    'macos':   ['Helvetica', 'Geneva', 'Monaco', 'Optima', 'Futura', 'Arial', 'Times New Roman', 'Courier New'],
    'linux':   ['DejaVu Sans', 'Liberation Sans', 'Ubuntu', 'FreeSans', 'Arial', 'Times New Roman'],
}


# ── Step 7: Tor IP management helpers ──

def reset_ip():
    """Ask the Tor controller API to rotate to a new exit IP."""
    try:
        requests.get(RESET_API, timeout=10)
    except Exception:
        pass

def set_exit_ip(country):
    """Pin the Tor exit node to a specific country.
    Calls /ip/<country> to get a candidate IP, then /set-exit-ip/<ip> to lock it.
    Returns the pinned IP string, or None on failure.
    """
    try:
        r = requests.get(f'http://{TOR_HOST}:{API_PORT}/ip/{country}', timeout=10).json()
        ip = r.get('ip')
        if not ip:
            print(f"[!] No IP returned for country '{country}'")
            return None
        resp = requests.get(f'http://{TOR_HOST}:{API_PORT}/set-exit-ip/{ip}', timeout=10).json()
        print(f"[exit-ip] {ip} [{country}] → {resp.get('status')} fp={resp.get('fingerprint','?')}")
        return ip
    except Exception as e:
        print(f"[!] set_exit_ip error: {e}")
        return None

# Remote API used to check whether an IP has already been used
CHECK_API = 'https://f-api-s36l.onrender.com/api/v1'

def check_ip(ip):
    """Query the check API to see if this IP is approved (not previously used).
    Returns (approved: bool, response: dict).
    """
    try:
        r = requests.get(f'{CHECK_API}/{ip}', timeout=10).json()
        return r.get('used') != 'yes', r
    except Exception:
        return False, {}

def _fetch_ip(retries=12, delay=5):
    """Fetch the current Tor exit IP from the local API.
    Retries up to `retries` times with `delay` seconds between attempts.
    Raises RuntimeError if the API never responds.
    """
    for attempt in range(retries):
        try:
            return requests.get(IP_API, timeout=10).json().get('ip', '0.0.0.0')
        except Exception as e:
            print(f"[*] IP API not ready ({e}), retrying in {delay}s... ({attempt+1}/{retries})")
            time.sleep(delay)
    raise RuntimeError(f"IP API unreachable after {retries} attempts")

def get_approved_ip():
    """Rotate Tor exit IPs in a loop until the check API approves one.
    After each rejection, triggers a reset and waits for the IP to actually change.
    """
    ip = _fetch_ip()
    while True:
        print(f"[*] testing {ip} ...")
        approved, resp = check_ip(ip)
        if approved:
            print(f"[*] ✅ approved: {ip} → {resp}")
            return ip
        print(f"[*] ❌ rejected: {ip} → {resp}, resetting...")
        reset_ip()
        # Poll until Tor gives a different IP (up to 20 × 3s = 60s)
        for _ in range(20):
            time.sleep(3)
            new_ip = _fetch_ip()
            if new_ip != ip:
                ip = new_ip
                break
        else:
            print("[*] ⚠️  IP didn't change after reset, retrying reset...")
            ip = new_ip


# ── Step 8: Country-code → locale/timezone mapping ──
# Used to set browser locale and timezone to match the exit IP's country
CC_LANG = {
    'US': ('en-US', 'America/New_York'),
    'GB': ('en-GB', 'Europe/London'),
    'DE': ('de-DE', 'Europe/Berlin'),
    'FR': ('fr-FR', 'Europe/Paris'),
    'NL': ('nl-NL', 'Europe/Amsterdam'),
    'ES': ('es-ES', 'Europe/Madrid'),
    'IT': ('it-IT', 'Europe/Rome'),
    'PL': ('pl-PL', 'Europe/Warsaw'),
    'SE': ('sv-SE', 'Europe/Stockholm'),
    'NO': ('nb-NO', 'Europe/Oslo'),
    'FI': ('fi-FI', 'Europe/Helsinki'),
    'RO': ('ro-RO', 'Europe/Bucharest'),
    'CZ': ('cs-CZ', 'Europe/Prague'),
    'AT': ('de-AT', 'Europe/Vienna'),
    'CH': ('de-CH', 'Europe/Zurich'),
    'CA': ('en-CA', 'America/Toronto'),
    'AU': ('en-AU', 'Australia/Sydney'),
    'JP': ('ja-JP', 'Asia/Tokyo'),
    'BR': ('pt-BR', 'America/Sao_Paulo'),
    'IN': ('en-IN', 'Asia/Kolkata'),
    'PT': ('pt-PT', 'Europe/Lisbon'),
    'BE': ('nl-BE', 'Europe/Brussels'),
    'DK': ('da-DK', 'Europe/Copenhagen'),
    'HU': ('hu-HU', 'Europe/Budapest'),
    'SK': ('sk-SK', 'Europe/Bratislava'),
    'HR': ('hr-HR', 'Europe/Zagreb'),
    'BG': ('bg-BG', 'Europe/Sofia'),
    'GR': ('el-GR', 'Europe/Athens'),
    'TR': ('tr-TR', 'Europe/Istanbul'),
    'RU': ('ru-RU', 'Europe/Moscow'),
    'UA': ('uk-UA', 'Europe/Kiev'),
    'LT': ('lt-LT', 'Europe/Vilnius'),
    'LV': ('lv-LV', 'Europe/Riga'),
    'EE': ('et-EE', 'Europe/Tallinn'),
    'RS': ('sr-RS', 'Europe/Belgrade'),
    'SI': ('sl-SI', 'Europe/Ljubljana'),
    'MX': ('es-MX', 'America/Mexico_City'),
    'AR': ('es-AR', 'America/Argentina/Buenos_Aires'),
    'CL': ('es-CL', 'America/Santiago'),
    'CO': ('es-CO', 'America/Bogota'),
    'PE': ('es-PE', 'America/Lima'),
    'ZA': ('en-ZA', 'Africa/Johannesburg'),
    'NG': ('en-NG', 'Africa/Lagos'),
    'EG': ('ar-EG', 'Africa/Cairo'),
    'SA': ('ar-SA', 'Asia/Riyadh'),
    'AE': ('ar-AE', 'Asia/Dubai'),
    'IL': ('he-IL', 'Asia/Jerusalem'),
    'KR': ('ko-KR', 'Asia/Seoul'),
    'CN': ('zh-CN', 'Asia/Shanghai'),
    'TW': ('zh-TW', 'Asia/Taipei'),
    'HK': ('zh-HK', 'Asia/Hong_Kong'),
    'SG': ('en-SG', 'Asia/Singapore'),
    'MY': ('ms-MY', 'Asia/Kuala_Lumpur'),
    'TH': ('th-TH', 'Asia/Bangkok'),
    'ID': ('id-ID', 'Asia/Jakarta'),
    'PH': ('en-PH', 'Asia/Manila'),
    'VN': ('vi-VN', 'Asia/Ho_Chi_Minh'),
    'PK': ('ur-PK', 'Asia/Karachi'),
    'BD': ('bn-BD', 'Asia/Dhaka'),
    'NZ': ('en-NZ', 'Pacific/Auckland'),
}

def get_ip_info(ip):
    """Resolve geo metadata for the given IP using ipwho.is.
    Returns a dict with ip, country, cc, city, locale, timezone.
    Falls back to US defaults on any error.
    """
    try:
        d = requests.get(f'http://ipwho.is/{ip}', timeout=8).json()
        cc = d.get('country_code', 'US')
        locale, tz = CC_LANG.get(cc, ('en-US', 'America/New_York'))
        return {
            'ip':       ip,
            'country':  d.get('country', '?'),
            'cc':       cc,
            'city':     d.get('city', '?'),
            'locale':   locale,
            'timezone': d.get('timezone', {}).get('id', tz),
        }
    except Exception:
        # Return safe US defaults if geo lookup fails
        return {'ip': ip, 'country': '?', 'cc': 'US', 'city': '?', 'locale': 'en-US', 'timezone': 'America/New_York'}


# ── Step 9: Wait for Tor to bootstrap ──
# Poll the IP API every 2s for up to 60s before giving up
print("[*] Waiting for Tor to bootstrap...")
for _ in range(30):
    try:
        if requests.get(IP_API, timeout=5).status_code == 200:
            break
    except Exception:
        pass
    time.sleep(2)
else:
    print("[!] Tor not ready after 60s, continuing anyway...")

# ── Step 10: Initial IP rotation after bootstrap ──
print("[*] Resetting IP after bootstrap...")
reset_ip()
print("[*] Waiting for new IP...")

# ── Step 11: Acquire an approved exit IP ──
if args.c:
    # Country flag provided: pin exit node to that country
    pinned_ip = set_exit_ip(args.c)
    raw_ip = pinned_ip or requests.get(IP_API, timeout=10).json().get('ip', '0.0.0.0')
    approved, resp = check_ip(raw_ip)
    if not approved:
        # Pinned IP was rejected; fall back to automatic rotation
        print(f"[*] ❌ pinned IP {raw_ip} rejected → {resp}, falling back to rotation...")
        raw_ip = get_approved_ip()
else:
    # No country flag: rotate until an approved IP is found
    raw_ip = get_approved_ip()

# ── Step 12: Resolve geo info and pick a random browser profile ──
geo     = get_ip_info(raw_ip)
profile = random.choice(OS_PROFILES)

# ── Step 13: Build the session report skeleton ──
# This dict is populated throughout the session and POSTed at the end
session_report = {
    'device_id': _device_id(),
    'ip':        geo['ip'],
    'country':   geo['country'],
    'cc':        geo['cc'],
    'city':      geo['city'],
    'locale':    geo['locale'],
    'timezone':  geo['timezone'],
    'os':        profile['os'],
    'window':    list(profile['window']),
    'titles':    [],   # ad alt texts collected during navigation
    'iframes':   [],   # iframe text/alt snapshots from final re-read
}

print(f"[IP]      {geo['ip']} [{geo['cc']}] {geo['country']}, {geo['city']}")
print(f"[locale]  {geo['locale']} / {geo['timezone']}")
print(f"[profile] os={profile['os']} window={profile['window']}")


# ── Step 14: Launch Camoufox browser with anti-fingerprint config ──
# Camoufox is a hardened Firefox fork that spoofs browser fingerprints.
# All traffic is routed through the Tor SOCKS5 proxy.
with Camoufox(
    headless='virtual',
    # headless=False,
    os=profile['os'],                                        # spoof OS in JS APIs
    window=profile['window'],                                # set window/screen size
    geoip=geo['ip'],                                         # spoof geolocation to match exit IP
    block_webrtc=True,                                       # prevent WebRTC IP leaks
    fonts=OS_FONTS.get(profile['os'], []),                   # spoof available fonts
    config={'navigator.hardwareConcurrency': random.choice([4, 8, 12, 16])},  # randomise CPU core count
    exclude_addons=[DefaultAddons.UBO],                      # disable uBlock Origin
    i_know_what_im_doing=True,
    firefox_user_prefs={
        'network.proxy.type': 1,                             # manual proxy
        'network.proxy.socks': TOR_HOST,
        'network.proxy.socks_port': SOCKS_PORT,
        'network.proxy.socks_version': 5,
        'network.proxy.socks_remote_dns': True,              # resolve DNS through Tor
        'network.proxy.no_proxies_on': '',
        'network.dns.disablePrefetch': True,                 # no DNS prefetch leaks
        'general.useragent.override': random.choice(USER_AGENTS[profile['os']]),  # spoof UA
    },
) as browser:
    page = browser.new_page()

    # ── creep_session capture (disabled) ──
    # report = creep_session.capture(page, tor_ip=geo['ip'])
    # sess_path = os.path.join(creep_session.SESSIONS_DIR, report['session_id'], 'creepjs.json')
    # with open(sess_path) as f:
    #     saved = json.load(f)
    # saved['geo'] = geo
    # with open(sess_path, 'w') as f:
    #     json.dump(saved, f, indent=2)
    # print(f"[geo] saved to session {report['session_id']}")

    # ── Step 15: Warm-up visit to URL_3 ──
    # Visit the secondary URL first to build a realistic browsing history
    print(f"\n🌐  Navigating to {URL_3} ...")
    try:
        page.goto(URL_3, wait_until='networkidle', timeout=60000)
        print(f"✅  Page loaded: \033[96m{page.title()}\033[0m  ({page.url})")
    except Exception as e:
        print(f"⚠️  URL_3 navigation failed: {e}")
        page.close()
        sys.exit(1)
    print("⏳  Waiting 10 seconds...")
    time.sleep(30)  # dwell on the page to simulate reading

    # ── Step 16: Hover over iframe during the wait ──
    # Moves the mouse to a random point inside the first iframe to simulate engagement
    try:
        iframe_el = page.query_selector('iframe')
        if iframe_el:
            box = iframe_el.bounding_box()
            if box:
                tx = box['x'] + box['width']  * random.uniform(0.3, 0.7)
                ty = box['y'] + box['height'] * random.uniform(0.3, 0.7)
                page.mouse.move(tx, ty, steps=random.randint(8, 15))
                print("   🖱️  hovering iframe during wait...")
    except Exception as e:
        print(f"   ⚠️  iframe hover error: {e}")
    time.sleep(20)  # additional dwell after hover

    # ── Step 17: Navigate to the primary target URL_2 ──
    print(f"\n🌐  Navigating to {URL_2} ...")
    try:
        page.goto(URL_2, wait_until='networkidle', timeout=60000)
        print(f"✅  Page loaded: \033[96m{page.title()}\033[0m  ({page.url})")
    except Exception as e:
        print(f"⚠️  URL_2 navigation failed: {e}")
        page.close()
        sys.exit(1)

    # ── Step 18: Enumerate all iframes on the page ──
    iframes = page.query_selector_all('iframe')
    print(f"\n🖼️  Found \033[93m{len(iframes)}\033[0m iframe(s):")
    for i, fr in enumerate(iframes):
        src   = fr.get_attribute('src') or '(no src)'
        name  = fr.get_attribute('name') or fr.get_attribute('id') or f'iframe-{i}'
        print(f"   \033[90m[{i}]\033[0m 📦 \033[94m{name}\033[0m → {src}")
        try:
            # Read visible text from inside the iframe
            cf    = fr.content_frame()
            text  = cf.inner_text('body') if cf else ''
            short = text.strip()[:200].replace('\n', ' ')
            if short:
                print(f"       📄 text: \033[37m{short}\033[0m")
        except Exception as e:
            print(f"       ⚠️  could not read frame: {e}")

    # ── Step 19: Deep inspection of iframe-0 ──
    # Extract all HTML attributes and unique image alt texts from the first iframe
    if iframes:
        fr = iframes[0]
        print(f"\n🔍  Title :")
        iframe0_attrs = []
        for attr in ('src', 'id', 'name', 'alt', 'title', 'class'):
            val = fr.get_attribute(attr)
            if val:
                print(f"   {val}")
                iframe0_attrs.append(val)
        session_report['iframe0_attrs'] = iframe0_attrs
        try:
            cf = fr.content_frame()
            if cf:
                cf.wait_for_load_state('domcontentloaded', timeout=15000)
                elements = cf.query_selector_all('img')
                seen = set()
                unique_alts = []
                # Collect unique alt texts from all images inside iframe-0
                for el in elements:
                    alt = (el.get_attribute('alt') or '').strip()
                    if alt and alt not in seen:
                        seen.add(alt)
                        unique_alts.append(alt)
                if unique_alts:
                    print(f"\n📄  title :")
                    for alt in unique_alts:
                        print(f"   • {alt}")
                session_report['iframe0_alts'] = unique_alts
            else:
                print("⚠️  Could not get content frame for iframe-0")
        except Exception as e:
            print(f"⚠️  Error reading iframe-0: {e}")
    else:
        print("⚠️  No iframes found on page")

    # ── Step 20: Helper – read all iframes on the current page ──
    def read_iframes():
        """Read and print text + unique image alt texts from every iframe on the page.
        Also appends ad alt texts to session_report['titles'].
        """
        try:
            frames = page.query_selector_all('iframe')
            if not frames:
                return
            for i, fr in enumerate(frames):
                try:
                    cf = fr.content_frame()
                    if not cf:
                        continue
                    cf.wait_for_load_state('domcontentloaded', timeout=10000)
                    body_text = cf.inner_text('body') if cf else ''
                    short = body_text.strip()[:200].replace('\n', ' ')
                    if short:
                        print(f"   📄 title-{i} text: \033[37m{short}\033[0m")
                    # Collect unique image alt texts (ad labels)
                    imgs = cf.query_selector_all('img')
                    seen = set()
                    alts = []
                    for el in imgs:
                        alt = (el.get_attribute('alt') or '').strip()
                        if alt and alt not in seen:
                            seen.add(alt)
                            alts.append(alt)
                    if alts:
                        print(f"   📢 title-{i} : {' • '.join(alts)}")
                        session_report['titles'].extend(alts)
                except Exception as e:
                    print(f"   ⚠️  iframe-{i} read error: {e}")
        except Exception as e:
            print(f"⚠️  iframe read error: {e}")

    # ── Step 21: Helper – simulate a human-like mouse click ──
    def human_click(el):
        """Move the mouse in a curved, jittery path before clicking the element.
        Uses random offsets and intermediate waypoints to mimic real mouse movement.
        """
        box = el.bounding_box()
        if not box:
            el.click()  # fallback: direct click if no bounding box
            return
        # Target point: random position within the element
        tx = box['x'] + box['width']  * random.uniform(0.3, 0.7)
        ty = box['y'] + box['height'] * random.uniform(0.3, 0.7)
        # Start point: offset from target to simulate cursor coming from elsewhere
        sx = tx + random.uniform(-120, 120)
        sy = ty + random.uniform(-80, 80)
        page.mouse.move(sx, sy, steps=random.randint(5, 12))
        time.sleep(random.uniform(0.05, 0.15))
        # Midpoint with jitter for a curved path
        mx = (sx + tx) / 2 + random.uniform(-40, 40)
        my = (sy + ty) / 2 + random.uniform(-40, 40)
        page.mouse.move(mx, my, steps=random.randint(8, 18))
        time.sleep(random.uniform(0.05, 0.12))
        # Final approach to the target
        page.mouse.move(tx, ty, steps=random.randint(6, 14))
        time.sleep(random.uniform(0.08, 0.25))
        page.mouse.click(tx, ty)

    # ── Step 22: Randomly navigate through site sections ──
    # Shuffle nav links so the visit order looks organic
    NAV_HREFS = ['/', '/', '/gainers', '/losers', '/watchlist']
    random.shuffle(NAV_HREFS)

    for href in NAV_HREFS:
        time.sleep(random.uniform(1.5, 4.0))  # random dwell before each click
        try:
            el = page.query_selector(f'a[href="{href}"]')
            if not el:
                print(f"⚠️  Could not find link href={href}")
                continue
            text = (el.inner_text() or '').strip()[:40]
            print(f"\n🖱️  Clicking \033[92m'{text}'\033[0m href={href}")
            human_click(el)
            # Wait for page to settle after navigation
            try:
                page.wait_for_load_state('networkidle', timeout=10000)
            except Exception:
                page.wait_for_load_state('domcontentloaded', timeout=10000)
            read_iframes()

            # ── Step 23: After /gainers – click a random crypto pair ──
            if href == '/gainers':
                time.sleep(random.uniform(1.5, 3.0))
                pair_links = page.query_selector_all('a[href^="/pair/"]')
                if pair_links:
                    pick = random.choice(pair_links)
                    pair_text = (pick.inner_text() or '').strip()[:40].replace('\n', ' ')
                    print(f"\n🖱️  Clicking pair \033[92m'{pair_text}'\033[0m")
                    human_click(pick)
                    try:
                        page.wait_for_load_state('networkidle', timeout=20000)
                    except Exception:
                        page.wait_for_load_state('domcontentloaded', timeout=10000)
                    read_iframes()
                else:
                    print("⚠️  No pair links found on /gainers")

            # ── Step 24: After /losers – click a random pair, then return home ──
            if href == '/losers':
                time.sleep(random.uniform(1.5, 3.0))
                pair_links = page.query_selector_all('a[href^="/pair/"]')
                if pair_links:
                    pick = random.choice(pair_links)
                    pair_text = (pick.inner_text() or '').strip()[:40].replace('\n', ' ')
                    print(f"\n🖱️  Clicking pair \033[92m'{pair_text}'\033[0m")
                    human_click(pick)
                    try:
                        page.wait_for_load_state('networkidle', timeout=20000)
                    except Exception:
                        page.wait_for_load_state('domcontentloaded', timeout=10000)
                    read_iframes()
                else:
                    print("⚠️  No pair links found on /losers")

                time.sleep(random.uniform(1.5, 3.0))

                # Click the CryptoScope home logo to return to the homepage
                logo = page.query_selector('a.text-accent.font-bold.text-lg.tracking-tight.shrink-0[href="/"]')
                if logo:
                    logo_text = (logo.inner_text() or '').strip()
                    print(f"\n🖱️  Clicking '{logo_text}' (home logo)")
                    human_click(logo)
                    try:
                        page.wait_for_load_state('networkidle', timeout=20000)
                    except Exception:
                        page.wait_for_load_state('domcontentloaded', timeout=10000)
                    read_iframes()
                else:
                    print("⚠️  CryptoScope logo not found")

                time.sleep(random.uniform(1.5, 3.0))

        except Exception as e:
            print(f"⚠️  Click error on {href}: {e}")

    print(f"\n✅  Analysis complete.\n")

    # ── Step 25: Final iframe re-read after all navigation ──
    # Capture a fresh snapshot of all iframes for the session report
    print("🔄  Re-reading iframes after analysis complete...")
    iframes = page.query_selector_all('iframe')
    print(f"🖼️  Found {len(iframes)} iframe(s):")
    for i, fr in enumerate(iframes):
        try:
            cf = fr.content_frame()
            if not cf:
                continue
            cf.wait_for_load_state('domcontentloaded', timeout=10000)
            text = cf.inner_text('body').strip()[:300].replace('\n', ' ')
            if text:
                print(f"   📄 iframe-{i} text: {text}")
            imgs = cf.query_selector_all('img')
            seen = set()
            alts = []
            for el in imgs:
                alt = (el.get_attribute('alt') or '').strip()
                if alt and alt not in seen:
                    seen.add(alt)
                    alts.append(alt)
                    print(f"   🖼️  iframe-{i} alt: {alt}")
            # Store iframe snapshot in the report
            session_report['iframes'].append({'index': i, 'text': text, 'alts': alts})
        except Exception as e:
            print(f"   ⚠️  iframe-{i} error: {e}")

    # ── Step 26: POST session report to the remote API ──
    print(f"\n📋  session report:\n{json.dumps(session_report, indent=2)}")
    if REPORT_URL:
        try:
            r = requests.post(REPORT_URL, json=session_report, timeout=10)
            print(f"📤  report sent → {r.status_code}")
        except Exception as e:
            print(f"⚠️  report send failed: {e}")

    # ── Step 27: Click iframes and handle new tabs (lik) ──
    def lik():
        """Hover over each iframe, click it, and track the resulting new tab.
        Monitors title changes in the new tab and delegates to task_action.run()
        for any non-'click' title (i.e. the final landing page after redirects).
        """
        iframes = page.query_selector_all('iframe')
        for i, fr in enumerate(iframes):
            try:
                box = fr.bounding_box()
                if not box:
                    continue
                # Move mouse to a random point inside the iframe
                tx = box['x'] + box['width']  * random.uniform(0.3, 0.7)
                ty = box['y'] + box['height'] * random.uniform(0.3, 0.7)
                page.mouse.move(tx, ty, steps=random.randint(8, 15))
                print(f"   🖱️  hovering iframe-{i}")
                time.sleep(random.uniform(0.5, 1.2))

                # Click and capture the new tab that opens
                with page.context.expect_page() as new_page_info:
                    page.mouse.click(tx, ty)
                new_tab = new_page_info.value

                print(f"   🆕  new tab opened")
                seen_titles = set()  # (unused – kept for potential dedup logic)
                last_title = None

                # Poll the new tab for up to 60s, watching for title changes
                # Titles containing 'click' are intermediate redirect pages; skip them
                for _ in range(60):
                    try:
                        title = new_tab.title()
                        if title and title != last_title:
                            if 'click' in title.lower():
                                print(f"   ⏳  title has 'click', waiting... [{title}]")
                            else:
                                print(f"   📄  title: {title} | url: {new_tab.url}")
                                # Delegate the final page to task_action for further processing
                                task_action.run(title, new_tab)
                            last_title = title
                    except Exception:
                        pass
                    time.sleep(1)

            except Exception as e:
                print(f"   ⚠️  iframe-{i} error: {e}")

    lik()
