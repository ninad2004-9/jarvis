import sys
import os
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import json
from datetime import datetime

# Make sure Python can see jarvis.py
sys.path.append(os.path.dirname(__file__))

from jarvis import handle_command, remove_wake, ASSISTANT_NAME

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)  # allow frontend requests if needed

# Path to reminders file
REMINDERS_FILE = os.path.join(os.path.dirname(__file__), "reminders.json")

# Helper functions for reminders
def load_reminders():
    if os.path.exists(REMINDERS_FILE):
        with open(REMINDERS_FILE, 'r') as f:
            return json.load(f)
    return []

def save_reminders(reminders):
    with open(REMINDERS_FILE, 'w') as f:
        json.dump(reminders, f, indent=2)

# Serve frontend
@app.route("/")
def home():
    return render_template("jarvis.html")

# API for voice commands
@app.route("/command", methods=["POST"])
def command():
    data = request.json or {}
    text = data.get("text", "")
    cmd = remove_wake(text) if ASSISTANT_NAME.lower() in text.lower() else text
    response_text = handle_command(cmd)
    return jsonify({"response": response_text})

# API for reminders - Get all reminders
@app.route("/api/reminders", methods=["GET"])
def get_reminders():
    reminders = load_reminders()
    return jsonify({"reminders": reminders})

# API for reminders - Add a new reminder
@app.route("/api/reminders", methods=["POST"])
def add_reminder():
    data = request.json or {}
    title = data.get("title")
    note = data.get("note", "")
    time = data.get("time")
    
    if not title or not time:
        return jsonify({"error": "Title and time are required"}), 400
    
    reminders = load_reminders()
    
    new_reminder = {
        "id": int(datetime.now().timestamp() * 1000),
        "title": title,
        "note": note,
        "time": time
    }
    
    reminders.append(new_reminder)
    save_reminders(reminders)
    
    return jsonify({"success": True, "reminder": new_reminder})

# API for reminders - Delete a reminder
@app.route("/api/reminders/<int:reminder_id>", methods=["DELETE"])
def delete_reminder(reminder_id):
    reminders = load_reminders()
    reminders = [r for r in reminders if r["id"] != reminder_id]
    save_reminders(reminders)
    
    return jsonify({"success": True})

if __name__ == "__main__":
    app.run(debug=True, port=5000)