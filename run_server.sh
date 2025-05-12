#!/bin/bash
export FLASK_APP=api_server.py
export FLASK_ENV=production # development # ou production
export FLASK_RUN_PORT=5001
# Para chaves, você pode definir aqui ou deixar o padrão no api_server.py
export SECRET_KEY='my_flask_secret'
export JWT_SECRET_KEY='my_jwt_secret'

echo "Starting Simple Flask API on port $FLASK_RUN_PORT..."
python3 server.py
