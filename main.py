from flask import Flask, render_template, request, jsonify
import sqlite3
import requests
import re
from datetime import datetime
from bs4 import BeautifulSoup
import json
import time
import traceback

app = Flask(__name__)

# Database setup
def get_db():
    conn = sqlite3.connect('fraud.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    try:
        with get_db() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS searches
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                         phone TEXT UNIQUE,
                         pathao TEXT,
                         steadfast TEXT,
                         redx TEXT,
                         count INTEGER DEFAULT 1,
                         updated TIMESTAMP)''')
            conn.commit()
            print("Database initialized successfully")
    except Exception as e:
        print(f"Database init error: {e}")

init_db()

# Config (update these with your credentials)
PATHOA_USER = "mrzuyan@gmail.com"
PATHOA_PASS = "Zuyan@123"
STEADFAST_EMAIL = "mrzuyan@gmail.com"
STEADFAST_PASS = "zuyan@123"
REDX_PHONE = "01837478901"
REDX_PASS = "zuyan@123"

def clean_phone(phone):
    phone = re.sub(r'\D', '', phone)
    return phone if len(phone) == 11 and phone.startswith('01') else None

def check_pathao(phone):
    try:
        # Step 1: Login to get access token
        login_data = {
            "username": PATHOA_USER,
            "password": PATHOA_PASS
        }
        
        login_headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; 21061119AG Build/TP1A.220624.014) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": "https://merchant.pathao.com",
            "Referer": "https://merchant.pathao.com/login"
        }
        
        login = requests.post('https://merchant.pathao.com/api/v1/login', 
                            json=login_data,
                            headers=login_headers,
                            timeout=10)
        
        print(f"Pathao login status: {login.status_code}")
        
        if login.status_code != 200:
            print(f"Pathao login failed: {login.text}")
            return None
            
        login_response = login.json()
        access_token = login_response.get('access_token')
        
        if not access_token:
            print("Pathao no access token")
            return None
        
        print(f"Pathao login successful, token obtained")
        
        # Step 2: Try v2 user success endpoint first (from your earlier error)
        v2_headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; 21061119AG Build/TP1A.220624.014) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json"
        }
        
        v2_data = {
            "phone": phone
        }
        
        v2_response = requests.post(
            'https://merchant.pathao.com/api/v2/user/success',
            headers=v2_headers,
            json=v2_data,
            timeout=10
        )
        
        print(f"Pathao v2 response status: {v2_response.status_code}")
        
        if v2_response.status_code == 200:
            v2_data = v2_response.json()
            print(f"Pathao v2 response: {v2_data}")
            
            # Check for customer rating
            if v2_data.get('type') == 'success' and v2_data.get('code') == 200:
                response_data = v2_data.get('data', {})
                customer_rating = response_data.get('customer_rating', '')
                
                if customer_rating:
                    if customer_rating == 'fraud_customer':
                        return {
                            'success': 0,
                            'cancel': 1,
                            'total': 1,
                            'rating': 'FRAUD',
                            'risk': 'high'
                        }
                    elif customer_rating == 'good_customer':
                        return {
                            'success': 1,
                            'cancel': 0,
                            'total': 1,
                            'rating': 'GOOD',
                            'risk': 'low'
                        }
                    else:
                        return {
                            'success': 0,
                            'cancel': 0,
                            'total': 1,
                            'rating': customer_rating.upper(),
                            'risk': 'medium'
                        }
        
        # Step 3: Query orders for the phone number using v1 endpoint
        orders_params = {
            "receiver_phone": phone,
            "transfer_status": "4",  # 4 might represent delivered/completed
            "archive": "0",
            "page": "1",
            "limit": "20"
        }
        
        orders_headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; 21061119AG Build/TP1A.220624.014) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://merchant.pathao.com/courier/orders/list",
            "X-Requested-With": "mark.via.gp"
        }
        
        orders_response = requests.get(
            'https://merchant.pathao.com/api/v1/orders/all',
            params=orders_params,
            headers=orders_headers,
            timeout=10
        )
        
        print(f"Pathao orders status: {orders_response.status_code}")
        
        if orders_response.status_code == 200:
            data = orders_response.json()
            print(f"Pathao orders response: {data}")
            
            if data.get('type') == 'success' and data.get('code') == 200:
                orders_data = data.get('data', {})
                orders_list = orders_data.get('data', [])
                total_orders = orders_data.get('total', 0)
                
                # Count successful deliveries
                successful = 0
                cancelled = 0
                
                for order in orders_list:
                    # Check order status - adjust based on actual status values
                    status = order.get('transfer_status')
                    order_status = order.get('order_status', '')
                    
                    # You may need to adjust these conditions based on actual status codes
                    if status == 4 or order_status == 'delivered':
                        successful += 1
                    elif status == 3 or order_status == 'cancelled':
                        cancelled += 1
                
                if total_orders > 0:
                    return {
                        'success': successful,
                        'cancel': cancelled,
                        'total': total_orders,
                        'has_orders': True
                    }
        
        # Return default if no data found
        return {
            'success': 0,
            'cancel': 0,
            'total': 0,
            'message': 'No data available'
        }
        
    except requests.exceptions.Timeout:
        print("Pathao timeout")
        return None
    except requests.exceptions.ConnectionError:
        print("Pathao connection error")
        return None
    except Exception as e:
        print(f"Pathao error: {e}")
        traceback.print_exc()
        return None

def check_steadfast(phone):
    try:
        session = requests.Session()
        
        # Get CSRF token
        r = session.get('https://steadfast.com.bd/login', timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        token = soup.find('input', {'name': '_token'})
        
        if not token:
            return None
            
        # Login
        login_res = session.post('https://steadfast.com.bd/login', 
                                data={
                                    '_token': token['value'], 
                                    'email': STEADFAST_EMAIL, 
                                    'password': STEADFAST_PASS
                                },
                                timeout=10)
        
        if login_res.status_code not in [200, 302]:
            return None
            
        # Check fraud
        r = session.get(f'https://steadfast.com.bd/user/frauds/check/{phone}', timeout=10)
        if r.status_code == 200:
            data = r.json()
            delivered = data.get('total_delivered', 0)
            cancelled = data.get('total_cancelled', 0)
            return {
                'success': delivered,
                'cancel': cancelled,
                'total': delivered + cancelled
            }
    except Exception as e:
        print(f"Steadfast error: {e}")
        return None
    return None

def check_redx(phone):
    try:
        # Login
        login = requests.post('https://api.redx.com.bd/v4/auth/login',
                            json={'phone': f'88{REDX_PHONE}', 'password': REDX_PASS},
                            timeout=10)
        
        if login.status_code != 200:
            return None
            
        token = login.json()['data']['accessToken']
        if not token:
            return None
            
        # Get stats
        res = requests.get(f'https://redx.com.bd/api/redx_se/admin/parcel/customer-success-return-rate?phoneNumber=88{phone}',
                         headers={'Authorization': f'Bearer {token}'},
                         timeout=10)
        
        if res.status_code == 200:
            data = res.json()['data']
            delivered = data.get('deliveredParcels', 0)
            total = data.get('totalParcels', 0)
            return {
                'success': delivered,
                'cancel': total - delivered,
                'total': total
            }
    except Exception as e:
        print(f"Redx error: {e}")
        return None
    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/check', methods=['POST'])
def check():
    phone = clean_phone(request.form['phone'])
    if not phone:
        return jsonify({'error': 'Invalid phone number'}), 400
    
    with get_db() as conn:
        # Check cache
        cached = conn.execute('SELECT * FROM searches WHERE phone = ?', (phone,)).fetchone()
        
        if cached and cached['updated']:
            try:
                age = datetime.now() - datetime.fromisoformat(cached['updated'])
                if age.seconds < 3600:  # 1 hour cache
                    conn.execute('UPDATE searches SET count = count + 1 WHERE phone = ?', (phone,))
                    conn.commit()
                    return jsonify({
                        'phone': phone,
                        'pathao': json.loads(cached['pathao']),
                        'steadfast': json.loads(cached['steadfast']),
                        'redx': json.loads(cached['redx']),
                        'cached': True
                    })
            except:
                pass
        
        # Check all services
        pathao = check_pathao(phone) or {'success': 0, 'cancel': 0, 'total': 0, 'message': 'Service unavailable'}
        steadfast = check_steadfast(phone) or {'success': 0, 'cancel': 0, 'total': 0}
        redx = check_redx(phone) or {'success': 0, 'cancel': 0, 'total': 0}
        
        # Log the results
        print(f"Final Pathao result for {phone}: {pathao}")
        print(f"Final Steadfast result for {phone}: {steadfast}")
        print(f"Final Redx result for {phone}: {redx}")
        
        # Save to DB
        if cached:
            conn.execute('''UPDATE searches SET 
                          pathao = ?, steadfast = ?, redx = ?,
                          count = count + 1, updated = ?
                          WHERE phone = ?''',
                       (json.dumps(pathao), json.dumps(steadfast), json.dumps(redx),
                        datetime.now().isoformat(), phone))
        else:
            conn.execute('''INSERT INTO searches 
                          (phone, pathao, steadfast, redx, updated)
                          VALUES (?, ?, ?, ?, ?)''',
                       (phone, json.dumps(pathao), json.dumps(steadfast), 
                        json.dumps(redx), datetime.now().isoformat()))
        
        conn.commit()
        
        return jsonify({
            'phone': phone,
            'pathao': pathao,
            'steadfast': steadfast,
            'redx': redx,
            'cached': False
        })

@app.route('/history')
def history():
    search = request.args.get('q', '')
    with get_db() as conn:
        if search:
            rows = conn.execute('''SELECT phone, pathao, steadfast, redx, count, updated 
                                 FROM searches WHERE phone LIKE ? ORDER BY updated DESC''', 
                                 (f'%{search}%',)).fetchall()
        else:
            rows = conn.execute('''SELECT phone, pathao, steadfast, redx, count, updated 
                                 FROM searches ORDER BY updated DESC LIMIT 50''').fetchall()
        
        searches = []
        for row in rows:
            search_item = dict(row)
            try:
                search_item['pathao'] = json.loads(search_item['pathao']) if search_item['pathao'] else {'success': 0, 'cancel': 0, 'total': 0}
            except:
                search_item['pathao'] = {'success': 0, 'cancel': 0, 'total': 0}
                
            try:
                search_item['steadfast'] = json.loads(search_item['steadfast']) if search_item['steadfast'] else {'success': 0, 'cancel': 0, 'total': 0}
            except:
                search_item['steadfast'] = {'success': 0, 'cancel': 0, 'total': 0}
                
            try:
                search_item['redx'] = json.loads(search_item['redx']) if search_item['redx'] else {'success': 0, 'cancel': 0, 'total': 0}
            except:
                search_item['redx'] = {'success': 0, 'cancel': 0, 'total': 0}
            
            for provider in ['pathao', 'steadfast', 'redx']:
                if search_item[provider].get('total', 0) > 0:
                    rate = (search_item[provider]['success'] / search_item[provider]['total']) * 100
                    search_item[provider]['rate'] = round(rate, 1)
                else:
                    search_item[provider]['rate'] = 0
                
            searches.append(search_item)
    
    return render_template('history.html', searches=searches, search_query=search)

@app.errorhandler(Exception)
def handle_error(e):
    print(f"Error: {e}")
    traceback.print_exc()
    return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)