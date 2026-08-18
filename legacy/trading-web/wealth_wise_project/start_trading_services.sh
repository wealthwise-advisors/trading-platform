#!/bin/bash

# ===== Clear logs on startup using truncate =====
LOG_DIR="/home/ubuntu/logs"
BACKEND_DIR="/home/ubuntu/infrastructure/wealth_wise_project/backend"
FRONTEND_DIR="/home/ubuntu/infrastructure/wealth_wise_project/frontend"
BACKUP_DIR="/home/ubuntu/backup_logs"

mkdir -p "$LOG_DIR"
mkdir -p "$BACKUP_DIR"

# ----- Backup trading_bot.log before truncating -----
if [ -f "$LOG_DIR/trading_bot.log" ]; then
    cp "$LOG_DIR/trading_bot.log" "$BACKUP_DIR/trading_bot.log"
fi
if [ -f "$LOG_DIR/trading_bot_important.log" ]; then
    cp "$LOG_DIR/trading_bot_important.log" "$BACKUP_DIR/trading_bot_important.log"
fi

# List of logs to truncate
LOG_FILES=(
  "$LOG_DIR/trading_bot_important.log"
  "$LOG_DIR/trading_bot.log"
  "$BACKEND_DIR/backend.log"
  "$BACKEND_DIR/flask.log"
  "$FRONTEND_DIR/react.log"
)

for f in "${LOG_FILES[@]}"; do
  truncate -s 0 "$f" 2>/dev/null || :
done

echo "Logs truncated"
# =====================================


echo "Starting Frontend..."
cd /home/ubuntu/infrastructure/wealth_wise_project/frontend
HOST=0.0.0.0 PORT=3000 nohup npm start > react.log 2>&1 & disown

echo "Starting Backend..."
export RITHMIC_CREDENTIALS_PATH=/home/ubuntu/infrastructure/wealth_wise_project/backend
cd /home/ubuntu/infrastructure/wealth_wise_project/backend
source /home/ubuntu/miniconda3/etc/profile.d/conda.sh
conda activate myenv310
echo "Resetting bot state in database..."
python reset_bot_state.py
nohup python app.py > flask.log 2>&1 & disown

echo "All services started!"
