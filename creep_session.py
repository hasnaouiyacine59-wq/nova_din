"""Shared CreepJS fingerprint snapshot — usable from any script."""
import os, json, time, requests

SESSIONS_DIR = os.path.join(os.path.dirname(__file__), "sessions_fp")

CC_LANG = {
    "US":("en-US","America/New_York"),    "GB":("en-GB","Europe/London"),
    "DE":("de-DE","Europe/Berlin"),       "FR":("fr-FR","Europe/Paris"),
    "IT":("it-IT","Europe/Rome"),         "ES":("es-ES","Europe/Madrid"),
    "NL":("nl-NL","Europe/Amsterdam"),    "PL":("pl-PL","Europe/Warsaw"),
    "BR":("pt-BR","America/Sao_Paulo"),   "RU":("ru-RU","Europe/Moscow"),
    "TR":("tr-TR","Europe/Istanbul"),     "JP":("ja-JP","Asia/Tokyo"),
    "CN":("zh-CN","Asia/Shanghai"),       "SE":("sv-SE","Europe/Stockholm"),
    "CA":("en-CA","America/Toronto"),     "AU":("en-AU","Australia/Sydney"),
    "IN":("en-IN","Asia/Kolkata"),        "MX":("es-MX","America/Mexico_City"),
    "KR":("ko-KR","Asia/Seoul"),          "SG":("en-SG","Asia/Singapore"),
    "NO":("nb-NO","Europe/Oslo"),         "CH":("de-CH","Europe/Zurich"),
    "AT":("de-AT","Europe/Vienna"),       "BE":("fr-BE","Europe/Brussels"),
    "MA":("ar-MA","Africa/Casablanca"),   "SA":("ar-SA","Asia/Riyadh"),
    "AE":("ar-AE","Asia/Dubai"),          "ZA":("en-ZA","Africa/Johannesburg"),
    "UA":("uk-UA","Europe/Kyiv"),         "RO":("ro-RO","Europe/Bucharest"),
    "PT":("pt-PT","Europe/Lisbon"),       "IE":("en-IE","Europe/Dublin"),
    "FI":("fi-FI","Europe/Helsinki"),     "DK":("da-DK","Europe/Copenhagen"),
    "HU":("hu-HU","Europe/Budapest"),     "GR":("el-GR","Europe/Athens"),
    "ID":("id-ID","Asia/Jakarta"),        "TH":("th-TH","Asia/Bangkok"),
    "VN":("vi-VN","Asia/Ho_Chi_Minh"),    "PH":("en-PH","Asia/Manila"),
    "NZ":("en-NZ","Pacific/Auckland"),    "AR":("es-AR","America/Argentina/Buenos_Aires"),
    "HK":("zh-HK","Asia/Hong_Kong"),      "TW":("zh-TW","Asia/Taipei"),
    "MY":("ms-MY","Asia/Kuala_Lumpur"),   "EG":("ar-EG","Africa/Cairo"),
    "IL":("he-IL","Asia/Jerusalem"),      "NG":("en-NG","Africa/Lagos"),
}

def get_ip(ip_api="http://127.0.0.1:5000/ip"):
    try:
        return requests.get(ip_api, timeout=5).json().get("ip", "?")
    except Exception:
        return "?"

def capture(page, tor_ip=None, wait_ms=18000):
    """
    Visit CreepJS, wait for evaluation, parse results, save session JSON.
    Returns the report dict.
    """
    page.goto("https://abrahamjuliot.github.io/creepjs", timeout=60000)
    page.wait_for_timeout(wait_ms)

    creep = page.evaluate("""() => {
        const txt = document.body.innerText;
        const m = (re) => { const r = txt.match(re); return r ? r[1] : null; };
        return {
            fp_id:       m(/FP ID:\\s*([a-f0-9]{10,})/),
            headless:    m(/(\\d+)% like headless/),
            stealth:     m(/(\\d+)% stealth/),
            platform:    m(/device:\\s*([^\\n]+)/),
            cores_ram:   m(/cores: (\\d+, ram: \\d+)/),
            webrtc_ip:   m(/\\nip: ([\\d\\.]+)/),
            raw_summary: txt.slice(0, 6000),
        };
    }""")

    session_id = str(int(time.time()))
    sess_dir   = os.path.join(SESSIONS_DIR, session_id)
    os.makedirs(sess_dir, exist_ok=True)

    report = {
        "session_id":  session_id,
        "tor_ip":      tor_ip or get_ip(),
        "fingerprint": {
            "fp_id":     creep.get("fp_id"),
            "headless%": creep.get("headless"),
            "stealth%":  creep.get("stealth"),
            "platform":  creep.get("platform"),
            "cores_ram": creep.get("cores_ram"),
            "webrtc_ip": creep.get("webrtc_ip"),
        },
        "raw_summary": creep.get("raw_summary"),
    }

    with open(os.path.join(sess_dir, "creepjs.json"), "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n  SESSION  : {session_id}")
    print(f"  TOR IP   : {report['tor_ip']}")
    for k, v in report["fingerprint"].items():
        flag = " ⚠️" if k == "headless%" and v and int(v) > 20 else ""
        print(f"  {k:<10}: {v}{flag}")
    print(f"  Saved → {sess_dir}/creepjs.json\n")

    return report
