Supabase SQL Database တည်ဆောက်ခြင်းနှင့် RLS ပိတ်ခြင်း လမ်းညွှန်Supabase ၏ လုံခြုံရေးအရ ပိတ်ဆို့မှု (RLS Block) ကို ကျော်ဖြတ်ပြီး အကောင့်များ စနစ်တကျ ပြန်လည်ပေါ်လာစေရန်အတွက် ဤ SQL Code အား သင့် Supabase SQL Editor တွင် မဖြစ်မနေ Run ပေးရန် လိုအပ်ပါသည်။လုပ်ဆောင်ရန် အဆင့်များ -Supabase Dashboard သို့ ဝင်ရောက်ပါ။သင့် Project ထဲသို့ သွားပြီး ဘယ်ဘက် Menu ရှိ SQL Editor ကို နှိပ်ပါ။New Query ကို နှိပ်ပါ။အောက်ဖော်ပြပါ SQL ကုဒ်များအားလုံးကို ကော်ပီကူးယူပြီး ထည့်သွင်း (Paste) လိုက်ပါ --- ၁။ ရှိပြီးသား Table ဟောင်းများရှိပါက သန့်ရှင်းသွားစေရန် ဖျက်ပစ်ပါမည်
DROP TABLE IF EXISTS iptv_users;

-- ၂။ အကောင့်များ သိမ်းဆည်းရန် Table အသစ် ပြန်လည်ဆောက်လုပ်ခြင်း
CREATE TABLE iptv_users (
    username text PRIMARY KEY,
    password text NOT NULL,
    locked_ip text,
    last_active text,
    created_at text NOT NULL
);

-- ၃။ ⚠️ [အရေးကြီးဆုံးအဆင့်] Row Level Security (RLS) အား ပိတ်ပစ်ခြင်း
-- ဤသို့ပြုလုပ်ခြင်းဖြင့် Render ရှိ Flask App က အကောင့်များကို လွတ်လပ်စွာ ဖတ်/ရေး ပြုလုပ်ခွင့်ရရှိသွားမည် ဖြစ်သည်။
ALTER TABLE iptv_users DISABLE ROW LEVEL SECURITY;

-- ၄။ စမ်းသပ်ရန် အခြေခံအကောင့်တစ်ခု ထည့်သွင်းထားခြင်း
INSERT INTO iptv_users (username, password, locked_ip, last_active, created_at)
VALUES ('nyi12', '99999', NULL, NULL, '2026-06-05T12:30:00Z');
ညာဘက်အောက်နားရှိ Run ကို နှိပ်လိုက်ပါ။အောင်မြင်စွာ Run ပြီးပါက သင့် Admin Panel ထဲတွင် အခြေခံစမ်းသပ်အကောင့်ဖြစ်သော nyi12 (Password: 99999) လေး ချက်ချင်း ပြန်လည်ပေါ်လာရမည် ဖြစ်ပါသည်။
