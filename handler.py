# lambda/handler.py
import os
import time
import json
import boto3
import requests
import re
from datetime import datetime

# Environment / config
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
REGION = os.environ.get("REGION", "us-east-1")
USER_TABLE = os.environ.get("USER_TABLE", "user_data")
META_TABLE = os.environ.get("META_TABLE", "bot_meta")
USER_MESSAGES_TABLE = os.environ.get("USER_MESSAGES_TABLE", "user_messages")
KEYWORD_INDEX_TABLE = os.environ.get("KEYWORD_INDEX_TABLE", "keyword_index")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# AWS resources
dynamodb = boto3.resource("dynamodb", region_name=REGION)
user_table = dynamodb.Table(USER_TABLE)
meta_table = dynamodb.Table(META_TABLE)
user_messages_table = dynamodb.Table(USER_MESSAGES_TABLE)
keyword_index_table = dynamodb.Table(KEYWORD_INDEX_TABLE)

# Simple stopword set for tokenization
STOPWORDS = {
    "the","a","an","and","is","in","on","at","to","for","of","with","that","this","it",
    "as","are","was","be","by"
}

# ---------- Utilities ----------
def get_last_offset():
    try:
        resp = meta_table.get_item(Key={"meta_key": "update_offset"})
        if "Item" in resp:
            return int(resp["Item"].get("value", "0"))
    except Exception as ex:
        print("get_last_offset error:", ex)
    return 0


def set_last_offset(offset):
    try:
        meta_table.put_item(Item={"meta_key": "update_offset", "value": str(offset)})
    except Exception as ex:
        print("set_last_offset error:", ex)


def send_message(chat_id, text):
    if not BOT_TOKEN:
        print("BOT_TOKEN not set, cannot send message")
        return
    url = f"{TELEGRAM_API}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print("Failed to send message:", e)


# ---------- Simple key/value handlers (existing) ----------
def handle_save(chat_id, parts):
    if len(parts) < 3:
        return "Usage: /save <key> <value>"
    key = parts[1]
    value = " ".join(parts[2:])
    try:
        user_table.put_item(
            Item={
                "user_id": str(chat_id),
                "item_key": key,
                "value": value,
                "created_at": int(time.time())
            }
        )
    except Exception as e:
        print("handle_save error:", e)
        return "Failed to save."
    return f"Saved key '{key}'."

def handle_get(chat_id, parts):
    if len(parts) < 2:
        return "Usage: /get <key>"
    key = parts[1]
    try:
        resp = user_table.get_item(Key={"user_id": str(chat_id), "item_key": key})
        if "Item" in resp:
            return f"{key} = {resp['Item'].get('value')}"
    except Exception as e:
        print("handle_get error:", e)
    return f"No value found for key '{key}'."

def handle_list(chat_id):
    try:
        resp = user_table.query(KeyConditionExpression=boto3.dynamodb.conditions.Key("user_id").eq(str(chat_id)))
        items = resp.get("Items", [])
        if not items:
            return "You have no saved keys."
        keys = [it["item_key"] for it in items]
        return "Your keys:\n" + "\n".join(keys)
    except Exception as e:
        print("handle_list error:", e)
        return "Failed to list keys."


# ---------- Message store + index ----------
def normalize_text(text):
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    tokens = [t for t in text.split() if t and t not in STOPWORDS and len(t) > 2]
    return tokens

def save_message_to_dynamodb(chat_id, update_id, message_id, text, raw=None, message_type="text"):
    """
    Stores the message in user_messages and populates a simple keyword_index.
    Returns saved item dict.
    """
    created_at = int(time.time())
    pk = str(chat_id)
    msg_id = f"{chat_id}:{message_id}"
    item = {
        "user_id": pk,
        "created_at": created_at,
        "message_id": msg_id,
        "update_id": int(update_id) if update_id is not None else 0,
        "message_type": message_type,
        "text": text or "",
    }
    if raw is not None:
        item["raw"] = json.dumps(raw)

    try:
        user_messages_table.put_item(Item=item)
    except Exception as e:
        print("put_item user_messages error:", e)
        raise

    # build keywords into keyword_index
    if text:
        tokens = normalize_text(text)
        seen = set()
        for tok in tokens:
            if tok in seen:
                continue
            seen.add(tok)
            user_created = f"{pk}#{created_at:020d}"
            snippet = text if len(text) <= 200 else text[:200]
            try:
                keyword_index_table.put_item(Item={
                    "keyword": tok,
                    "user_created": user_created,
                    "message_id": msg_id,
                    "user_id": pk,
                    "created_at": created_at,
                    "snippet": snippet
                })
            except Exception as e:
                # index writes should not block the main flow; log and continue
                print("keyword_index put_item error for", tok, e)
    return item


# ---------- Retrieval handlers ----------
def handle_history(chat_id, limit=10):
    try:
        resp = user_messages_table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("user_id").eq(str(chat_id)),
            Limit=int(limit),
            ScanIndexForward=False  # newest first
        )
        items = resp.get("Items", [])
        if not items:
            return "No history found."
        out_lines = []
        for it in items:
            ts = datetime.utcfromtimestamp(int(it["created_at"])).strftime("%Y-%m-%d %H:%M:%S")
            out_lines.append(f"[{it['message_id']}] {ts} — {it.get('text','')[:200]}")
        return "\n".join(out_lines)
    except Exception as e:
        print("handle_history error:", e)
        return "Failed to fetch history."

def handle_getid(chat_id, parts):
    if len(parts) < 2:
        return "Usage: /getid <message_id>"
    msgid = parts[1]
    try:
        resp = user_messages_table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("user_id").eq(str(chat_id)),
            FilterExpression=boto3.dynamodb.conditions.Attr("message_id").eq(msgid)
        )
        items = resp.get("Items", [])
        if not items:
            return f"No message found with id {msgid}"
        it = items[0]
        ts = datetime.utcfromtimestamp(int(it["created_at"])).strftime("%Y-%m-%d %H:%M:%S")
        return f"[{it['message_id']}] {ts}\n{it.get('text','')}"
    except Exception as e:
        print("handle_getid error:", e)
        return "Failed to fetch message by id."

def handle_search(chat_id, parts, limit=10):
    if len(parts) < 2:
        return "Usage: /search <keyword>"
    keyword = parts[1].lower()
    try:
        resp = keyword_index_table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("keyword").eq(keyword),
            Limit=int(limit),
            ScanIndexForward=False
        )
        items = resp.get("Items", [])
        if not items:
            return f"No results for '{keyword}'"
        user_items = [it for it in items if it.get("user_id") == str(chat_id)]
        if not user_items:
            return f"No results for '{keyword}' in your messages."
        out_lines = []
        for it in user_items[:limit]:
            ts = datetime.utcfromtimestamp(int(it["created_at"])).strftime("%Y-%m-%d %H:%M:%S")
            out_lines.append(f"[{it['message_id']}] {ts} — {it.get('snippet','')[:200]}")
        return "\n".join(out_lines)
    except Exception as e:
        print("handle_search error:", e)
        return "Search failed."


# ---------- message processing ----------
def process_message(msg):
    # msg is the full update dict from Telegram
    chat_obj = msg.get("message") or msg.get("edited_message") or {}
    if not chat_obj:
        return
    chat_id = chat_obj["chat"]["id"]
    text = chat_obj.get("text", "")
    first_name = chat_obj.get("from", {}).get("first_name", "")

    # Save message to DB (non-blocking-ish)
    try:
        update_id = msg.get("update_id")
        message_id = chat_obj.get("message_id")
        # only save if we have message_id
        if message_id is not None:
            saved = save_message_to_dynamodb(chat_id, update_id, message_id, text, raw=chat_obj)
            print("Saved message:", saved.get("message_id"))
    except Exception as e:
        print("Failed to save message:", str(e))

    if not text:
        return

    # command handling
    if not text.startswith("/"):
        send_message(chat_id, "I only respond to commands. Send /help to see commands.")
        return

    parts = text.strip().split()
    cmd = parts[0].lower()

    if cmd == "/start":
        send_message(chat_id, f"Welcome, {first_name}! 🤖\nUse /help to see what I can do.")
    elif cmd == "/hello":
        send_message(chat_id, f"Hello, {first_name} 👋")
    elif cmd == "/help":
        send_message(chat_id,
            "/hello - greet\n"
            "/help - this message\n"
            "/echo <text> - echo back\n"
            "/save <key> <value> - save your data\n"
            "/get <key> - retrieve your value\n"
            "/list - list saved keys\n"
            "/history [n] - last n messages\n"
            "/getid <message_id> - fetch specific message\n"
            "/search <keyword> - search your messages\n"
        )
    elif cmd == "/echo":
        if len(parts) > 1:
            send_message(chat_id, " ".join(parts[1:]))
        else:
            send_message(chat_id, "Usage: /echo <text>")
    elif cmd == "/save":
        reply = handle_save(chat_id, parts)
        send_message(chat_id, reply)
    elif cmd == "/get":
        reply = handle_get(chat_id, parts)
        send_message(chat_id, reply)
    elif cmd == "/list":
        reply = handle_list(chat_id)
        send_message(chat_id, reply)
    elif cmd == "/history":
        n = 10
        if len(parts) > 1 and parts[1].isdigit():
            n = int(parts[1])
        send_message(chat_id, handle_history(chat_id, limit=n))
    elif cmd == "/getid":
        send_message(chat_id, handle_getid(chat_id, parts))
    elif cmd == "/search":
        send_message(chat_id, handle_search(chat_id, parts))
    else:
        send_message(chat_id, f"Unknown command {cmd}. Use /help")


# ---------- lambda entry ----------
def lambda_handler(event, context):
    # allow disabling poller during debug
    if os.environ.get("ENABLE_POLLER", "true").lower() == "false":
        return {"status": "ok", "debug": "poller disabled"}

    last_offset = get_last_offset()
    params = {"timeout": 5}
    if last_offset:
        params["offset"] = last_offset + 1

    if not BOT_TOKEN:
        print("BOT_TOKEN not configured")
        return {"status": "error", "error": "BOT_TOKEN not configured"}

    updates_url = f"{TELEGRAM_API}/getUpdates"
    try:
        resp = requests.get(updates_url, params=params, timeout=(2, 8))
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print("Failed to fetch updates:", e)
        return {"status": "error", "error": str(e)}

    updates = data.get("result", [])
    max_update_id = last_offset

    for upd in updates:
        update_id = upd.get("update_id")
        if update_id is None:
            continue
        try:
            process_message(upd)
        except Exception as e:
            print("Error processing update:", e)
        if update_id > max_update_id:
            max_update_id = update_id

    if max_update_id > last_offset:
        set_last_offset(max_update_id)

    return {"status": "ok", "processed": len(updates)}
