import os, json, time, random, requests
from camoufox.sync_api import Camoufox
from camoufox.addons import DefaultAddons
import creep_session

URL_2     = 'https://cryptyos.nl.eu.org/'
TOR_HOST  = os.getenv('TOR_HOST',   '127.0.0.1')
PROXY     = os.getenv('PROXY',     f'socks5://{TOR_HOST}:9050')
IP_API    = os.getenv('IP_API',    f'http://{TOR_HOST}:5000/ip')
RESET_API = os.getenv('RESET_API', f'http://{TOR_HOST}:5000/reset-ip')

OS_PROFILES = [
    {'os': 'macos',   'window': (1440, 900)},
    {'os': 'macos',   'window': (1024, 768)},
    {'os': 'windows', 'window': (1366, 768)},
    {'os': 'windows', 'window': (1920, 1080)},
    {'os': 'windows', 'window': (1280, 800)},
    {'os': 'linux',   'window': (1280, 800)},
]

def reset_ip():
    try:
        requests.get(RESET_API, timeout=10)
    except Exception:
        pass

def get_ip_info(ip):
    try:
        d = requests.get(f'http://ipwho.is/{ip}', timeout=8).json()
        cc = d.get('country_code', 'US')
        locale, tz = creep_session.CC_LANG.get(cc, ('en-US', 'America/New_York'))
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

reset_ip()
time.sleep(3)
raw_ip  = creep_session.get_ip(IP_API)
geo     = get_ip_info(raw_ip)
profile = random.choice(OS_PROFILES)

print(f"[IP]      {geo['ip']} [{geo['cc']}] {geo['country']}, {geo['city']}")
print(f"[locale]  {geo['locale']} / {geo['timezone']}")
print(f"[profile] os={profile['os']} window={profile['window']}")

with Camoufox(
    headless=False,
    os=profile['os'],
    window=profile['window'],
    block_images=False,
    geoip=False,
    exclude_addons=[DefaultAddons.UBO],
    locale=geo['locale'],
    i_know_what_im_doing=True,
    firefox_user_prefs={
        'network.proxy.type': 1,
        'network.proxy.socks': TOR_HOST,
        'network.proxy.socks_port': 9050,
        'network.proxy.socks_version': 5,
        'network.proxy.socks_remote_dns': True,
        'network.proxy.no_proxies_on': '',
        'network.dns.disablePrefetch': True,
    },
) as browser:
    page = browser.new_page(timezone_id=geo['timezone'])

    report = creep_session.capture(page, tor_ip=geo['ip'])

    # attach geo info to saved session
    sess_path = os.path.join(creep_session.SESSIONS_DIR, report['session_id'], 'creepjs.json')
    with open(sess_path) as f:
        saved = json.load(f)
    saved['geo'] = geo
    with open(sess_path, 'w') as f:
        json.dump(saved, f, indent=2)
    print(f"[geo] saved to session {report['session_id']}")

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
        print(f"\n🔍  iframe-0 attributes:")
        for attr in ('src', 'id', 'name', 'alt', 'title', 'class'):
            val = fr.get_attribute(attr)
            if val:
                print(f"   {attr}: {val}")
        try:
            cf = fr.content_frame()
            if cf:
                cf.wait_for_load_state('domcontentloaded', timeout=15000)
                elements = cf.query_selector_all('img')
                print(f"\n📄  img alt tags inside iframe-0:")
                for el in elements:
                    alt = el.get_attribute('alt') or ''
                    if alt:
                        print(f"   alt={alt!r}")
            else:
                print("⚠️  Could not get content frame for iframe-0")
        except Exception as e:
            print(f"⚠️  Error reading iframe-0: {e}")
    else:
        print("⚠️  No iframes found on page")

    def dump_iframe_ads():
        try:
            iframes = page.query_selector_all('iframe')
            if not iframes:
                return
            cf = iframes[0].content_frame()
            if not cf:
                return
            cf.wait_for_load_state('domcontentloaded', timeout=10000)
            imgs = cf.query_selector_all('img')
            alts = [el.get_attribute('alt') for el in imgs if el.get_attribute('alt')]
            if alts:
                print(f"\n📢  Ads in iframe-0:")
                for alt in alts:
                    print(f"   alt={alt!r}")
        except Exception as e:
            print(f"⚠️  iframe ad dump error: {e}")

    def human_click(el):
        box = el.bounding_box()
        if not box:
            el.click()
            return
        # move to a random point inside the element
        x = box['x'] + box['width']  * random.uniform(0.3, 0.7)
        y = box['y'] + box['height'] * random.uniform(0.3, 0.7)
        page.mouse.move(x, y, steps=random.randint(10, 25))
        time.sleep(random.uniform(0.1, 0.4))
        page.mouse.click(x, y)

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
            page.wait_for_load_state('networkidle', timeout=20000)
            dump_iframe_ads()
        except Exception as e:
            print(f"⚠️  Click error on {href}: {e}")

    print(f"\n✅  Analysis complete.\n")

