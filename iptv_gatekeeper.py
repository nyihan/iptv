# -*- coding: utf-8 -*-
import os
import re
import string
import random
from datetime import datetime, timedelta
from flask import Flask, request, Response, jsonify, render_template_string, session, redirect, url_for
import requests
from supabase import create_client

app = Flask(__name__)

# ==================== လုံခြုံရေးနှင့် ဆက်ရှင် သတ်မှတ်ချက်များ ====================
# Render ပေါ်တွင် Restart ကျသော်လည်း Session များမပြတ်တောက်စေရန် တည်ငြိမ်သော Secret Key သတ်မှတ်ခြင်း
app.secret_key = "iptv-gatekeeper-secure-session-key-99988"

# သင့် Supabase Project URL နှင့် API Key များဖြစ်ကြသည်
SUPABASE_URL = "https://mykfodrelbkdsmednyka.supabase.co"  
SUPABASE_KEY = "sb_secret_COWhBX3R6grwer9oMsi00g_t6wmst-U"  
BUCKET_NAME = "iptv"  

# Admin Panel သို့ ဝင်ရောက်ရန် သတ်မှတ်အကောင့်နှင့် စကားဝှက်
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

# သင့် Supabase Storage မှ ဖိုင်လင့်ခ်အစစ်အမှန်များ
SUPABASE_M3U_URL = "https://mykfodrelbkdsmednyka.supabase.co/storage/v1/object/public/iptv/ott_updated.m3u"
SUPABASE_EPG_URL = "https://mykfodrelbkdsmednyka.supabase.co/storage/v1/object/public/iptv/epg.xml"
# ===============================================================

# Supabase Client အား ချိတ်ဆက်တည်ဆောက်ခြင်း
try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    print(f"Supabase ချိတ်ဆက်မှု အမှားရှိပါသည်: {e}")

# ==================== SUPABASE DATABASE FUNCTIONS ====================

def get_user(username):
    """Supabase ထဲမှ အသုံးပြုသူတစ်ဦးချင်းစီ၏ အချက်အလက်ကို ရှာဖွေခြင်း"""
    try:
        res = supabase.table("iptv_users").select("*").eq("username", username).execute()
        if res.data:
            return res.data[0]
    except Exception as e:
        print(f"အသုံးပြုသူရှာဖွေရာတွင် အမှားရှိပါသည်: {e}")
    return None

def create_user(username, password):
    """Supabase ထဲတွင် အသုံးပြုသူအသစ် ဖန်တီးထည့်သွင်းခြင်း"""
    try:
        supabase.table("iptv_users").insert({
            "username": username,
            "password": password,
            "locked_ip": None,
            "last_active": None,
            "created_at": datetime.utcnow().isoformat()
        }).execute()
        return True
    except Exception as e:
        print(f"အသုံးပြုသူအသစ်ဖန်တီးရာတွင် အမှားရှိပါသည်: {e}")
        return False

def update_user_data(username, update_data):
    """Supabase ထဲရှိ အသုံးပြုသူ၏ IP သို့မဟုတ် လှုပ်ရှားမှုအချိန်ကို အပ်ဒိတ်လုပ်ခြင်း"""
    try:
        supabase.table("iptv_users").update(update_data).eq("username", username).execute()
        return True
    except Exception as e:
        print(f"ဒေတာအပ်ဒိတ်လုပ်ရာတွင် အမှားရှိပါသည်: {e}")
        return False

def delete_user(username):
    """Supabase ထဲမှ အသုံးပြုသူအား ဖျက်သိမ်းခြင်း"""
    try:
        supabase.table("iptv_users").delete().eq("username", username).execute()
        return True
    except Exception as e:
        print(f"အသုံးပြုသူဖျက်သိမ်းရာတွင် အမှားရှိပါသည်: {e}")
        return False

def get_all_users():
    """Supabase ထဲရှိ အသုံးပြုသူအားလုံးကို Admin Panel အတွက် ဆွဲယူခြင်း"""
    try:
        res = supabase.table("iptv_users").select("*").execute()
        return res.data if res.data else []
    except Exception as e:
        print(f"အသုံးပြုသူအားလုံးကို ဆွဲယူရာတွင် အမှားရှိပါသည်: {e}")
        return []

# =====================================================================

# ၅ လုံးတွဲ ကျပန်းစာလုံး ထုတ်ပေးသည့်စနစ်
def generate_random_string(length=5):
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def get_myanmar_time(utc_iso_str):
    """ISO UTC အချိန်အား မြန်မာစံတော်ချိန် (GMT+6:30) သို့ ပြောင်းလဲခြင်း"""
    if not utc_iso_str:
        return "မရှိသေးပါ"
    try:
        dt = datetime.fromisoformat(utc_iso_str)
        mm_dt = dt + timedelta(hours=6, minutes=30)
        return mm_dt.strftime("%Y-%m-%d %I:%M:%S %p")
    except Exception:
        return utc_iso_str

def get_client_ip():
    """X-Forwarded-For Header မှတစ်ဆင့် သုံးစွဲသူ၏ IP အစစ်အမှန်ကို ရှာဖွေဖတ်ယူခြင်း"""
    if request.headers.get("X-Forwarded-For"):
        return request.headers.get("X-Forwarded-For").split(",")[0].strip()
    return request.remote_addr

def check_device_access(username, user_data):
    """1-Device Limit ကို စမတ်ကျကျ စစ်ဆေးပေးမည့်စနစ် (Supabase Database နှင့် တွဲဖက်လုပ်ဆောင်ပါသည်)"""
    client_ip = get_client_ip()
    now = datetime.utcnow()

    locked_ip = user_data.get("locked_ip")
    last_active_str = user_data.get("last_active")

    if not locked_ip:
        update_user_data(username, {
            "locked_ip": client_ip,
            "last_active": now.isoformat()
        })
        return True, "IP Locked Successfully"

    if locked_ip == client_ip:
        update_user_data(username, {
            "last_active": now.isoformat()
        })
        return True, "IP Matched"

    if last_active_str:
        last_active = datetime.fromisoformat(last_active_str)
        if now - last_active > timedelta(minutes=15):
            print(f"[AUTO-RELEASE] {username} သည် IP ဟောင်း {locked_ip} မှ IP အသစ် {client_ip} သို့ အလိုအလျောက်ပြောင်းလဲသွားပါပြီ။")
            update_user_data(username, {
                "locked_ip": client_ip,
                "last_active": now.isoformat()
            })
            return True, "IP Auto-Transferred"

    return False, f"အကောင့်အား အခြားစက်တစ်ခုတွင် အသုံးပြုနေဆဲဖြစ်ပါသည်။ (Locked IP: {locked_ip})"


# ==================== WEB ROUTES ====================

@app.route("/")
def home():
    return "<h1>IPTV Gateway is Online (Supabase DB & Site Login Integrated).</h1>"


# --- ADMIN LOGIN ROUTE (ဆိုက်လော့ဂ်အင် စနစ်) ---
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error_msg = None
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            return redirect(url_for("admin_panel"))
        else:
            error_msg = "အသုံးပြုသူအမည် သို့မဟုတ် စကားဝှက် မှားယွင်းနေပါသည်။"

    # လှပသော ခေတ်မီဆန်းသစ်သည့် Login Page Template (အရောင် Clashing ဖြစ်မှုများအား လုံးဝ ပြုပြင်ထားပါသည်)
    login_html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>IPTV Panel Login</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-950 text-gray-100 flex items-center justify-center min-h-screen p-4">
        <div class="bg-gray-900 p-8 rounded-2xl shadow-2xl border border-gray-800 w-full max-w-md">
            <div class="text-center mb-6">
                <h1 class="text-3xl font-extrabold text-blue-500 tracking-wider">IPTV PANEL</h1>
                <p class="text-sm text-gray-400 mt-2">စီမံခန့်ခွဲသူစာမျက်နှာသို့ အကောင့်ဝင်ရောက်ပါ</p>
            </div>
            
            {% if error %}
            <div class="bg-red-950 border border-red-800 text-red-200 text-sm p-3 rounded-lg mb-4 text-center">
                {{ error }}
            </div>
            {% endif %}
            
            <form action="/admin/login" method="POST" class="space-y-4">
                <div>
                    <label class="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Username</label>
                    <input type="text" name="username" required placeholder="အသုံးပြုသူအမည်" 
                           class="w-full bg-gray-800 border border-gray-750 rounded-lg p-3 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-900/30 transition duration-200">
                </div>
                <div>
                    <label class="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Password</label>
                    <input type="password" name="password" required placeholder="စကားဝှက်" 
                           class="w-full bg-gray-800 border border-gray-750 rounded-lg p-3 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-900/30 transition duration-200">
                </div>
                <button type="submit" class="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 rounded-lg shadow-lg hover:shadow-blue-900/30 transition duration-200 mt-2">
                    လော့ဂ်အင်ဝင်မည်
                </button>
            </form>
        </div>
    </body>
    </html>
    """
    return render_template_string(login_html, error=error_msg)


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("admin_login"))


# --- ADMIN CONTROL PANEL ---
@app.route("/admin")
def admin_panel():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    users_list = get_all_users()
    
    formatted_users = []
    for data in users_list:
        formatted_users.append({
            "username": data["username"],
            "password": data["password"],
            "locked_ip": data["locked_ip"] if data["locked_ip"] else "No Lock",
            "last_active": get_myanmar_time(data["last_active"]),
            "created_at": get_myanmar_time(data["created_at"])
        })

    new_user_data = session.pop("new_user_created", None)

    # လှပသော Tailwind CSS Dashboard နှင့် Premium Modal ပါဝင်သော Template
    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>IPTV User Controller</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-950 text-gray-100 min-h-screen p-4 md:p-6">
        <div class="max-w-6xl mx-auto">
            <header class="flex justify-between items-center mb-8 border-b border-gray-800 pb-4">
                <div>
                    <h1 class="text-2xl md:text-3xl font-extrabold text-blue-500 tracking-wide">IPTV Panel (Cloud DB)</h1>
                    <p class="text-xs text-gray-400 mt-1">အကောင့်များအားလုံးအား စမတ်ကျကျ စောင့်ကြည့်ထိန်းချုပ်နိုင်သည်</p>
                </div>
                <a href="/admin/logout" class="bg-red-950 hover:bg-red-900 text-red-200 border border-red-800 text-xs font-bold py-2 px-4 rounded-lg transition duration-200">
                    ထွက်မည်
                </a>
            </header>

            <!-- Control Box -->
            <div class="bg-gray-900 p-6 rounded-2xl shadow-xl border border-gray-800 mb-8 flex flex-col md:flex-row gap-4 items-center justify-between">
                <div>
                    <h2 class="text-lg md:text-xl font-bold mb-1">အကောင့်အသစ် ထုတ်ပေးရန်</h2>
                    <p class="text-xs text-gray-400">၅ လုံးတွဲ Username နှင့် Password ကို အလိုအလျောက် ထုတ်လုပ်ပြီး Supabase ထဲတွင် သိမ်းဆည်းပါမည်။</p>
                </div>
                <form action="/admin/create" method="POST" class="flex gap-2">
                    <button type="submit" class="bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-6 rounded-lg shadow-lg hover:shadow-blue-900/20 transition duration-200">
                        + Auto Generate Account
                    </button>
                </form>
            </div>

            <!-- Users Table -->
            <div class="bg-gray-900 rounded-2xl shadow-xl border border-gray-800 overflow-hidden">
                <div class="overflow-x-auto">
                    <table class="w-full text-left border-collapse">
                        <thead>
                            <tr class="bg-gray-800/50 text-gray-300 text-sm border-b border-gray-800">
                                <th class="p-4">Username</th>
                                <th class="p-4">Password</th>
                                <th class="p-4">Locked IP (Device)</th>
                                <th class="p-4">နောက်ဆုံးကြည့်ရှုချိန်</th>
                                <th class="p-4">ဖန်တီးချိန်</th>
                                <th class="p-4 text-center">လုပ်ဆောင်ချက်</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for user in users %}
                            <tr class="border-b border-gray-800 hover:bg-gray-900/50 transition">
                                <td class="p-4 font-mono font-bold text-yellow-400">{{ user.username }}</td>
                                <!-- Password အား လုံးဝ အဆင်ပြေစွာ ဖတ်ရှုနိုင်စေရန် text-gray-200 တောက်ပသောအရောင် သတ်မှတ်ထားပါသည် -->
                                <td class="p-4 font-mono font-semibold text-gray-200">{{ user.password }}</td>
                                <td class="p-4">
                                    {% if user.locked_ip != 'No Lock' %}
                                    <span class="px-2.5 py-1 rounded-full text-xs font-semibold bg-red-950/80 text-red-200 border border-red-900/50">
                                        {{ user.locked_ip }}
                                    </span>
                                    {% else %}
                                    <span class="px-2.5 py-1 rounded-full text-xs font-semibold bg-green-950/80 text-green-200 border border-green-900/50">
                                        No Lock
                                    </span>
                                    {% endif %}
                                </td>
                                <td class="p-4 text-xs text-gray-300">{{ user.last_active }}</td>
                                <td class="p-4 text-xs text-gray-400">{{ user.created_at }}</td>
                                <td class="p-4 flex justify-center gap-2">
                                    <form action="/admin/reset-ip" method="POST" class="inline">
                                        <input type="hidden" name="username" value="{{ user.username }}">
                                        <button type="submit" class="bg-yellow-600/10 hover:bg-yellow-600/20 text-yellow-400 border border-yellow-800/30 text-xs font-bold py-1.5 px-3 rounded-lg transition duration-150">
                                            Reset Device
                                        </button>
                                    </form>
                                    <form action="/admin/delete" method="POST" class="inline" onsubmit="return confirm('ဤအကောင့်အား ပယ်ဖျက်ရန် သေချာပါသလား။');">
                                        <input type="hidden" name="username" value="{{ user.username }}">
                                        <button type="submit" class="bg-red-600/10 hover:bg-red-600/20 text-red-400 border border-red-800/30 text-xs font-bold py-1.5 px-3 rounded-lg transition duration-150">
                                            Delete
                                        </button>
                                    </form>
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- --- BEAUTIFUL MODAL POP-UP (အကောင့်အသစ် ထွက်သည့်သေတ္တာလေး) --- -->
        {% if new_user %}
        <div id="accountModal" class="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 z-50 transition duration-300">
            <div class="bg-gray-900 border border-gray-850 p-6 md:p-8 rounded-2xl max-w-xl w-full shadow-2xl space-y-6">
                <div class="text-center">
                    <div class="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-green-900/30 text-green-400 mb-3 border border-green-800/30">
                        ✓
                    </div>
                    <h3 class="text-2xl font-extrabold text-green-400">အကောင့်အသစ် ဖန်တီးပြီးပါပြီ။</h3>
                    <p class="text-xs text-gray-400 mt-1">အသုံးပြုသူအတွက် လင့်ခ်များနှင့် အချက်အလက်များ</p>
                </div>

                <div class="space-y-4 bg-gray-950 p-4 rounded-xl border border-gray-800">
                    <!-- Credentials -->
                    <div class="grid grid-cols-2 gap-4 border-b border-gray-800 pb-3">
                        <div>
                            <span class="text-gray-400 text-xs block uppercase">Username</span>
                            <span class="font-mono text-lg font-bold text-yellow-400">{{ new_user.username }}</span>
                        </div>
                        <div>
                            <span class="text-gray-400 text-xs block uppercase">Password</span>
                            <span class="font-mono text-lg font-bold text-gray-200">{{ new_user.password }}</span>
                        </div>
                    </div>

                    <!-- Links with Copy Button -->
                    <div class="space-y-3 pt-1">
                        <div>
                            <span class="text-gray-400 text-xs block mb-1">M3U Playlist URL</span>
                            <div class="flex gap-2">
                                <input id="m3uLink" type="text" readonly 
                                       value="{{ base_url }}/m3u?user={{ new_user.username }}&pass={{ new_user.password }}"
                                       class="bg-gray-900 border border-gray-800 rounded-lg p-2 text-xs font-mono w-full text-blue-300 focus:outline-none">
                                <button id="m3uLink-btn" onclick="copyText('m3uLink')" class="bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold px-3 py-2 rounded-lg whitespace-nowrap">
                                    Copy
                                </button>
                            </div>
                        </div>
                        <div>
                            <span class="text-gray-400 text-xs block mb-1">EPG (TV Guide) URL</span>
                            <div class="flex gap-2">
                                <input id="epgLink" type="text" readonly 
                                       value="{{ base_url }}/epg?user={{ new_user.username }}&pass={{ new_user.password }}"
                                       class="bg-gray-900 border border-gray-800 rounded-lg p-2 text-xs font-mono w-full text-blue-300 focus:outline-none">
                                <button id="epgLink-btn" onclick="copyText('epgLink')" class="bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold px-3 py-2 rounded-lg whitespace-nowrap">
                                    Copy
                                </button>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="flex justify-end pt-2">
                    <button onclick="closeModal()" class="w-full bg-gray-800 hover:bg-gray-700 text-gray-200 font-bold py-3 rounded-lg border border-gray-700 transition duration-200">
                        ပိတ်မည်
                    </button>
                </div>
            </div>
        </div>

        <script>
            // Clipboard Copy System
            function copyText(elementId) {
                var copyText = document.getElementById(elementId);
                copyText.select();
                copyText.setSelectionRange(0, 99999); // Mobile Support
                document.execCommand("copy");
                
                var btn = document.getElementById(elementId + "-btn");
                var originalText = btn.innerText;
                btn.innerText = "Copied!";
                btn.className = "bg-green-600 text-white text-xs font-bold px-3 py-2 rounded-lg whitespace-nowrap";
                setTimeout(function() {
                    btn.innerText = originalText;
                    btn.className = "bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold px-3 py-2 rounded-lg whitespace-nowrap";
                }, 2000);
            }

            function closeModal() {
                document.getElementById("accountModal").classList.add("hidden");
            }
        </script>
        {% endif %}
    </body>
    </html>
    """
    base_url = request.host_url.rstrip('/')
    return render_template_string(html_template, users=formatted_users, new_user=new_user_data, base_url=base_url)


# အကောင့်အလိုအလျောက် ဖန်တီးပေးသည့် Route
@app.route("/admin/create", methods=["POST"])
def admin_create():
    if not session.get("admin_logged_in"):
        return "Unauthorized", 403

    while True:
        new_user = generate_random_string(5)
        if not get_user(new_user):
            break
            
    new_pass = generate_random_string(5)
    
    # Supabase ထဲသို့ အကောင့်သိမ်းဆည်းခြင်း
    create_user(new_user, new_pass)
    
    # Pop-up Modal တွင် ချပြနိုင်ရန် ဆက်ရှင်ထဲသို့ ယာယီထည့်သွင်းခြင်း
    session["new_user_created"] = {
        "username": new_user,
        "password": new_pass
    }
    
    return redirect(url_for("admin_panel"))


# Device IP Lock အား ပြန်လည်ရှင်းလင်းပေးသည့် Route (Reset Device)
@app.route("/admin/reset-ip", methods=["POST"])
def admin_reset_ip():
    if not session.get("admin_logged_in"):
        return "Unauthorized", 403

    username = request.form.get("username")
    update_user_data(username, {
        "locked_ip": None,
        "last_active": None
    })
    return redirect(url_for("admin_panel"))


# အကောင့်ပယ်ဖျက်သည့် Route
@app.route("/admin/delete", methods=["POST"])
def admin_delete():
    if not session.get("admin_logged_in"):
        return "Unauthorized", 403

    username = request.form.get("username")
    delete_user(username)
    return redirect(url_for("admin_panel"))


# ==================== PLAYLIST & STREAM GATEWAY ====================

@app.route("/m3u")
def get_m3u():
    """လုံခြုံစိတ်ချရသော Proxy Playlist စနစ်"""
    user = request.args.get("user")
    pass_word = request.args.get("pass")

    user_data = get_user(user) if user else None
    if not user_data or user_data["password"] != pass_word:
        return Response("ဝင်ရောက်ခွင့်မရှိပါ - Username သို့မဟုတ် Password မှားယွင်းနေပါသည်။", status=403)

    # 1-Device Limit အား စစ်ဆေးခြင်း
    allowed, msg = check_device_access(user, user_data)
    if not allowed:
        return Response(msg, status=403)

    try:
        res = requests.get(SUPABASE_M3U_URL)
        m3u_content = res.text
        
        base_url = request.host_url.rstrip('/')
        lines = m3u_content.splitlines()
        new_m3u_lines = []
        
        # epg.xml လမ်းကြောင်းအား Secure Link သို့ လွှဲပြောင်းပေးခြင်း
        secure_epg_url = f"{base_url}/epg?user={user}&pass={pass_word}"
        
        for line in lines:
            line_strip = line.strip()
            if line_strip.startswith("#EXTM3U"):
                line_strip = re.sub(r'x-tvg-url="[^"]*"', f'x-tvg-url="{secure_epg_url}"', line_strip)
                new_m3u_lines.append(line_strip)
            elif line_strip.startswith("http://") or line_strip.startswith("https://"):
                secure_live_url = f"{base_url}/live?user={user}&pass={pass_word}&orig={line_strip}"
                new_m3u_lines.append(secure_live_url)
            else:
                new_m3u_lines.append(line)
                
        return Response("\n".join(new_m3u_lines), mimetype="text/plain")
    except Exception as e:
        return Response(f"အမှားအယွင်းရှိပါသည်: {e}", status=500)


@app.route("/live")
def live_stream_proxy():
    """ရုပ်သံလိုင်းများ ဖွင့်ကြည့်သည့်အခါ Device စစ်ဆေးပြီး လွှဲပြောင်းပေးသည့် စနစ်"""
    user = request.args.get("user")
    pass_word = request.args.get("pass")
    orig_url = request.args.get("orig")

    user_data = get_user(user) if user else None
    if not user_data or user_data["password"] != pass_word:
        return Response("Access Denied", status=403)

    # 1-Device Limit အား ထပ်မံစစ်ဆေးခြင်း
    allowed, msg = check_device_access(user, user_data)
    if not allowed:
        return Response(msg, status=403)

    if not orig_url:
        return Response("Missing stream URL", status=400)

    # အကုန်အောင်မြင်ပါက မူရင်း Stream လင့်ခ်ဆီသို့ Redirect (HTTP 302) လုပ်ပေးခြင်း
    return Response("", status=302, headers={"Location": orig_url})


@app.route("/epg")
def get_epg():
    """လုံခြုံစိတ်ချရသော TV Guide (EPG) ထုတ်ပေးသည့်စနစ်"""
    user = request.args.get("user")
    pass_word = request.args.get("pass")

    user_data = get_user(user) if user else None
    if not user_data or user_data["password"] != pass_word:
        return Response("Access Denied", status=403)

    try:
        res = requests.get(SUPABASE_EPG_URL)
        return Response(res.text, mimetype="text/xml")
    except Exception as e:
        return Response(f"Error: {e}", status=500)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
