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
    last_ai_summary = generate_with_groq(prompt)
    return jsonify({"summary": last_ai_summary})


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
