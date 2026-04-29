# Snipr — URL Shortener

Full-stack URL shortener: **Flask backend + SQLite database + Vanilla JS frontend**.

---

## Project Structure

```
snipr/
├── backend/
│   ├── app.py            ← Flask API + SQLAlchemy models
│   ├── requirements.txt  ← Python dependencies
│   └── snipr.db          ← SQLite database (auto-created on first run)
└── frontend/
    └── index.html        ← Frontend (open in browser)
```

---

## Setup

### 1. Install dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Run the Flask backend

```bash
python app.py
```

The API will start at **http://localhost:5000**

### 3. Open the frontend

Open `frontend/index.html` in your browser (double-click or drag into Chrome/Firefox).

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/shorten` | Shorten a URL |
| `GET` | `/r/:code` | Redirect to original URL |
| `GET` | `/api/links` | List all links (last 20) |
| `GET` | `/api/links/:code` | Get a specific link |
| `DELETE` | `/api/links/:code` | Delete a link |
| `GET` | `/api/stats` | Global stats + 7-day chart |
| `GET` | `/api/health` | Health check |

### POST /api/shorten

**Request body:**
```json
{
  "url": "https://your-long-url.com",
  "alias": "my-link",      // optional
  "expiry": "7 days"       // "Never" | "1 day" | "7 days" | "30 days"
}
```

**Response:**
```json
{
  "code": "my-link",
  "short_url": "http://localhost:5000/r/my-link",
  "long_url": "https://your-long-url.com",
  "expiry": "7 days",
  "expires_at": "2024-12-31T00:00:00",
  "clicks": 0,
  "created_at": "2024-12-24T10:00:00"
}
```

---

## Database Schema

### `short_urls`
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| code | VARCHAR(32) | Unique short code |
| long_url | TEXT | Original URL |
| expiry | VARCHAR(16) | Human-readable expiry label |
| expires_at | DATETIME | Expiry timestamp (null = never) |
| clicks | INTEGER | Total click count |
| created_at | DATETIME | Creation timestamp |

### `click_logs`
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| code | VARCHAR(32) | FK → short_urls.code |
| clicked_at | DATETIME | When the click happened |
| user_agent | TEXT | Browser user agent |
| ip | VARCHAR(64) | Requester IP |

---

## Tech Stack

- **Backend:** Python 3, Flask, Flask-SQLAlchemy, Flask-CORS
- **Database:** SQLite (via SQLAlchemy ORM)
- **Frontend:** Vanilla HTML/CSS/JS (no framework needed)
- **Encoding:** Random Base62 (6-char codes)
"# url_shortener" 
