# Setup Guide

Complete setup instructions for AI Blog Agent.

## Prerequisites

- Python 3.9 or higher
- OpenAI API key
- WordPress site(s) with REST API enabled
- Google Cloud account (for Sheets API)
- Pexels API key
- Unsplash API key

---

## Step 1: Clone Repository

```bash
git clone https://github.com/sirliboyev-uz/ai-blog-agent.git
cd ai-blog-agent
```

---

## Step 2: Python Environment Setup

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

---

## Step 3: API Keys Setup

### 3.1 OpenAI API Key

1. Go to https://platform.openai.com/api-keys
2. Create a new API key
3. Copy the key (starts with `sk-`)

### 3.2 Pexels API Key

1. Go to https://www.pexels.com/api/
2. Sign up for free account
3. Get your API key from dashboard

### 3.3 Unsplash API Key

1. Go to https://unsplash.com/developers
2. Create a new application
3. Copy the "Access Key"

### 3.4 Google Sheets API

1. Go to https://console.cloud.google.com/
2. Create a new project
3. Enable "Google Sheets API" and "Google Drive API"
4. Create credentials → Service Account
5. Download JSON credentials file
6. Save as `config/google-credentials.json`
7. Share your Google Sheet with the service account email

---

## Step 4: WordPress Application Passwords

For each WordPress site:

1. Log in to WordPress admin
2. Go to Users → Profile
3. Scroll to "Application Passwords"
4. Enter name: "AI Blog Agent"
5. Click "Add New Application Password"
6. Copy the generated password (format: `xxxx xxxx xxxx xxxx xxxx xxxx`)

**Note**: Your WordPress site must have REST API enabled (enabled by default in WordPress 4.7+)

---

## Step 5: Configuration

```bash
# Copy environment template
cp config/.env.example config/.env

# Edit config/.env with your values
nano config/.env  # or use your preferred editor
```

### Environment Variables

```bash
# OpenAI
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o  # or gpt-4o-mini for lower cost

# Images
PEXELS_API_KEY=your-pexels-key
UNSPLASH_ACCESS_KEY=your-unsplash-key

# Google Sheets
GOOGLE_SHEETS_CREDENTIALS_FILE=config/google-credentials.json
GOOGLE_SHEET_ID=your-sheet-id  # From sheet URL

# WordPress Sites (JSON array)
WORDPRESS_SITES='[
  {
    "name": "My Blog",
    "url": "https://yourblog.com",
    "username": "admin",
    "app_password": "xxxx xxxx xxxx xxxx xxxx xxxx"
  }
]'

# Scheduling
POSTS_PER_WEEK_PER_SITE=3
POSTING_HOURS=9,12,15

# Content
MIN_WORD_COUNT=800
MAX_WORD_COUNT=1000
```

---

## Step 6: Google Sheets Setup

### Create Template Sheet

```bash
python src/main.py --create-template
```

This creates two worksheets:

**Topics Sheet** (Input):
- Topic
- Business Type
- Location
- Internal Link URLs
- Site Domain
- Status
- Post URL

**Logs Sheet** (Output):
- Date
- Site
- Topic
- Post Title
- Post URL
- Word Count
- Status
- Error

### Add Sample Data

Add rows to "Topics" sheet:

| Topic | Business Type | Location | Internal Link URLs | Site Domain | Status |
|-------|--------------|----------|-------------------|-------------|--------|
| Best Coffee Shops | Coffee Shop | San Francisco | https://example.com/about,https://example.com/menu | example.com | Pending |

---

## Step 7: Test Connections

```bash
python src/main.py --test-connections
```

This verifies:
- OpenAI API connection
- WordPress site access
- Google Sheets authentication

---

## Step 8: Run Demo

```bash
python src/main.py --demo
```

This generates a test blog post **without publishing** to verify content generation.

---

## Step 9: Process First Batch

```bash
# Process 1 topic
python src/main.py --batch 1
```

Check:
1. WordPress site for published post
2. Google Sheets "Logs" worksheet for results
3. "Topics" worksheet status updated to "Completed"

---

## Step 10: Setup Automated Scheduling

```bash
# Run scheduler (blocking process)
python src/main.py --schedule
```

Or using Docker:

```bash
# Build and run with docker-compose
docker-compose up -d
```

---

## Deployment Options

### Option 1: VPS Deployment (DigitalOcean, Hetzner)

```bash
# On server
git clone https://github.com/sirliboyev-uz/ai-blog-agent.git
cd ai-blog-agent
cp config/.env.example config/.env
# Edit config/.env with your keys

# Run with docker-compose
docker-compose up -d

# Or use systemd service
sudo nano /etc/systemd/system/blog-agent.service
```

### Option 2: Heroku

```bash
heroku create ai-blog-agent
heroku config:set $(cat config/.env | xargs)
git push heroku main
```

### Option 3: Local Development

```bash
# Activate virtual environment
source venv/bin/activate

# Run scheduler
python src/main.py --schedule
```

---

## Troubleshooting

### "Failed to authenticate with Google Sheets"

- Verify `google-credentials.json` is in `config/` folder
- Check service account email has access to the sheet
- Ensure Google Sheets API and Drive API are enabled

### "WordPress connection failed"

- Verify application password (no spaces when entered)
- Check WordPress REST API is accessible: `https://yoursite.com/wp-json/wp/v2`
- Ensure user has publishing permissions

### "OpenAI API error"

- Check API key is valid
- Verify billing is setup on OpenAI account
- Check rate limits haven't been exceeded

---

## Next Steps

- [API Reference](API.md)
- [Deployment Guide](DEPLOYMENT.md)
- [Troubleshooting](TROUBLESHOOTING.md)
