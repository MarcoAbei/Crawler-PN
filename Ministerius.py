import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time
import json
import os

# Configurazione (puoi personalizzarle per il tuo sito)
START_URL = "https://pninclusione21-27.lavoro.gov.it/"
DOMAIN = "pninclusione21-27.lavoro.gov.it"
CHECK_INTERVAL = 0.5
DATA_FILE = "link_results.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:100.0) Gecko/20100101 Firefox/100.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}

def print_banner():
    print(r"""
                                                                                                                                                  

.___  ___.  __  .__   __.  __       _______.___________. _______ .______       __   __    __       _______.
|   \/   | |  | |  \ |  | |  |     /       |           ||   ____||   _  \     |  | |  |  |  |     /       |
|  \  /  | |  | |   \|  | |  |    |   (----`---|  |----`|  |__   |  |_)  |    |  | |  |  |  |    |   (----`
|  |\/|  | |  | |  . `  | |  |     \   \       |  |     |   __|  |      /     |  | |  |  |  |     \   \    
|  |  |  | |  | |  |\   | |  | .----)   |      |  |     |  |____ |  |\  \----.|  | |  `--'  | .----)   |   
|__|  |__| |__| |__| \__| |__| |_______/       |__|     |_______|| _| `._____||__|  \______/  |_______/    
                                                                                                           
                                                                   
              Sovrano della Coerenza Digitale
    """)

def crawl_website(start_url, domain):
    visited = set()
    to_visit = [start_url]
    referrers = {}

    while to_visit:
        current_page = to_visit.pop()

        if current_page in visited:
            continue

        visited.add(current_page)

        try:
            response = requests.get(current_page, timeout=10, headers=HEADERS)
        except requests.exceptions.RequestException as e:
            print(f"Errore di connessione a {current_page}: {e}")
            continue

        if response.status_code >= 400:
            continue

        soup = BeautifulSoup(response.text, "html.parser")

        def register_link(link_url):
            if link_url not in referrers:
                referrers[link_url] = set()
            referrers[link_url].add(current_page)

        # Link <a>
        for a_tag in soup.find_all("a"):
            href = a_tag.get("href")
            if href:
                absolute_link = urljoin(current_page, href)
                parsed_link = urlparse(absolute_link)
                register_link(absolute_link)
                if parsed_link.netloc == domain:
                    if absolute_link not in visited:
                        to_visit.append(absolute_link)

        # Immagini <img>
        for img_tag in soup.find_all("img"):
            src = img_tag.get("src")
            if src:
                absolute_link = urljoin(current_page, src)
                register_link(absolute_link)

        # Tag multimediali (video, audio, source, iframe)
        for media_tag in soup.find_all(["video", "audio", "source", "iframe"]):
            src = media_tag.get("src")
            if src:
                absolute_link = urljoin(current_page, src)
                register_link(absolute_link)

        time.sleep(CHECK_INTERVAL)
    
    return visited, referrers

def check_links(links):
    results = {}
    for link in links:
        try:
            response = requests.head(link, allow_redirects=True, timeout=10, headers=HEADERS)
            code = response.status_code

            if code in [401, 403, 405]:
                response = requests.get(link, allow_redirects=True, timeout=10, headers=HEADERS)
                code = response.status_code

            is_ok = (code < 400)
            parsed_link = urlparse(link)
            is_internal = (parsed_link.netloc == DOMAIN)
            results[link] = {
                "status_code": code,
                "is_working": is_ok,
                "internal_link": is_internal
            }
        except requests.exceptions.RequestException:
            parsed_link = urlparse(link)
            is_internal = (parsed_link.netloc == DOMAIN)
            results[link] = {
                "status_code": None,
                "is_working": False,
                "internal_link": is_internal
            }
        time.sleep(CHECK_INTERVAL)
    return results

def load_previous_data(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def main():
    # Stampiamo l'ASCII art
    print_banner()

    print(f"[*] Inizio crawling del sito {START_URL} ...")
    internal_links, referrers = crawl_website(START_URL, DOMAIN)
    print(f"[+] Trovate {len(internal_links)} pagine interne.")
    print(f"[+] Referrers registrati per {len(referrers)} link totali.")

    all_links = set(referrers.keys())

    print("\n[*] Verifico lo stato di ogni link...")
    current_results = check_links(all_links)

    previous_data = load_previous_data(DATA_FILE)
    previous_links = set(previous_data.keys())
    current_links = set(current_results.keys())

    removed = previous_links - current_links
    added = current_links - previous_links

    became_broken = []
    for link in current_links.intersection(previous_links):
        if previous_data[link]["is_working"] and not current_results[link]["is_working"]:
            became_broken.append(link)

    print("\n=== REPORT ===")

    if removed:
        print("\nLink potenzialmente rimossi (erano presenti prima, ora no):")
        for r in removed:
            print(f" - {r}")
    else:
        print("Nessun link rimosso.")

    if added:
        print("\nLink nuovi (non esistevano prima):")
        for a in added:
            print(f" + {a}")
    else:
        print("\nNessun link nuovo.")

    if became_broken:
        print("\nLink che prima funzionavano e ora sono rotti:")
        for b in became_broken:
            print(f" ! {b}")
    else:
        print("\nNessun link, prima funzionante, è diventato rotto.")

    broken_links_now = [l for l, val in current_results.items() if not val["is_working"]]
    if broken_links_now:
        print(f"\nLink rotti nella scansione attuale ({len(broken_links_now)}):")
        for bl in broken_links_now:
            code = current_results[bl]['status_code']
            print(f" - {bl} (status: {code})")
            if bl in referrers:
                print(f"   -> Riferimento in {len(referrers[bl])} pagine:")
                for ref_page in referrers[bl]:
                    print(f"      - {ref_page}")
    else:
        print("\nNon ci sono link rotti nella scansione attuale.")

    # Unione dei dati di referrers nei risultati
    for link in current_results:
        if link in referrers:
            current_results[link]["referrers"] = sorted(list(referrers[link]))
        else:
            current_results[link]["referrers"] = []

    save_data(DATA_FILE, current_results)
    print(f"\n[*] Analisi completata. Risultati salvati in {DATA_FILE}")

if __name__ == "__main__":
    main()
