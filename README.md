# Nova — Desktop Voice Assistant

Nova is a modular desktop voice assistant designed for Windows. It combines deterministic command routing for local applications and system controls with rule-based offline conversation, dual-mode text/speech synthesis, continuous microphone capture, and strict security isolation.

---

## 🌟 Core Features

- **Continuous Listening & Auto-Listen Loop**:
  - Hands-free microphone capture with `speech_recognition` and Google STT.
  - Automatic ambient room calibration (`adjust_for_ambient_noise`).
  - Configurable speech timeouts (`SPEECH_TIMEOUT`) and phrase limits (`SPEECH_PHRASE_LIMIT`).
  - Speech synthesis echo prevention: microphone input automatically pauses during TTS playback to avoid audio feedback loops.
  - Desktop mode starts with spoken replies and continuous listening enabled; both can be changed from the sidebar.
- **Offline Text-to-Speech (TTS)**:
  - Natural speech playback powered by `pyttsx3` (Windows SAPI5).
  - Configurable speech rate and volume.
  - Automatic fallback to console or UI display if audio hardware is unavailable.
- **Deterministic Action Router**:
  - Over 25 pre-registered, allowlisted local desktop and web commands.
  - Local execution without sending commands to a conversational model.
- **YouTube Music & Video Discovery**:
  - Robust intent extraction cleanly isolating song titles from polite phrasing (e.g., *"Play song Believer on YouTube"* cleanly resolves to `Believer`).
- **Safe WhatsApp Integration**:
  - Automatically parses recipients and messages (e.g., *"send whatsapp message to Sarah saying see you soon"*).
  - Explicit confirmation gate before opening the chat.
  - Truthful communication: Nova launches the prefilled chat and directs the user to review and send, never claiming the message was already delivered.
- **Safe System Power Management**:
  - Controlled laptop/PC shutdown (`shutdown /s /t 15`) and restart (`shutdown /r /t 15`).
  - Mandatory confirmation gate: system power actions are aborted unless explicitly approved by the user.
  - Emergency cancellation support (`"cancel shutdown"` invokes `shutdown /a`).
- **Interactive Multi-Mode Interface**:
  - **Modern CustomTkinter GUI** with dark glassmorphic design, reactive status indicators, audio toggle switches, and recent command history.
  - **Voice Mode**: Full hands-free voice loop via microphone and speaker.
  - **Text CLI Mode**: Terminal keyboard loop with zero audio hardware requirement.

In desktop mode, Nova starts listening automatically when a microphone is available. Speak naturally for
supported computer commands or simple conversation, and Nova will speak its response before listening again.
General knowledge, writing, and open-ended reasoning are not supported offline; Nova says so instead of guessing.
- **Enterprise Security & Secret Scrubbing**:
  - Strict keyword blacklist prevents destructive filesystem operations (`format`, `delete`, `wipe`, `rmdir`).
  - API keys and high-entropy secrets are automatically scrubbed from logs and voice responses.
  - `.env` and log artifacts are protected by `.gitignore`.

---

## 📋 Prerequisites & Installation

### 1. Requirements
- **OS**: Windows 10 or Windows 11 (64-bit)
- **Python**: Python 3.10 or 3.11 recommended
- **Hardware**: Working microphone and speakers / headphones

### 2. Create a Virtual Environment (Windows PowerShell)

```powershell
# Navigate to the project directory
cd "c:\Users\2k22c\Downloads\VoxAI — Voice Assistant"

# Create and activate an isolated environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Upgrade pip
python -m pip install --upgrade pip

# Install dependencies, including SpeechRecognition and PyAudio
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, use `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` for the current terminal only, or run `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` without activating. PyAudio needs a working Windows audio input device. If its installation fails, use a Python version supported by the PyAudio wheels and retry `python -m pip install PyAudio`; avoid downloading wheels from unofficial sources.

---

## ⚙️ Configuration & Environment Variables

Copy the sample configuration and add an OpenWeather key only if you want live weather results. Local commands, rule-based responses, and text-to-speech need no conversational AI key.

```powershell
if (!(Test-Path ".env")) { Copy-Item .env.example .env }
notepad ".env"
```

`OPENWEATHER_API_KEY` is optional and only needed for live weather results. Speech recognition uses Google's online speech-to-text service and needs an internet connection; this is separate from conversational AI. Weather, Wikipedia, and web search also need internet access for live results.

The `.env.example` file lists the supported settings. Voice input uses `SPEECH_LANGUAGE`, `SPEECH_TIMEOUT`, `SPEECH_PHRASE_LIMIT`, and `SPEECH_RECOGNITION_TIMEOUT`; speech output uses `TTS_RATE` and `TTS_VOLUME`. Defaults allow a 7-second start wait, a 20-second phrase, and a 15-second recognition service timeout. The default input language is `en-IN`.

---

## 🚀 Launch Modes

Nova supports three distinct execution modes:

### 1. Desktop GUI Mode (Default)
Launches the modern CustomTkinter interface with sidebar controls, real-time status banner, conversation chat view, and history drawer:
```powershell
python app.py
# or explicitly
python app.py --gui
```
- **🔊 Voice Speech switch**: Toggle TTS voice synthesis on/off.
- **🔁 Continuous Mic switch**: Keep voice conversations going across follow-up turns; turn it off to stop continuous listening.
- **🎤 Mic button**: Start or stop a voice capture. Recognized words appear as a chat message before Nova processes them.

### 2. Voice-Only Mode (Microphone + TTS)
Runs continuous voice loop in the terminal:
```powershell
python app.py --voice
```
- Speaks responses aloud.
- Listens continuously for user queries.
- Recovers automatically from silence or unrecognized speech.
- Exit anytime by saying *"goodbye"*, *"exit"*, or pressing `Ctrl+C`.

### 3. Text CLI Mode (Keyboard Only)
Runs an interactive text prompt for headless or non-audio environments:
```powershell
python app.py --text
```
- Prompts for input via keyboard (`You > `).
- Outputs responses cleanly in text format.
- Exit by typing `exit`, `quit`, or pressing `Ctrl+C`.

---

## 🗣️ Voice Commands Reference

| Category | Example Voice Commands | Action |
| :--- | :--- | :--- |
| **Media & YouTube** | *"Play Believer"*<br>*"Play song Believer on YouTube"*<br>*"Can you please open a song on YouTube?"*<br>*"Play Despacito"* | Extracts exact title and launches YouTube search results. |
| **Communication** | *"Send WhatsApp message to Sarah saying see you soon"*<br>*"Open WhatsApp chat with Rahul"* | Confirms with user, then opens WhatsApp Web/app with prefilled text. |
| **Applications** | *"Open Google Chrome"*<br>*"Open VS Code"*<br>*"Launch Notepad"*<br>*"Open Calculator"*<br>*"Open Spotify"* | Launches desktop application or opens web fallback. |
| **System Info** | *"What time is it?"*<br>*"What is today's date?"* | Reports exact formatted system time and date. |
| **System Power** | *"Shutdown my laptop"*<br>*"Restart my computer"*<br>*"Cancel shutdown"*<br>*"Lock screen"* | Prompts confirmation, schedules 15s timer, allows cancellation, or locks PC. |
| **Folders** | *"Open Downloads folder"*<br>*"Open Documents"*<br>*"Open Desktop"* | Opens Windows Explorer directly to the target folder. |
| **Web & Knowledge** | *"Search Google for Python tutorials"*<br>*"Who is Alan Turing?"*<br>*"What is the weather in Delhi?"* | Runs Google search, queries Wikipedia REST API, or fetches live weather. |
| **Local Conversation** | *"Hello Nova"*<br>*"What can you do?"*<br>*"Tell me a joke"* | Handles simple patterns locally. Unsupported questions receive an explicit offline limitation. |

---

## 🧪 Testing & Verification

Nova includes automated tests with mocks for microphone, speakers, system commands, and browser actions:

```powershell
# Run the complete test suite
pytest -v

# Run with short test output
pytest -q

# Run specific command regression tests
pytest tests/test_commands.py -v
```

The GUI keeps microphone capture, command processing, and speech synthesis off the UI thread. Silence and unclear speech are retried during continuous listening; microphone and recognition-service failures stop auto-listening and show recovery guidance. The microphone is not reopened until the previous capture worker has exited.

---

## ⚠️ Known Limitations & Troubleshooting

1. **WhatsApp Delivery**:
   - Nova prepares messages via WhatsApp Web (`web.whatsapp.com`) or desktop URL protocol (`wa.me`). Due to WhatsApp's end-to-end encryption and user security policies, Nova cannot simulate physical keyboard keystrokes to press the Send button automatically. Nova pre-fills the message and asks the user to confirm sending.
2. **Microphone Hardware Permissions**:
   - If Nova reports `"No functional microphone detected"`, ensure microphone permissions are granted under **Windows Settings > Privacy & Security > Microphone**.
3. **PyAudio Device Errors**:
   - If `OSError: -9996` or similar audio device error occurs, check that a valid default recording device is selected in the Windows Sound Control Panel.
4. **Offline TTS COM Apartment**:
   - `pyttsx3` uses Windows SAPI5. When running inside multi-threaded GUI environments, TTS operations are safely executed within worker threads. In rare instances where COM threading conflicts arise, Nova automatically logs the warning and continues via text output.
5. **Offline conversation**:
   - Nova supports common greetings, help, identity, and a small set of canned responses locally. It cannot answer general knowledge or open-ended questions; use supported desktop commands or web search for information.
