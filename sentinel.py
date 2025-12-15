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
WHITELIST_STEAMIDS = [sid.strip() for sid in os.getenv('WHITELIST_STEAMIDS', '').split(',') if sid.strip()]

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
    Returns a list of dicts: {'userid': '12', 'name': 'Player', 'ip': '1.2.3.4', 'steamid': 'STEAM_1:0:12345'}
    """
    players = []
    # CS2 Status format example from logs:
    # "Mayonnaise.<0><[U:1:311970591]><Spectator>"
    # Line format: userid time ping loss state rate ip:port 'name'
    
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
                    
                    players.append({'userid': userid, 'name': name, 'ip': ip, 'steamid': None})
                    
            except Exception as e:
                logging.warning(f"Failed to parse line: {line} - {e}")
    
    return players

def get_steamid_from_status(client, userid):
    """
    Gets Steam ID for a player by checking detailed status output.
    Steam IDs appear in connection messages in the format [U:1:XXXXXXX]
    """
    try:
        # Use status to get full output which may contain Steam IDs
        response = client.run(f'status')
        # Look for Steam ID format [U:1:XXXXXXX] or STEAM_X:X:XXXXX
        steamid_match = re.search(rf'\[U:1:(\d+)\]', response)
        if steamid_match:
            return steamid_match.group(1)
    except Exception as e:
        logging.debug(f"Could not get Steam ID for userid {userid}: {e}")
    return None

def main():
    logging.info("Sentinel Geo-Lock started.")
    logging.info(f"Configuration: RCON_HOST={RCON_HOST}, RCON_PORT={RCON_PORT}, CHECK_INTERVAL={CHECK_INTERVAL}s")
    logging.info(f"Allowed Countries: {ALLOWED_COUNTRIES}")
    
    while True:
        try:
            with Client(RCON_HOST, RCON_PORT, passwd=RCON_PASS, timeout=10) as client:
                response = client.run('status')
                players = parse_status(response)
                
                if not players:
                    logging.info("No players on server")
                
                for player in players:
                    ip = player['ip']
                    name = player['name']
                    userid = player['userid']
                    
                    # Get Steam ID for whitelist check
                    steamid = get_steamid_from_status(client, userid)
                    
                    if steamid and steamid in WHITELIST_STEAMIDS:
                        logging.info(f"Whitelisted: {name} (Steam ID: {steamid})")
                        continue

                    country = get_country(ip)
                    if country and country not in ALLOWED_COUNTRIES:
                        logging.warning(f"KICKED: {name} from {country} ({ip})")
                        with Client(RCON_HOST, RCON_PORT, passwd=RCON_PASS, timeout=5) as kick_client:
                            kick_client.run(f'kickid {userid}')
                    elif country in ALLOWED_COUNTRIES:
                        logging.info(f"Verified: {name} from {country}")
                    else:
                        logging.warning(f"Could not verify country: {name} ({ip})")

        except Exception as e:
            logging.error(f"RCON Error: {e}")
        
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()