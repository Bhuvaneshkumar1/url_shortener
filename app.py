"""
Snipr — URL Shortener Backend
Flask + MongoDB (PyMongo)
"""

from flask import Flask, request, jsonify, redirect, send_from_directory
from flask_cors import CORS
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from pymongo.errors import DuplicateKeyError
from datetime import datetime, timedelta
import string, random, os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# ── Config ──────────────────────────────────────────────────────
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/snipr")
client = MongoClient(MONGO_URI, server_api=ServerApi('1'))
db = client.get_database("snipr")

# Create collections and indexes
short_urls = db["short_urls"]
click_logs = db["click_logs"]

# Ensure indexes
short_urls.create_index("code", unique=True)
click_logs.create_index("code")

EXPIRY_MAP = {
    "Never":   None,
    "1 day":   1,
    "7 days":  7,
    "30 days": 30,
}

# ── Helpers ───────────────────────────────────────────────────────
CHARS = string.ascii_letters + string.digits   # Base62

def gen_code(length=6):
    """Generate a random Base62 code."""
    return "".join(random.choices(CHARS, k=length))

def unique_code():
    for _ in range(10):
        code = gen_code()
        if not short_urls.find_one({"code": code}):
            return code
    raise RuntimeError("Could not generate unique code after 10 attempts")

def url_to_dict(doc, base_url="http://localhost:5000"):
    """Convert MongoDB document to JSON-friendly dict."""
    return {
        "code":       doc["code"],
        "short_url":  f"{base_url}/r/{doc['code']}",
        "long_url":   doc["long_url"],
        "expiry":     doc["expiry"],
        "expires_at": doc["expires_at"].isoformat() if doc["expires_at"] else None,
        "clicks":     doc["clicks"],
        "created_at": doc["created_at"].isoformat(),
    }

def is_expired(doc):
    """Check if a URL entry has expired."""
    if doc["expires_at"] is None:
        return False
    return datetime.utcnow() > doc["expires_at"]

# ── Routes ───────────────────────────────────────────────────────

@app.route("/")
def home():
    return send_from_directory('.', 'index.html')

@app.route("/api/shorten", methods=["POST"])
def shorten():
    data = request.get_json(force=True)
    long_url = (data.get("url") or "").strip()
    alias    = (data.get("alias") or "").strip()
    expiry   = data.get("expiry", "Never")

    if not long_url:
        return jsonify({"error": "URL is required"}), 400

    # Ensure scheme
    if not long_url.startswith(("http://", "https://")):
        long_url = "https://" + long_url

    # Resolve code
    if alias:
        if short_urls.find_one({"code": alias}):
            return jsonify({"error": f"Alias '{alias}' is already taken"}), 409
        code = alias
    else:
        code = unique_code()

    # Expiry timestamp
    days = EXPIRY_MAP.get(expiry)
    expires_at = datetime.utcnow() + timedelta(days=days) if days else None

    entry = {
        "code":       code,
        "long_url":   long_url,
        "expiry":     expiry,
        "expires_at": expires_at,
        "clicks":     0,
        "created_at": datetime.utcnow(),
    }
    
    try:
        short_urls.insert_one(entry)
    except DuplicateKeyError:
        return jsonify({"error": f"Code '{code}' already exists"}), 409

    base_url = request.host_url.rstrip('/')
    return jsonify(url_to_dict(entry, base_url)), 201


@app.route("/r/<code>")
def redirect_url(code):
    """Redirect short → long and log click."""
    entry = short_urls.find_one({"code": code})
    if not entry:
        return jsonify({"error": "Link not found"}), 404
    
    if is_expired(entry):
        return jsonify({"error": "Link has expired"}), 410

    # Log click
    click_log = {
        "code":       code,
        "clicked_at": datetime.utcnow(),
        "user_agent": request.user_agent.string,
        "ip":         request.remote_addr,
    }
    click_logs.insert_one(click_log)
    
    # Increment clicks
    short_urls.update_one({"code": code}, {"$inc": {"clicks": 1}})

    return redirect(entry["long_url"], code=302)


@app.route("/api/links", methods=["GET"])
def list_links():
    """Return last 20 links (newest first)."""
    links = list(short_urls.find().sort("created_at", -1).limit(20))
    base_url = request.host_url.rstrip('/')
    return jsonify([url_to_dict(l, base_url) for l in links])


@app.route("/api/links/<code>", methods=["GET"])
def get_link(code):
    entry = short_urls.find_one({"code": code})
    if not entry:
        return jsonify({"error": "Not found"}), 404
    base_url = request.host_url.rstrip('/')
    return jsonify(url_to_dict(entry, base_url))


@app.route("/api/links/<code>", methods=["DELETE"])
def delete_link(code):
    entry = short_urls.find_one({"code": code})
    if not entry:
        return jsonify({"error": "Not found"}), 404
    
    click_logs.delete_many({"code": code})
    short_urls.delete_one({"code": code})
    return jsonify({"deleted": code})


@app.route("/api/stats", methods=["GET"])
def stats():
    total_links  = short_urls.count_documents({})
    total_clicks = sum(doc["clicks"] for doc in short_urls.find({}, {"clicks": 1}))

    # Clicks per day for last 7 days
    seven_days = []
    for i in range(6, -1, -1):
        day = datetime.utcnow().date() - timedelta(days=i)
        day_start = datetime(day.year, day.month, day.day)
        day_end   = day_start + timedelta(days=1)
        
        count = click_logs.count_documents({
            "clicked_at": {
                "$gte": day_start,
                "$lt":  day_end,
            }
        })
        seven_days.append({"date": day.strftime("%a"), "clicks": count})

    return jsonify({
        "total_links":  total_links,
        "total_clicks": total_clicks,
        "last_7_days":  seven_days,
    })


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "time": datetime.utcnow().isoformat()})


if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_ENV", "production") == "development"
    app.run(debug=debug_mode, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
