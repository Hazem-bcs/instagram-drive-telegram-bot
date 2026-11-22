# Instagram → Google Drive | Telegram Bot

بوت تيليغرام يحفظ فيديوهات Instagram العامة في مجلد Google Drive ويعيد رابط الفيديو تلقائياً، **بدون VPS أو حاسوب يعمل دائماً**.

**Infrastructure:** Telegram Bot → Cloudflare Worker (webhook) → encrypted GitHub Actions `workflow_dispatch` → Python / yt-dlp → Google Drive → Telegram.

**التكلفة:** يستهدف الطبقات المجانية. GitHub Actions باستخدام standard runner مجاني في المستودعات العامة، وCloudflare Workers له حصة مجانية، ومساحة Drive محدودة بحصة حسابك.

> ⚠️ إنستغرام قد يحظر التنزيل أو يتطلب تسجيل الدخول. التطبيق مخصص للمقاطع العامة التي لديك الحق في حفظها ومشاركتها، وليس لتجاوز صلاحيات المحتوى الخاص. مجلد Drive والفيديوهات **عامة للقراءة**: أي شخص معه الرابط يمكنه المشاهدة.

## 1. أنشئ المستودع العام

أنشئ مستودعاً عاماً على GitHub باسم `instagram-drive-telegram-bot` مع فرع افتراضي `main`، وارفع إليه ملفات هذا المشروع **من دون** ملفات `client_secret.json` أو `.secrets/` أو `.env`.

إذا اختلف اسم المستودع عن المثال، غيّر `GITHUB_REPO` في ملف `wrangler.toml`.

## 2. إنشاء بوت Telegram

**بوت هذا المشروع:** [@hazemdownloaderbot](https://t.me/hazemdownloaderbot).

على جهاز ROG تم نشر Cloudflare Worker وتجهيز مفتاح التشفير. لإكمال تفعيل البوت دون لصق التوكن في المحادثة أو سطر الأوامر، أرسل `/start` إلى البوت، ثم شغّل هذا الأمر من Terminal على ROG:

```bash
cd /home/hazem/projects/instagram-drive-telegram-bot
python3 scripts/activate_telegram.py
```

سيطلب البرنامج توكن BotFather بطريقة مخفية، ويعرض معرف تيليغرام الرقمي لتأكيده، ويضع التوكن في Cloudflare/GitHub Secrets ثم يسجل Webhook. لا ينسخ التوكن إلى GitHub العام. يلزم إعداد `GITHUB_TOKEN` و`GOOGLE_OAUTH_JSON` أدناه لتمكين تنزيل الفيديو.

**إذا أكمل `activate_telegram.py` ضبط الأسرار ثم فشل عند `setWebhook`، لا تكرر الإعداد كله.** استخدم البرنامج التالي؛ سيطلب توكن BotFather محلياً بشكل مخفي، يعيد محاولة الاتصال، ثم يتأكد من تسجيل عنوان الـWebhook:

```bash
cd /home/hazem/projects/instagram-drive-telegram-bot
python3 scripts/finish_webhook.py
```

إذا رد Telegram بـ`bad webhook: Failed to resolve host`، يعيد هذا السكربت التسجيل باستخدام عنوان IPv4 الذي يحلّه الجهاز لخدمة Cloudflare مع خيار Telegram الرسمي `ip_address`، دون تغيير رابط HTTPS. بعد نجاحه أرسل `/start` إلى البوت للتحقق من الرد. يستلزم تنزيل الفيديو الفعلي إعداد `GITHUB_TOKEN` و`GOOGLE_OAUTH_JSON`.

**لإعداد بوت مختلف بدلاً من البوت الحالي:**

- افتح https://t.me/BotFather وأرسل `/newbot`، واحتفظ بالتوكن سراً.
- افتح محادثة البوت الجديد وأرسل `/start`.
- لتحديد معرفك الرقمي (قبل تسجيل webhook) نفّذ محلياً:

  ```bash
  export TELEGRAM_BOT_TOKEN='TOKEN_FROM_BOTFATHER'
  python scripts/get_chat_id.py
  ```

  في PowerShell استخدم `$env:TELEGRAM_BOT_TOKEN="..."` بدلاً من `export`.
  يجب أن يكون `Telegram user ID` مطابقاً لمعرف المحادثة الخاصة.

## 3. ربط Google Drive مرة واحدة (OAuth)

1. افتح https://console.cloud.google.com/ وأنشئ مشروعاً، وفعّل **Google Drive API**.
2. في **Google Auth Platform / OAuth consent screen** اختر إعداد التطبيق للاستخدام الشخصي. استخدم نطاق `https://www.googleapis.com/auth/drive.file` فقط؛ وهو وصول محدود للملفات التي ينشئها التطبيق أو يفتحها بموافقتك.
3. أنشئ **OAuth Client ID** من نوع **Desktop app**. نزّل JSON إلى جذر المستودع المحلي باسم `client_secret.json` (موجود في `.gitignore`).
4. إذا بقي التطبيق في وضع *Testing* مع مستخدمين خارجيين، قد تنتهي صلاحية refresh token بعد 7 أيام؛ لتشغيل دائم انشر التطبيق بوضع *Production* عندما تسمح إعدادات Google بذلك.
5. على جهازك الشخصي نفّذ:

   ```bash
   python -m pip install -r requirements.txt
   python scripts/google_auth.py
   ```

6. سيُفتح متصفح Google لتوافق بنفسك. بعدها يتولد `.secrets/google_oauth.json` محلياً؛ لا ترفعه ولا ترسله لأحد. انسخ محتواه كاملاً إلى GitHub Actions secret باسم `GOOGLE_OAUTH_JSON` (Settings → Secrets and variables → Actions → New repository secret).

سيُنشئ البوت مجلد `Instagram Videos` في **My Drive** تلقائياً عند أول عملية. سيمنح المجلد وملفات الفيديو صلاحية `anyone: reader` لمشاركة الروابط.

## 4. GitHub Secrets

داخل المستودع في `Settings → Secrets and variables → Actions` أضف:

| Name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token from BotFather |
| `GOOGLE_OAUTH_JSON` | Entire local `.secrets/google_oauth.json` JSON |
| `PIPELINE_KEY` | Key generated in step 5 |

لا تضع أي قيمة سرية داخل الكود، README، Issues، أو محادثة عامة.

## 5. Cloudflare Worker

من جهازك المحلي:

```bash
python scripts/create_keys.py
npm install
npx wrangler login
npx wrangler deploy
```

احفظ المفتاح `PIPELINE_KEY` نفسه في **GitHub Actions secret** وفي **Cloudflare Worker secret**؛ سيشفر Cloudflare رابط إنستغرام ومعرف تيليغرام قبل تسليمه إلى GitHub Actions (المستودع عام). مفتاح `TELEGRAM_WEBHOOK_SECRET` يبقى في Cloudflare وإعداد webhook فقط.

أدخل أسرار Cloudflare بأوامر متكررة؛ كل أمر يطلب إدخال القيمة بصورة منفصلة:

```bash
npx wrangler secret put TELEGRAM_BOT_TOKEN
npx wrangler secret put TELEGRAM_ALLOWED_USER_ID
npx wrangler secret put TELEGRAM_WEBHOOK_SECRET
npx wrangler secret put PIPELINE_KEY
npx wrangler secret put GITHUB_TOKEN
```

- `TELEGRAM_ALLOWED_USER_ID`: معرفك الرقمي من الخطوة 2.
- `GITHUB_TOKEN`: GitHub **fine-grained PAT** محدود فقط لهذا المستودع مع صلاحية **Actions: Read and write**، لإنشاء `workflow_dispatch` عبر API. أنشئه من GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens. سيحتاج تجديداً إذا انتهت صلاحيته.
- `PIPELINE_KEY`: 32-byte base64url من `scripts/create_keys.py`، نفسه لدى GitHub Actions.
- `TELEGRAM_WEBHOOK_SECRET`: القيمة الأخرى الناتجة من نفس البرنامج.

بعد كتابة الأسرار، يصبح عنوان الخدمة على الأغلب `https://instagram-drive-telegram-bot.<SUBDOMAIN>.workers.dev` حسب مخرجات `wrangler deploy`.

> تأكد أن الإعدادات العادية في `wrangler.toml` تحتوي اسم حساب GitHub والمستودع الصحيحين. لا تضع التوكن في `wrangler.toml`.

## 6. تفعيل Telegram webhook

من جهازك نفسه، عيّن محلياً متغيري `TELEGRAM_BOT_TOKEN` و `TELEGRAM_WEBHOOK_SECRET` من القيم السابقة، ثم:

```bash
python scripts/set_webhook.py https://instagram-drive-telegram-bot.<SUBDOMAIN>.workers.dev
```

سجّل عنوان Cloudflare Worker الحقيقي الذي ظهر بعد deploy. عند نجاح التسجيل، أرسل للبوت `/start`، ثم رابط Reel عام.

## 7. تجربة وتشخيص

- `https://YOUR-WORKER.workers.dev/health` يجب أن يظهر `ok`.
- إذا ردّ البوت «استلمت الرابط»، افتح GitHub → Actions → Transfer Instagram video to Google Drive لمتابعة حالة المهمة.
- عند اكتمال المهمة سترى رابط الفيديو ورابط مجلد Drive في تيليغرام.
- إن كان الفيديو خاصاً أو تغيّرت حماية Instagram فقد تفشل عملية التنزيل؛ لا يدعم المشروع تسجيل الدخول إلى حسابات Instagram الخاصة.
- لا ترسل عشرات الروابط دفعة واحدة؛ الحدود المجانية والحصص وإجراءات مكافحة إساءة الاستخدام قد تحد من المهام.

## Tests

```bash
python -m pip install 'cryptography>=44,<47'
python -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/worker.test.mjs
```

### Security

- مستودع عام، لكن لا يحتوي مفاتيح أو رموز وصول.
- تمرّر Cloudflare إلى GitHub مدخلات مشفرة بـ AES-256-GCM؛ لا يظهر رابط الفيديو الخام في مدخلات التشغيل العامة.
- Cloudflare يرفض أي رسالة من مستخدم Telegram مختلف عن معرفك المحدد، ويرفض webhook بلا رمز تحقّق.
- Google OAuth يستخدم `drive.file` بدلاً من منح البوت صلاحية قراءة كل ملفات Drive.
- ملفات الفيديو والمجلد عامة للقراءة، لأن هذا هو السلوك المطلوب. استخدم `PUBLIC_FOLDER=false` في الـWorkflow وعدّل مشاركة الملفات إن أردت لاحقاً خصوصية أكبر.
- لا توجد ملفات فيديو محفوظة في GitHub؛ التنزيل مؤقت على runner فقط.
