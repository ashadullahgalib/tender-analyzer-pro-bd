# Tender Analyzer Pro — Web Application

## Project Structure
```
tender_web/
├── app.py              ← Flask backend (all logic)
├── requirements.txt    ← Python dependencies
├── templates/
│   └── index.html      ← Full frontend (single file)
└── README.md
```

## Setup & Run

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the server
```bash
python app.py
```

### 3. Open in browser
```
http://localhost:5000
```

## API Endpoints

| Method | Endpoint         | Description                        |
|--------|------------------|------------------------------------|
| GET    | /                | Serves the web UI                  |
| POST   | /api/analyze     | Upload PDF + estimate → results    |
| POST   | /api/recalculate | Recalculate after bidder removal   |
| POST   | /api/export-pdf  | Download PDF report                |

## Deploying for Clients (Production)

### Option A — Render.com (Free tier available)
1. Push to GitHub
2. Connect repo on render.com
3. Set start command: `gunicorn app:app`
4. Done — live URL in minutes

### Option B — VPS (DigitalOcean / Contabo)
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```
Use Nginx as reverse proxy for production.

### Install gunicorn for production
```bash
pip install gunicorn
```
