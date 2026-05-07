import os, csv, logging, asyncio, re, requests, sys
from datetime import datetime
from faker import Faker
from playwright.async_api import async_playwright

# --- CONFIGURAÇÕES ---
CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "accounts.csv")

POSTBACK_URLS = [
    "https://jadedynasty.online/postback.php",
    "https://kunlun.jadedynasty.online/postback.php",
    "https://classic.jadedynasty.online/postback.php"
]

fake = Faker()
logging.basicConfig(level=logging.INFO, format="%(message)s")

# --- MECÂNICA 1: VOTO INVISÍVEL (HTTP) ---
def run_postback_full(uid, ip):
    success_count = 0
    if not uid: return 0
    
    headers = {
        "User-Agent": fake.user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    }

    for pb in POSTBACK_URLS:
        try:
            requests.get(f"{pb}?p_resp={uid}&ip={ip}", headers=headers, timeout=5)
            requests.get(f"{pb}?custom={uid}&votingip={ip}", headers=headers, timeout=5)
            
            payload = f"VoterIP={ip}&pingUsername={uid}&Successful=0&Reason=Successful"
            post_headers = headers.copy()
            post_headers["Content-Type"] = "application/x-www-form-urlencoded"
            requests.post(pb, data=payload, headers=post_headers, timeout=5)
            
            success_count += 1
        except Exception as e:
            logging.error(f"Erro no postback para ID {uid}: {e}")
            continue
    return success_count

# --- MECÂNICA 2: NAVEGADOR (CONFERÊNCIA E RESGATE) ---
async def process_acc(acc, ip, pb_count):
    login, pwd = acc.get('login'), acc.get('senha')
    res = {"u": login, "v": 0, "j": 0, "ok": False, "pb": pb_count}
    
    async with async_playwright() as p:
        browser = None
        try:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
            context = await browser.new_context(user_agent=fake.user_agent())
            page = await context.new_page()
            
            await page.goto("https://jadedynasty.online/page.php?page=account", timeout=60000)
            await page.fill('input[name="login"]', login)
            await page.fill('input[name="passwd"]', pwd)
            await page.click('button.all-btn')
            
            await page.wait_for_selector("#green_jades", timeout=15000)
            
            v_text = await page.locator("p:has-text('Your votes')").first.text_content()
            res["v"] = int(re.search(r"(\d+)", v_text).group(1)) if v_text else 0
            
            j_text = await page.locator("#green_jades").text_content()
            res["j"] = float(j_text.replace('.', '').replace(',', '.')) if j_text else 0
            
            for img in ["top1.png", "top2.png", "top3.png"]:
                sel = f'a[href*="claim=1"] img[src*="{img}"]'
                if await page.locator(sel).is_visible():
                    await page.click(sel)
                    await asyncio.sleep(1)
            
            res["ok"] = True
        except Exception as e:
            logging.error(f"Erro ao processar conta {login}: {e}")
            res["ok"] = False
        finally:
            if browser: await browser.close()
    return res

# --- ORQUESTRAÇÃO PRINCIPAL ---
async def main():
    if not os.path.exists(CSV_PATH):
        logging.error(f"Arquivo {CSV_PATH} não encontrado!")
        return

    with open(CSV_PATH, encoding='utf-8') as f:
        accs = [row for row in csv.DictReader(f)]
    
    results = []
    print(f"🚀 Iniciando processamento de {len(accs)} contas...")

    for a in accs:
        ip = fake.ipv4()
        uid = a.get('id')
        print(f"📡 Processando: {a.get('login')} (IP: {ip})")
        
        pb_count = run_postback_full(uid, ip)
        res = await process_acc(a, ip, pb_count)
        results.append(res)

    # Relatório simplificado no Log do GitHub
    total_jades = sum(r['j'] for r in results)
    success_count = sum(1 for r in results if r['ok'])
    
    print("\n" + "="*30)
    print(f"RESUMO DA EXECUÇÃO")
    print(f"Total Jades: {total_jades:,.0f}")
    print(f"Sucesso: {success_count}/{len(results)}")
    print("="*30)

if __name__ == "__main__":
    asyncio.run(main())