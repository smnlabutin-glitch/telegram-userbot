#!/usr/bin/env bash
set -e
rm -rf /opt/telegram-userbot
git clone https://github.com/smnlabutin-glitch/telegram-userbot.git /opt/telegram-userbot
cd /opt/telegram-userbot
chmod +x deploy.sh
./deploy.sh
