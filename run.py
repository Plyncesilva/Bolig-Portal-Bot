#!./.venv/bin/python
import httpx
from dotenv import load_dotenv, dotenv_values
load_dotenv()

import logging
from bs4 import BeautifulSoup
import json
import random
import time
from datetime import datetime

from constants import *

cookies = dotenv_values(".env.cookies")

headers = {
    "Host": "www.boligportal.dk",
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:137.0) Gecko/20100101 Firefox/137.0",
    "Cookie": cookies["COOKIES"],
    "Accept": "*/*",
    "Accept-Language": "da",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.boligportal.dk/login",
    "X-Request-Source": "WEB_FRONTEND",
    "X-Csrftoken": "KOeHTlFz5ba5JALh7NyI25y2d1StOzAS",
    "Content-Type": "text/plain;charset=UTF-8",
    "Origin": "https://www.boligportal.dk",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "Priority": "u=0",
    "Te": "trailers"
}

def setup_logging():
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # Basic logging config
    logging.basicConfig(
        filename='bolig_bot.log',  # Or any path you want
        filemode='a',                       # Append mode
        level=logging.INFO,                 # Or DEBUG, WARNING, etc.
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

def extract_store_json(response_text: str) -> dict:
    """
    Extracts the JSON object inside the <script id="store" type="application/json"> tag.
    """
    soup = BeautifulSoup(response_text, "html.parser")

    store_script = soup.find("script", {"id": "store", "type": "application/json"})

    if not store_script:
        raise ValueError("❌ <script id='store' type='application/json'> tag not found.")
    
    try:
        store_json = json.loads(store_script.string)
        return store_json
    except json.JSONDecodeError as e:
        raise ValueError(f"❌ Failed to parse JSON from script tag: {e}")
    except Exception as e:
        raise ValueError(f"❌ Unrecognized error while extracting json data: {e}")

def login(credentials: dict):
    """
    credentials of format:
    {"username":"email","password":"password"}
    """
    url = BASE_URL + LOGIN
    try:
        with httpx.Client(http2=True) as client:  # Or add proxies & verify=False if using Burp
            response = client.post(
                url,
                headers=headers,
                json=credentials
            )
            response.raise_for_status()

            # Extract cookies from the response
            new_cookies = response.cookies.jar  # CookieJar object
            cookie_dict = {cookie.name: cookie.value for cookie in new_cookies}
            
            # Parse the original cookies into a dict
            existing_cookie_header = headers.get("Cookie", "")
            cookie_parts = [c.strip() for c in existing_cookie_header.split(";") if "=" in c]
            cookie_dict_existing = dict(c.split("=", 1) for c in cookie_parts)

            # Merge new cookies (override if same keys)
            cookie_dict_combined = {**cookie_dict_existing, **cookie_dict}

            # Rebuild Cookie header string
            new_cookie_header = "; ".join(f"{k}={v}" for k, v in cookie_dict_combined.items())
            headers["Cookie"] = new_cookie_header

    except httpx.RequestError as e:
        logging.error(f"Error making request, aborting: {e}")
        exit(0)
    except Exception as e:
        logging.error(f"Error processing data, aborting: {e}")
        exit(0)

def get_request(url):
    try:
        with httpx.Client(http2=True) as client:
            response = client.get(
                url,
                headers=headers
            )
            response.raise_for_status()

            return response

    except httpx.RequestError as e:
        logging.error(f"Error making request: {e}")
    except Exception as e:
        logging.error(f"Error processing data: {e}")

def get_properties(offset):
    url = BASE_URL + PROPERTIES + f"&offset={offset}"
    response = get_request(url)

    return extract_store_json(response.text)["props"]["page_props"]["results"]

def get_total_properties():
    url = BASE_URL + PROPERTIES
    response = get_request(url)

    return extract_store_json(response.text)["props"]["page_props"]["result_count"]

def send_message(ad_id):
    """
    MESSAGE of format:
    {"ad_id":"ad_id","message":"message"}
    """
    url = BASE_URL + SEND_MESSAGE
    env = dotenv_values(".env")
    json_body = { "ad_id": ad_id, "message": env["LANDLORD_MESSAGE"] }

    try:
        with httpx.Client(http2=True) as client:  # Or add proxies & verify=False if using Burp
            response = client.post(
                url,
                headers=headers,
                json=json_body
            )
            response.raise_for_status()

            print(f"✅ Sent message to id {ad_id}")

    except httpx.RequestError as e:
        logging.error(f"Error making request: {e}")
    except Exception as e:
        logging.error(f"Error processing data: {e}")

def record_processed_property(url):
    with open(PROCESSED_URLS_FILE_NAME, "a") as file:
        file.write(url + "\n")

def process_properties(urls: list):
    for url in urls:
        logging.info(f"➡️ Processing new property: {url} ...")
        ad_id = url.split('-')[-1]
        # send_message(ad_id)
        record_processed_property(url)
        logging.info(f"🟢 Done!")
        random_seconds = random.randint(60, 60 * 5)
        logging.info(f"💤 Sleeping for {random_seconds} seconds before the next property...")
        time.sleep(random_seconds)

def get_all_properties_urls():
    urls = []
    offset = 0
    total = get_total_properties()

    while offset < total:
        properties = get_properties(offset)
        for p in properties:
            urls.append(p["url"])
        offset += len(properties)
    
    return urls

def filter_new_urls(urls: list):
    try:
        with open(PROCESSED_URLS_FILE_NAME, "r") as file:
            processed_urls = set(line.strip() for line in file)
    except FileNotFoundError:
        processed_urls = set()

    return [url for url in urls if url not in processed_urls]

if __name__ == "__main__":
    setup_logging()
    
    credentials = dotenv_values(".env.credentials")

    logging.info("")
    logging.info("======================================")
    logging.info("🟢 BEGIN BOLIG PORTAL BOT EXECUTION 🟢")
    logging.info("======================================")
    logging.info("")
    logging.info("👀 Logging in to Bolig Portal...")
    login(credentials)
    logging.info("✅ Logged in!")

    logging.info("")
    logging.info("➰ Initializing main loop...")
    try:
        while True:
            urls = get_all_properties_urls()
            new_urls = filter_new_urls(urls)
            if new_urls != []:
                logging.info(f"🏘️ Found {len(new_urls)} new properties! 💬 Writing to the landlords...")
                process_properties(new_urls)
                logging.info(f"✅ Successfully processed {len(new_urls)} new properties!")
            else:
                if 0 <= datetime.now().hour < 6:
                    # Between midnight and 6 AM: 1 to 2 hours
                    random_seconds = random.randint(60 * 60, 60 * 60 * 2)
                else:
                    random_seconds = random.randint(60, 5 * 60)

                logging.info(f"😑 Nothing new yet... Will take a nap for {random_seconds} seconds 💤")
                time.sleep(random_seconds)

    except Exception as e:
        logging.error(f"Error: {e}")