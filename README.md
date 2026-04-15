# Sub-Trans Manager 🎬

Sub-Trans Manager is een krachtige, web-gebaseerde tool voor het beheren en automatisch vertalen van ondertitels. Het maakt gebruik van Google Gemini AI om hoogwaardige, context-bewuste vertalingen te genereren voor je film- en seriecollectie.

## 🚀 Hoofdfuncties

- **AI-Aangedreven Vertaling**: Maakt gebruik van Gemini (1.5 of 2.0) om SRT-bestanden te vertalen met oog voor context en natuurlijk taalgebruik.
- **Smart Chunking**: Verwerkt grote ondertitelbestanden in geoptimaliseerde blokken (10.000+ karakters) voor maximale contextuele accuratesse.
- **Side-by-Side Editor**: Een robuuste SRT-editor met een rij-gebaseerde layout, zodat de originele Engelse tekst en de vertaling altijd perfect uitgelijnd blijven.
- **Subtitle Audit Tool**: 
  - Scan je hele bibliotheek op vertaalde bestanden.
  - Automatische taal-detectie (detecteert 'stiekeme' Engelse teksten in Nederlandse bestanden).
  - Bulk-verwijdering van verdachte bestanden.
- **Automatisering**: Ingebouwde scheduler voor dagelijkse scans en vertaal-batches.
- **Jellyfin Integratie**: Automatische bibliotheek-verversing via webhooks na een geslaagde vertaling.
- **Data Veiligheid**: Automatische backups van zowel bronbestanden (`.en.srt.bak`) als bestaande vertalingen (`.nl.srt.bak`).

## 🛠 Technologie Stack

- **Backend**: Python (FastAPI, APScheduler, Google Generative AI SDK)
- **Frontend**: React (Vite, Lucide-React, Tailwind-achtige glassmorphism styling)
- **Deployment**: Docker & Docker Compose support

## 📦 Installatie & Gebruik

### Docker (Aanbevolen)

Gebruik de meegeleverde `Dockerfile` of Docker Compose om de container te draaien. Zorg dat je de volgende volumes koppelt:
- `/Films`: Pad naar je filmcollectie.
- `/Series`: Pad naar je seriecollectie.
- `/app/backend/config`: Voor persistentie van de `settings.json`.

### Configuratie

1. Start de applicatie en navigeer naar **Settings**.
2. Voer je **Gemini API Key** in en klik op "Verbinding Maken".
3. Selecteer het gewenste AI-model (bijv. `gemini-1.5-flash-latest` of `gemini-2.0-flash`).
4. Stel je **Doeltaal** (standaard: Dutch) en batch-limieten in.
5. Sla de instellingen op.

## 🔍 Audit & Controle

Met de **Subtitle Audit Tool** kun je de kwaliteit van je vertalingen bewaken. De tool gebruikt een heuristische analyse om te waarschuwen als een vertaling nog te veel Engelse "stopwoorden" bevat. Je kunt deze gemarkeerde bestanden met één druk op de knop verwijderen, waarna ze in de volgende batch-ronde opnieuw worden opgepakt.

## 📄 Licentie

Dit project is ontwikkeld voor eigen gebruik en automatisering van ondertitel-workflows.

---
*Gemaakt met ❤️ voor filmliefhebbers die houden van goede ondertiteling.*
