# MotorMind 🚗⚡

### Automotive Electronics Learning Platform Built with Django

<p align="center">
  <img src="assets/motormind-mockup.png" alt="MotorMind Screenshot" width="900">
</p>

<p align="center">
  <strong>Interactive automotive electronics education platform with AI tutoring, quizzes, semantic search, and optional Solana skill badges.</strong>
</p>

---

# 📚 Overview

**MotorMind** is an automotive electronics education platform built using:

* 🐍 Django
* 🔌 Django REST Framework
* 🤖 Google Gemini AI
* 🧠 ChromaDB Vector Search
* 🎤 ElevenLabs TTS
* ☀️ Solana Devnet

Teachers can create and manage:

* Courses
* Training videos
* Learning sections
* Quizzes
* Reading resources
* AI-assisted study content

Students can:

* Watch embedded lessons
* Navigate videos by timestamped sections
* Take quizzes
* View leaderboards
* Earn optional Solana Devnet skill badges
* Chat with an AI tutor

---

# ✨ Features

## 🎓 Course System

* Create and manage automotive electronics courses
* Custom course icons
* Course descriptions and structured learning content
* Public course catalogue

## 🎥 Training Videos

* Embedded YouTube videos
* Auto-fetch:

  * video titles
  * thumbnails
  * transcripts
* Timestamped learning sections
* Section-based navigation

## 🤖 AI Tutor

Course-specific AI tutor powered by Google Gemini.

The tutor can reference:

* Course descriptions
* Reading content
* Training transcripts
* Video timestamps
* Quiz content
* Previous quiz performance

Optional speech playback is powered by ElevenLabs.

## 📄 Resource Library + Vector Search

Teachers can upload:

* PDFs
* Manuals
* Notes
* Transcripts
* Books

Resources are:

* Embedded into ChromaDB
* Searchable with semantic retrieval
* Linked to one or many courses

## 🧠 Semantic Retrieval (RAG-Ready)

* ChromaDB vector storage
* Local embeddings
* Retrieval testing dashboard
* No per-chunk SQLite rows

## 🏆 Quiz System

* Timed quizzes
* Leaderboards
* Pass/fail scoring
* Quiz analytics

## ☀️ Solana Devnet Skill Badges

Optional blockchain-backed proof of skill:

* Devnet memo transactions
* Claimable after passing quizzes
* Issuer wallet pays fees
* No NFTs

## 🧪 AR Tasks API

The `ar_tasks` app remains available through the API for future companion app support.

> Public AR task pages were removed from the main web UI to keep the learning experience focused.

---

# 🛠 Tech Stack

| Category   | Technology                          |
| ---------- | ----------------------------------- |
| Backend    | Django                              |
| API        | Django REST Framework               |
| Database   | SQLite                              |
| Vector DB  | ChromaDB                            |
| AI         | Google Gemini                       |
| TTS        | ElevenLabs                          |
| Blockchain | Solana Devnet                       |
| Frontend   | Bootstrap 5                         |
| Embeddings | sentence-transformers / ONNX MiniLM |

---

# 🚀 Quick Start

## Requirements

* Python 3.10+
* pip

## Installation

```bash
git clone <your-repo-url>
cd MotorMind

python3 -m venv .venv
source .venv/bin/activate
# Windows:
# .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env

python3 manage.py migrate
python3 manage.py check_trainingvideo_schema

python3 manage.py seed_demo

python3 manage.py runserver
```

Open:

```txt
http://127.0.0.1:8000/
```

---

# 🔐 Environment Variables

Create a `.env` file from `.env.example`.

## AI Features

```env
GOOGLE_API_KEY=
GOOGLE_MODEL_NAME=gemma-3-27b-it
```

## ElevenLabs

```env
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=
ELEVENLABS_MODEL=
```

## Solana

```env
SOLANA_RPC_URL=https://api.devnet.solana.com
SOLANA_NETWORK=devnet
SOLANA_ISSUER_PRIVATE_KEY=[...]
```

> Never commit API keys or wallet secrets.

---

# 👤 Demo Accounts

| Role    | Username   | Password     |
| ------- | ---------- | ------------ |
| Teacher | `teacher`  | `teacher123` |
| Student | `student1` | `student123` |
| Student | `student2` | `student123` |

---

# 🧠 AI Tutor

The AI tutor is available on:

```txt
/courses/<id>/
```

Features:

* Context-aware responses
* Voice input (Web Speech API)
* Optional voice playback
* Course-specific reasoning
* Quiz-aware assistance

## Powered By

| Service    | Purpose                     |
| ---------- | --------------------------- |
| Gemini     | Reasoning + text generation |
| ElevenLabs | Speech playback only        |

---

# 🎥 YouTube Auto-Fill

Teachers can paste a YouTube URL and automatically fetch:

* Video title
* Thumbnail
* Captions/transcripts

## Uses

* YouTube oEmbed
* youtube-transcript-api

## Transcript Priority

1. Manual English captions
2. Auto-generated English captions

If no captions exist:

* Transcript remains empty
* Teacher can manually add one later

---

# 📚 Learning Sections

Training videos support timestamped learning sections.

Teachers can:

* Generate suggested sections
* Save selected sections
* Replace existing sections
* Append sections during save

---

# 🗂 Resource Library

Upload:

* PDFs
* Manuals
* Notes
* Automotive books
* Training material

## Features

* ISBN validation
* Automatic metadata lookup
* ChromaDB ingestion
* Semantic search
* Course linking

---

# 🔍 Semantic Search

MotorMind stores vector embeddings inside:

```txt
vector_db/
```

## Stored in SQLite

* Resource metadata
* Ingestion jobs
* Retrieval logs

## Stored in ChromaDB

* Chunk embeddings
* Full chunk text
* Vector metadata

---

# 📖 ISBN Book Workflow

Example valid filenames:

```txt
9780415725774.pdf
978-0-415-72577-4.pdf
```

MotorMind automatically:

* Validates ISBN
* Fetches metadata
* Ingests vectors

Metadata sources:

* Open Library
* Google Books

---

# ☀️ Solana Devnet Badges

Students can claim proof-of-skill badges after passing quizzes.

## Setup

```bash
python manage.py check_solana_badges
```

## Test Transaction

```bash
python manage.py send_test_solana_badge --wallet <DEVNET_WALLET>
```

## Notes

* Devnet only
* No NFTs
* No mainnet usage
* Issuer wallet pays fees

---

# 🧩 Project Structure

```txt
carhoot/           Django project settings + URLs
accounts/          Authentication + dashboards
courses/           Courses, videos, sections
tutor/             AI tutor system
quizzes/           Quiz engine + leaderboards
resources/         ChromaDB + ingestion
study_content/     Reading content generation
api/               REST API
templates/         Frontend templates
solana_badges/     Solana memo badge system
ar_tasks/          AR task API
```

---

# 🧑‍🏫 Teacher Admin Panel

Accessible at:

```txt
/admin-panel/
```

## Includes

* Course management
* Video management
* Quiz management
* Resource ingestion
* Student progress tracking
* Retrieval testing tools

---

# ⚙️ Management Commands

## Courses

```bash
python manage.py list_courses_debug
python manage.py delete_course <course_id> --confirm
```

## Resources

```bash
python manage.py ingest_resource <resource_id>
python manage.py clear_vector_db
python manage.py test_vector_search "query"
```

## Cleanup

```bash
python manage.py cleanup_demo_attempts --users a,b --quizzes T
```

---

# 🌐 Main URLs

| URL                                | Description        |
| ---------------------------------- | ------------------ |
| `/`                                | Landing page       |
| `/courses/`                        | Course catalogue   |
| `/dashboard/`                      | User dashboard     |
| `/admin-panel/`                    | Teacher admin      |
| `/leaderboard/`                    | Quiz leaderboard   |
| `/profile/`                        | User profile       |
| `/badges/claim/quiz-attempt/<id>/` | Claim Solana badge |

---

# 🔌 API Endpoints

All endpoints are under:

```txt
/api/
```

Authentication required.

## Examples

### Courses

```txt
GET /api/courses/
GET /api/courses/<id>/
```

### Videos

```txt
GET /api/courses/<id>/videos/
GET /api/videos/<id>/sections/
```

### Quizzes

```txt
GET /api/courses/<id>/quizzes/
GET /api/quizzes/<id>/
```

### Resources

```txt
POST /api/resources/search/
POST /api/resources/upload/
```

### AR Tasks

```txt
GET /api/courses/<id>/ar-tasks/
POST /api/ar-tasks/<id>/progress/
```

---

# 🧪 Example API Requests

## Semantic Search

```bash
curl -u teacher:teacher123 \
-X POST http://127.0.0.1:8000/api/resources/search/ \
-H "Content-Type: application/json" \
-d '{
  "query":"how do you test a car fuse?",
  "top_k":3,
  "course_id":1
}'
```

## AR Task Progress

```bash
curl -u student1:student123 \
-X POST http://127.0.0.1:8000/api/ar-tasks/1/progress/ \
-H "Content-Type: application/json" \
-d '{
  "status":"completed",
  "notes":"Simulated fault isolated"
}'
```

---

# 🧰 Embeddings

MotorMind tries:

1. `sentence-transformers`
2. ONNX MiniLM fallback

This avoids TensorFlow/Keras dependency issues on some systems.

---

# 📝 Notes

* SQLite is used for development
* Bootstrap 5 is loaded via CDN
* Uploaded resources are stored under:

```txt
MEDIA_ROOT/resources/
```

* Large PDFs may take longer to ingest
* Vector rebuilds can be triggered manually

---

# 📌 Future Improvements

* OCR pipeline for scanned PDFs
* Hosted embedding providers
* Better vector filtering
* Expanded AR learning companion app
* More analytics
* Async ingestion queue

---

# 📄 License

Add your preferred license here.

Example:

```txt
MIT License
```

---

# ❤️ Credits

Built with:

* Django
* DRF
* ChromaDB
* Gemini
* ElevenLabs
* Solana Devnet

---

# ⭐ MotorMind

> Interactive automotive electronics learning with AI-powered education tools.
