from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, flash
import os
from dotenv import load_dotenv
from groq import Groq
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    current_user,
    logout_user,
)
from flask_bcrypt import Bcrypt

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///app.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# DB/Auth setup
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
bcrypt = Bcrypt(app)


# Models
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password: str):
        self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash, password)


class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User")


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# Temporary cache for last AI summary
last_ai_summary = ""

# Format markdown-style output to HTML
def format_to_html(text):
    """Convert AI text output to clean HTML"""
    lines = text.split('\n')
    html_output = []
    in_list = False
    
    for line in lines:
        line = line.strip()
        if not line:
            if in_list:
                html_output.append('</ul>')
                in_list = False
            continue
        
        # Day headings (starts with "Day")
        if line.startswith('Day ') and '–' in line:
            if in_list:
                html_output.append('</ul>')
                in_list = False
            html_output.append(f'<h3 style="color: #2d6fa3; margin-top: 1.5rem; margin-bottom: 0.5rem; font-size: 1.1rem;">{line}</h3>')
        
        # Section markers (Morning, Afternoon, Evening, Tips, Budget)
        elif line.endswith(':') or 'Tips:' in line or 'Tip:' in line or 'Budget' in line:
            if in_list:
                html_output.append('</ul>')
                in_list = False
            if 'Tip' in line:
                html_output.append(f'<p style="margin-top: 1rem; padding: 0.6rem; background: #f0f9ff; border-left: 3px solid #6ec1e4; color: #1e3a8a; font-size: 0.85rem;">💡 {line}</p>')
            elif 'Budget' in line:
                html_output.append(f'<p style="margin-top: 0.5rem; color: #f9a26c; font-weight: 600; font-size: 0.85rem;">{line}</p>')
            else:
                html_output.append(f'<h4 style="color: #4a5568; margin-top: 0.8rem; margin-bottom: 0.3rem; font-size: 0.9rem; font-weight: 600;">{line}</h4>')
        
        # Bullet points (starts with - or •)
        elif line.startswith('-') or line.startswith('•'):
            if not in_list:
                html_output.append('<ul style="margin: 0; padding-left: 1.5rem; list-style-type: disc;">')
                in_list = True
            clean_line = line[1:].strip()
            html_output.append(f'<li style="margin-bottom: 0.5rem; line-height: 1.6; color: #333; font-size: 0.85rem;">{clean_line}</li>')
        
        # Regular text
        else:
            if in_list:
                html_output.append('</ul>')
                in_list = False
            html_output.append(f'<p style="margin-bottom: 0.5rem; line-height: 1.5; color: #333;">{line}</p>')
    
    if in_list:
        html_output.append('</ul>')
    
    return '\n'.join(html_output)

# Groq AI integration
def generate_with_groq(prompt):
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a helpful travel assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_completion_tokens=2000,
            top_p=1,
            stop=None,
            stream=False
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"[Error generating itinerary: {e}]"

# Ensure tables exist (non-destructive)
with app.app_context():
    try:
        db.create_all()
        # Lightweight migration: drop legacy 'itinerary_text' column from review if it exists (SQLite-compatible)
        insp = db.inspect(db.engine)
        if 'review' in insp.get_table_names():
            review_cols = [c['name'] for c in insp.get_columns('review')]
            if 'itinerary_text' in review_cols:
                from sqlalchemy import text
                with db.engine.begin() as conn:
                    conn.execute(text("PRAGMA foreign_keys=off;"))
                    conn.execute(text(
                        """
                        CREATE TABLE IF NOT EXISTS review_new (
                            id INTEGER PRIMARY KEY,
                            user_id INTEGER NOT NULL,
                            rating INTEGER NOT NULL,
                            comment TEXT NOT NULL,
                            created_at DATETIME,
                            FOREIGN KEY(user_id) REFERENCES user(id)
                        );
                        """
                    ))
                    conn.execute(text(
                        """
                        INSERT INTO review_new (id, user_id, rating, comment, created_at)
                        SELECT id, user_id, rating, comment, created_at FROM review;
                        """
                    ))
                    conn.execute(text("DROP TABLE review;"))
                    conn.execute(text("ALTER TABLE review_new RENAME TO review;"))
                    conn.execute(text("PRAGMA foreign_keys=on;"))
    except Exception:
        pass

# Landing page
@app.route("/")
def home():
    return render_template("home.html")

# Planner page
@app.route("/plan")
def planner():
    return render_template("index.html")

@app.route("/generate_trip", methods=["POST"])
def generate_trip():
    data = request.json
    destination = data.get("destination", "")
    from_date = data.get("from_date", "")
    to_date = data.get("to_date", "")
    days = data.get("days", "")
    budget = data.get("budget", "")
    interests = data.get("interests", [])
    
    prompt = f"""
You are VoyageIQ, an AI-powered travel itinerary planner.
User Input:
- Destination: {destination}
- Dates: {from_date} to {to_date}
- Duration: {days} days
- Budget: {budget}
- Interests: {', '.join(interests)}

Your Task:
Generate a detailed travel plan for each day, following this structure and tone:

Day 1 – Arrival and City Walk
- Check into your hotel and relax after arrival.
- Explore the local markets or a nearby attraction.
- Try a local restaurant or café in the evening.
Tips: Use local cabs or metro for short distances.

Repeat for all {days} days, with a unique title, 2-4 activities per day, and a useful tip. Do NOT use JSON or code formatting. Make it easy to read for travelers.
"""
    
    global last_ai_summary
    raw_summary = generate_with_groq(prompt)
    last_ai_summary = raw_summary
    formatted_summary = format_to_html(raw_summary)
    
    return jsonify({"summary": formatted_summary})

# Export page (download options)
@app.route("/export_page")
@login_required
def export_page():
    global last_ai_summary
    formatted_summary = format_to_html(last_ai_summary) if last_ai_summary else "<p>No summary generated yet. Please generate a plan first.</p>"
    reviews = Review.query.order_by(Review.created_at.desc()).all()
    return render_template("export.html", summary=formatted_summary, reviews=reviews)

# Export file endpoint
@app.route("/export", methods=["GET"])
@login_required
def export():
    from io import BytesIO
    fmt = request.args.get("format", "pdf")
    if fmt == "txt":
        txt_buffer = BytesIO(last_ai_summary.encode("utf-8"))
        return send_file(txt_buffer, as_attachment=True, download_name="VoyageIQ_Itinerary.txt", mimetype="text/plain")
    else:
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas
            pdf_buffer = BytesIO()
            c = canvas.Canvas(pdf_buffer, pagesize=letter)
            textobject = c.beginText(40, 750)
            for line in last_ai_summary.split('\n'):
                textobject.textLine(line)
            c.drawText(textobject)
            c.showPage()
            c.save()
            pdf_buffer.seek(0)
            return send_file(pdf_buffer, as_attachment=True, download_name="VoyageIQ_Itinerary.pdf", mimetype="application/pdf")
        except Exception:
            txt_buffer = BytesIO(last_ai_summary.encode("utf-8"))
            return send_file(txt_buffer, as_attachment=True, download_name="VoyageIQ_Itinerary.txt", mimetype="text/plain")


# ---------- Auth Routes ----------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        # Validation
        if not username or not email or not password:
            flash("All fields are required.", "error")
            return redirect(url_for("signup"))

        existing = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing:
            flash("Username or email already exists.", "error")
            return redirect(url_for("signup"))

        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("Welcome to VoyageIQ!", "success")
        return redirect(url_for("home"))

    return render_template("login_signup.html", mode="signup")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")
        # Allow login with username or email
        user = User.query.filter((User.username == identifier) | (User.email == identifier.lower())).first()
        if user and user.check_password(password):
            login_user(user)
            flash("Logged in successfully!", "success")
            next_url = request.args.get("next")
            return redirect(next_url or url_for("home"))
        flash("Invalid credentials.", "error")
        return redirect(url_for("login"))

    return render_template("login_signup.html", mode="login")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out.", "success")
    return redirect(url_for("home"))


# ---------- Reviews ----------
@app.route("/review", methods=["POST"])
@login_required
def add_review():
    global last_ai_summary
    rating = int(request.form.get("rating", 0))
    comment = request.form.get("comment", "").strip()
    if rating < 1 or rating > 5 or not comment:
        flash("Please provide a rating (1-5) and a comment.", "error")
        return redirect(url_for("export_page"))

    review = Review(
        user_id=current_user.id,
        rating=rating,
        comment=comment,
    )
    db.session.add(review)
    db.session.commit()
    flash("Review added successfully!", "success")
    return redirect(url_for("export_page"))

if __name__ == "__main__":
    app.run(debug=True)