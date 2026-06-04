# Crypto Market Intelligence Bot

A production-grade Telegram bot for crypto market analysis and trading signals.

## Features

- âœ… Telegram command-based interface
- âœ… Market signal management
- âœ… Daily statistics tracking
- âœ… Signal history database (SQLite)
- âœ… Easy deployment to cloud servers
- âœ… Lightweight and low resource usage
- âœ… **Works in India** - No blocked exchange APIs

## Tech Stack

- **Language:** Python 3.9+
- **Database:** SQLite
- **Bot Framework:** python-telegram-bot
- **Async:** asyncio

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the root directory:

```env
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Bot Configuration
ENABLE_DEBUG=False
LOG_LEVEL=INFO

# Database
DATABASE_PATH=data/signals.db

# Deployment
ENVIRONMENT=production
```

## Getting Telegram Credentials

### 1. Create a Bot Token
- Chat with [@BotFather](https://t.me/botfather) on Telegram
- Send `/newbot` command
- Follow the instructions
- Copy your bot token

### 2. Get Your Chat ID
- Chat with [@userinfobot](https://t.me/userinfobot) on Telegram
- Send `/start`
- Copy your numeric Chat ID

## Usage

```bash
python main.py
```

The bot will:
1. Start and listen for commands
2. Respond to user commands
3. Store signals in database
4. Display statistics and history

## Available Commands

| Command | Description |
|---------|-------------|
| `/start` | Start the bot |
| `/help` | Show help message |
| `/top` | Show top BUY and SELL opportunities |
| `/buy <coin>` | Show BUY LONG analysis for a coin |
| `/sell <coin>` | Show SELL SHORT analysis for a coin |
| `/analysis <coin>` | Show detailed technical analysis for a coin |
| `/alerts` | Show automatic alert scanner status |
| `/summary` | Daily market summary |
| `/status` | Bot status and uptime |

## Project Structure

```
crypto-futures-intelligence-bot/
â”œâ”€â”€ main.py                 # Entry point
â”œâ”€â”€ requirements.txt        # Dependencies
â”œâ”€â”€ .env                    # Configuration (create this)
â”œâ”€â”€ .env.example            # Configuration template
â”œâ”€â”€ config.py              # Configuration management
â”œâ”€â”€ database.py            # SQLite operations
â”œâ”€â”€ bot_telegram/
â”‚   â”œâ”€â”€ __init__.py
â”‚   â”œâ”€â”€ bot.py            # Telegram bot handler
â”‚   â””â”€â”€ handlers.py       # Command handlers
â”œâ”€â”€ utils/
â”‚   â”œâ”€â”€ __init__.py
â”‚   â”œâ”€â”€ logger.py         # Logging setup
â”‚   â””â”€â”€ helpers.py        # Utility functions
â””â”€â”€ tests/
    â””â”€â”€ test_telegram_bot.py
```

## Deployment

### Local Development
```bash
python main.py
```

### Cloud Hosting (Recommended)
Deploy to any cloud platform that supports Python:

**Heroku:**
```bash
heroku create your-bot-name
git push heroku main
```

**Railway:**
1. Connect your GitHub repo
2. Deploy automatically

**Google Cloud Run:**
```bash
gcloud run deploy crypto-bot --source . --platform managed
```

**AWS EC2:**
1. Launch Ubuntu instance
2. Install Python 3.9+
3. Clone repo and run `python main.py`

### Using systemd (Linux Servers)
Create `/etc/systemd/system/crypto-bot.service`:
```ini
[Unit]
Description=Crypto Market Intelligence Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/crypto-futures-intelligence-bot
ExecStart=/usr/bin/python3 main.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable crypto-bot
sudo systemctl start crypto-bot
sudo systemctl status crypto-bot
```

## Database Schema

Signals are stored with:
- Coin name
- Action (BUY LONG / SELL SHORT)
- Signal Type
- Confidence Score (0-100)
- Risk Level (LOW / MEDIUM / HIGH)
- Analysis Reasons
- Price
- Timeframe
- Timestamp

## Inserting Signals Manually

```python
from database import db

signal = {
    'coin': 'BTCUSDT',
    'action': 'BUY LONG',
    'signal_type': 'SWING',
    'confidence': 85,
    'risk_level': 'LOW',
    'reasons': 'Strong breakout with high volume',
    'price': 42500.50,
    'timeframe': '4H',
    'timestamp': '2026-06-02 18:00:00'
}

db.insert_signal(signal)
```

## License

MIT

## Support

For issues and questions:
- GitHub Issues: https://github.com/yasir069-cs/crypto-futures-intelligence-bot/issues
- Telegram: @yasir069
