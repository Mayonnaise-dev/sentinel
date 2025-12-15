import time
import re
import requests
import os
import logging
from valve.rcon import RCON

# Configuration via Environment Variables
RCON_HOST = os.getenv('RCON_HOST', '192.168.1.50')
RCON_PORT = int(os.getenv('RCON_PORT', '27015'))
RCON_PASS = os.getenv('RCON_PASS', 'password')
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '60'))
ALLOWED_COUNTRIES = [country.strip() for country in os.getenv('ALLOWED_COUNTRIES', 'ZA').split(',') if country.strip()]
WHITELIST_IPS = [ip.strip() for ip in os.getenv('WHITELIST_IPS', '').split(',') if ip.strip()]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_country(ip):
    # Local loopback check
    if ip.startswith('192.168.') or ip.startswith('10.') or ip == '127.0.0.1':
        return ALLOWED_COUNTRIES
    
    try:
        # Using ip-api.com (Free for non-commercial, 45 req/min limit)
        response = requests.get(f'http://ip-api.com/json/{ip}', timeout=5)
        data = response.json()
        if data['status'] == 'success':
            return data['countryCode']
    except Exception as e:
        logging.error(f"GeoIP Lookup failed for {ip}: {e}")
    return None

def parse_status(status_output):
    """
    Parses CS2 'status' command output.
    Returns a list of dicts: {'userid': '12', 'name': 'Player', 'ip': '1.2.3.4'}
    """
    players = []
    # Regex to capture: # userid "Name" ... ip:port ...
    # CS2 Status format can vary, but typically:
    # # 52 "Name" STEAM_1:1:12345 00:15 65 0 active 196.x.x.x:27005
    
    lines = status_output.split('\n')
    for line in lines:
        if '"' in line and 'active' in line: 
            try:
                # Extract parts
                parts = line.split()
                # UserID is usually the second item (after the #)
                userid = parts[1]
                
                # Extract IP (usually near the end, looks like IP:PORT)
                ip_port = parts[-1] 
                if ':' in ip_port:
                    ip = ip_port.split(':')[0]
                    
                    # Extract Name (Everything between the first quotes)
                    name_match = re.search(r'"(.*?)"', line)
                    name = name_match.group(1) if name_match else "Unknown"

                    players.append({'userid': userid, 'name': name, 'ip': ip})
            except Exception as e:
                logging.warning(f"Failed to parse line: {line} - {e}")
    return players

def main():
    logging.info("Sentinel Geo-Lock started.")
    
    while True:
        try:
            with RCON((RCON_HOST, RCON_PORT), RCON_PASS) as rcon:
                response = rcon.execute('status')
                players = parse_status(response)

                logging.info(f"Currently {len(players)} players connected.")
                
                if not players:
                    logging.info("Server is empty.")
                
                for player in players:
                    ip = player['ip']
                    name = player['name']
                    userid = player['userid']

                    if ip in WHITELIST_IPS:
                        continue

                    country = get_country(ip)
                    
                    if country and country not in ALLOWED_COUNTRIES:
                        logging.info(f"KICKING {name} (IP: {ip}, Country: {country})")
                        rcon.execute(f'kickid {userid} "Sorry, your country is not allowed to play on this server."')
                    elif country in ALLOWED_COUNTRIES:
                        logging.info(f"Verified {name} from {country}")
                    else:
                        logging.warning(f"Could not verify country for {name} ({ip})")

        except Exception as e:
            logging.error(f"Connection/RCON Error: {e}")
        
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()