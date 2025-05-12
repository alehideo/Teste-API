import requests
import time
import random
import threading
import os
from faker import Faker
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:5000/api")
NUM_USERS = int(os.getenv("NUM_SIMULTANEOUS_USERS", "3"))
DELAY_MIN = float(os.getenv("REQUEST_DELAY_MIN_S", "0.5"))
DELAY_MAX = float(os.getenv("REQUEST_DELAY_MAX_S", "2.0"))
RUN_INDEFINITELY = os.getenv("RUN_DURATION_SECONDS", "0") == "0"


fake = Faker('pt_BR')
user_tokens = {}
admin_token_global = None
available_item_ids_global = []
admin_login_lock = threading.Lock() # Para evitar múltiplas tentativas de login do admin simultaneamente

# Lista de User-Agents comuns para simular diferentes navegadores
COMMON_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
    "Mozilla/5.0 (iPad; CPU OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/91.0.4472.80 Mobile/15E148 Safari/604.1"
]

def req(method, endpoint, data=None, token_for_user=None, is_admin_req=False):
    url = f"{API_BASE_URL}{endpoint}"
    headers = {"Content-Type": "application/json", "User-Agent": random.choice(COMMON_USER_AGENTS)}
    
    token_to_use = None
    if is_admin_req and admin_token_global:
        token_to_use = admin_token_global
    elif token_for_user and token_for_user in user_tokens:
        token_to_use = user_tokens[token_for_user]

    if token_to_use:
        headers['Authorization'] = f'Bearer {token_to_use}'

    try:
        # print(f"[{threading.get_ident()}] {method} {url} Data: {data}")
        response = requests.request(method, url, json=data, headers=headers, timeout=10)
        # print(f"[{threading.get_ident()}] Response {response.status_code} from {url}: {response.text[:100]}")
        if response.status_code == 401 and token_for_user and token_for_user in user_tokens:
            print(f"Token for {token_for_user} expired or invalid. Removing.")
            del user_tokens[token_for_user]
        elif response.status_code == 401 and is_admin_req:
            print("Admin token expired or invalid. Attempting to re-login admin...")
            # Tentar refazer o login do admin
            if attempt_admin_relogin():
                # Tentar a requisição original novamente com o novo token
                print("Admin re-login successful. Retrying original request...")
                headers['Authorization'] = f'Bearer {admin_token_global}' # Atualiza o header com o novo token
                response = requests.request(method, url, json=data, headers=headers, timeout=10)
            else:
                print("Admin re-login failed. Original request will likely fail.")
            del user_tokens[token_for_user]
        return response
    except requests.exceptions.RequestException as e:
        print(f"Error for {url}: {e}")
        return None

def initial_setup():
    global admin_token_global, available_item_ids_global
    # Login Admin
    admin_user = os.getenv("ADMIN_USERNAME", "admin")
    admin_pass = os.getenv("ADMIN_PASSWORD", "adminpassword")
    resp = req("POST", "/user/login", {"username": admin_user, "password": admin_pass})
    if resp and resp.status_code == 200:
        admin_token_global = resp.json().get("access_token")
        print("Admin logged in.")
    else:
        print(f"Admin login failed: {resp.text if resp else 'No response'}")

    # Fetch items
    resp_items = req("GET", "/items")
    if resp_items and resp_items.status_code == 200:
        items_data = resp_items.json()
        available_item_ids_global = [item['item_id'] for item in items_data if isinstance(item, dict) and 'item_id' in item]
        print(f"Fetched {len(available_item_ids_global)} items.")
    else:
        print("Failed to fetch items.")

def attempt_admin_relogin():
    global admin_token_global
    # Usar um lock para garantir que apenas uma thread tente o relogin do admin por vez
    with admin_login_lock:
        # Verificar novamente se outro thread já não fez o relogin enquanto este esperava pelo lock
        # (Isso é uma simplificação; uma verificação real da validade do token seria melhor se possível)
        # Para esta simulação, vamos apenas tentar o login.
        print("Attempting admin re-login critical section...")
        admin_user = os.getenv("ADMIN_USERNAME", "admin")
        admin_pass = os.getenv("ADMIN_PASSWORD", "adminpassword")
        # Faz a requisição de login sem usar a função 'req' para evitar recursão infinita em caso de falha no login
        login_url = f"{API_BASE_URL}/user/login"
        login_payload = {"username": admin_user, "password": admin_pass}
        resp = requests.post(login_url, json=login_payload, headers={"Content-Type": "application/json"}, timeout=10)
        if resp and resp.status_code == 200:
            admin_token_global = resp.json().get("access_token")
            return True
    return False

def user_simulation(user_id_prefix):
    username = f"{user_id_prefix}_{random.randint(1000,9999)}"
    password = fake.password()
    pii_data = { # PII
        "email": fake.email(), "full_name": fake.name(),
        "address": fake.address().replace("\n", ", ")
    }

    # Register
    print(f"{username}: Registering with PII...")
    reg_payload = {"username": username, "password": password, **pii_data}
    req("POST", "/user/register", reg_payload)
    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    # Login
    print(f"{username}: Logging in...")
    login_resp = req("POST", "/user/login", {"username": username, "password": password})
    if not (login_resp and login_resp.status_code == 200 and login_resp.json().get("access_token")):
        print(f"{username}: Login failed. Aborting.")
        return
    user_tokens[username] = login_resp.json()["access_token"]

    # Browse items (already fetched globally, but could simulate individual viewing)
    print(f"{username}: Browsing items...")
    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    # Add items to cart
    if available_item_ids_global:
        num_items_to_add = random.randint(1, min(3, len(available_item_ids_global)))
        for _ in range(num_items_to_add):
            item_to_add = random.choice(available_item_ids_global)
            print(f"{username}: Adding item {item_to_add} to cart...")
            req("POST", "/cart/item", {"item_id": item_to_add, "quantity": 1}, token_for_user=username)
            time.sleep(random.uniform(DELAY_MIN / 2, DELAY_MAX / 2))
    else:
        print(f"{username}: No items to add to cart.")
        return # End early if no items

    # Checkout
    print(f"{username}: Checking out...")
    checkout_resp = req("POST", "/order/checkout", token_for_user=username)
    order_id = None
    if checkout_resp and checkout_resp.status_code == 201:
        order_id = checkout_resp.json().get("order_id")
        print(f"{username}: Checkout successful, order ID: {order_id}")
    else:
        print(f"{username}: Checkout failed. {checkout_resp.text if checkout_resp else 'No response'}")
        return

    # Pay (PII for card)
    if order_id:
        payment_pii = { # PII
            "card_number": fake.credit_card_number(),
            "expiry_month": fake.credit_card_expire().split("/")[0],
            "expiry_year": "20" + fake.credit_card_expire().split("/")[1],
            "cvv": fake.credit_card_security_code()
        }
        print(f"{username}: Paying for order {order_id} with card PII...")
        req("POST", f"/order/{order_id}/pay/card", payment_pii, token_for_user=username)

    print(f"{username}: Simulation ended.")
    if username in user_tokens: # Clean up token
        del user_tokens[username]


def admin_actions_simulation():
    if not admin_token_global:
        print("Admin not logged in, skipping admin actions.")
        return

    print("Admin: Fetching purchases (contains PII)...")
    resp = req("GET", "/admin/purchases", is_admin_req=True)
    if resp and resp.status_code == 200:
        purchases = resp.json()
        print(f"Admin: Fetched {len(purchases)} purchases.")
        if purchases:
            sample_purchase = purchases[0]
            print(f"  Sample PII from purchase: User '{sample_purchase.get('user_full_name')}', Address '{sample_purchase.get('shipping_address')}'")
    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    # 2. List users (receives PII)
    print("Admin: Fetching first page of users (contains PII)...")
    # Solicita a primeira página, com o limite padrão de 50 (ou o que o servidor impuser)
    resp_users = req("GET", "/admin/users?page=1&per_page=50", is_admin_req=True) 
    if resp_users and resp_users.status_code == 200:
        response_data = resp_users.json()
        users_on_page = response_data.get("users", [])
        total_users = response_data.get("total_users", 0)
        current_page = response_data.get("page", 1)
        total_pages = response_data.get("total_pages", 1)
        print(f"Admin: Fetched {len(users_on_page)} users on page {current_page}/{total_pages}. Total users: {total_users}.")
        if users_on_page:
            first_user = users_on_page[0] # Pega o primeiro usuário da página atual para exemplo
            print(f"  Sample PII from first user: Username='{first_user.get('username')}', Email='{first_user.get('email')}', Full Name='{first_user.get('full_name')}'")
    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    # 3. Add a new item OR Restock an existing item
    if random.random() < 0.7: # 70% chance to add a new item
        print("Admin: Adding a new item...")
        new_item_payload = {
            "name": f"Awesome Gadget {random.randint(100,999)}",
            "description": fake.sentence(nb_words=6),
            "price": round(random.uniform(10, 500), 2),
            "stock": random.randint(20, 150) # Start with a decent stock
        }
        resp_add = req("POST", "/admin/item", data=new_item_payload, is_admin_req=True)
        if resp_add and resp_add.status_code == 201:
            # Optionally, refresh the global item list if a new item is added
            fetch_items_for_gen()
    elif available_item_ids_global: # Else, 30% chance to restock (if items exist)
        num_items_to_restock = random.randint(1, min(3, len(available_item_ids_global)))
        print(f"Admin: Attempting to restock {num_items_to_restock} item(s)...")
        items_to_consider_restock = random.sample(available_item_ids_global, min(len(available_item_ids_global), 5)) # Consider a sample
        
        for item_id_to_restock in items_to_consider_restock[:num_items_to_restock]:
            # Simple logic: restock to a random higher value
            new_stock_value = random.randint(50, 250) 
            print(f"Admin: Restocking item {item_id_to_restock} to {new_stock_value} units.")
            restock_payload = {"stock": new_stock_value}
            req("PUT", f"/admin/item/{item_id_to_restock}/stock", data=restock_payload, is_admin_req=True)
            time.sleep(random.uniform(DELAY_MIN / 4, DELAY_MAX / 4))
    else:
        print("Admin: No items to restock or chose not to add new item.")

    # Could also fetch items again to update available_item_ids_global
    print("Admin actions finished.")


def main():
    print("Starting traffic generator...")
    print(f"Target API: {API_BASE_URL}, Users: {NUM_USERS}, Delay: {DELAY_MIN}-{DELAY_MAX}s")
    if not RUN_INDEFINITELY:
        print(f"Will run for a limited number of cycles based on NUM_USERS.")

    initial_setup() # Login admin, fetch initial items

    threads = []
    run_count = 0
    max_runs = NUM_USERS * 2 # Arbitrary number of runs if not indefinite

    try:
        while RUN_INDEFINITELY or run_count < max_runs:
            # Clean up finished threads
            threads = [t for t in threads if t.is_alive()]

            if len(threads) < NUM_USERS:
                if random.random() < 0.2 and admin_token_global: # 20% chance for admin action
                    thread = threading.Thread(target=admin_actions_simulation)
                else:
                    user_id = f"simuser_{int(time.time()*1000)}"
                    thread = threading.Thread(target=user_simulation, args=(user_id,))
                
                threads.append(thread)
                thread.start()
                run_count +=1

            time.sleep(0.2) # Small delay to manage thread creation rate
            if not RUN_INDEFINITELY and run_count >= max_runs and not any(t.is_alive() for t in threads):
                break


    except KeyboardInterrupt:
        print("\nStopping traffic generator...")
    finally:
        print("Waiting for active threads to complete...")
        for t in threads:
            t.join(timeout=15)
        print("Traffic generation finished.")

def fetch_items_for_gen(): # Helper function to refresh item list
    global available_item_ids_global
    print("Generator: Fetching item list...")
    resp_items = req("GET", "/items")
    if resp_items and resp_items.status_code == 200:
        items_data = resp_items.json()
        new_item_ids = [item['item_id'] for item in items_data if isinstance(item, dict) and 'item_id' in item]
        # Only update if there's a change to avoid too much printing if list is stable
        if set(new_item_ids) != set(available_item_ids_global):
            available_item_ids_global = new_item_ids
            print(f"Generator: Updated available items list. Count: {len(available_item_ids_global)}")
    else:
        print("Generator: Failed to fetch/update items list.")

if __name__ == "__main__":
    main()
    # Ensure initial_setup calls fetch_items_for_gen or incorporates its logic
    # The current initial_setup already fetches items, so it's mostly fine.
    # Adding a direct call to fetch_items_for_gen in initial_setup after admin login
    # would ensure the print statements from fetch_items_for_gen are used.
    # For simplicity, the existing item fetch in initial_setup is sufficient.
