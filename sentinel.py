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
PLAYER_POLL_INTERVAL = int(os.getenv('PLAYER_POLL_INTERVAL', '5'))
ALLOWED_COUNTRIES = [country.strip() for country in os.getenv('ALLOWED_COUNTRIES', 'ZA').split(',') if country.strip()]
WHITELIST_IPS = [ip.strip() for ip in os.getenv('WHITELIST_IPS', '').split(',') if ip.strip()]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_country(ip):
    # Local loopback check - return first allowed country for local IPs
    if ip.startswith('192.168.') or ip.startswith('10.') or ip == '127.0.0.1':
        return ALLOWED_COUNTRIES[0] if ALLOWED_COUNTRIES else 'ZA'
    
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
    # CS2 Status format:
    # 65281    17:53   33    0     active 786432 196.251.208.21:34862 'Vlerrie'
    # Format: userid time ping loss state rate ip:port 'name'
    
    lines = status_output.split('\n')
    in_player_section = False
    
    for line in lines:
        # Start parsing after the player section header
        if '---------players--------' in line:
            in_player_section = True
            continue
        
        # Stop at #end or empty line after players
        if in_player_section and ('#end' in line or line.strip() == ''):
            break
            
        if in_player_section and line.strip():
            # Skip header line
            if 'id     time ping loss' in line:
                continue
                
            try:
                # Skip bots (they have "BOT" instead of time)
                if 'BOT' in line:
                    continue
                
                # Skip challenging players (userid 65535)
                if line.strip().startswith('65535'):
                    continue
                
                parts = line.split()
                
                # userid is first field
                userid = parts[0]
                
                # Find the IP:PORT (has colon and dots)
                ip_port = None
                for part in parts:
                    if ':' in part and '.' in part:
                        ip_port = part
                        break
                
                if ip_port:
                    ip = ip_port.split(':')[0]
                    
                    # Name is in single quotes at the end
                    name_match = re.search(r"'(.*?)'", line)
                    name = name_match.group(1) if name_match else "Unknown"
                    
                    players.append({'userid': userid, 'name': name, 'ip': ip})
                    
            except Exception as e:
                logging.warning(f"Failed to parse line: {line} - {e}")
    
    return players

def main():
    logging.info("Sentinel Geo-Lock started.")
    logging.info(f"Configuration: RCON_HOST={RCON_HOST}, RCON_PORT={RCON_PORT}, PLAYER_POLL_INTERVAL={PLAYER_POLL_INTERVAL}s")
    logging.info(f"Allowed Countries: {ALLOWED_COUNTRIES}")

    # Tracks IPs that have already been geo-checked and allowed.
    # key: ip (str), value: player name (str)
    known_ips: dict[str, str] = {}

    while True:
        try:
            with Client(RCON_HOST, RCON_PORT, passwd=RCON_PASS, timeout=10) as client:
                response = client.run('status')
                players = parse_status(response)

                current_ips = {p['ip'] for p in players}

                # Evict IPs of players who have disconnected
                for ip in list(known_ips.keys()):
                    if ip not in current_ips:
                        logging.info(f"Player left: {known_ips[ip]} ({ip})")
                        del known_ips[ip]

                # Only process players whose IP has not been verified yet
                for player in players:
                    ip = player['ip']
                    name = player['name']
                    userid = player['userid']

                    if ip in known_ips:
                        continue

                    if ip in WHITELIST_IPS:
                        logging.info(f"Whitelisted: {name} ({ip})")
                        known_ips[ip] = name
                        continue

                    country = get_country(ip)
                    if country and country not in ALLOWED_COUNTRIES:
                        logging.warning(f"KICKED: {name} from {country} ({ip})")
                        with Client(RCON_HOST, RCON_PORT, passwd=RCON_PASS, timeout=5) as kick_client:
                            kick_client.run(f'kickid {userid}')
                    elif country in ALLOWED_COUNTRIES:
                        logging.info(f"Verified: {name} from {country}")
                        known_ips[ip] = name
                    else:
                        logging.warning(f"Could not verify country for {name} ({ip}), will retry next cycle")

        except Exception as e:
            logging.error(f"RCON Error: {e}")

        time.sleep(PLAYER_POLL_INTERVAL)

if __name__ == "__main__":
    main()