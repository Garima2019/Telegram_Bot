import json
import os
import urllib.request
import urllib.parse
from datetime import datetime, timezone
import urllib.error
import boto3
from boto3.dynamodb.conditions import Key

TELEGRAM_API_BASE = "https://api.telegram.org/bot"

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
DDB_TABLE_NAME = os.environ.get("DDB_TABLE_NAME")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(DDB_TABLE_NAME)


# --------- TELEGRAM HELPERS ---------


def telegram_request(method: str, payload: dict):
    """Low level helper to call Telegram Bot API."""
    url = f"{TELEGRAM_API_BASE}{TELEGRAM_BOT_TOKEN}/{method}"

    encoded = {
        k: json.dumps(v) if isinstance(v, (dict, list)) else v
        for k, v in payload.items()
        if v is not None
    }

    data = urllib.parse.urlencode(encoded).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req) as resp:
        body = resp.read()
        try:
            return json.loads(body.decode("utf-8"))
        except Exception:
            return None


def send_message(chat_id: int, text: str):
    payload = {
        "chat_id": chat_id,
        "text": text,
    }
    return telegram_request("sendMessage", payload)


def answer_callback_query(callback_query_id: str, text: str | None = None):
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    return telegram_request("answerCallbackQuery", payload)


# --------- DYNAMODB HELPERS ---------


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Key/value storage (for /save, /get, /list)
def save_key_value(user_id: int, key: str, value: str):
    item = {
        "user_id": str(user_id),
        "sort_key": f"kv#{key}",
        "value": value,
        "updated_at": now_iso(),
    }
    table.put_item(Item=item)


def get_key_value(user_id: int, key: str):
    resp = table.get_item(
        Key={
            "user_id": str(user_id),
            "sort_key": f"kv#{key}",
        }
    )
    return resp.get("Item")


def list_keys(user_id: int):
    resp = table.query(
        KeyConditionExpression=Key("user_id").eq(str(user_id))
        & Key("sort_key").begins_with("kv#"),
        ScanIndexForward=True,
    )
    items = resp.get("Items", [])
    keys = [item["sort_key"][3:] for item in items]
    return keys


# Message archive (for /getid, /search, /latest, /history, /summarize, /stats)


def save_message_record(user_id: int, message_id: int, text: str):
    item = {
        "user_id": str(user_id),
        "sort_key": f"msg#{message_id}",
        "message_id": message_id,
        "text": text,
        "created_at": now_iso(),
    }
    table.put_item(Item=item)


def get_message_by_id(user_id: int, message_id: int):
    resp = table.get_item(
        Key={
            "user_id": str(user_id),
            "sort_key": f"msg#{message_id}",
        }
    )
    return resp.get("Item")


def get_all_messages(user_id: int):
    resp = table.query(
        KeyConditionExpression=Key("user_id").eq(str(user_id))
        & Key("sort_key").begins_with("msg#"),
        ScanIndexForward=True,
    )
    return resp.get("Items", [])


def get_last_messages(user_id: int, limit: int = 5):
    items = get_all_messages(user_id)
    items_sorted = sorted(
        items, key=lambda x: x.get("created_at", ""), reverse=True
    )
    return items_sorted[:limit]


def search_messages(user_id: int, keyword: str, limit: int = 20):
    items = get_all_messages(user_id)
    keyword_lower = keyword.lower()
    matches = [
        item
        for item in items
        if "text" in item and keyword_lower in item["text"].lower()
    ]
    matches_sorted = sorted(
        matches, key=lambda x: x.get("created_at", ""), reverse=True
    )
    return matches_sorted[:limit]


def get_last_notes(user_id: int, limit: int = 10):
    """
    Return the last N non-command messages (user's 'notes'),
    sorted from newest to oldest.
    """
    items = get_all_messages(user_id)
    notes = [
        item
        for item in items
        if isinstance(item.get("text"), str)
        and not item["text"].strip().startswith("/")
    ]
    notes_sorted = sorted(
        notes, key=lambda x: x.get("created_at", ""), reverse=True
    )
    return notes_sorted[:limit]


# --------- OPENAI / AI HELPER ---------


def ask_ai(question: str) -> str:
    """Call OpenAI Chat Completions API."""
    if not OPENAI_API_KEY:
        return "AI is not configured yet. Ask the admin to set OPENAI_API_KEY in Lambda."

    url = "https://api.openai.com/v1/chat/completions"
    payload = {
        "model": "gpt-4.1-mini",
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant answering concisely.",
            },
            {"role": "user", "content": question},
        ],
        "max_tokens": 300,
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {OPENAI_API_KEY}")

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))
        return resp_data["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        # Read error body for logging
        err_body = e.read().decode("utf-8", errors="ignore")
        print("HTTPError from OpenAI:", e.code, err_body)

        if e.code == 429:
            return (
                "I'm hitting the OpenAI rate/usage limit right now.\n"
                "Please try again in a bit, or increase your OpenAI quota."
            )
        else:
            return "OpenAI returned an error. Please try again later."
    except Exception as e:
        print("Error calling OpenAI:", repr(e))
        return "Sorry, I could not get an AI reply right now."


# --------- ANALYTICS / STATS HELPERS ---------


def compute_personal_stats(user_id: int) -> str:
    items = get_all_messages(user_id)
    if not items:
        return "No messages stored yet, so I can't compute stats."

    total_msgs = len(items)

    # Parse timestamps
    created_times = []
    for item in items:
        ts = item.get("created_at")
        if not ts:
            continue
        try:
            created_times.append(datetime.fromisoformat(ts))
        except Exception:
            continue

    now = datetime.now(timezone.utc)

    msgs_last_7_days = 0
    notes_count = 0
    total_chars_notes = 0

    command_counts: dict[str, int] = {}

    for item in items:
        text = (item.get("text") or "").strip()
        ts_str = item.get("created_at")
        dt = None
        if ts_str:
            try:
                dt = datetime.fromisoformat(ts_str)
            except Exception:
                dt = None

        # last 7 days
        if dt is not None:
            delta = now - dt
            if delta.days < 7:
                msgs_last_7_days += 1

        # notes vs commands
        if text.startswith("/"):
            cmd = text.split(maxsplit=1)[0]
            command_counts[cmd] = command_counts.get(cmd, 0) + 1
        else:
            notes_count += 1
            total_chars_notes += len(text)

    avg_note_length = 0
    if notes_count > 0:
        avg_note_length = round(total_chars_notes / notes_count, 1)

    first_ts = min(created_times) if created_times else None
    last_ts = max(created_times) if created_times else None

    most_used_cmd = None
    most_used_cmd_count = 0
    if command_counts:
        most_used_cmd, most_used_cmd_count = max(
            command_counts.items(), key=lambda kv: kv[1]
        )

    lines = []
    lines.append("📊 *Your Personal Stats*")
    lines.append("")
    lines.append(f"• Total stored messages: {total_msgs}")
    lines.append(f"• Messages in last 7 days: {msgs_last_7_days}")
    lines.append(f"• Notes (non-command messages): {notes_count}")
    if notes_count > 0:
        lines.append(f"• Avg note length: {avg_note_length} characters")

    if first_ts and last_ts:
        lines.append(
            f"• First stored message: {first_ts.strftime('%Y-%m-%d %H:%M UTC')}"
        )
        lines.append(
            f"• Latest stored message: {last_ts.strftime('%Y-%m-%d %H:%M UTC')}"
        )

    if most_used_cmd:
        lines.append(
            f"• Most used command: {most_used_cmd} ({most_used_cmd_count} times)"
        )

    return "\n".join(lines)


def summarize_last_notes(user_id: int, limit: int = 10) -> str:
    notes = get_last_notes(user_id, limit=limit)
    if not notes:
        return "I couldn't find any notes to summarise (non-command messages)."

    # Sort oldest -> newest for a coherent narrative
    notes_sorted = sorted(notes, key=lambda x: x.get("created_at", ""))

    parts = []
    for idx, item in enumerate(notes_sorted, start=1):
        ts = item.get("created_at", "")
        txt = item.get("text", "").strip()
        if len(txt) > 400:
            txt = txt[:397] + "..."
        parts.append(f"{idx}. [{ts}] {txt}")

    joined_notes = "\n".join(parts)

    prompt = (
        "You are an assistant helping a user with their personal notes.\n"
        "Below are the user's latest notes (messages that are not commands).\n"
        "Please provide a concise summary in 5–7 bullet points, capturing:\n"
        "- main themes/topics\n"
        "- any tasks or follow-ups implied\n"
        "- overall sentiment if relevant.\n\n"
        "User notes:\n"
        f"{joined_notes}"
    )

    return ask_ai(prompt)


# --------- COMMAND HELPERS ---------


def help_text() -> str:
    return (
        "Here’s what I can do:\n\n"
        "/hello - greet\n"
        "/help - this message\n"
        "/echo <text> - echo back\n"
        "/save <key> <value> - save your data\n"
        "/get <key> - retrieve your value\n"
        "/list - list saved keys\n"
        "/getid <message_id> - fetch specific message\n"
        "/search <keyword> - search your messages\n"
        "/latest - show your latest note/message\n"
        "/history - show your last 5 notes/messages\n"
        "/ask <question> - get an AI answer\n"
        "/summarize - AI summary of your last 10 notes\n"
        "/stats - personal analytics based on your messages\n"
        "/menu - show this menu again\n"
    )


# --------- COMMAND HANDLING ---------


def handle_text_message(chat_id: int, message_id: int, text: str, first_name: str | None):
    text = text.strip()

    # /start
    if text.startswith("/start"):
        username = first_name or "there"
        send_message(chat_id, f"Welcome, {username}! 😉")
        send_message(chat_id, help_text())
        return

    # /hello
    if text.startswith("/hello"):
        send_message(chat_id, "👋 Hello! How can I help you today?")
        return

    # /help
    if text.startswith("/help"):
        send_message(chat_id, help_text())
        return

    # /echo
    if text.startswith("/echo"):
        parts = text.split(maxsplit=1)
        if len(parts) == 1:
            send_message(chat_id, "Usage: /echo <text>")
        else:
            send_message(chat_id, parts[1])
        return

    # /save <key> <value>
    if text.startswith("/save"):
        parts = text.split(maxsplit=3)
        if len(parts) < 3:
            send_message(
                chat_id,
                "Usage: /save <key> <value>\nExample: /save email user@example.com",
            )
            return
        key = parts[1]
        value = parts[2] if len(parts) == 3 else " ".join(parts[2:])
        save_key_value(chat_id, key, value)
        send_message(chat_id, f"✅ Saved key '{key}'.")
        return

    # /get <key>
    if text.startswith("/get"):
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            send_message(chat_id, "Usage: /get <key>\nExample: /get email")
            return
        key = parts[1]
        item = get_key_value(chat_id, key)
        if not item:
            send_message(chat_id, f"❌ No value found for key '{key}'.")
        else:
            send_message(chat_id, f"🔑 {key} = {item.get('value', '')}")
        return

    # /list
    if text == "/list":
        keys = list_keys(chat_id)
        if not keys:
            send_message(chat_id, "You have not saved any keys yet.")
        else:
            lines = "\n".join(f"• {k}" for k in keys)
            send_message(chat_id, "Your saved keys:\n" + lines)
        return

    # /getid <message_id>
    if text.startswith("/getid"):
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            send_message(chat_id, "Usage: /getid <message_id>")
            return
        try:
            msg_id = int(parts[1])
        except ValueError:
            send_message(chat_id, "Message id must be a number.")
            return

        item = get_message_by_id(chat_id, msg_id)
        if not item:
            send_message(chat_id, f"No message stored with id {msg_id}.")
        else:
            send_message(
                chat_id,
                f"🧾 Message {msg_id} (at {item.get('created_at', '')}):\n\n{item.get('text', '')}",
            )
        return

    # /search <keyword>
    if text.startswith("/search"):
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            send_message(
                chat_id,
                "Usage: /search <keyword>\nExample: /search interview",
            )
            return
        keyword = parts[1]
        matches = search_messages(chat_id, keyword)
        if not matches:
            send_message(chat_id, f"No messages found containing '{keyword}'.")
            return

        lines = []
        for item in matches:
            msg_id = item.get("message_id")
            snippet = item.get("text", "")
            if len(snippet) > 80:
                snippet = snippet[:77] + "..."
            lines.append(f"{msg_id}: {snippet}")
        send_message(chat_id, "🔍 Search results:\n\n" + "\n".join(lines))
        return

    # /latest
    if text.startswith("/latest"):
        items = get_last_messages(chat_id, limit=1)
        if not items:
            send_message(chat_id, "No messages stored yet.")
            return
        item = items[0]
        send_message(
            chat_id,
            f"📝 Latest message (at {item.get('created_at', '')}):\n\n{item.get('text', '')}",
        )
        return

    # /history
    if text.startswith("/history"):
        items = get_last_messages(chat_id, limit=5)
        if not items:
            send_message(chat_id, "No messages stored yet.")
            return
        lines = []
        for idx, item in enumerate(items, start=1):
            snippet = item.get("text", "")
            if len(snippet) > 80:
                snippet = snippet[:77] + "..."
            lines.append(
                f"{idx}. [{item.get('created_at', '')}]\n{snippet}"
            )
        send_message(chat_id, "🧾 Your last messages:\n\n" + "\n\n".join(lines))
        return

    # /ask <question>
    if text.startswith("/ask"):
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            send_message(
                chat_id,
                "Usage: /ask <question>\nExample: /ask What is DynamoDB?",
            )
            return
        question = parts[1]
        reply = ask_ai(question)
        send_message(chat_id, reply)
        return

    # /summarize
    if text.startswith("/summarize"):
        reply = summarize_last_notes(chat_id, limit=10)
        send_message(chat_id, reply)
        return

    # /stats
    if text.startswith("/stats"):
        stats_text = compute_personal_stats(chat_id)
        send_message(chat_id, stats_text)
        return

    # /menu (just show text menu now)
    if text.startswith("/menu"):
        send_message(chat_id, help_text())
        return

    # Fallback
    send_message(
        chat_id,
        "I did not recognise that. Type /help to see all commands.",
    )


def handle_callback_query(callback_query: dict):
    # We don't use inline buttons right now, just acknowledge
    callback_id = callback_query["id"]
    answer_callback_query(callback_id)


# --------- LAMBDA HANDLER ---------


def lambda_handler(event, context):
    print("Incoming event:", json.dumps(event))

    if not TELEGRAM_BOT_TOKEN:
        return {
            "statusCode": 500,
            "body": json.dumps({"ok": False, "error": "Missing TELEGRAM_BOT_TOKEN"}),
        }

    try:
        body = event.get("body") or "{}"
        update = json.loads(body)
    except json.JSONDecodeError:
        print("Invalid JSON body")
        return {"statusCode": 400, "body": "Invalid JSON"}

    if "callback_query" in update:
        handle_callback_query(update["callback_query"])
    else:
        message = update.get("message") or update.get("edited_message")
        if not message:
            return {"statusCode": 200, "body": json.dumps({"ok": True})}

        chat = message.get("chat", {})
        chat_id = chat.get("id")
        text = message.get("text", "")
        message_id = message.get("message_id")
        from_user = message.get("from", {}) or {}
        first_name = from_user.get("first_name") or from_user.get("username") or None

        if chat_id is None:
            return {"statusCode": 200, "body": json.dumps({"ok": True})}

        # store every incoming text for history/search/stats/summarise
        if text and message_id is not None:
            try:
                save_message_record(chat_id, message_id, text)
            except Exception as e:
                print("Error saving message record:", e)

        if text:
            handle_text_message(chat_id, message_id, text, first_name)
        else:
            send_message(chat_id, "Right now I only understand text messages.")

    return {
        "statusCode": 200,
        "body": json.dumps({"ok": True}),
    }
