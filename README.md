# Sub-Trans Manager 🎬

Sub-Trans Manager is a powerful, web-based tool for managing and automatically translating subtitles. It leverages Google Gemini AI to generate high-quality, context-aware translations for your movie and TV series collection.

## 🚀 Key Features

- **AI-Powered Translation**: Uses Gemini (1.5 or 2.0) to translate SRT files with a focus on context and natural dialogue.
- **Smart Chunking**: Processes large subtitle files in optimized blocks (10,000+ characters) for maximum contextual accuracy.
- **Side-by-Side Editor**: A robust SRT editor with a row-based layout, ensuring the original English text and the translation always remain perfectly aligned.
- **Subtitle Audit Tool**: 
  - Scan your entire library for translated files.
  - Automatic language detection (detects "fake" translated files that are actually still English).
  - Bulk deletion of suspicious files.
- **Automation**: Built-in scheduler for daily scans and translation batches.
- **Jellyfin Integration**: Automatic library refresh via webhooks after successful translation.
- **Data Safety**: Automatic backups of both source files (`.en.srt.bak`) and existing translations (`.nl.srt.bak`).

## 🛠 Technology Stack

- **Backend**: Python (FastAPI, APScheduler, Google Generative AI SDK)
- **Frontend**: React (Vite, Lucide-React, Glassmorphism UI)
- **Deployment**: Docker & Docker Compose support

## 📦 Installation & Usage

### Docker (Recommended)

Use the provided `Dockerfile` or Docker Compose to run the container. Ensure you map the following volumes:
- `/Films`: Path to your movie collection.
- `/Series`: Path to your series collection.
- `/app/backend/config`: For persistence of the `settings.json`.

### Configuration

1. Start the application and navigate to **Settings**.
2. Enter your **Gemini API Key** and click "Connect".
3. Select the desired AI model (e.g., `gemini-1.5-flash-latest` or `gemini-2.0-flash`).
4. Set your **Target Language** (default: Dutch) and batch limits.
5. Save the settings.

## 🔍 Audit & Verification

The **Subtitle Audit Tool** allows you to monitor the quality of your translations. The tool uses heuristic analysis to warn you if a translation contains too many English "function words". You can delete these flagged files with a single click, allowing them to be re-translated in the next batch run.

## 📄 License

This project is developed for personal use and subtitle workflow automation.

---
*Created with ❤️ for movie enthusiasts who value high-quality subtitles.*
