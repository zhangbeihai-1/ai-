import requests

BASE_URL = 'http://127.0.0.1:5000'

def test_system():
    print("Testing Homepage...")
    try:
        r = requests.get(BASE_URL)
        if r.status_code == 200 and '欢迎登录' in r.text:
            print("SUCCESS: Homepage loaded.")
        else:
            print(f"FAILED: Homepage status {r.status_code}")
            return
            
        print("Testing Login...")
        payload = {'username': 'admin', 'password': 'admin123'}
        r = requests.post(f"{BASE_URL}/login", data=payload, allow_redirects=True)
        if r.status_code == 200 and '仪表盘' in r.text:
            print("SUCCESS: Login successful and redirected to Dashboard.")
            if '1,245,678' in r.text:
                print("SUCCESS: Dashboard contains seeded statistics.")
        else:
            print(f"FAILED: Login failed. Status {r.status_code}")
            
    except Exception as e:
        print(f"ERROR: Could not connect to server: {e}")

if __name__ == '__main__':
    test_system()
