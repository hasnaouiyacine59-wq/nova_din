import os, json, time, random, requests, argparse, platform, uuid, socket
os.environ['CAMOUFOX_NO_UPDATE'] = '1'

VERSION = "v5.0.0"
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

def _device_id():
    """Stable device ID based on hostname + MAC."""
    mac = uuid.UUID(int=uuid.getnode()).hex[-12:]
    return f"{socket.gethostname()}-{mac}"

print(f"[device]  id       : {_device_id()}")
print(f"[device]  hostname : {socket.gethostname()}")
print(f"[device]  os       : {platform.system()} {platform.release()} ({platform.machine()})")
print(f"[device]  python   : {platform.python_version()}")
print(f"[device]  cpu      : {platform.processor() or 'n/a'}")
try:
    import psutil
    mem = psutil.virtual_memory()
    print(f"[device]  ram      : {mem.total // (1024**3)}GB total, {mem.percent}% used")
    print(f"[device]  cpu%     : {psutil.cpu_percent(interval=0.5)}%")
except ImportError:
    pass
print()

parser = argparse.ArgumentParser()
parser.add_argument('-c', metavar='COUNTRY', help='Use /ip/<country> endpoint and set exit IP (e.g. -c sw)')
args = parser.parse_args()

from camoufox.sync_api import Camoufox
from camoufox.addons import DefaultAddons
import task_action
from user_agnt import user_agent_list as _ua_pool

_UA_FILTERS = {
    'windows': lambda ua: 'Windows NT' in ua and 'Android' not in ua,
    'macos':   lambda ua: 'Macintosh' in ua or 'Mac OS X' in ua,
    'linux':   lambda ua: ('X11' in ua or 'Linux' in ua) and 'Android' not in ua and 'Macintosh' not in ua,
}
USER_AGENTS = {
    os_key: [ua for ua in _ua_pool if fn(ua)] or _ua_pool
    for os_key, fn in _UA_FILTERS.items()
}
# import creep_session

URL_2     = 'https://cryptyos.nl.eu.org/'
URL_3     = 'https://cryptyos.eu.org/'
TOR_HOST   = os.getenv('TOR_HOST',    '127.0.0.1')
SOCKS_PORT = int(os.getenv('SOCKS_PORT', '9050'))
API_PORT   = int(os.getenv('API_PORT',   '5000'))
PROXY      = f'socks5://{TOR_HOST}:{SOCKS_PORT}'
IP_API     = f'http://{TOR_HOST}:{API_PORT}/ip'
RESET_API  = f'http://{TOR_HOST}:{API_PORT}/reset-ip'

REPORT_URL = os.getenv('REPORT_URL', 'https://f-api-exb5.onrender.com/api/v1/status')

OS_PROFILES = [
    {'os': 'macos',   'window': (1440, 900)},
    {'os': 'macos',   'window': (1024, 768)},
    {'os': 'windows', 'window': (1366, 768)},
    {'os': 'windows', 'window': (1920, 1080)},
    {'os': 'windows', 'window': (1280, 800)},
    {'os': 'linux',   'window': (1280, 800)},
]

OS_FONTS = {
    'windows': ['Arial', 'Times New Roman', 'Georgia', 'Verdana', 'Trebuchet MS', 'Comic Sans MS', 'Impact', 'Courier New'],
    'macos':   ['Helvetica', 'Geneva', 'Monaco', 'Optima', 'Futura', 'Arial', 'Times New Roman', 'Courier New'],
    'linux':   ['DejaVu Sans', 'Liberation Sans', 'Ubuntu', 'FreeSans', 'Arial', 'Times New Roman'],
}


def reset_ip():
    try:
        requests.get(RESET_API, timeout=10)
    except Exception:
        pass

def set_exit_ip(country):
    """Call /ip/<country>, then /set-exit-ip/<ip> to pin the exit node."""
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

CHECK_API = 'https://f-api-exb5.onrender.com/api/v1'

def check_ip(ip):
    """Return True if the API approves this IP. Returns (approved, response)."""
    try:
        r = requests.get(f'{CHECK_API}/{ip}', timeout=10).json()
        return r.get('used') != 'yes', r
    except Exception:
        return False, {}

def _fetch_ip(retries=12, delay=5):
    """Fetch current Tor exit IP, retrying on timeout until the API is ready."""
    for attempt in range(retries):
        try:
            return requests.get(IP_API, timeout=10).json().get('ip', '0.0.0.0')
        except Exception as e:
            print(f"[*] IP API not ready ({e}), retrying in {delay}s... ({attempt+1}/{retries})")
            time.sleep(delay)
    raise RuntimeError(f"IP API unreachable after {retries} attempts")

def get_approved_ip():
    """Keep rotating Tor exit IPs until the check API approves one."""
    ip = _fetch_ip()
    while True:
        print(f"[*] testing {ip} ...")
        approved, resp = check_ip(ip)
        if approved:
            print(f"[*] ✅ approved: {ip} → {resp}")
            return ip
        print(f"[*] ❌ rejected: {ip} → {resp}, resetting...")
        reset_ip()
        # wait until Tor actually gives a different IP
        for _ in range(20):
            time.sleep(3)
            new_ip = _fetch_ip()
            if new_ip != ip:
                ip = new_ip
                break
        else:
            print("[*] ⚠️  IP didn't change after reset, retrying reset...")
            ip = new_ip

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
        return {'ip': ip, 'country': '?', 'cc': 'US', 'city': '?', 'locale': 'en-US', 'timezone': 'America/New_York'}
        return {'ip': ip, 'country': '?', 'cc': 'US', 'city': '?', 'locale': 'en-US', 'timezone': 'America/New_York'}

# ── rotate IP + resolve geo ──
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

print("[*] Resetting IP after bootstrap...")
reset_ip()
print("[*] Waiting for new IP...")

if args.c:
    pinned_ip = set_exit_ip(args.c)
    raw_ip = pinned_ip or requests.get(IP_API, timeout=10).json().get('ip', '0.0.0.0')
    approved, resp = check_ip(raw_ip)
    if not approved:
        print(f"[*] ❌ pinned IP {raw_ip} rejected → {resp}, falling back to rotation...")
        raw_ip = get_approved_ip()
else:
    raw_ip = get_approved_ip()

geo     = get_ip_info(raw_ip)
profile = random.choice(OS_PROFILES)

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
    'titles':    [],
    'iframes':   [],
}

print(f"[IP]      {geo['ip']} [{geo['cc']}] {geo['country']}, {geo['city']}")
print(f"[locale]  {geo['locale']} / {geo['timezone']}")
print(f"[profile] os={profile['os']} window={profile['window']}")

with Camoufox(
    headless=False,
    os=profile['os'],
    window=profile['window'],
    geoip=geo['ip'],
    block_webrtc=True,
    fonts=OS_FONTS.get(profile['os'], []),
    config={'navigator.hardwareConcurrency': random.choice([4, 8, 12, 16])},
    exclude_addons=[DefaultAddons.UBO],
    i_know_what_im_doing=True,
    firefox_user_prefs={
        'network.proxy.type': 1,
        'network.proxy.socks': TOR_HOST,
        'network.proxy.socks_port': SOCKS_PORT,
        'network.proxy.socks_version': 5,
        'network.proxy.socks_remote_dns': True,
        'network.proxy.no_proxies_on': '',
        'network.dns.disablePrefetch': True,
        'general.useragent.override': random.choice(USER_AGENTS[profile['os']]),
    },
) as browser:
    page = browser.new_page()

    # ── creep_session capture (commented out) ──
    # report = creep_session.capture(page, tor_ip=geo['ip'])
    # sess_path = os.path.join(creep_session.SESSIONS_DIR, report['session_id'], 'creepjs.json')
    # with open(sess_path) as f:
    #     saved = json.load(f)
    # saved['geo'] = geo
    # with open(sess_path, 'w') as f:
    #     json.dump(saved, f, indent=2)
    # print(f"[geo] saved to session {report['session_id']}")

    # ── load URL_2 and analyse ──
    print(f"\n🌐  Navigating to {URL_2} ...")
    page.goto(URL_2, wait_until='networkidle', timeout=60000)
    print(f"✅  Page loaded: \033[96m{page.title()}\033[0m  ({page.url})")

    # ── find all iframes ──
    iframes = page.query_selector_all('iframe')
    print(f"\n🖼️  Found \033[93m{len(iframes)}\033[0m iframe(s):")
    for i, fr in enumerate(iframes):
        src   = fr.get_attribute('src') or '(no src)'
        name  = fr.get_attribute('name') or fr.get_attribute('id') or f'iframe-{i}'
        print(f"   \033[90m[{i}]\033[0m 📦 \033[94m{name}\033[0m → {src}")
        try:
            cf    = fr.content_frame()
            text  = cf.inner_text('body') if cf else ''
            short = text.strip()[:200].replace('\n', ' ')
            if short:
                print(f"       📄 text: \033[37m{short}\033[0m")
        except Exception as e:
            print(f"       ⚠️  could not read frame: {e}")

    # ── deep dump of iframe-0 ──
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

    def read_iframes():
        """Read and print text + unique ad alts from every iframe on the page."""
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

    def human_click(el):
        box = el.bounding_box()
        if not box:
            el.click()
            return
        tx = box['x'] + box['width']  * random.uniform(0.3, 0.7)
        ty = box['y'] + box['height'] * random.uniform(0.3, 0.7)
        sx = tx + random.uniform(-120, 120)
        sy = ty + random.uniform(-80, 80)
        page.mouse.move(sx, sy, steps=random.randint(5, 12))
        time.sleep(random.uniform(0.05, 0.15))
        mx = (sx + tx) / 2 + random.uniform(-40, 40)
        my = (sy + ty) / 2 + random.uniform(-40, 40)
        page.mouse.move(mx, my, steps=random.randint(8, 18))
        time.sleep(random.uniform(0.05, 0.12))
        page.mouse.move(tx, ty, steps=random.randint(6, 14))
        time.sleep(random.uniform(0.08, 0.25))
        page.mouse.click(tx, ty)

    # ── nav links to randomly click ──
    NAV_HREFS = ['/', '/', '/gainers', '/losers', '/watchlist']
    random.shuffle(NAV_HREFS)

    for href in NAV_HREFS:
        time.sleep(random.uniform(1.5, 4.0))
        try:
            el = page.query_selector(f'a[href="{href}"]')
            if not el:
                print(f"⚠️  Could not find link href={href}")
                continue
            text = (el.inner_text() or '').strip()[:40]
            print(f"\n🖱️  Clicking \033[92m'{text}'\033[0m href={href}")
            human_click(el)
            try:
                page.wait_for_load_state('networkidle', timeout=10000)
            except Exception:
                page.wait_for_load_state('domcontentloaded', timeout=10000)
            read_iframes()

            # ── after Gainers: click a random pair link ──
            if href == '/gainers':
                time.sleep(random.uniform(1.5, 3.0))
                pair_links = page.query_selector_all('a[href^="/pair/"]')
                if pair_links:
                    pick = random.choice(pair_links)
                    pair_text = (pick.inner_text() or '').strip()[:40].replace('\n', ' ')
                    print(f"\n🖱️  Clicking pair \033[92m'{pair_text}'\033[0m")
                    human_click(pick)
                    page.wait_for_load_state('networkidle', timeout=20000)
                    read_iframes()
                else:
                    print("⚠️  No pair links found on /gainers")

            # ── after Losers: click random pair, then logo ──
            if href == '/losers':
                time.sleep(random.uniform(1.5, 3.0))
                pair_links = page.query_selector_all('a[href^="/pair/"]')
                if pair_links:
                    pick = random.choice(pair_links)
                    pair_text = (pick.inner_text() or '').strip()[:40].replace('\n', ' ')
                    print(f"\n🖱️  Clicking pair \033[92m'{pair_text}'\033[0m")
                    human_click(pick)
                    page.wait_for_load_state('networkidle', timeout=20000)
                    read_iframes()
                else:
                    print("⚠️  No pair links found on /losers")

                time.sleep(random.uniform(1.5, 3.0))

                # click the CryptoScope home logo
                logo = page.query_selector('a.text-accent.font-bold.text-lg.tracking-tight.shrink-0[href="/"]')
                if logo:
                    logo_text = (logo.inner_text() or '').strip()
                    print(f"\n🖱️  Clicking '{logo_text}' (home logo)")
                    human_click(logo)
                    page.wait_for_load_state('networkidle', timeout=20000)
                    read_iframes()
                else:
                    print("⚠️  CryptoScope logo not found")

                time.sleep(random.uniform(1.5, 3.0))

            

        except Exception as e:
            print(f"⚠️  Click error on {href}: {e}")

    print(f"\n✅  Analysis complete.\n")

    # ── re-read current iframes after analysis ──
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
            session_report['iframes'].append({'index': i, 'text': text, 'alts': alts})
        except Exception as e:
            print(f"   ⚠️  iframe-{i} error: {e}")

    # ── send report ──
    print(f"\n📋  session report:\n{json.dumps(session_report, indent=2)}")
    if REPORT_URL:
        try:
            r = requests.post(REPORT_URL, json=session_report, timeout=10)
            print(f"📤  report sent → {r.status_code}")
        except Exception as e:
            print(f"⚠️  report send failed: {e}")

    def lik():
        iframes = page.query_selector_all('iframe')
        for i, fr in enumerate(iframes):
            try:
                box = fr.bounding_box()
                if not box:
                    continue
                tx = box['x'] + box['width']  * random.uniform(0.3, 0.7)
                ty = box['y'] + box['height'] * random.uniform(0.3, 0.7)
                page.mouse.move(tx, ty, steps=random.randint(8, 15))
                print(f"   🖱️  hovering iframe-{i}")
                time.sleep(random.uniform(0.5, 1.2))

                # click and wait for new tab
                with page.context.expect_page() as new_page_info:
                    page.mouse.click(tx, ty)
                new_tab = new_page_info.value

                print(f"   🆕  new tab opened")
                seen_titles = set()
                last_title = None

                # track title changes through redirections
                for _ in range(60):
                    try:
                        title = new_tab.title()
                        if title and title != last_title:
                            if 'click' in title.lower():
                                print(f"   ⏳  title has 'click', waiting... [{title}]")
                            else:
                                print(f"   📄  title: {title} | url: {new_tab.url}")
                                task_action.run(title, new_tab)
                            last_title = title
                    except Exception:
                        pass
                    time.sleep(1)

            except Exception as e:
                print(f"   ⚠️  iframe-{i} error: {e}")

    lik()

    # ── visit URL_3 and close ──
    print(f"\n🌐  Navigating to {URL_3} ...")
    page.goto(URL_3, wait_until='networkidle', timeout=60000)
    print(f"✅  Page loaded: \033[96m{page.title()}\033[0m  ({page.url})")
    print("⏳  Waiting 10 seconds...")
    time.sleep(10)
    print("👋  Closing browser.")


