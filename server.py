import os
import uuid
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, jsonify, g, current_app
from werkzeug.security import generate_password_hash, check_password_hash
import jwt

# --- Configurações ---
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or '123 de oliveira quatro'
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or '123 de oliveira quatro'
    JWT_ALGORITHM = 'HS256'
    JWT_EXPIRATION_DELTA = timedelta(hours=1)
    PREDEFINED_ADMIN_USERNAME = "admin"
    PREDEFINED_ADMIN_PASSWORD = "adminpassword"

app = Flask(__name__)
app.config.from_object(Config)

# --- Simulação de Banco de Dados em Memória ---
users = {}
items = {}
reviews = {}
carts = {}
orders = {}

def initialize_data():
    admin_username = app.config['PREDEFINED_ADMIN_USERNAME']
    if admin_username not in users:
        users[admin_username] = {
            "password_hash": generate_password_hash(app.config['PREDEFINED_ADMIN_PASSWORD']),
            "email": "admin@example.com", "full_name": "Admin User",
            "address": "123 Admin St, Admin City", "is_admin": True,
            "created_at": datetime.utcnow().isoformat()
        }
        print(f"Admin user '{admin_username}' initialized.")

    if not items:
        item1_id = str(uuid.uuid4())
        items[item1_id] = {"item_id": item1_id, "name": "Laptop Pro", "description": "High-performance laptop", "price": 1200.99, "stock": 50, "created_at": datetime.utcnow().isoformat()}
        item2_id = str(uuid.uuid4())
        items[item2_id] = {"item_id": item2_id, "name": "Wireless Mouse", "description": "Ergonomic wireless mouse", "price": 25.50, "stock": 200, "created_at": datetime.utcnow().isoformat()}
        print("Sample items initialized.")

with app.app_context():
    initialize_data()

# --- Autenticação JWT e Decorators ---
def create_jwt_token(username):
    payload = {
        'sub': username, 'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + current_app.config['JWT_EXPIRATION_DELTA']
    }
    return jwt.encode(payload, current_app.config['JWT_SECRET_KEY'], algorithm=current_app.config['JWT_ALGORITHM'])

def decode_jwt_token(token):
    try:
        payload = jwt.decode(token, current_app.config['JWT_SECRET_KEY'], algorithms=[current_app.config['JWT_ALGORITHM']])
        return payload['sub']
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None

def token_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(" ")[1]
        if not token: return jsonify({"message": "Token is missing!"}), 401
        username = decode_jwt_token(token)
        if not username or username not in users: return jsonify({"message": "Token is invalid or expired!"}), 401
        g.current_user = users[username]
        g.current_username = username
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    @token_required
    def decorated_function(*args, **kwargs):
        if not g.current_user.get('is_admin'): return jsonify({"message": "Admin privileges required!"}), 403
        return f(*args, **kwargs)
    return decorated_function

# --- Funções Auxiliares ---
def get_user_cart(username):
    carts.setdefault(username, {})
    return carts[username]

def mask_card_number(card_number):
    return f"xxxx-xxxx-xxxx-{card_number[-4:]}" if card_number and len(card_number) > 4 else "xxxx"

# --- Endpoints da API ---

# Root endpoint for health check
@app.route('/', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
def health_check():
    return jsonify({"message": "working"}), 200


# USER
@app.route('/api/user/register', methods=['POST'])
def register_user():
    data = request.get_json()
    pii_fields = ['username', 'password', 'email', 'full_name', 'address']
    if not data or not all(field in data for field in pii_fields):
        return jsonify({"message": f"Missing required PII fields: {', '.join(pii_fields)}"}), 400
    if data['username'] in users: return jsonify({"message": "Username already exists"}), 409
    users[data['username']] = {
        "password_hash": generate_password_hash(data['password']), "email": data['email'],
        "full_name": data['full_name'], "address": data['address'], "is_admin": False,
        "created_at": datetime.utcnow().isoformat()
    }
    app.logger.info(f"User registered: {data['username']}. PII received: email, full_name, address.")
    return jsonify({"message": "User registered successfully"}), 201

@app.route('/api/user/login', methods=['POST'])
def login_user():
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({"message": "Username and password required"}), 400
    user = users.get(data['username'])
    if not user or not check_password_hash(user['password_hash'], data['password']):
        return jsonify({"message": "Invalid credentials"}), 401
    token = create_jwt_token(data['username'])
    return jsonify({"access_token": token, "is_admin": user.get("is_admin", False)}), 200

@app.route('/api/user/logout', methods=['POST'])
@token_required
def logout_user():
    return jsonify({"message": "Logout successful. Please discard the token."}), 200

@app.route('/api/user/profile', methods=['GET'])
@token_required
def get_user_profile():
    user_data = g.current_user.copy()
    del user_data['password_hash']
    return jsonify(user_data), 200

# ITEMS
@app.route('/api/items', methods=['GET'])
def list_items():
    return jsonify(list(items.values())), 200

@app.route('/api/item/<item_id>', methods=['GET'])
def get_item(item_id):
    item = items.get(item_id)
    return jsonify(item) if item else (jsonify({"message": "Item not found"}), 404)

@app.route('/api/item/<item_id>/review', methods=['POST'])
@token_required
def add_review(item_id):
    if item_id not in items: return jsonify({"message": "Item not found"}), 404
    data = request.get_json()
    if not data or not data.get('rating') or not data.get('comment'):
        return jsonify({"message": "Rating and comment are required"}), 400
    review_id = str(uuid.uuid4())
    reviews[review_id] = {
        "item_id": item_id, "username": g.current_username, "rating": data['rating'],
        "comment": data['comment'], "created_at": datetime.utcnow().isoformat()
    }
    return jsonify({"message": "Review added", "review_id": review_id}), 201

# CART
@app.route('/api/cart', methods=['GET'])
@token_required
def view_cart():
    user_cart = get_user_cart(g.current_username)
    # Detalhes do carrinho podem ser enriquecidos aqui se necessário
    return jsonify({"cart_items": user_cart, "message": "Cart view (simple)"}), 200

@app.route('/api/cart/item', methods=['POST'])
@token_required
def add_item_to_cart():
    data = request.get_json()
    item_id, quantity = data.get('item_id'), data.get('quantity', 1)
    if not item_id or item_id not in items: return jsonify({"message": "Item not found"}), 404
    if not isinstance(quantity, int) or quantity <= 0: return jsonify({"message": "Invalid quantity"}), 400
    if items[item_id]['stock'] < quantity: return jsonify({"message": "Not enough stock"}), 400
    user_cart = get_user_cart(g.current_username)
    user_cart[item_id] = user_cart.get(item_id, 0) + quantity
    return jsonify({"message": "Item added to cart", "cart": user_cart}), 200

@app.route('/api/cart/item/<item_id>', methods=['DELETE'])
@token_required
def remove_item_from_cart(item_id):
    user_cart = get_user_cart(g.current_username)
    if item_id not in user_cart: return jsonify({"message": "Item not in cart"}), 404
    del user_cart[item_id]
    return jsonify({"message": "Item removed from cart", "cart": user_cart}), 200

# PAYMENT / ORDER
@app.route('/api/order/checkout', methods=['POST'])
@token_required
def checkout():
    username = g.current_username
    user_cart = get_user_cart(username)
    if not user_cart: return jsonify({"message": "Cart is empty"}), 400
    
    order_items_details = []
    total_amount = 0
    for item_id, quantity in user_cart.items():
        item_info = items.get(item_id)
        if not item_info or item_info['stock'] < quantity:
            return jsonify({"message": f"Item {item_id} issue."}), 400
        order_items_details.append({"item_id": item_id, "name": item_info["name"], "quantity": quantity, "price_at_purchase": item_info["price"]})
        total_amount += item_info["price"] * quantity
        items[item_id]['stock'] -= quantity

    order_id = str(uuid.uuid4())
    orders[order_id] = {
        "order_id": order_id, "username": username, "items": order_items_details,
        "total_amount": round(total_amount, 2),
        "shipping_address": users[username].get("address", "N/A"), # PII
        "status": "pending_payment", "created_at": datetime.utcnow().isoformat()
    }
    carts[username] = {} # Clear cart
    app.logger.info(f"Order {order_id} for {username}. PII (address) included.")
    return jsonify({"message": "Checkout successful, order created.", "order_id": order_id}), 201

@app.route('/api/order/<order_id>/pay/card', methods=['POST'])
@token_required
def pay_by_card(order_id):
    order = orders.get(order_id)
    if not order or order['username'] != g.current_username: return jsonify({"message": "Order not found"}), 404
    if order['status'] != 'pending_payment': return jsonify({"message": "Order not pending payment"}), 400
    data = request.get_json()
    pii_card_fields = ['card_number', 'expiry_month', 'expiry_year', 'cvv']
    if not data or not all(field in data for field in pii_card_fields):
        return jsonify({"message": f"Missing PII for card payment: {', '.join(pii_card_fields)}"}), 400
    
    app.logger.info(f"Card payment for {order_id}. PII received: card_number, expiry, cvv.")
    order['status'] = 'paid'
    order['payment_method'] = 'card'
    order['payment_details_masked'] = f"Card {mask_card_number(data['card_number'])}"
    return jsonify({"message": "Card payment successful (simulated)"}), 200

@app.route('/api/order/<order_id>/pay/pix', methods=['POST'])
@token_required
def pay_by_pix(order_id):
    order = orders.get(order_id)
    if not order or order['username'] != g.current_username: return jsonify({"message": "Order not found"}), 404
    if order['status'] != 'pending_payment': return jsonify({"message": "Order not pending payment"}), 400
    order['status'] = 'paid'
    order['payment_method'] = 'pix'
    order['payment_details_masked'] = f"PIX Code: SIMULATED-{str(uuid.uuid4())[:8]}"
    app.logger.info(f"PIX payment for order {order_id}.")
    return jsonify({"message": "PIX payment successful (simulated)"}), 200

# ADMIN
@app.route('/api/admin/purchases', methods=['GET']) # Simplified from admin/orders
@admin_required
def admin_list_purchases():
    # Retorna PII (username, shipping_address, payment_details_masked) para o admin
    admin_view_orders = []
    for oid, odata in orders.items():
        odata_copy = odata.copy()
        user_profile = users.get(odata['username'], {})
        odata_copy['user_full_name'] = user_profile.get('full_name', 'N/A') # PII
        odata_copy['user_email'] = user_profile.get('email', 'N/A') # PII
        admin_view_orders.append(odata_copy)
    app.logger.info(f"Admin {g.current_username} accessed all purchases. PII exposed.")
    return jsonify(admin_view_orders), 200

@app.route('/api/admin/users', methods=['GET'])
@admin_required
def admin_list_users():
    # Parâmetros de paginação com valores padrão
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50)) # Limite padrão de 50
    except ValueError:
        return jsonify({"message": "Invalid page or per_page parameter. Must be integers."}), 400

    if page < 1: page = 1
    if per_page < 1: per_page = 1
    if per_page > 50: # Aplicando o limite máximo de 50 por página
        app.logger.warning(f"Admin {g.current_username} requested {per_page} users per page, capped at 50.")
        per_page = 50

    all_user_data = []
    # Convertendo o dicionário de usuários para uma lista para facilitar a paginação
    # Em um banco de dados real, isso seria uma query com LIMIT e OFFSET
    # Ordenar por username para consistência na paginação, embora não seja estritamente necessário aqui
    sorted_usernames = sorted(users.keys()) 

    for username in sorted_usernames:
        data = users[username]
        user_copy = data.copy()
        if 'password_hash' in user_copy:
            del user_copy['password_hash'] # Nunca retorne o hash da senha
        all_user_data.append({"username": username, **user_copy})

    total_users = len(all_user_data)
    start_index = (page - 1) * per_page
    end_index = start_index + per_page
    paginated_users = all_user_data[start_index:end_index]

    app.logger.info(f"Admin {g.current_username} accessed user data page {page}, {per_page} users per page. PII exposed.")
    return jsonify({
        "users": paginated_users,
        "page": page,
        "per_page": per_page,
        "total_users": total_users,
        "total_pages": (total_users + per_page - 1) // per_page # Cálculo de teto para total_pages
    }), 200

@app.route('/api/admin/item', methods=['POST'])
@admin_required
def admin_add_item():
    data = request.get_json()
    if not data or not data.get('name') or not data.get('price') or not data.get('stock'):
        return jsonify({"message": "Name, price, stock required"}), 400
    item_id = str(uuid.uuid4())
    items[item_id] = {
        "item_id": item_id, "name": data['name'], "description": data.get('description', ''),
        "price": float(data['price']), "stock": int(data['stock']),
        "created_at": datetime.utcnow().isoformat()
    }
    return jsonify({"message": "Item added", "item": items[item_id]}), 201

@app.route('/api/admin/item/<item_id>/stock', methods=['PUT'])
@admin_required
def admin_update_item_stock(item_id):
    if item_id not in items:
        return jsonify({"message": "Item not found"}), 404
    
    data = request.get_json()
    new_stock = data.get('stock')

    if new_stock is None or not isinstance(new_stock, int) or new_stock < 0:
        return jsonify({"message": "Invalid stock value. 'stock' must be a non-negative integer."}), 400
    
    items[item_id]['stock'] = new_stock
    items[item_id]['updated_at'] = datetime.utcnow().isoformat()
    app.logger.info(f"Admin {g.current_username} updated stock for item {item_id} ('{items[item_id]['name']}') to {new_stock}.")
    return jsonify({"message": "Item stock updated successfully", "item": items[item_id]}), 200

@app.route('/api/admin/item/<item_id>', methods=['DELETE'])
@admin_required
def admin_delete_item(item_id):
    if item_id not in items: return jsonify({"message": "Item not found"}), 404
    del items[item_id]
    return jsonify({"message": "Item deleted"}), 200


if __name__ == '__main__':
    port = int(os.environ.get("FLASK_RUN_PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
