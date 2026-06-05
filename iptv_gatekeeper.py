# -*- coding: utf-8 -*-
import os
import re
import string
import random
from datetime import datetime, timedelta
from flask import Flask, request, Response, jsonify, render_template_string
import requests
from supabase import create_client

app = Flask(__name__)

# ==================== SUPABASE သတ်မှတ်ချက်များ ====================
# သင့် Supabase Project URL နှင့် API Key များဖြစ်ကြသည် (Secret API Key ဖြစ်၍ bypass RLS လုပ်ဆောင်နိုင်ပါသည်)
SUPABASE_URL = "https://mykfodrelbkdsmednyka.supabase.co"  
SUPABASE_KEY = "sb_secret_COWhBX3R6grwer9oMsi00g_t6wmst-U"  
BUCKET_NAME = "iptv"  

# Admin Dashboard သို့ ဝင်ရောက်ရန် လျှို့ဝှက်ကုဒ် (မိမိစိတ်ကြိုက် ပြောင်းလဲနိုင်သည်)
ADMIN_SECRET_KEY = "admin123"

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

    # ပထမဆုံးအကြိမ် ဝင်ရောက်ခြင်း သို့မဟုတ် IP လုံးဝမရှိသေးပါက IP Lock ချမည်
    if not locked_ip:
        update_user_data(username, {
            "locked_ip": client_ip,
            "last_active": now.isoformat()
        })
        return True, "IP Locked Successfully"

    # လက်ရှိစက်နှင့် Lock ချထားသော IP တူညီပါက အချိန်အား အပ်ဒိတ်လုပ်ပြီး ဝင်ခွင့်ပေးမည်
    if locked_ip == client_ip:
        update_user_data(username, {
            "last_active": now.isoformat()
        })
        return True, "IP Matched"

    # အကယ်၍ IP မတူညီပါက - နောက်ဆုံးလှုပ်ရှားမှုအချိန်ကို စစ်ဆေးမည် (၁၅ မိနစ်ပြည့်ပါက စက်ပြောင်းခွင့်ပေးမည်)
    if last_active_str:
        last_active = datetime.fromisoformat(last_active_str)
        if now - last_active > timedelta(minutes=15):
            print(f"[AUTO-RELEASE] {username} သည် IP ဟောင်း {locked_ip} မှ IP အသစ် {client_ip} သို့ အလိုအလျောက်ပြောင်းလဲသွားပါပြီ။")
            update_user_data(username, {
                "locked_ip": client_ip,
                "last_active": now.isoformat()
            })
            return True, "IP Auto-Transferred"

    # လှုပ်ရှားမှု ရှိနေဆဲဖြစ်ပြီး အခြားစက်မှ လှမ်းဖွင့်ပါက ငြင်းပယ်မည် (1-Device Block)
    return False, f"အကောင့်အား အခြားစက်တစ်ခုတွင် အသုံးပြုနေဆဲဖြစ်ပါသည်။ (Locked IP: {locked_ip})"


# ==================== WEB ROUTES ====================

@app.route("/")
def home():
    return "<h1>IPTV Gateway is Online (Supabase DB Integrated).</h1>"

# Admin Control Panel စာမျက်နှာ (အကောင့်များ ထုတ်ပေးခြင်းနှင့် စောင့်ကြည့်ခြင်း)
@app.route("/admin")
def admin_panel():
    key = request.args.get("key")
    if key != ADMIN_SECRET_KEY:
        return "<h1>ဝင်ရောက်ခွင့်မရှိပါ - လျှို့ဝှက်ကုဒ် မမှန်ကန်ပါ။</h1>", 403

    # Supabase မှ အကောင့်အားလုံးကို ဖတ်ယူခြင်း
    users_list = get_all_users()
    
    # ပြသရန်အတွက် မြန်မာစံတော်ချိန်သို့ ပြောင်းလဲခြင်း
    formatted_users = []
    for data in users_list:
        formatted_users.append({
            "username": data["username"],
            "password": data["password"],
            "locked_ip": data["locked_ip"] if data["locked_ip"] else "No Lock",
            "last_active": get_myanmar_time(data["last_active"]),
            "created_at": get_myanmar_time(data["created_at"])
        })

    # လှပသော Tailwind CSS အသုံးပြုထားသည့် Dashboard Template
    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>IPTV User Controller (Cloud DB)</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-900 text-gray-100 min-h-screen p-6">
        <div class="max-w-6xl mx-auto">
            <header class="flex justify-between items-center mb-8 border-b border-gray-800 pb-4">
                <h1 class="text-3xl font-extrabold text-blue-500">IPTV Gatekeeper Panel (Cloud DB)</h1>
                <span class="text-sm text-gray-400">စနစ်စတင်ချိန် (မြန်မာစံတော်ချိန်)</span>
            </header>

            <!-- Control Box -->
            <div class="bg-gray-800 p-6 rounded-lg shadow-lg mb-8 flex flex-col md:flex-row gap-4 items-center justify-between">
                <div>
                    <h2 class="text-xl font-bold mb-2">အကောင့်အသစ် ထုတ်ပေးရန်</h2>
                    <p class="text-sm text-gray-400">၅ လုံးတွဲ Username နှင့် Password ကို အလိုအလျောက် ထုတ်လုပ်ပြီး Supabase ထဲတွင် သိမ်းဆည်းပါမည်။</p>
                </div>
                <form action="/admin/create" method="POST" class="flex gap-2">
                    <input type="hidden" name="key" value="{{ key }}">
                    <button type="submit" class="bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-6 rounded transition duration-200">
                        + Auto Generate Account
                    </button>
                </form>
            </div>

            <!-- Users Table -->
            <div class="bg-gray-800 rounded-lg shadow-lg overflow-hidden">
                <table class="w-full text-left border-collapse">
                    <thead>
                        <tr class="bg-gray-700 text-gray-200">
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
                        <tr class="border-b border-gray-700 hover:bg-gray-750">
                            <td class="p-4 font-mono font-bold text-yellow-400">{{ user.username }}</td>
                            <td class="p-4 font-mono">{{ user.password }}</td>
                            <td class="p-4">
                                <span class="px-2 py-1 rounded text-xs {{ 'bg-red-900 text-red-200' if user.locked_ip != 'No Lock' else 'bg-green-900 text-green-200' }}">
                                    {{ user.locked_ip }}
                                </span>
                            </td>
                            <td class="p-4 text-sm text-gray-300">{{ user.last_active }}</td>
                            <td class="p-4 text-sm text-gray-400">{{ user.created_at }}</td>
                            <td class="p-4 flex justify-center gap-2">
                                <form action="/admin/reset-ip" method="POST" class="inline">
                                    <input type="hidden" name="key" value="{{ key }}">
                                    <input type="hidden" name="username" value="{{ user.username }}">
                                    <button type="submit" class="bg-yellow-600 hover:bg-yellow-700 text-white text-xs font-bold py-2 px-3 rounded">
                                        Reset Device
                                    </button>
                                </form>
                                <form action="/admin/delete" method="POST" class="inline" onsubmit="return confirm('သေချာပါသလား။');">
                                    <input type="hidden" name="key" value="{{ key }}">
                                    <input type="hidden" name="username" value="{{ user.username }}">
                                    <button type="submit" class="bg-red-600 hover:bg-red-700 text-white text-xs font-bold py-2 px-3 rounded">
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
    </body>
    </html>
    """
    return render_template_string(html_template, users=formatted_users, key=key)

# အကောင့်အလိုအလျောက် ဖန်တီးပေးသည့် Route
@app.route("/admin/create", methods=["POST"])
def admin_create():
    key = request.form.get("key")
    if key != ADMIN_SECRET_KEY:
        return "Unauthorized", 403

    # ထပ်နေခြင်းမရှိသော ၅ လုံးတွဲ စာလုံးများ ထုတ်ပေးခြင်း
    while True:
        new_user = generate_random_string(5)
        # database ထဲတွင် ရှိပြီးသားလား တိုက်စစ်သည်
        if not get_user(new_user):
            break
            
    new_pass = generate_random_string(5)
    
    # Supabase ထဲသို့ အကောင့်သိမ်းဆည်းခြင်း
    create_user(new_user, new_pass)
    
    return render_template_string("""
    <script>
        alert("အကောင့်အသစ် ဖန်တီးပြီးပါပြီ။\\n\\nUsername: {{ u }}\\nPassword: {{ p }}");
        window.location.href = "/admin?key=" + "{{ key }}";
    </script>
    """, u=new_user, p=new_pass, key=key)

# Device IP Lock အား ပြန်လည်ရှင်းလင်းပေးသည့် Route (Reset Device)
@app.route("/admin/reset-ip", methods=["POST"])
def admin_reset_ip():
    key = request.form.get("key")
    username = request.form.get("username")
    if key != ADMIN_SECRET_KEY:
        return "Unauthorized", 403

    # Supabase ထဲတွင် IP Lock ကို ရှင်းလင်းသည်
    update_user_data(username, {
        "locked_ip": None,
        "last_active": None
    })
        
    return render_template_string("""
    <script>
        alert("Device Lock ကို အောင်မြင်စွာ ရှင်းလင်းပြီးပါပြီ။");
        window.location.href = "/admin?key=" + "{{ key }}";
    </script>
    """, key=key)

# အကောင့်ပယ်ဖျက်သည့် Route
@app.route("/admin/delete", methods=["POST"])
def admin_delete():
    key = request.form.get("key")
    username = request.form.get("username")
    if key != ADMIN_SECRET_KEY:
        return "Unauthorized", 403

    # Supabase ထဲမှ အကောင့်ကို ဖျက်ဆီးသည်
    delete_user(username)
        
    return render_template_string("""
    <script>
        window.location.href = "/admin?key=" + "{{ key }}";
    </script>
    """, key=key)


# ==================== PLAYLIST & STREAM GATEWAY ====================

@app.route("/m3u")
def get_m3u():
    """လုံခြုံစိတ်ချရသော Proxy Playlist စနစ်"""
    user = request.args.get("user")
    pass_word = request.args.get("pass")

    # Supabase Database ထဲမှ အသုံးပြုသူအား စစ်ဆေးခြင်း
    user_data = get_user(user) if user else None
    if not user_data or user_data["password"] != pass_word:
        return Response("ဝင်ရောက်ခွင့်မရှိပါ - Username သို့မဟုတ် Password မှားယွင်းနေပါသည်။", status=403)

    # 1-Device Limit အား စစ်ဆေးခြင်း
    allowed, msg = check_device_access(user, user_data)
    if not allowed:
        return Response(msg, status=403)

    print(f"[APPROVED ACCESS] {user} သည် Playlist အား ရယူနေပါသည်။ IP: {get_client_ip()}")
    
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
