# Bricksy Android App

Voice-first Android client for the Bricksy vehicle copilot. Emulates vehicle sensors and provides hands-free interaction with the Bricksy agent via speech-to-text and text-to-speech.

## What It Does

- **Sensor emulation**: Input fields for engine temperature, tyre pressures (FL/FR/BL/BR), AC temperature, and fuel level — simulating what OBD-II or CAN bus sensors would provide in a real vehicle
- **Telemetry streaming**: Sends sensor data to Databricks via Zerobus every 5 seconds for near-real-time ingestion into Delta Lake
- **Voice interaction**: Push-to-talk button using Android's `SpeechRecognizer` for STT, with `TextToSpeech` for audio responses
- **Context injection**: Every voice request includes the full telemetry snapshot, user ID, vehicle model, and conversation ID in a single JSON payload
- **Multi-turn sessions**: Maintains conversation context via `conversation_id` for follow-up queries

## Project Structure

```
android-app/
├── app/
│   ├── build.gradle.kts                    # App dependencies (Compose, Material3)
│   └── src/main/
│       ├── AndroidManifest.xml             # Permissions: INTERNET, RECORD_AUDIO
│       ├── java/com/example/bricksy/
│       │   ├── MainActivity.kt             # Main UI (Jetpack Compose) + voice + telemetry
│       │   ├── SplashActivity.kt           # Splash screen
│       │   └── ui/theme/                   # Material 3 theme (Color, Theme, Type)
│       └── res/
│           ├── drawable/                   # Buttons, logos, engine icons
│           ├── layout/                     # XML layouts
│           ├── raw/                        # Engine start/stop audio
│           └── values/                     # Colors, strings, themes
├── build.gradle.kts                        # Root build config
├── settings.gradle.kts                     # Module settings
├── gradle.properties                       # Gradle config
└── gradle/libs.versions.toml               # Version catalogue
```

## Prerequisites

- Android Studio (latest stable)
- JDK 11+
- Android SDK with API level 29+ (Android 10)

## Setup

1. Open `android-app/` in Android Studio
2. Update the **backend endpoint URL** in `MainActivity.kt` to point to your deployed Bricksy agent:
   ```kotlin
   // Replace with your Databricks Model Serving endpoint
   val BACKEND_URL = "https://<your-workspace>.azuredatabricks.net/serving-endpoints/<your-endpoint>/invocations"
   ```
3. Update the **telemetry server URL** for Zerobus ingestion
4. Sync Gradle and build

## Running

- **Emulator**: Use a Pixel device with API 33+ for best results
- **Physical device**: Enable USB debugging, connect via ADB
- Build and run from Android Studio

## Configuration

| Setting | Location | Description |
|---------|----------|-------------|
| Backend URL | `MainActivity.kt` | Bricksy agent endpoint |
| Telemetry URL | `MainActivity.kt` | Zerobus telemetry server |
| Telemetry interval | `MainActivity.kt` | Sensor streaming frequency (default: 5s) |
| Vehicle model | `MainActivity.kt` | Default vehicle for RAG filtering |

## Tech Stack

- **Language**: Kotlin
- **UI**: Jetpack Compose + Material Design 3
- **Voice**: Android `SpeechRecognizer` (STT) + `TextToSpeech` (TTS)
- **Networking**: HTTP client for REST API calls
- **Min SDK**: 29 (Android 10)
- **Target SDK**: 36 (Android 15)
