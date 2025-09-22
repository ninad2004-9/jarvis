import os
import re
import time
import json
import threading
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import wikipedia
import pyttsx3
import pyjokes
import requests
from dotenv import load_dotenv
import speech_recognition as sr
import sounddevice as sd
import numpy as np

# ============ Setup ============

load_dotenv(override=True)

ASSISTANT_NAME = "jarvis"
LANG = "en"
wikipedia.set_lang(LANG)

engine = pyttsx3.init()
engine.setProperty("rate", 175)
engine.setProperty("volume", 0.9)

recognizer = sr.Recognizer()
recognizer.energy_threshold = 300
recognizer.dynamic_energy_threshold = True
recognizer.pause_threshold = 0.7

REMINDERS_FILE = Path("reminders.txt")
NOTES_FILE = Path("notes.txt")

# ============ Utils ============

def speak(text: str) -> str:
    """Say text aloud in a safe thread and also return it for API use."""
    print(f"[JARVIS]: {text}")

    def run():
        try:
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            print("Speech error:", e)

    threading.Thread(target=run, daemon=True).start()
    return text   # ✅ always return the spoken text

def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())

def remove_wake(text: str) -> str:
    text = clean(text)
    if text.startswith(ASSISTANT_NAME):
        return text.replace(ASSISTANT_NAME, "", 1).strip(",.:- ").strip()
    return text

def internet_ok(timeout=3):
    try:
        requests.get("https://www.google.com", timeout=timeout)
        return True
    except Exception:
        return False

def get_weather(qcity=None):
    key = os.getenv("OPENWEATHER_API_KEY")
    if not key:
        return "Weather needs an OpenWeatherMap API key in your .env."
    city = qcity or os.getenv("CITY", "Mumbai")
    cc = os.getenv("COUNTRY_CODE", "IN")
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city},{cc}&appid={key}&units=metric"
    try:
        r = requests.get(url, timeout=7)
        data = r.json()
        if r.status_code != 200:
            return f"Weather error: {data.get('message','unknown')}"
        desc = data['weather'][0]['description']
        temp = round(data['main']['temp'])
        feels = round(data['main']['feels_like'])
        hum = data['main']['humidity']
        wind = round(data['wind']['speed'])
        return f"Current weather in {city}: {desc}, {temp}°C, feels like {feels}°C, humidity {hum}%, wind {wind} m/s."
    except Exception as e:
        return f"Couldn't fetch weather: {e}"

def wiki_summary(query, sentences=2):
    try:
        return wikipedia.summary(query, sentences=sentences, auto_suggest=True, redirect=True)
    except wikipedia.DisambiguationError as e:
        return f"That’s ambiguous. Options include: {', '.join(e.options[:5])}."
    except wikipedia.PageError:
        return "I couldn't find a relevant article."
    except Exception as e:
        return f"Wikipedia error: {e}"

def open_site_or_search(text):
    sites = {
        "youtube": "https://www.youtube.com",
        "gmail": "https://mail.google.com",
        "google": "https://www.google.com",
        "github": "https://github.com",
        "stackoverflow": "https://stackoverflow.com",
    }
    for key, url in sites.items():
        if key in text:
            webbrowser.open(url)
            return f"Opening {key}."
    webbrowser.open(f"https://www.google.com/search?q={text}")
    return f"Searching the web for {text}."

def open_youtube_search(q):
    webbrowser.open(f"https://www.youtube.com/results?search_query={q}")
    return f"Looking for {q} on YouTube."

def save_note(text):
    NOTES_FILE.write_text((NOTES_FILE.read_text() if NOTES_FILE.exists() else "") + text + "\n", encoding="utf-8")
    return "Saved your note."

def list_notes():
    if not NOTES_FILE.exists():
        return "No notes yet."
    return "Here are your notes:\n" + NOTES_FILE.read_text(encoding="utf-8")

def schedule_reminder(msg, minutes):
    due = datetime.now() + timedelta(minutes=minutes)
    line = f"{due.isoformat()} | {msg}\n"
    with open(REMINDERS_FILE, "a", encoding="utf-8") as f:
        f.write(line)

    def timer():
        time.sleep(minutes * 60)
        speak(f"Reminder: {msg}")

    threading.Thread(target=timer, daemon=True).start()
    return f"Reminder set for {minutes} minute(s) from now."

def check_due_reminders():
    if not REMINDERS_FILE.exists(): 
        return
    remaining = []
    now = datetime.now()
    with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for line in lines:
        try:
            due_str, msg = line.strip().split(" | ", 1)
            due = datetime.fromisoformat(due_str)
            if now >= due:
                speak(f"Reminder: {msg}")
            else:
                remaining.append(line)
        except Exception:
            continue
    with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
        f.writelines(remaining)

# ============ Intent Router ============

def handle_command(cmd: str) -> str:
    if not cmd:
        return "No command detected."

    if re.search(r"\b(hello|hi|hey)\b", cmd):
        return speak("Hello! How can I help?")
    if "how are you" in cmd:
        return speak("Running at optimal parameters!")
    if cmd in {"exit", "quit", "stop", "goodbye", "bye"}:
        return speak("Shutting down. Goodbye.")
    if "time" in cmd:
        return speak(f"It is {datetime.now().strftime('%I:%M %p')}.")
    if "date" in cmd or "day" in cmd:
        return speak(f"Today is {datetime.now().strftime('%A, %d %B %Y')}.")

    m = re.search(r"weather(?: in (?P<city>[\w\s]+))?", cmd)
    if m:
        city = m.group("city").strip() if m.group("city") else None
        return speak(get_weather(city))

    if cmd.startswith(("who is", "what is", "tell me about", "define", "explain")):
        topic = re.sub(r"^(who is|what is|tell me about|define|explain)\s+", "", cmd).strip()
        ans = wiki_summary(topic, sentences=2)
        return speak(ans)

    if cmd.startswith(("open ", "go to ")):
        query = re.sub(r"^(open|go to)\s+", "", cmd)
        return speak(open_site_or_search(query))

    if cmd.startswith(("search ", "google ")):
        query = re.sub(r"^(search|google)\s+", "", cmd)
        return speak(open_site_or_search(query))

    if cmd.startswith(("play ", "youtube ")):
        query = re.sub(r"^(play|youtube)\s+", "", cmd)
        return speak(open_youtube_search(query))

    if cmd.startswith(("note ", "remember ")):
        note = re.sub(r"^(note|remember)\s+", "", cmd)
        return speak(save_note(note))

    if "list notes" in cmd or "show notes" in cmd:
        return speak(list_notes())

    m = re.search(r"remind me in (\d+)\s*(minutes|minute|min)\s*(.*)", cmd)
    if m:
        minutes = int(m.group(1))
        msg = m.group(3).strip() or "No message"
        return speak(schedule_reminder(msg, minutes))

    if "joke" in cmd:
        return speak(pyjokes.get_joke())

    return speak("Sorry, I didn't catch that. Try saying time, weather, Wikipedia, open, search, play, note, or remind.")
