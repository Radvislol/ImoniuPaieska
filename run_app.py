import os
import sys
import subprocess
import time
import requests.exceptions
import requests
from threading import Thread
from waitress import serve
import logging # Importuojame logging modulį

os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUNBUFFERED'] = '1'

from app import app as flask_app 

# Funkcija, kuri paleidžia Waitress serverį
def run_waitress_server():
    print("Starting Flask server with Waitress...")
    
    current_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    waitress_log_path = os.path.join(current_dir, "waitress.log")

    # --- NAUJA LOGAVIMO KONFIGŪRACIJA WAITRESS'UI ---
    # Konfigūruojame Waitress logavimą į failą
    logging.basicConfig(filename=waitress_log_path, level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')
    waitress_logger = logging.getLogger('waitress')
    waitress_logger.setLevel(logging.INFO)
    # Jei nenorite, kad Waitress logai eitų ir į konsolę, galite pašalinti Handlerius
    # Arba, jei norite, kad konsolėje būtų tik kritiniai pranešimai, galite nustatyti kitą lygį
    # (šiuo atveju jie jau eina į failą)
    # --- PABAIGA NAUJOS LOGAVIMO KONFIGŪRACIJOS ---

    try:
        # Paleidžiame Waitress serverį
        # Pašalintas neteisingas 'log_file' parametras
        serve(flask_app, host='127.0.0.1', port=5000, _quiet=True) 
    except Exception as e:
        print(f"Waitress server failed to start: {e}")
        logging.error(f"Waitress server failed to start: {e}", exc_info=True) # Įrašome klaidą į log failą
        sys.exit(1)


def check_server_started():
    print("Checking if server is online...")
    for _ in range(15): 
        try:
            requests.get("http://127.0.0.1:5000/", timeout=2) 
            return True
        except requests.exceptions.ConnectionError:
            time.sleep(1) 
    return False

if __name__ == "__main__":
    print("Welcome to the Company Search Application!")
    print("Opening local server...")
    
    server_thread = Thread(target=run_waitress_server)
    server_thread.daemon = True 
    server_thread.start()

    time.sleep(2) 

    if check_server_started():
        print("Server successfully started at: http://127.0.0.1:5000/")
        print("\n-----------------------------------------------------------")
        print("Open your web browser and go to this address:")
        print("                  http://127.0.0.1:5000/")
        print("-----------------------------------------------------------\n")
        print("DO NOT CLOSE THIS WINDOW while the application is running!")
        print("When you are finished, simply close this window.")
        
        try:
            input("Press Enter to close this window...")
        except KeyboardInterrupt:
            print("\nApplication is stopping.")
        finally:
            print("Application closed.")
    else:
        print("\nFailed to start or connect to the server.")
        print("Please check if port 5000 is free and not blocked by other applications.")
        
        current_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        waitress_log_path = os.path.join(current_dir, "waitress.log")
        if os.path.exists(waitress_log_path):
            print(f"Check '{waitress_log_path}' for server process errors.")
        else:
            print("No waitress.log file found. Server might have failed to initialize logging.")
        
        print("Error starting the application. Please contact the developer.")
        input("Press Enter to close this window...")

if __name__ == "__main__":
    main()