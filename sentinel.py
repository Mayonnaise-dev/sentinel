import time
import re
import requests
import os
import logging
from rcon.source import Client

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
    logging.info(f"Configuration: RCON_HOST={RCON_HOST}, RCON_PORT={RCON_PORT}, CHECK_INTERVAL={CHECK_INTERVAL}s")
    logging.info(f"Allowed Countries: {ALLOWED_COUNTRIES}")
    
    while True:
        try:
            logging.info("Connecting to RCON...")
            with Client(RCON_HOST, RCON_PORT, passwd=RCON_PASS, timeout=10) as client:
                logging.info("RCON connected. Executing 'status' command...")
                response = client.run('status')
                logging.info(f"Received response ({len(response)} bytes)")
                logging.debug(f"Raw RCON response:\n{response}")
                
                players = parse_status(response)
                logging.info(f"Parsed {len(players)} players from status output.")
                
                if not players:
                    logging.info("No players detected on server.")
                
                for player in players:
                    ip = player['ip']
                    name = player['name']
                    userid = player['userid']
                    
                    logging.info(f"Checking player: {name} (ID: {userid}, IP: {ip})")

                    if ip in WHITELIST_IPS:
                        logging.info(f"  -> {name} is whitelisted, skipping.")
                        continue

                    country = get_country(ip)
                    if country and country not in ALLOWED_COUNTRIES:
                        logging.info(f"  -> KICKING {name} (IP: {ip}, Country: {country})")
                        with Client(RCON_HOST, RCON_PORT, passwd=RCON_PASS, timeout=5) as kick_client:
                            kick_client.run(f'kickid {userid} "Sorry, your country is not allowed to play on this server."')
                        rcon.execute(f'kickid {userid} "Sorry, your country is not allowed to play on this server."')
                    elif country in ALLOWED_COUNTRIES:
                        logging.info(f"  -> {name} verified from {country}")
                    else:
                        logging.warning(f"  -> Could not verify country for {name} ({ip})")

        except Exception as e:
            logging.error(f"Connection/RCON Error: {e}", exc_info=True)
        
        logging.info(f"Sleeping for {CHECK_INTERVAL} seconds...")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()