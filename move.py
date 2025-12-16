#!/usr/bin/env python3
"""
connect_and_send_wifi.py

Behavior:
- اسکن می‌کند دنبال SSID (پیش‌فرض "Nova_Robot")
- اگر پیدا شد، یک profile وای‌فای موقت می‌سازد با رمز 12345678 و تلاش می‌کند وصل شود
- وقتی وصل شد، به 192.168.4.1:5000 TCP وصل می‌شود و JSONها را می‌فرستد
- حالت یک‌بار ارسال (--left/--right) و حالت interactive (--interactive)

Usage examples:
  python connect_and_send_wifi.py --ssid Nova_Robot --password 12345678 --left 2 --right -3
  python connect_and_send_wifi.py --interactive
"""

import subprocess, time, socket, json, argparse, tempfile, os, sys

def run_cmd(cmd):
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
        return out.decode('utf-8', errors='ignore')
    except subprocess.CalledProcessError as e:
        return e.output.decode('utf-8', errors='ignore')

def scan_for_ssid(target_ssid):
    txt = run_cmd('netsh wlan show networks')
    # خروجی شامل خطوطی مانند: "SSID 1 : Nova_Robot"
    for line in txt.splitlines():
        if ':' in line:
            parts = line.split(':',1)
            left = parts[0].strip().lower()
            right = parts[1].strip()
            # برخی خطوط "SSID 1 : <name>"
            if left.startswith('ssid') and target_ssid.lower() == right.lower():
                return True
    return False

def is_currently_connected_to(ssid):
    txt = run_cmd('netsh wlan show interfaces')
    # خروجی شامل خط "SSID                   : Nova_Robot" وقتی متصل است
    for line in txt.splitlines():
        if ':' in line:
            k,v = line.split(':',1)
            k = k.strip().lower()
            v = v.strip()
            if k == 'ssid' and v.lower() == ssid.lower():
                return True
    return False

def add_wifi_profile(ssid, password):
    # ساختن فایل XML پروفایل موقت
    xml = f'''<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
    <name>{ssid}</name>
    <SSIDConfig>
        <SSID>
            <name>{ssid}</name>
        </SSID>
    </SSIDConfig>
    <connectionType>ESS</connectionType>
    <connectionMode>auto</connectionMode>
    <MSM>
        <security>
            <authEncryption>
                <authentication>WPA2PSK</authentication>
                <encryption>AES</encryption>
                <useOneX>false</useOneX>
            </authEncryption>
            <sharedKey>
                <keyType>passPhrase</keyType>
                <protected>false</protected>
                <keyMaterial>{password}</keyMaterial>
            </sharedKey>
        </security>
    </MSM>
</WLANProfile>'''
    fd, path = tempfile.mkstemp(suffix='.xml', text=True)
    os.write(fd, xml.encode('utf-8'))
    os.close(fd)
    out = run_cmd(f'netsh wlan add profile filename="{path}" user=current')
    # پاک کردن فایل موقت
    try:
        os.remove(path)
    except:
        pass
    return out

def connect_to_ssid(ssid, timeout=30):
    # تلاش برای کانکت با netsh
    run_cmd(f'netsh wlan connect name="{ssid}" ssid="{ssid}"')
    start = time.time()
    while time.time() - start < timeout:
        if is_currently_connected_to(ssid):
            return True
        time.sleep(1)
    return False

def wait_for_ssid_then_connect(ssid, password, scan_timeout=120):
    start = time.time()
    print(f"[+] Scanning for SSID '{ssid}' for up to {scan_timeout} s ...")
    while time.time() - start < scan_timeout:
        if scan_for_ssid(ssid):
            print(f"[+] Found SSID '{ssid}'. Adding profile and trying to connect...")
            add_wifi_profile(ssid, password)
            ok = connect_to_ssid(ssid, timeout=30)
            if ok:
                print(f"[+] Connected to {ssid}")
                return True
            else:
                print("[!] Could not connect after profile add; retrying scan...")
        time.sleep(2)
    return False

def tcp_send_once(host, port, payload, timeout=5):
    try:
        with socket.create_connection((host, port), timeout=timeout) as s:
            s.sendall((json.dumps(payload, separators=(',',':')) + "\n").encode('utf-8'))
            print("[SENT]", payload)
            return True
    except Exception as e:
        print("[TCP ERROR]", e)
        return False

def interactive_mode(host, port):
    print("Interactive mode. Type JSON like {\"left\":2,\"right\":-3} or 'left 2 right -3' or 'exit'")
    try:
        with socket.create_connection((host, port), timeout=10) as s:
            while True:
                line = input("> ").strip()
                if not line:
                    continue
                if line.lower() in ('exit','quit'): break
                if line.startswith('{'):
                    try:
                        payload = json.loads(line)
                    except Exception as e:
                        print("Invalid JSON:", e); continue
                else:
                    parts = line.split()
                    payload = {}
                    try:
                        i = 0
                        while i < len(parts)-1:
                            key = parts[i].lower()
                            val = int(parts[i+1])
                            if key in ('left','right'):
                                payload[key] = val
                            i += 2
                        if not payload:
                            print("Couldn't parse. Use 'left 2 right -3' or JSON.")
                            continue
                    except Exception as e:
                        print("Parse error:", e); continue
                s.sendall((json.dumps(payload, separators=(',',':')) + "\n").encode('utf-8'))
                print("Sent:", payload)
    except Exception as e:
        print("Could not open TCP connection for interactive mode:", e)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ssid", default="Nova_Robot")
    parser.add_argument("--password", default="12345678")
    parser.add_argument("--left", type=int, default=None)
    parser.add_argument("--right", type=int, default=None)
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--scan-timeout", type=int, default=120, help="How long to wait for AP to appear (seconds)")
    parser.add_argument("--host", default="192.168.4.1", help="ESP32 AP IP (default 192.168.4.1)")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()

    ssid = args.ssid
    pwd = args.password

    # اگر الان قبلاً متصل به SSID هستیم که فورا ادامه می‌دهیم
    if is_currently_connected_to(ssid):
        print(f"[+] Already connected to {ssid}")
        connected = True
    else:
        connected = wait_for_ssid_then_connect(ssid, pwd, scan_timeout=args.scan_timeout)

    if not connected:
        print("[FAIL] Could not find/connect to WiFi. If AP is not up, power the ESP32 or increase --scan-timeout.")
        sys.exit(1)

    # تلاش برای باز کردن اتصال TCP به ESP32
    host = args.host
    port = args.port
    print(f"[+] Trying TCP connect to {host}:{port} ...")
    try:
        sock = socket.create_connection((host, port), timeout=10)
        print("[+] TCP connected.")
    except Exception as e:
        print("[!] TCP connect failed:", e)
        sock = None

    if sock:
        sock.close()

    # اگر دستور left/right داده شده، ارسال کن
    if args.left is not None or args.right is not None:
        payload = {}
        if args.left is not None: payload['left'] = args.left
        if args.right is not None: payload['right'] = args.right
        ok = tcp_send_once(host, port, payload)
        if not ok:
            print("[!] Failed to send payload. Maybe server not ready. Try interactive mode.")
    if args.interactive:
        # interactive: باز کردن اتصال TCP دائمی برای ارسال‌های بعدی
        interactive_mode(host, port)

if __name__ == "__main__":
    main()
