from flask import Flask, render_template, request, jsonify, send_file
import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)
app = Flask(__name__)

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
You are TripTactix, an AI-powered travel itinerary planner.
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
def export_page():
    return render_template("export.html")

# Export file endpoint
@app.route("/export", methods=["GET"])
def export():
    from io import BytesIO
    fmt = request.args.get("format", "pdf")
    if fmt == "txt":
        txt_buffer = BytesIO(last_ai_summary.encode("utf-8"))
        return send_file(txt_buffer, as_attachment=True, download_name="TripTactix_Itinerary.txt", mimetype="text/plain")
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
            return send_file(pdf_buffer, as_attachment=True, download_name="TripTactix_Itinerary.pdf", mimetype="application/pdf")
        except Exception:
            txt_buffer = BytesIO(last_ai_summary.encode("utf-8"))
            return send_file(txt_buffer, as_attachment=True, download_name="TripTactix_Itinerary.txt", mimetype="text/plain")

if __name__ == "__main__":
    app.run(debug=True)