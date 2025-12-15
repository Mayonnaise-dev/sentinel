# Sentinel - CS2 Geo-Lock Monitor

A Docker-based geo-restriction bot for Counter-Strike 2 servers. Automatically kicks players from unauthorized regions using RCON.

## Features

- 🌍 Geo-location verification using IP lookup
- 🔄 Automatic player monitoring and enforcement
- 🎯 Whitelist support for specific IPs
- 🐳 Dockerized for easy deployment
- ⚙️ Fully configurable via environment variables

## Quick Start

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd sentinel
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

3. **Deploy with Docker**
   ```bash
   docker-compose up -d
   ```

## Configuration

Edit `.env` file:

| Variable | Description | Default |
|----------|-------------|---------|
| `RCON_HOST` | CS2 server IP address | `192.168.1.50` |
| `RCON_PORT` | RCON port | `27015` |
| `RCON_PASS` | RCON password | `password` |
| `CHECK_INTERVAL` | Check frequency (seconds) | `60` |
| `ALLOWED_COUNTRIES` | Comma-separated country codes (e.g., `ZA,US`) | `ZA` |
| `WHITELIST_IPS` | Comma-separated IPs to allow | `` |

## Requirements

- Docker & Docker Compose
- CS2 server with RCON enabled
- Network access to CS2 server

## License

MIT License - see LICENSE file for details.

## Note

Uses [ip-api.com](https://ip-api.com) for geolocation (free tier: 45 requests/minute).
