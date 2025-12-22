"""
Скрипт для диагностики OAuth 400 ошибки GigaChat.
Запусти так: python oauth_debug.py
"""
import asyncio
import httpx
import uuid
import base64
import sys

print("\n" + "="*70)
print("GIGACHAT OAUTH DEBUG - ВЫБЕРИ СПОСОБ")
print("="*70)
print("1. Ввести CLIENT_ID и CLIENT_SECRET вручную")
print("2. Вставить готовую строку 'Authorization: Basic ...' из ЛК")
print()

choice = input("Выбери (1 или 2): ").strip()

if choice == "1":
    print("\n⚠️  ВАЖНО: При копировании из ЛК убедись, что нет пробелов!")
    print()
    CLIENT_ID = input("Вставь CLIENT_ID: ").strip()
    CLIENT_SECRET = input("Вставь CLIENT_SECRET: ").strip()

    if not CLIENT_ID or not CLIENT_SECRET:
        print("❌ CLIENT_ID или CLIENT_SECRET пусты!")
        sys.exit(1)

    print(f"\n📋 Диагностика введённых данных:")
    print(f"  CLIENT_ID length: {len(CLIENT_ID)}")
    print(f"  CLIENT_ID contains whitespace: {any(c.isspace() for c in CLIENT_ID)}")
    print(f"  CLIENT_SECRET length: {len(CLIENT_SECRET)}")
    print(f"  CLIENT_SECRET contains whitespace: {any(c.isspace() for c in CLIENT_SECRET)}")

    # Кодируем
    auth_string = f"{CLIENT_ID}:{CLIENT_SECRET}"
    print(f"  Combined string: {auth_string[:50]}...")

    auth_key = base64.b64encode(auth_string.encode()).decode()
    print(f"  Base64 encoded: {auth_key[:30]}...")

elif choice == "2":
    full_auth = input("Вставь полную строку (Authorization: Basic XxYyZz...): ").strip()

    if not full_auth.startswith("Authorization: Basic "):
        print("❌ Строка должна начинаться с 'Authorization: Basic '")
        sys.exit(1)

    auth_key = full_auth.replace("Authorization: Basic ", "").strip()
    print(f"\n✓ Извлечена auth_key: {auth_key[:30]}...")

else:
    print("❌ Неверный выбор")
    sys.exit(1)

# ===== ПРОВЕРКА auth_key =====
print("\n" + "="*70)
print("ПРОВЕРКА AUTH_KEY")
print("="*70)

auth_key = auth_key.strip()
print(f"✓ Length: {len(auth_key)}")
print(f"✓ Contains only valid Base64 chars: {all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=' for c in auth_key)}")

try:
    decoded = base64.b64decode(auth_key).decode('utf-8')
    print(f"✓ Decoded successfully: {decoded[:50]}...")
    if ':' in decoded:
        print(f"✓ Contains ':' separator: YES")
        client_id, client_secret = decoded.split(':', 1)
        print(f"  → CLIENT_ID: {client_id[:30]}...")
        print(f"  → CLIENT_SECRET: {client_secret[:30]}...")
    else:
        print(f"❌ NO ':' separator found! This is the problem!")
        print(f"   Decoded value is: {decoded}")
except Exception as e:
    print(f"❌ Failed to decode Base64: {e}")
    sys.exit(1)

# ===== SCOPE =====
SCOPE = input("\nВведи SCOPE [GIGACHAT_API_B2B]: ").strip() or "GIGACHAT_API_B2B"
print(f"✓ scope: {SCOPE}")

# ===== RqUID =====
rq_uid = str(uuid.uuid4())
print(f"✓ rq_uid: {rq_uid}")

# ===== HEADERS =====
headers = {
    "Authorization": f"Basic {auth_key}",
    "RqUID": rq_uid,
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept": "application/json",
}

payload = f"scope={SCOPE}"

print("\n" + "="*70)
print("REQUEST DETAILS")
print("="*70)
print(f"URL: https://ngw.devices.sberbank.ru:9443/api/v2/oauth")
print(f"\nHeaders:")
for k, v in headers.items():
    if k == "Authorization":
        print(f"  {k}: {v[:35]}...")
    else:
        print(f"  {k}: {v}")
print(f"\nBody:")
print(f"  {payload}")

# ===== ОТПРАВКА =====
async def test():
    print("\n" + "="*70)
    print("SENDING REQUEST...")
    print("="*70 + "\n")

    async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
        response = await client.post(
            "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
            headers=headers,
            content=payload,
        )

        print(f"Status Code: {response.status_code}\n")
        print(f"Response Body:")
        print(response.text)

        if response.status_code == 200:
            try:
                data = response.json()
                print(f"\n✅ ✅ ✅ SUCCESS! ✅ ✅ ✅")
                print(f"Access Token (first 30 chars): {data.get('access_token', '')[:30]}...")
                print(f"Expires In: {data.get('expires_in', 'N/A')} seconds")

                # Покажи как использовать в коннекторе
                print(f"\n" + "="*70)
                print("ИСПОЛЬЗУЙ В КОННЕКТОРЕ:")
                print("="*70)
                print(f"connector = GigaChatConnector(")
                print(f"    get_logger=get_logger,")
                print(f"    auth_key='{auth_key}',")
                print(f"    model='GigaChat-Max',")
                print(f"    scope='{SCOPE}',")
                print(f")")

                return True
            except Exception as e:
                print(f"\n❌ Got 200 but failed to parse JSON: {e}")
                return False
        else:
            print(f"\n❌ ERROR {response.status_code}")
            if response.status_code == 400:
                print("\n🔍 РЕШЕНИЕ: Твой auth_key всё ещё неправильный.")
                print("   Попробуй способ #2 — скопируй готовую строку из ЛК.")
            elif response.status_code == 401:
                print("\n🔍 РЕШЕНИЕ: CLIENT_ID или CLIENT_SECRET неверные.")
                print("   Проверь их в личном кабинете https://developers.sber.ru")
            return False

success = asyncio.run(test())
sys.exit(0 if success else 1)