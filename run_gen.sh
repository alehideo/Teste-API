#!/bin/bash
export API_BASE_URL="http://api.demoshow.com.br/api"
export NUM_SIMULTANEOUS_USERS="10"
export REQUEST_DELAY_MIN_S="0.3"
export REQUEST_DELAY_MAX_S="1.5"
export RUN_DURATION_SECONDS="0" # 0 para rodar indefinidamente (ou até Ctrl+C)

# Admin credentials (devem corresponder ao definido em api_server.py)
export ADMIN_USERNAME="admin"
export ADMIN_PASSWORD="adminpassword"

echo "Starting Simple Traffic Generator..."
python3 gen.py
