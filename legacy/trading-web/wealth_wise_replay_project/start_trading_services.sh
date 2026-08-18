#!/bin/bash

echo "Starting Frontend..."
cd /home/ubuntu/infrastructure/wealth_wise_project/frontend
nohup npm start > react.log 2>&1 & disown

echo "Starting Backend..."
cd /home/ubuntu/infrastructure/wealth_wise_project/backend
source /home/ubuntu/miniconda3/etc/profile.d/conda.sh
conda activate myenv310
nohup python app.py > flask.log 2>&1 & disown

echo "All services started!"
