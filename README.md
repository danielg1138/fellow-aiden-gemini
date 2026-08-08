# Fellow Aiden (Gemini & Grinder Edition)

> 📌 **Fork Information**: This repository is an enhanced fork of [`9b/fellow-aiden`](https://github.com/9b/fellow-aiden). It expands the Brew Studio with Google Gemini Vision AI, home grinder calibration presets, and mobile phone pairing.

[![PyPI version](https://badge.fury.io/py/fellow-aiden.svg)](https://badge.fury.io/py/fellow-aiden)

This library provides an interface to the Fellow Aiden coffee brewer. An additional brew studio UI with support for AI-generated recipes is also included.

![Fellow Brew Studio](https://github.com/9b/fellow-aiden/blob/master/brew_studio/fellow-brew-studio.png?raw=true)

---

## ⚡ Device Support & Status Matrix

| Device | Status | Cloud REST API Support | Notes |
| :--- | :---: | :---: | :--- |
| **Fellow Aiden (Pour-Over)** | ✅ **Fully Supported** | Full Read/Write (`GET/POST /v1/devices/{id}/profiles`) | Wi-Fi profile sync, schedule management, instant cloud profile creation & `brew.link` shortcode generation. |
| **Fellow Espresso Series 1** | 🧪 **Experimental / WIP** | Cloud Library Read (`GET /v1/profiles`), BLE Mobile Sync | Cloud recipe library discovery (8,900+ recipes) and AI shot parameter generation. *Note: Custom profile creation on Series 1 requires Bluetooth (BLE) sync via the official Fellow Mobile App.* |

> [!NOTE]  
> **Espresso Series 1 Notice**: Fellow's cloud API permits third-party REST profile uploads for Aiden over Wi-Fi, but restricts custom Series 1 profile creation to local Bluetooth Low Energy (BLE) syncing inside the official Fellow mobile app. Brew Studio provides AI shot parameter generation, grinder dial setting recommendations, recipe summaries, and QR code cards to assist manual or app entry.

---

## 🚀 Fork Features & Key Differences

Compared to the original [`9b/fellow-aiden`](https://github.com/9b/fellow-aiden), this fork includes:

### 1. ⚙️ Grinder Presets & AI Grind Size Recommendations
- **Grinder Selection**: Choose your exact home grinder from the Brew Studio sidebar:
  - *Fellow Ode (Gen 2)*
  - *Fellow Ode (Gen 1)*
  - *Baratza Encore / Virtuoso*
  - *Comandante C40*
  - *1Zpresso K-Series*
  - *Timemore C2/C3*
  - *Niche Zero*
  - *Generic / Microns*
- **AI Physics Engine**: Gemini analyzes roast density, bean process (washed, natural, anaerobic), and altitude to recommend the exact dial setting number.
- **Grind Banner UI**: Displays a dedicated grind recommendation banner at the top of the Brew Profile editor.
- **Preferences**: Save your default grinder via `PREFERRED_GRINDER` in environment variables or `.streamlit/secrets.toml`.

### 2. 📷 Google Gemini Vision & Gem Integration
- **Coffee Bag Photo Scanning**: Upload or take a picture of any coffee bag label with your camera. Gemini Vision automatically reads the roaster name, origin, process, and tasting notes to design an optimal pour-over profile.
- **Gemini 2.5 Flash**: Support for Gemini API Key mode and Gem/Prompt mode alongside OpenAI models.

### 3. 📱 Mobile Phone Pairing & QR Code Generator
- Built-in QR code generator in the Brew Studio sidebar that detects your local network IP (`http://<local-ip>:8501`) so you can open and control Brew Studio from your phone camera instantly.

### 4. 🔑 Streamlit Secrets Auto-Connect
- Auto-loads `FELLOW_EMAIL`, `FELLOW_PASSWORD`, `GEMINI_API_KEY`, and `PREFERRED_GRINDER` from Streamlit secrets or environment variables for seamless startup without re-entering credentials.

---

## Quick Start

**Install requirements and package**:

```sh
# Create virtual environment (Windows)
py -m venv venv
.\venv\Scripts\activate

# Install requirements & fellow-aiden in editable mode
pip install -e . streamlit openai google-genai qrcode pillow
```

**Set Environment Variables or Secrets**:

```sh
export FELLOW_EMAIL='YOUR-EMAIL-HERE'
export FELLOW_PASSWORD='YOUR-PASSWORD-HERE'
export GEMINI_API_KEY='YOUR-GEMINI-KEY-HERE'
export PREFERRED_GRINDER='Niche Zero'
```

**Run Brew Studio**:

```sh
streamlit run brew_studio/brew_studio.py
```

---

## Original Sample Code

This sample code shows the core library functionality:

```python
import os
from fellow_aiden import FellowAiden

EMAIL = os.environ['FELLOW_EMAIL']
PASSWORD = os.environ['FELLOW_PASSWORD']

# Create an instance
aiden = FellowAiden(EMAIL, PASSWORD)

# Get display name of brewer
name = aiden.get_display_name()

# Get profiles
profiles = aiden.get_profiles()

# Add a profile
profile = {
    "profileType": 0,
    "title": "Debug-FellowAiden",
    "ratio": 16,
    "bloomEnabled": True,
    "bloomRatio": 2,
    "bloomDuration": 30,
    "bloomTemperature": 96,
    "ssPulsesEnabled": True,
    "ssPulsesNumber": 3,
    "ssPulsesInterval": 23,
    "ssPulseTemperatures": [96,97,98],
    "batchPulsesEnabled": True,
    "batchPulsesNumber": 2,
    "batchPulsesInterval": 30,
    "batchPulseTemperatures": [96,97]
}
aiden.create_profile(profile)

# Find profile
pid = None
option = aiden.get_profile_by_title('FellowAiden', fuzzy=True)
if option:
    pid = option['id']

# Share a profile
share_link = aiden.generate_share_link(pid)

# Delete a profile
aiden.delete_profile_by_id(pid)

# Add profile from shared brew link
aiden.create_profile_from_link('https://brew.link/p/ws98')

# Add a schedule
schedule = {
    "days": [True, True, False, True, False, True, False],
    "secondFromStartOfTheDay": 28800,
    "enabled": True,
    "amountOfWater": 950,
    "profileId": "p7",
}
aiden.create_schedule(schedule)

# Delete a schedule
aiden.delete_schedule_by_id('s0')
```

---

## Features

* Access all settings and details from Fellow Aiden brewer
* Manage custom brewing profiles
* Add shared profiles from URL
* Generate share links from custom profiles
* Search profiles using title (match and fuzzy)
* Manage custom brewing schedules
* Brew Studio UI with support for Gemini Vision, Grinder Presets, Brew Links, and Mobile Pairing
