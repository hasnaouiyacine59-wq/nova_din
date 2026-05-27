import time, random, string

AADS_URL = 'https://aads.com/'
EMAIL_DOMAINS = ["techxbox.eu.org", "beta-sig.eu.org", "itchigho.eu.org", "sec4891.eu.org", "youoneshell.eu.org"]

CHAT_MESSAGES = [
    "Hi, I just signed up and wanted to know how to get started with advertising.",
    "Hello! Can you tell me more about your ad pricing?",
    "Hey, I'm new here. What's the minimum budget to run a campaign?",
    "Hi there! I'm interested in crypto advertising, can you help?",
    "Hello, I'd like to learn more about your publisher program.",
    "Hi! How long does it take for a campaign to get approved?",
    "Hey, what payment methods do you accept?",
    "Hello! I'm looking to promote my crypto project, where do I start?",
    "Hi, can you explain how the CPM model works on your platform?",
    "Hey there! Do you offer any discounts for new advertisers?",
    "I confirmed my email but still can't log in, what's going on?",
    "My account says it's active but I get an error every time I try to access it.",
    "I've been waiting for account activation for hours, this is ridiculous.",
    "Why is my account blocked after just signing up? I haven't done anything wrong.",
    "Your support is absolutely useless, I've been going in circles for hours.",
    "I confirmed my email and my account still shows as inactive, fix this.",
    "This is the worst onboarding experience I've ever had on any platform.",
    "I can't access my dashboard even though my account is supposedly confirmed.",
    "Every time I try to log in it just redirects me back to the homepage, great system.",
    "I signed up, confirmed email, and now I'm locked out. What kind of service is this?",
    "Your activation emails take forever and then the account still doesn't work.",
    "I've tried resetting my password twice and still can't get in, please help.",
    "Is there actually anyone on support or is it all bots?",
    "My account was activated according to the email but the platform says otherwise.",
    "How is it possible that a crypto ad network has such broken account management?",
    "activate my account asshole",
    "activez mon compte espèce d'idiot",
    "aktiviere mein Konto du Vollidiot",
    "activa mi cuenta imbécil",
    "attiva il mio account stronzo",
    "ative minha conta seu idiota",
    "активируй мой аккаунт, придурок",
    "hesabımı etkinleştir aptal",
    "فعّل حسابي يا أحمق",
    "मेरा अकाउंट एक्टिवेट करो बेवकूफ",
    "私のアカウントを有効にしろ、このバカ",
    "내 계정 활성화해 이 멍청아",
    "激活我的账户，你这个混蛋",
    "activeer mijn account idioot",
    "aktywuj moje konto idioto",
    "aktivera mitt konto ditt as",
    "aktiver kontoen min din idiot",
    "aktivoi tilini idiootti",
    "aktiváld a fiókomat te hülye",
    "aktivuj můj účet ty vole",
    "ενεργοποίησε τον λογαριασμό μου ηλίθιε",
    "активуй мій акаунт, ідіоте",
    "活化我的帳戶，你這個混蛋",
    "aktifkan akun saya bodoh",
    "เปิดใช้งานบัญชีของฉันไอ้โง่",
    "kích hoạt tài khoản của tôi đồ ngốc",
    "i-activate ang aking account gago",
    "حساب منو فعال کن احمق",
    "aktivizoni llogarinë time budalla",
    "aktiviraj moj nalog idiote",
]

MONEY_MESSAGES = [
    "i need back my 2$ asshole",
    "rends-moi mes 2$ espèce d'idiot",
    "gib mir meine 2$ zurück du Vollidiot",
    "devuélveme mis 2$ imbécil",
    "ridammi i miei 2$ stronzo",
    "me devolva meus 2$ seu idiota",
    "верни мои 2$, придурок",
    "2 dolarımı geri ver aptal",
    "أعدني 2$ يا أحمق",
    "मेरे 2$ वापस करो बेवकूफ",
    "2ドル返せ、このバカ",
    "내 2달러 돌려줘 이 멍청아",
    "还我2美元，你这个混蛋",
    "geef me mijn 2$ terug idioot",
    "oddaj mi moje 2$ idioto",
    "ge tillbaka mina 2$ ditt as",
    "gi meg tilbake mine 2$ din idiot",
    "palauta 2$ idiootti",
    "add vissza a 2$-om te hülye",
    "vrať mi moje 2$ ty vole",
    "δώσε μου πίσω τα 2$ μου ηλίθιε",
    "поверни мої 2$, ідіоте",
    "還我2美元，你這個混蛋",
    "kembalikan 2$ saya bodoh",
    "คืนเงิน 2$ ของฉันมาไอ้โง่",
    "trả lại 2$ của tôi đồ ngốc",
    "ibalik mo ang 2$ ko gago",
    "2 دلارمو پس بده احمق",
    "kthemni 2$ e mia budalla",
    "vrati mi moja 2$ idiote",
]

def random_email():
    user = ''.join(random.choices(string.ascii_lowercase + string.digits, k=random.randint(7, 12)))
    return f"{user}@{random.choice(EMAIL_DOMAINS)}"

def run(page):
    print(f"\n🌐  Navigating to {AADS_URL} ...")
    try:
        page.goto(AADS_URL, wait_until='domcontentloaded', timeout=60000)
        page.wait_for_load_state('load', timeout=30000)
    except Exception as e:
        print(f"[ads] goto/load warning: {e}")

    if page.is_closed():
        print("[ads] page closed during navigation, skipping")
        return

    print(f"✅  {page.title()} ({page.url})")
    time.sleep(random.uniform(3, 6))


if __name__ == '__main__':
    import os, glob, shutil, sys
    sys.stdout.reconfigure(encoding='utf-8')
    os.environ['CAMOUFOX_NO_UPDATE'] = '1'

    for _p in glob.glob('/tmp/playwright_firefoxdev_profile-*') + glob.glob('/tmp/playwright-artifacts-*'):
        try: shutil.rmtree(_p)
        except Exception: pass

    from camoufox.sync_api import Camoufox
    from camoufox.addons import DefaultAddons

    with Camoufox(
        headless=False,
        os='windows',
        window=(1366, 768),
        block_webrtc=True,
        exclude_addons=[DefaultAddons.UBO],
        i_know_what_im_doing=True,
    ) as browser:
        page = browser.new_page()
        run(page)

        # wait for JS hydration
        try:
            page.wait_for_load_state('networkidle', timeout=15000)
        except Exception:
            pass

        # --- SIGNUP STEPS (commented out) ---
        # with open('ads_dump.html', 'w', encoding='utf-8') as f:
        #     f.write(page.content())
        # print("[ads] HTML dumped to ads_dump.html")

        # links = page.eval_on_selector_all('a', 'els => els.map(e => e.innerText.trim() + " | " + e.href)')
        # for l in links:
        #     if l.strip():
        #         print(f"[ads] link: {l}")

        # try:
        #     nav_btn = page.locator('[class*="sign-up"]').first
        #     nav_btn.wait_for(state='visible', timeout=15000)
        #     nav_btn.click()
        #     print("[ads] nav auth button clicked")
        #     time.sleep(1)

        #     signup_tab = page.locator('text=Sign Up').first
        #     signup_tab.wait_for(state='visible', timeout=10000)
        #     signup_tab.click()
        #     print("[ads] Sign Up tab clicked")
        #     time.sleep(1)

        #     email = random_email()
        #     print(f"[ads] using email: {email}")
        #     email_input = page.locator('#create-account-email-field')
        #     email_input.wait_for(state='visible', timeout=10000)
        #     email_input.fill(email)
        #     time.sleep(random.uniform(0.5, 1.2))

        #     cb = page.locator('#sign-up-receive-emails-checkbox')
        #     if not cb.is_checked():
        #         page.locator('label[for="sign-up-receive-emails-checkbox"]').click()
        #         print("[ads] opted out of emails")

        #     continue_btn = page.locator('button[type="submit"], button:has-text("Continue")').first
        #     continue_btn.click()
        #     print("[ads] Continue clicked")
        #     time.sleep(2)
        #     try:
        #         if continue_btn.is_visible():
        #             continue_btn.click()
        #             print("[ads] Continue re-clicked")
        #     except Exception:
        #         pass

        #     pwd_input = page.locator('input[type="password"], input[placeholder*="password" i]').first
        #     pwd_input.wait_for(state='visible', timeout=60000)
        #     print("[ads] password field appeared")

        #     from get_2FA import get_aads_password
        #     pwd = get_aads_password(email)
        #     if not pwd:
        #         print("[ads] ❌ could not retrieve password from email")
        #     else:
        #         print(f"[ads] got password: {pwd}")
        #         pwd_input.fill(pwd)
        #         time.sleep(random.uniform(0.5, 1.0))
        #         page.locator('#confirm-account-password').press('Tab')
        #         time.sleep(0.3)
        #         page.locator('button[type="submit"]:has-text("Confirm")').click()
        #         print("[ads] Confirm clicked")
        #         try:
        #             page.wait_for_load_state('networkidle', timeout=15000)
        #         except Exception:
        #             pass
        #         print(f"[ads] ✅ signed up, url: {page.url}")
        #         with open('accounts.txt', 'a', encoding='utf-8') as f:
        #             f.write(f"{email}:{pwd}\n")
        #         print(f"[ads] saved {email}:{pwd} → accounts.txt")
        # except Exception as e:
        #     print(f"[ads] signup failed: {e}")
        # --- END SIGNUP ---

        # Click "Chat with AADS"
        try:
            chat_btn = page.locator('[data-type="chat"][aria-label="Chat with AADS"]').first
            chat_btn.wait_for(state='visible', timeout=20000)
            chat_btn.click()
            print("[ads] Chat with AADS clicked")
            time.sleep(6)

            crisp_frame = next((fr for fr in page.frames if 'crisp' in fr.url), None)
            if not crisp_frame:
                crisp_frame = next((fr for fr in page.frames if fr.locator('textarea[name="message"]').count() > 0), None)

            if crisp_frame:
                msg_box = crisp_frame.locator('textarea[name="message"]')
                msg_box.wait_for(state='visible', timeout=15000)
                msg_box.click()
                msg_box.type(random.choice(CHAT_MESSAGES), delay=60)
                msg_box.press('Enter')
                print("[ads] chat message sent")

                time.sleep(random.uniform(2, 4))
                msg_box.click()
                msg_box.type(random.choice(MONEY_MESSAGES), delay=60)
                msg_box.press('Enter')
                print("[ads] second chat message sent")
            else:
                print("[ads] crisp iframe not found")
        except Exception as e:
            print(f"[ads] chat failed: {e}")

        time.sleep(random.uniform(15, 30))
