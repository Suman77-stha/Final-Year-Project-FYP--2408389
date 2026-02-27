# ===================== IMPORTS =====================
import datetime
import time
import sys
import wikipedia

import speech_recognition as sr
import pyttsx3
from StockAPI import get_stock_data





# ===================== TEXT TO SPEECH ENGINE =====================
def initialize_engine():
    engine = pyttsx3.init("sapi5")
    voices = engine.getProperty('voices')
    engine.setProperty('voice', voices[1].id)

    rate = engine.getProperty('rate')
    engine.setProperty('rate', rate - 50)

    volume = engine.getProperty('volume')
    engine.setProperty('volume', min(volume + 0.25, 1.0))

    return engine


def Speak(text):
    engine = initialize_engine()
    engine.say(text)
    engine.runAndWait()


# ===================== VOICE COMMAND FUNCTION =====================
def command():
    r = sr.Recognizer()

    with sr.Microphone() as source:
        r.adjust_for_ambient_noise(source, duration=0.5)
        print("Listening.....", end="", flush=True)

        r.pause_threshold = 1
        r.phrase_threshold = 0.3
        r.dynamic_energy_threshold = True
        r.operation_timeout = 5
        r.non_speaking_duration = 0.5
        r.energy_threshold = 4000

        audio = r.listen(source, phrase_time_limit=10)

    try:
        print("\rRecognizing........", end="", flush=True)
        query = r.recognize_google(audio, language='en-NP')
        print(f"\nUser said: {query}\n")

    except Exception:
        Speak("Say that again please")
        print("Say that again please")
        return "none"

    return query


# ===================== WIKIPEDIA SEARCH =====================
def browsing(query):
    Speak("Ok, I am searching")
    try:
        result = wikipedia.summary(query, sentences=3)
        print(result)
        Speak(result)
    except Exception:
        Speak("Sorry, I could not find anything.")


# ===================== CALCULATE DAY =====================
def cal_day():
    day = datetime.datetime.today().weekday() + 1
    day_dict = {
        1: "Monday",
        2: "Tuesday",
        3: "Wednesday",
        4: "Thursday",
        5: "Friday",
        6: "Saturday",
        7: "Sunday",
    }
    return day_dict.get(day)


# ===================== GREETING FUNCTION =====================
def whishMe():
    hour = int(datetime.datetime.now().hour)
    t = time.strftime('%I:%M:%p')
    day = cal_day()

    if hour <= 12:
        Speak(f"Good morning Suman, it's {day} and the time is {t}")
    elif hour <= 16:
        Speak(f"Good afternoon Suman, it's {day} and the time is {t}")
    else:
        Speak(f"Good evening Suman, it's {day} and the time is {t}")

# ===================== STOCK DATA FUNCTION =====================
def stock_data(company_name):
    company_map = {
        "apple": "AAPL",
        "tesla": "TSLA",
        "google": "GOOGL",
        "microsoft": "MSFT"
    }

    for name, symbol in company_map.items():
        if name in company_name:
            Speak(f"Fetching stock price for {name}")
            data = get_stock_data(symbol)

            if data:
                price = data.get("close_price", "Unavailable")
                date = data.get("nepal_dt", "Unknown date")

                Speak(f"The stock price of {name} is {price}")
                print(f"{name.upper()} | Date: {date} | Price: {price}")
            else:
                Speak("Sorry, I could not fetch stock data.")
            return

    Speak("Sorry, this company is not in my stock list.")


# ===================== MAIN PROGRAM =====================
if __name__ == '__main__':

    whishMe()
    Speak("I am your AI voice personal stock price adviser. How can I help you")

    while True:
        # query = command().lower()
        query = str(input("enter ur query"))
        company_list = ['apple', 'tesla', 'google', 'microsoft']

        

        # Wikipedia search
        if ("search" in query) or ("browse" in query) or ("what" in query) or ("how" in query) or ("who" in query):
            browsing(query)

        # Stock search
        
        elif any(company in query for company in company_list):
            stock_data(query)

        elif "exit" in query:
            Speak("Goodbye Suman")
            sys.exit()