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

headers = {
    "Host": "www.boligportal.dk",
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:137.0) Gecko/20100101 Firefox/137.0",
    "Accept": "*/*",
    "Accept-Language": "da",
    "Accept-Encoding": "gzip, deflate, br",
    "X-Request-Source": "WEB_FRONTEND",
    "Content-Type": "text/plain;charset=UTF-8",
    "Origin": "https://www.boligportal.dk",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "Priority": "u=0",
    "Te": "trailers"
}

import sys

areas = {
        "osterbro": "/en/rental-apartments,rental-houses,rental-townhouse/all-cities/all-rooms/?max_monthly_rent=14000&zoom=13.335238619157435&center=12.593388516164737%2C55.69987525757085&min_lat=55.68706792441779&min_lng=12.549914819153656&max_lat=55.71267839537427&max_lng=12.636862213176784",
        "frederiksberg": "/en/rental-apartments,rental-houses,rental-townhouse/all-cities/all-rooms/?max_monthly_rent=14000&zoom=13.335238619157435&center=12.569100394086604%2C55.67690343223944&min_lat=55.66408857325047&min_lng=12.525626697074358&max_lat=55.68971409456097&max_lng=12.612574091097429"
    }


PROPERTIES = areas[sys.argv[1]]

def setup_logging():
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # Basic logging config
    logging.basicConfig(
        filename='bolig_bot.log',  # Or any path you want
        filemode='a',                       # Append mode
        level=logging.INFO,                 # Or DEBUG, WARNING, etc.
        format=f'%(asctime)s - %(levelname)s - {sys.argv[1]} - %(message)s'
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


def refresh_cloudflare_cookies():
    url = BASE_URL
    response = get_request(url)  # Expected to return a `requests.Response` object

    # Extract cookies from the response
    cookies = response.cookies

    extra_cookies = {
        '_ga_0H61X0LYSG': 'GS1.1.1744801180.4.1.1744801376.38.0.0',
        'CookieInformationConsent': '%7B%22website_uuid%22%3A%22f5510035-790d-43f0-94c7-4e49b742a6a4%22%2C%22timestamp%22%3A%222025-04-15T17%3A52%3A25.104Z%22%2C%22consent_url%22%3A%22https%3A%2F%2Fwww.boligportal.dk%2Flogin%22%2C%22consent_website%22%3A%22boligportal.dk%22%2C%22consent_domain%22%3A%22www.boligportal.dk%22%2C%22user_uid%22%3A%226f314d51-c843-4758-9d3b-28033790415d%22%2C%22consents_approved%22%3A%5B%22cookie_cat_necessary%22%2C%22cookie_cat_functional%22%2C%22cookie_cat_statistic%22%2C%22cookie_cat_marketing%22%2C%22cookie_cat_unclassified%22%5D%2C%22consents_denied%22%3A%5B%5D%2C%22user_agent%22%3A%22Mozilla%2F5.0%20%28X11%3B%20Ubuntu%3B%20Linux%20x86_64%3B%20rv%3A137.0%29%20Gecko%2F20100101%20Firefox%2F137.0%22%7D',
        '_pk_id.2.20f7': '8a86b228e09aa749.1744739545.',
        'mtm_cookie_consent': '1744801355276',
        '_gcl_au': '1.1.2105709907.1744739545',
        '_ga': 'GA1.1.1492258431.1744739547',
        '_gid': 'GA1.2.198060658.1744741297',
        '_ga_GCSK2D78ZH': 'GS1.1.1744797766.3.1.1744797931.60.0.0',
        '_pk_ses.2.20f7': '1',
        '_uetsid': '47bffbc01a2011f0ab463f59e62affb2',
        '_uetvid': '8c5f16607f3111efbc351b7893f6abea'
    }


    # Merge extra cookies into the main cookie dict
    cookies.update(extra_cookies)

    # Build final Cookie header string
    cookie_header = '; '.join(f"{key}={value}" for key, value in cookies.items())
    headers['Cookie'] = cookie_header

    # Add X-Csrftoken header if csrftoken is present
    if 'csrftoken' in cookies:
        headers['X-Csrftoken'] = cookies['csrftoken']



def login():
    """
    credentials of format:
    {"username":"email","password":"password"}
    """
    logging.info("👀 Logging in to Bolig Portal...")
    credentials = dotenv_values(".env.credentials")

    refresh_cloudflare_cookies()

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

            if 'csrftoken' in cookie_dict_combined:
                headers['X-Csrftoken'] = cookie_dict_combined['csrftoken']

    except httpx.RequestError as e:
        logging.error(f"Error making request, aborting: {e}")
        exit(0)
    except Exception as e:
        logging.error(f"Error processing data, aborting: {e}")
        exit(0)
    
    logging.info("✅ Logged in!")

def get_request(url, tries=3):
    try:
        with httpx.Client(http2=True) as client:
            response = client.get(
                url,
                headers=headers
        )
            response.raise_for_status()

            return response

    except httpx.RequestError as e:
        logging.error(f"Error making request: {e}\nRetrying with new login session")
        if tries > 0:
            login()
            get_request(url, tries - 1)
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

def send_message(url):
    """
    MESSAGE of format:
    {"ad_id":"ad_id","message":"message"}
    """
    ad_id = url.split('-')[-1]
    api_send_message = BASE_URL + SEND_MESSAGE
    env = dotenv_values(".env")
    json_body = { "ad_id": eval(ad_id), "body": env["LANDLORD_MESSAGE"] }

    headers["Referer"] = BASE_URL + url

    try:
        with httpx.Client( http2=True) as client:
            response = client.post(
                api_send_message,
                headers=headers,
                json=json_body
            )
            response.raise_for_status()
            logging.info(f"✅ Sent message to id {json_body.get('ad_id')}")
    
    except httpx.RequestError as e:
        logging.error(f"Error making request: {e}")
    except Exception as e:
        logging.error(f"Error processing data: {e}")

def record_processed_property(url):
    with open(PROCESSED_URLS_FILE_NAME, "a") as file:
        file.write(url + "\n")

def is_locked(url):
    try:
        with open(LOCKED_URLS_FILE_NAME, "r") as file:
            locked_urls = list(line.strip() for line in file)
            logging.info(f"Property {url} is locked? {url in locked_urls}")
            return url in locked_urls    
    except FileNotFoundError:
        return False

def unlock_properties(urls):
    logging.info(f"Unlocking {len(urls)} urls:\n{urls}")
    with open(LOCKED_URLS_FILE_NAME, "r") as file:
        locked_urls = file.readlines()
    locked_urls = [url.strip() for url in locked_urls]
    still_locked_urls = [url for url in locked_urls if url not in urls]

    with open(LOCKED_URLS_FILE_NAME, "w") as file:
        for url in still_locked_urls:
            file.write(url + "\n")

def lock_properties(urls):
    logging.info(f"Locking {len(urls)} properties for processing:\n{urls}")
    with open(LOCKED_URLS_FILE_NAME, "w") as file:
        for url in urls:
            file.write(url + "\n")

def process_properties(urls: list):
    random_seconds = random.randint(60 * 5, 60 * 20) # wait between 5 and 20 minutes before sending a message
    logging.info(f"💤 Sleeping for {random_seconds} seconds before processing the new properties...")
    time.sleep(random_seconds)
    for url in urls:
        logging.info(f"➡️ Processing new property: {url} ...")
        send_message(url)
        record_processed_property(url)
        logging.info(f"🟢 Done!")
        logging.info(f"💤 Sleeping for 60 seconds before processing the next property...")
        time.sleep(60)


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
    
    logging.info(f"Running bot for properties in {sys.argv[1]}...")

    logging.info("")
    logging.info("======================================")
    logging.info("🟢 BEGIN BOLIG PORTAL BOT EXECUTION 🟢")
    logging.info("======================================")
    logging.info("")
   
    login()
    
    logging.info("")
    logging.info("➰ Initializing main loop...")
    try:
        while True:
            urls = get_all_properties_urls()
            new_urls = filter_new_urls(urls)
            if new_urls != []:
                logging.info(f"🏘️ Found {len(new_urls)} new properties! 💬 Writing to the landlords...")
                
                new_urls = [url for url in new_urls if not is_locked(url) ]

                lock_properties(new_urls)
                process_properties(new_urls)
                unlock_properties(new_urls)
                
                logging.info(f"✅ Successfully processed {len(new_urls)} new properties!")
            else:
                hour = datetime.now().hour
                if 22 <= hour or hour < 4:
                    logging.info("Night night baby, see you tomorrow at 4 AM... 💤💤💤")
                    # wait until 4 AM to restart
                    while 22 <= hour or hour < 4:
                        time.sleep(60 * 60) # just sleep 1 hour before re-checking...
                        hour = datetime.now().hour

                    logging.info("Good morninggggggg, rise & shine baby, rise & shine 😎")
                    login()

                    random_seconds = 0 # dirty hack

                else:
                    random_seconds = random.randint(60, 5 * 60) # wait between 1 and 5 minutes before checking more houses

                logging.info(f"😑 Nothing new yet... Will take a nap for {random_seconds} seconds 💤")
                time.sleep(random_seconds)
    except KeyboardInterrupt:
        logging.info(f"🔴 PROGRAM INTERRUPTED! Exiting...")

    except Exception as e:
        logging.error(f"Error: {e}")
