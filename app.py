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


# Format AI output to clean HTML
def format_to_html(text):
    """Convert markdown-style text to clean HTML"""
    lines = text.split('\n')
    html_output = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Day headings (bold with **)
        if line.startswith('**Day') and line.endswith('**'):
            clean_line = line.strip('*')
            html_output.append(f'<h3 style="color: #2d6fa3; margin-top: 1.5rem; margin-bottom: 0.5rem; font-size: 1.1rem;">{clean_line}</h3>')
        
        # Section headings (Morning, Afternoon, Evening, Travel Tip, Budget)
        elif line.startswith('**') and line.endswith('**'):
            clean_line = line.strip('*')
            html_output.append(f'<h4 style="color: #4a5568; margin-top: 1rem; margin-bottom: 0.3rem; font-size: 0.95rem; font-weight: 600;">{clean_line}</h4>')
        
        # Bullet points
        elif line.startswith('•'):
            clean_line = line[1:].strip()
            html_output.append(f'<p style="margin-left: 1.2rem; margin-bottom: 0.4rem; line-height: 1.5; color: #333;">• {clean_line}</p>')
        
        # Separator
        elif line == '---':
            html_output.append('<hr style="margin: 1.5rem 0; border: none; border-top: 1px solid #e2e8f0;">')
        
        # Regular text
        else:
            html_output.append(f'<p style="margin-bottom: 0.5rem; line-height: 1.5; color: #333;">{line}</p>')
    
    return '\n'.join(html_output)


# Groq AI integration
def generate_with_groq(prompt):
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a helpful travel assistant that creates well-structured itineraries."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_completion_tokens=1024,
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
    days = int(data.get("days", 1))  # Convert to integer
    budget = data.get("budget", "")
    interests = data.get("interests", [])
    
    # Create explicit day structure
    day_structure = ""
    for day_num in range(1, days + 1):
        day_structure += f"""
<div class="day-section">
<h3>Day {day_num} – [Create an engaging title for this day]</h3>

<h4>Morning:</h4>
<ul>
<li>[Morning activity 1]</li>
<li>[Morning activity 2]</li>
</ul>

<h4>Afternoon:</h4>
<ul>
<li>[Afternoon activity 1]</li>
<li>[Afternoon activity 2]</li>
</ul>

<h4>Evening:</h4>
<ul>
<li>[Evening activity 1]</li>
<li>[Evening activity 2]</li>
</ul>

<p class="tip">💡 Travel Tip: [helpful tip for day {day_num}]</p>
<p class="budget">Budget Estimate: $[amount for day {day_num}]</p>
</div>

"""
    
    prompt = f"""
You are TripTactix, an AI-powered travel itinerary planner.

User Input:
- Destination: {destination}
- Dates: {from_date} to {to_date}
- Duration: {days} days (MUST generate exactly {days} days)
- Budget: ${budget} USD total
- Interests: {', '.join(interests) if interests else 'General sightseeing'}

CRITICAL INSTRUCTION: You MUST create itinerary for exactly {days} days. Not more, not less.

Fill in this template for ALL {days} days:

{day_structure}

RULES:
1. Replace [Create an engaging title for this day] with actual titles like "Arrival & City Exploration", "Cultural Heritage Tour", etc.
2. Replace all [activity] placeholders with real, specific activities in {destination}
3. Replace [helpful tip] with practical travel advice
4. Replace [amount] with realistic daily budget (total should be around ${budget})
5. Make each day unique and interesting
6. Consider user interests: {', '.join(interests) if interests else 'General exploration'}
7. Output ONLY the filled HTML. No extra text before or after.
8. Generate ALL {days} days - this is mandatory.

Start generating now:
"""
    
    global last_ai_summary
    raw_summary = generate_with_groq(prompt)
    last_ai_summary = raw_summary
    
    # Add CSS styling to the HTML output
    styled_output = f"""
<style>
.day-section {{
    margin-bottom: 2rem;
    padding-bottom: 1.5rem;
    border-bottom: 2px solid #e2e8f0;
}}
.day-section h3 {{
    color: #2d6fa3;
    font-size: 1.1rem;
    margin-bottom: 0.8rem;
    font-weight: 600;
}}
.day-section h4 {{
    color: #4a5568;
    font-size: 0.9rem;
    margin-top: 0.8rem;
    margin-bottom: 0.4rem;
    font-weight: 600;
}}
.day-section ul {{
    margin: 0;
    padding-left: 1.5rem;
    list-style-type: disc;
}}
.day-section li {{
    margin-bottom: 0.5rem;
    line-height: 1.6;
    color: #333;
    font-size: 0.85rem;
}}
.day-section .tip {{
    margin-top: 1rem;
    padding: 0.6rem;
    background: #f0f9ff;
    border-left: 3px solid #6ec1e4;
    color: #1e3a8a;
    font-size: 0.85rem;
}}
.day-section .budget {{
    margin-top: 0.5rem;
    color: #f9a26c;
    font-weight: 600;
    font-size: 0.85rem;
}}
</style>
{raw_summary}
"""
    
    return jsonify({"summary": styled_output})


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
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.units import inch
            
            pdf_buffer = BytesIO()
            doc = SimpleDocTemplate(pdf_buffer, pagesize=letter, 
                                   rightMargin=72, leftMargin=72,
                                   topMargin=72, bottomMargin=18)
            
            styles = getSampleStyleSheet()
            story = []
            
            # Split content by lines and format
            lines = last_ai_summary.split('\n')
            for line in lines:
                if line.strip():
                    if line.startswith('**') and line.endswith('**'):
                        # Heading
                        story.append(Paragraph(f"<b>{line.strip('*')}</b>", styles['Heading2']))
                    elif line.startswith('•'):
                        # Bullet point
                        story.append(Paragraph(line, styles['Normal']))
                    else:
                        story.append(Paragraph(line, styles['Normal']))
                    story.append(Spacer(1, 0.1*inch))
            
            doc.build(story)
            pdf_buffer.seek(0)
            return send_file(pdf_buffer, as_attachment=True, download_name="TripTactix_Itinerary.pdf", mimetype="application/pdf")
        except Exception as e:
            # Fallback to text
            txt_buffer = BytesIO(last_ai_summary.encode("utf-8"))
            return send_file(txt_buffer, as_attachment=True, download_name="TripTactix_Itinerary.txt", mimetype="text/plain")

if __name__ == "__main__":
    app.run(debug=True)