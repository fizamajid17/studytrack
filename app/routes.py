from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
from app.models import User, Subject, Note, Quiz
from app.forms import RegisterForm, LoginForm, SubjectForm, NoteForm
from config import Config
from groq import Groq
import json
import re

auth = Blueprint('auth', __name__)
main = Blueprint('main', __name__)


# ---------- AUTH ----------

@auth.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    form = RegisterForm()
    if form.validate_on_submit():
        hashed_pw = generate_password_hash(form.password.data)
        user = User(username=form.username.data,
                    email=form.email.data,
                    password=hashed_pw)
        db.session.add(user)
        db.session.commit()
        flash('Account created! Please log in.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html', form=form)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            return redirect(url_for('main.dashboard'))
        flash('Invalid email or password.', 'danger')
    return render_template('auth/login.html', form=form)

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))


# ---------- MAIN ----------

@main.route('/dashboard')
@login_required
def dashboard():
    subjects = Subject.query.filter_by(user_id=current_user.id).all()
    total_quizzes = Quiz.query.join(Subject).filter(Subject.user_id == current_user.id).count()
    total_subjects = len(subjects)
    recent_quizzes = Quiz.query.join(Subject).filter(
        Subject.user_id == current_user.id
    ).order_by(Quiz.taken_at.desc()).limit(5).all()
    avg_score = 0
    if total_quizzes > 0:
        all_quizzes = Quiz.query.join(Subject).filter(Subject.user_id == current_user.id).all()
        avg_score = round(sum(q.score / q.total * 100 for q in all_quizzes if q.total > 0) / total_quizzes)
    return render_template('main/dashboard.html',
                           subjects=subjects,
                           total_quizzes=total_quizzes,
                           total_subjects=total_subjects,
                           recent_quizzes=recent_quizzes,
                           avg_score=avg_score)


@main.route('/subjects', methods=['GET', 'POST'])
@login_required
def subjects():
    form = SubjectForm()
    if form.validate_on_submit():
        subject = Subject(name=form.name.data,
                          color=form.color.data,
                          user_id=current_user.id)
        db.session.add(subject)
        db.session.commit()
        flash('Subject added!', 'success')
        return redirect(url_for('main.subjects'))
    all_subjects = Subject.query.filter_by(user_id=current_user.id).all()
    return render_template('main/subjects.html', form=form, subjects=all_subjects)


@main.route('/subjects/delete/<int:subject_id>', methods=['POST'])
@login_required
def delete_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    if subject.user_id != current_user.id:
        flash('Not allowed.', 'danger')
        return redirect(url_for('main.subjects'))
    db.session.delete(subject)
    db.session.commit()
    flash('Subject deleted.', 'success')
    return redirect(url_for('main.subjects'))


@main.route('/notes/<int:subject_id>', methods=['GET', 'POST'])
@login_required
def notes(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    if subject.user_id != current_user.id:
        flash('Not allowed.', 'danger')
        return redirect(url_for('main.subjects'))
    form = NoteForm()
    existing_note = Note.query.filter_by(subject_id=subject_id).first()
    if form.validate_on_submit():
        if existing_note:
            existing_note.content = form.content.data
        else:
            note = Note(content=form.content.data, subject_id=subject_id)
            db.session.add(note)
        db.session.commit()
        flash('Notes saved!', 'success')
        return redirect(url_for('main.notes', subject_id=subject_id))
    if existing_note:
        form.content.data = existing_note.content
    return render_template('main/notes.html', form=form, subject=subject, note=existing_note)


@main.route('/quiz/<int:subject_id>')
@login_required
def quiz(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    if subject.user_id != current_user.id:
        flash('Not allowed.', 'danger')
        return redirect(url_for('main.subjects'))
    note = Note.query.filter_by(subject_id=subject_id).first()
    if not note:
        flash('Add some notes first before generating a quiz!', 'warning')
        return redirect(url_for('main.notes', subject_id=subject_id))
    try:
        client = Groq(api_key=Config.GROQ_API_KEY)
        clean_notes = re.sub(r'[^\x00-\x7F]+', ' ', note.content)
        clean_notes = re.sub(r'\s+', ' ', clean_notes).strip()
        prompt = f"""You are a quiz generator. Based on the study notes below, create exactly 5 multiple choice questions.

STRICT RULES:
- Return ONLY a raw JSON array. No explanation, no markdown, no code blocks, no backticks.
- Each item must have: "question" (string), "options" (array of exactly 4 strings), "answer" (must exactly match one of the options).
- Make questions test understanding, not just memory.
- Questions must be based strictly on the notes.

STUDY NOTES:
{clean_notes[:3000]}

RETURN FORMAT:
[{{"question": "...", "options": ["A", "B", "C", "D"], "answer": "A"}}]"""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1500
        )
        raw = response.choices[0].message.content.strip()
        raw = re.sub(r'```json|```', '', raw).strip()
        questions = json.loads(raw)
        session['quiz_questions'] = questions
        session['quiz_subject_id'] = subject_id
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('main.notes', subject_id=subject_id))
    return render_template('main/quiz.html', subject=subject, questions=questions)


@main.route('/quiz/submit/<int:subject_id>', methods=['POST'])
@login_required
def submit_quiz(subject_id):
    questions = session.get('quiz_questions', [])
    score = 0
    results = []
    for i, q in enumerate(questions):
        selected = request.form.get(f'q{i}')
        correct = q['answer']
        is_correct = selected == correct
        if is_correct:
            score += 1
        results.append({
            'question': q['question'],
            'selected': selected,
            'correct': correct,
            'is_correct': is_correct,
            'options': q['options']
        })
    quiz = Quiz(score=score, total=len(questions), subject_id=subject_id)
    db.session.add(quiz)
    db.session.commit()
    return render_template('main/results.html',
                           results=results,
                           score=score,
                           total=len(questions),
                           subject_id=subject_id)

@main.route('/notes/upload/<int:subject_id>', methods=['POST'])
@login_required
def upload_notes(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    if subject.user_id != current_user.id:
        flash('Not allowed.', 'danger')
        return redirect(url_for('main.subjects'))
    file = request.files.get('file')
    if not file or file.filename == '':
        flash('No file selected.', 'warning')
        return redirect(url_for('main.notes', subject_id=subject_id))
    text = ''
    file_bytes = file.read()
    if file.filename.endswith('.txt'):
        text = file_bytes.decode('utf-8', errors='ignore')
    elif file.filename.endswith('.pdf'):
        # First try normal text extraction
        try:
            import pdfplumber, io
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page in pdf.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text += extracted + '\n'
        except Exception:
            pass
        # If normal extraction failed or got garbage, use OCR
        if not text.strip() or len([c for c in text if c.isalpha()]) < 50:
            try:
                import pytesseract
                from pdf2image import convert_from_bytes
                from PIL import Image
                flash('Scanned PDF detected — using OCR. This may take 30-60 seconds...', 'info')
                images = convert_from_bytes(file_bytes, dpi=200)
                ocr_text = ''
                for img in images[:10]:  # limit to first 10 pages
                    ocr_text += pytesseract.image_to_string(img) + '\n'
                if ocr_text.strip():
                    text = ocr_text
            except Exception as e:
                flash(f'OCR failed: {str(e)}', 'danger')
                return redirect(url_for('main.notes', subject_id=subject_id))
    else:
        flash('Only PDF or TXT files allowed.', 'warning')
        return redirect(url_for('main.notes', subject_id=subject_id))
    if not text.strip():
        flash('Could not extract text. Try a different PDF.', 'danger')
        return redirect(url_for('main.notes', subject_id=subject_id))
    # Clean the extracted text
    import re
    text = re.sub(r'[^\x20-\x7E\n]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    existing = Note.query.filter_by(subject_id=subject_id).first()
    if existing:
        existing.content = text
    else:
        db.session.add(Note(content=text, subject_id=subject_id))
    db.session.commit()
    flash(f'Notes extracted successfully! ({len(text)} characters)', 'success')
    return redirect(url_for('main.notes', subject_id=subject_id))

@main.route('/all-notes')
@login_required
def all_notes():
    subjects = Subject.query.filter_by(user_id=current_user.id).all()
    return render_template('main/all_notes.html', subjects=subjects)

@main.route('/all-quizzes')
@login_required
def all_quizzes():
    subjects = Subject.query.filter_by(user_id=current_user.id).all()
    return render_template('main/all_quizzes.html', subjects=subjects)