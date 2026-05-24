# StudyTrack — AI-Powered Study Planner

A full stack web app that helps students study smarter using AI-generated quizzes.

## Features
- User registration and login
- Subject manager with color tags
- Add notes by typing or uploading PDF/TXT files
- AI quiz generator using Groq LLaMA 3
- Score tracking with progress dashboard

## Tech Stack
- Backend: Python, Flask, Flask-Login, Flask-WTF
- AI: Groq API LLaMA 3.3
- Database: SQLite + SQLAlchemy
- Frontend: Jinja2, Bootstrap 5

## Run locally
git clone https://github.com/fizamajid17/studytrack.git
cd studytrack
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python run.py
