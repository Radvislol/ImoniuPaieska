from flask import Flask, request, jsonify, render_template, send_file
import requests
import pandas as pd
import time
import re
from bs4 import BeautifulSoup
import io
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)

# !!! Svarbu: palik toki rakta !!!
API_KEY = "AIzaSyBA-p06TzO2hg0etC4L1PYDUIKrQLW9Fg0"

countries = [
    "Germany",
    "France",
    "Spain",
    "Poland",
    "Netherlands",
    "Italy",
]

industries = [
    "food manufacturer",
    "grain supplier",
    "meat supplier",
    "dairy supplier",
    "fruit supplier",
    "plastic manufacturer",
    "metal fabricator",
    "chemical manufacturer",
    "furniture manufacturer",
    "packaging manufacturer",
    "automotive manufacturer",
    "tire supplier",
    "construction supplier",
    "wood supplier",
    "e-commerce warehouse",
    "retail warehouse",
    "pharmaceuticals manufacturer",
    "industrial equipment supplier",
    "paper manufacturer",
    "electronics manufacturer",
    "steel manufacturer",
    "parts manufacturer",
]


global_seen_names = set()
global_seen_emails = set()

session = requests.Session()

def is_valid_domain(domain):
    """Patikrina, ar domenas turi dažnai naudojamus galūnes."""
    valid_extensions = (
        '.de', '.com', '.net', '.org', '.eu', '.info', '.biz', '.co', '.com.au',
        '.fr', '.it', '.es', '.nl', '.be', '.pl', '.ru', '.cn', '.jp', '.br',
        '.ca', '.us', '.uk', '.co.uk', '.in', '.mx', '.se', '.ch', '.at', '.dk',
        '.no', '.fi', '.cz', '.sk', '.hu', '.ro', '.gr', '.pt', '.ie', '.za',
        '.nz', '.ar', '.cl', '.tw', '.kr', '.my', '.sg', '.id', '.th', '.vn',
        '.gov', '.edu', '.mil', 
        '.pec.it', 
    )
    return any(domain.endswith(ext) for ext in valid_extensions)

def is_fake_email(email):
    """Patikrina, ar el. paštas yra potencialiai netikras ar bendrinis."""
    if len(email) > 50:
        return True 
    
    fake_patterns = [
        "example", "johndoe", "test@", "domain.com", 
        "no-reply@", "noreply@", "webmaster@", "postmaster@", "abuse@", 
        "hostmaster@", "root@", "ftp@", "smtp@", 
        "privacy@", "compliance@", 
        r"\d{3,}", # Tris ar daugiau skaičių
        r"^\d+-\d+.*@", # Skaičiai-brūkšnys-skaičiai el. pašto pradžioje (pvz., 591-0info@)
        r"^[a-zA-Z]*\d{3,}[a-zA-Z]*@" # Raidės+3+skaičiai+Raidės el. pašto pradžioje
    ]
    
    email_lower = email.lower()
    
    if any(re.search(pattern, email_lower) for pattern in fake_patterns): # Naudojame re.search, kad patikrintumėme regex
        return True
    
    if not email or len(email) < 6: 
        return True
    
    if "@" not in email_lower or email_lower.count("@") > 1: 
        return True
    
    if ".." in email_lower or ".dewww" in email_lower or ".comwww" in email_lower: 
        return True
    
    if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email_lower):
        return True
    
    return False

def clean_email(text):
    """Iš teksto randa ir išvalo el. pašto adresus."""
    candidates = re.findall(r"\b[a-zA-Z0-9._%+-]+(?:@|\[at\]| at |\(at\))[a-zA-Z0-9.-]+\.(?:[a-zA-Z]{2,63}|pec\.it)\b", text, re.IGNORECASE)
    
    for email in candidates:
        email = email.replace('[at]', '@').replace(' at ', '@').replace('(at)', '@').strip().lower()

        if email.count("@") != 1:
            continue

        domain = email.split('@')[1]
        if not is_valid_domain(domain):
            continue

        if is_fake_email(email): # Patikrinti po validacijos, kad išvengtume per didelio šalinimo
            continue

        return email
    return ""

def find_email_from_website(website_url, retries=3):
    """Bando rasti el. pašto adresą svetainėje ir jos kontaktų puslapyje, su pakartotiniais bandymais."""
    if not website_url:
        return ""
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9,lt;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }

    possible_contact_paths = [
        "",
        "/contact", "/contacts", "/contact-us", "/kontakt", "/kontakty",
        "/about", "/about-us", "/apie-mus", "/uber-uns",
        "/impressum",
    ]

    found_email = ""
    for path in possible_contact_paths:
        url_to_check = requests.compat.urljoin(website_url, path)
        for attempt in range(retries):
            try:
                headers['Referer'] = website_url
                response = session.get(url_to_check, timeout=10, headers=headers)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, "html.parser")

                email = clean_email(soup.text)
                if email:
                    found_email = email
                    break

                for a in soup.find_all('a', href=True):
                    href = a["href"].lower()
                    if href.startswith("mailto:"):
                        cleaned_mail = clean_email(href.replace("mailto:", ""))
                        if cleaned_mail:
                            found_email = cleaned_mail
                            break
                
                if found_email:
                    break

            except requests.exceptions.RequestException as e:
                if "404" in str(e) or "connection refused" in str(e).lower() or "not found" in str(e).lower() or "forbidden" in str(e).lower() or "too many requests" in str(e).lower():
                    break 
                if attempt < retries - 1:
                    time.sleep(random.uniform(0.5, 1.5))
            except Exception as e:
                if attempt < retries - 1:
                    time.sleep(random.uniform(0.5, 1.5))
        if found_email:
            break

    if not found_email and website_url:
        try:
            domain = website_url.replace("http://", "").replace("https://", "").split('/')[0]
            if domain.startswith("www."):
                domain = domain[4:]
            
            common_prefixes = ["info", "contact", "sales", "support", "hello", "office"]
            for prefix in common_prefixes:
                guessed_email = f"{prefix}@{domain}"
                if not is_fake_email(guessed_email):
                    if is_valid_domain(domain):
                        return guessed_email
        except Exception as e:
            print(f"--- Debug: Error guessing email for {website_url}: {e}")

    return found_email

# Pakeista funkcija search_places - dabar grąžina (Place_data, country_name, industry_name) tuple sąrašą
def search_places(query_text, max_results, country_name, industry_name, retries=3):
    """
    Atlieka vietų paiešką Google Places API pagal tekstinę užklausą.
    Grąžina sąrašą (Places_API_result, country_name, industry_name) tuple.
    """
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        "query": query_text,
        "key": API_KEY
    }
    results = [] # Šis sąrašas dabar laikys (place_data, country, industry)
    
    for attempt in range(retries):
        print(f"--- Places API Search: '{query_text}' (Attempt {attempt + 1}/{retries})")
        try:
            response = session.get(url, params=params, timeout=20)
            response.raise_for_status()

            data = response.json()
            if "error_message" in data:
                print(f"--- Places API Error Message for '{query_text}': {data['error_message']}")

            if "results" in data and data["results"]:
                print(f"--- Found {len(data['results'])} initial results for '{query_text}'.")
                # Pridedame šalį ir pramonę prie kiekvieno rezultato
                for place_data in data["results"]:
                    results.append((place_data, country_name, industry_name))
            else:
                print(f"--- Places API: ZERO_RESULTS or Error for '{query_text}': {data.get('status', 'Unknown status')}")
                if data.get('status') == 'OVER_QUERY_LIMIT':
                    print("   OVER_QUERY_LIMIT reached for Places API. Pausing and retrying or stopping.")
                    time.sleep(60)
                    continue
                break
                
            if "next_page_token" in data and (max_results is None or len(results) < max_results):
                print(f"--- Places API: Found next_page_token for '{query_text}'. Waiting before next page...")
                time.sleep(random.uniform(1, 3))
                params["pagetoken"] = data["next_page_token"]
            else:
                break

        except requests.exceptions.RequestException as e:
            print(f"--- Places API Network Error for '{query_text}' (Attempt {attempt + 1}/{retries}): {e}")
            if "404" in str(e) or "connection refused" in str(e).lower() or "not found" in str(e).lower() or "forbidden" in str(e).lower() or "too many requests" in str(e).lower():
                break 
            if attempt < retries - 1:
                time.sleep(random.uniform(5 * (attempt + 1), 10 * (attempt + 1)))
                print(f"   Retrying Places API search for '{query_text}'...")
            else:
                print(f"   Failed Places API search for '{query_text}' after {retries} attempts.")
        except ValueError:
            print(f"--- Places API JSON Decoding Error for '{query_text}' (Attempt {attempt + 1}/{retries}). Response: {response.text[:200]}...")
            if attempt < retries - 1:
                time.sleep(random.uniform(5 * (attempt + 1), 10 * (attempt + 1)))
                print(f"   Retrying Places API search for '{query_text}'...")
            else:
                print(f"   Failed Places API search for '{query_text}' after {retries} attempts.")
        except Exception as e:
            print(f"--- Places API Unexpected Error (Attempt {attempt + 1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(random.uniform(5 * (attempt + 1), 10 * (attempt + 1)))
                print(f"   Retrying Places API search for '{query_text}'...")
            else:
                print(f"   Failed Places API search for '{query_text}' after {retries} attempts.")
                
    # Grąžiname tik tiek rezultatų, kiek pageidaujama
    return results[:max_results] if max_results is not None else results


def extract_info(place_data, selected_country, selected_industry): # Priima šalies ir pramonės pavadinimus
    """Išgauna reikiamą informaciją iš Places API atsakymo."""
    name = place_data.get("name", "").strip()
    address = place_data.get("formatted_address", "").strip()
    place_id = place_data.get("place_id", "")
    
    print(f"\n--- Extracting details for: {name} (ID: {place_id[:10]}...) from {selected_country}, {selected_industry} ---")

    if name in global_seen_names:
        print(f"--- Skipping {name}: Name already processed. ---")
        return None

    rating = place_data.get("rating", "")
    website = ""
    email = ""
    
    try:
        if not place_id:
            print(f"--- Skipping place (no place_id) for {name}.")
            return None

        details_url = "https://maps.googleapis.com/maps/api/place/details/json"
        details_params = {
            "place_id": place_id,
            "fields": "website",
            "key": API_KEY
        }
        time.sleep(random.uniform(0.05, 0.2)) 
        
        r = session.get(details_url, params=details_params, timeout=10)
        r.raise_for_status()
        result = r.json().get("result", {})
        website = result.get("website", "")
        print(f"--- Details fetched for {name}. Website: {website if website else 'N/A'}")
        
        if website:
            email = find_email_from_website(website)
            email = clean_email(email)

    except requests.exceptions.RequestException as e:
        print(f"--- Error getting place details for {name} (ID: {place_id}): {e}")
    except ValueError:
        print(f"--- JSON decoding error for place details for {name}. Response: {r.text[:200]}...")
    except Exception as e:
        print(f"--- An unexpected error occurred getting details for {name}: {e}")

    if not email:
        print(f"--- No valid email found for {name}. Skipping.")
        return None
    
    if email in global_seen_emails:
        print(f"--- Skipping {name}: Email '{email}' already processed. ---")
        return None

    global_seen_names.add(name)
    global_seen_emails.add(email)
    print(f"--- Successfully collected valid email: {email} for {name}.")

    return {
        "name": name,
        "address": address,
        "rating": rating,
        "website": website,
        "email": email,
        "country": selected_country, 
        "industry": selected_industry 
    }


@app.route('/')
def index():
    """Pagrindinis puslapis su formomis."""
    return render_template('index.html',
                           countries=countries,
                           industries=industries)

@app.route('/email')
def email_page():
    """Puslapis, skirtas el. pašto siuntimui."""
    return render_template('email.html')

@app.route('/search', methods=['POST'])
def perform_search():
    """Atlieka paiešką pagal vartotojo pasirinkimus."""
    start_time = time.time()
    data = request.json
    selected_countries = data.get('countries', [])
    selected_industries = data.get('industries', [])
    quantity_per_search = data.get('quantity', None)

    all_found_data = []

    global global_seen_names, global_seen_emails
    global_seen_names = set()
    global_seen_emails = set()

    all_places_raw_with_context = [] 
    
    places_search_start_time = time.time()
    with ThreadPoolExecutor(max_workers=3) as executor:
        search_futures = []
        for country_name in selected_countries:
            for industry_name in selected_industries:
                query_text = f"{industry_name} {country_name}"
                print(f"\n--- Submitting Places API search for '{query_text}'...")
                search_futures.append(executor.submit(search_places, query_text, quantity_per_search, country_name, industry_name))
                time.sleep(random.uniform(0.1, 0.3))

        print("\n--- Waiting for all Places API search futures to complete... ---")
        for i, future in enumerate(as_completed(search_futures)):
            try:
                places_result_with_context = future.result()
                all_places_raw_with_context.extend(places_result_with_context)
                print(f"--- Places API Search Future {i+1} completed. Received {len(places_result_with_context)} results with context.")
            except Exception as exc:
                print(f"--- Places API Search Future {i+1} ERROR: {exc}")
    places_search_end_time = time.time()
    print(f"\n--- Places API Search stage completed in {places_search_end_time - places_search_start_time:.2f} seconds.")
    print(f"--- Total raw places collected from Places API with context: {len(all_places_raw_with_context)}")

    unique_places_to_process = {}
    for place_data, country_name, industry_name in all_places_raw_with_context:
        place_id = place_data.get("place_id")
        if place_id and place_id not in unique_places_to_process:
            unique_places_to_process[place_id] = (place_data, country_name, industry_name)

    print(f"\n--- After deduplication, {len(unique_places_to_process)} unique places identified for detail extraction. ---")
    
    detail_extraction_start_time = time.time()
    with ThreadPoolExecutor(max_workers=10) as executor:
        extract_info_futures = []
        for place_id, (place_data, country_name, industry_name) in unique_places_to_process.items():
            extract_info_futures.append(executor.submit(extract_info, place_data, country_name, industry_name))
            time.sleep(random.uniform(0.005, 0.02)) 

        print("\n--- Waiting for all detail extraction futures to complete... ---")
        for i, future in enumerate(as_completed(extract_info_futures)):
            try:
                info = future.result()
                if info:
                    all_found_data.append(info)
                    print(f"--- Detail Extraction Future {i+1} completed. Found valid info for {info.get('name')}. Total collected: {len(all_found_data)}")
            except Exception as exc:
                print(f"--- Detail Extraction Future {i+1} ERROR: {exc}")
    detail_extraction_end_time = time.time()
    print(f"\n--- Detail Extraction stage completed in {detail_extraction_end_time - detail_extraction_start_time:.2f} seconds.")

    total_time = time.time() - start_time
    print(f"\n=======================================================")
    print(f"Total RAW Places data collected with context: {len(all_places_raw_with_context)} items")
    print(f"Total UNIQUE places processed for details: {len(unique_places_to_process)} items")
    print(f"Total VALID companies found (with email) after all processing: {len(all_found_data)} items")
    print(f"Total processing time: {total_time:.2f} seconds.")
    print(f"=======================================================")
    
    return jsonify(all_found_data)

@app.route('/export_to_excel', methods=['POST'])
def export_to_excel():
    data = request.json.get('data', [])
    if not data:
        return jsonify({"message": "No data provided for export."}), 400

    df = pd.DataFrame(data)

    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, index=False, sheet_name='Companies')
    writer.close()
    output.seek(0)

    return send_file(output,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True,
                     download_name='ImoniuPaieskosRezultatai.xlsx')

# ... (likusi kodo dalis, prieš send_email_route)

# ... (likusi kodo dalis, prieš send_email_route)

@app.route('/send_email', methods=['POST'])
def send_email_route():
    data = request.json
    smtp_server = "smtp.gmail.com"
    smtp_port = 587

    smtp_user = data.get('smtp_user')
    smtp_password = data.get('smtp_password')
    recipient_email_str = data.get('recipient_email') # Kintamojo pavadinimas pakeistas dėl aiškumo
    subject = data.get('subject')
    body = data.get('body')

    if not all([smtp_user, smtp_password, recipient_email_str, subject, body]):
        return jsonify({"status": "error", "message": "Trūksta vieno ar daugiau el. pašto siuntimo parametrų."}), 400

    recipient_emails_list = [addr.strip() for addr in recipient_email_str.split(',')]

    msg = MIMEMultipart()
    msg['From'] = smtp_user
    msg['Subject'] = subject
    
    # Šis laukelis dabar bus tuščias. 
    # Svarbu atkreipti dėmesį, kad kai kurie serveriai gali atmesti tokius laiškus.
    # msg['To'] = '' # Galima palikti tuščią eilutę
    # Arba, dar geriau, nustatyti jį į tuščią sąrašą
    # msg['To'] = []
    # Taip pat galima šios eilutės tiesiog nerašyti:
    # msg['To'] = None (ne veiks)
    # Tiesiog išimkite šią eilutę, ir jis liks tuščias
    
    # Pridedame gavėjus į BCC lauką, kuris yra nematomas.
    msg['Bcc'] = recipient_email_str 

    msg.attach(MIMEText(body, 'plain', 'utf-8')) 

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            text = msg.as_string()
            
            # `sendmail` funkcija vis tiek turi žinoti, kam siųsti.
            # Jums reikia perduoti tuščią sąrašą gavėjų laukui, bet BCC gavėjus perduoti `sendmail` funkcijai
            # Štai čia yra esminis pakeitimas: siunčiame laiško tekstą
            # visiems gavėjams, esantiems `recipient_emails_list` sąraše.
            # Dabar sendmail funkcijai perduodame tuščią sąrašą gavėjų, nes visi BCC lauke
            server.sendmail(smtp_user, recipient_emails_list, text)
            
        print(f"--- El. laiškai sėkmingai išsiųsti {len(recipient_emails_list)} gavėjams.")
        return jsonify({"status": "success", "message": "El. laiškai sėkmingai išsiųsti!"})
    except smtplib.SMTPAuthenticationError:
        return jsonify({"status": "error", "message": "Autentifikacijos klaida. Patikrinkite vartotojo vardą ir slaptažodį."}), 401
    except Exception as e:
        print(f"--- Klaida siunčiant el. laišką: {e}")
        return jsonify({"status": "error", "message": f"Klaida siunčiant el. laišką: {str(e)}"}), 500
