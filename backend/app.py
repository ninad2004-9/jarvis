import sys
import os
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

# Make sure Python can see jarvis.py
sys.path.append(os.path.dirname(__file__))

from jarvis import handle_command, remove_wake, ASSISTANT_NAME

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)  # allow frontend requests if needed

# Serve frontend
@app.route("/")
def home():
    return render_template("jarvis.html")

# API for commands
@app.route("/command", methods=["POST"])
def command():
    data = request.json or {}
    text = data.get("text", "")
    cmd = remove_wake(text) if ASSISTANT_NAME.lower() in text.lower() else text
    response_text = handle_command(cmd)
    return jsonify({"response": response_text})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
