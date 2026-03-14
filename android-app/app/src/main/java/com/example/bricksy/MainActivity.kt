package com.example.bricksy

import android.Manifest
import android.content.Context
import android.content.SharedPreferences
import android.content.pm.PackageManager
import android.content.Intent
import android.media.MediaPlayer
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.view.MotionEvent
import android.view.View
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.EditText
import android.widget.ImageButton
import android.widget.Spinner
import android.widget.TextView
import android.speech.tts.TextToSpeech
import androidx.activity.ComponentActivity
import androidx.activity.result.ActivityResultLauncher
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import java.io.InputStream
import java.net.HttpURLConnection
import java.net.URL
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.UUID
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import org.json.JSONArray
import org.json.JSONObject

class MainActivity : ComponentActivity() {
    private lateinit var tpmsFrontLeftInput: EditText
    private lateinit var tpmsFrontRightInput: EditText
    private lateinit var tpmsBackRightInput: EditText
    private lateinit var tpmsBackLeftInput: EditText
    private lateinit var acTemperatureInput: EditText
    private lateinit var engineTemperatureInput: EditText
    private lateinit var driverNameInput: EditText
    private lateinit var vehicleSpinner: Spinner
    private lateinit var voiceButton: Button
    private lateinit var diagnoseButton: Button
    private lateinit var newSessionButton: Button
    private lateinit var engineToggleButton: ImageButton
    private lateinit var outputText: TextView
    private lateinit var sessionId: String
    private val backgroundExecutor: ExecutorService = Executors.newSingleThreadExecutor()
    private val mainHandler: Handler = Handler(Looper.getMainLooper())
    private var speechRecognizer: SpeechRecognizer? = null
    private var isSpeechRecognitionActive: Boolean = false
    private var isVoiceStartPending: Boolean = false
    private var textToSpeech: TextToSpeech? = null
    private var isTextToSpeechReady: Boolean = false
    private var isEngineRunning: Boolean = false
    private var engineStartSound: MediaPlayer? = null
    private var engineStopSound: MediaPlayer? = null
    private var zerobusAccessToken: String? = null
    private var zerobusTokenExpiryTime: Long = 0
    private val telemetryRunnable: Runnable = object : Runnable {
        override fun run(): Unit {
            if (isEngineRunning) {
                sendTelemetryDataViaZerobus()
                mainHandler.postDelayed(this, TELEMETRY_INTERVAL_MS)
            }
        }
    }
    private val microphonePermissionLauncher: ActivityResultLauncher<String> = registerForActivityResult(ActivityResultContracts.RequestPermission()) { isGranted: Boolean ->
        if (!isGranted) {
            isVoiceStartPending = false
            updateOutputText(getString(R.string.output_permission_denied))
            return@registerForActivityResult
        }
        if (isVoiceStartPending) {
            isVoiceStartPending = false
            startSpeechRecognition()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?): Unit {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        initializeSession()
        initializeTextToSpeech()
        initializeSpeechRecognizer()
        initializeEngineSounds()
        initializeViews()
        bindActions()
        displaySessionId()
    }

    private fun initializeEngineSounds(): Unit {
        engineStartSound = MediaPlayer.create(this, R.raw.engine_start)
        engineStopSound = MediaPlayer.create(this, R.raw.engine_stop)
    }

    private fun releaseEngineSounds(): Unit {
        engineStartSound?.release()
        engineStartSound = null
        engineStopSound?.release()
        engineStopSound = null
    }

    private fun playEngineStartSound(): Unit {
        engineStartSound?.let { player ->
            if (player.isPlaying) {
                player.seekTo(0)
            }
            player.start()
        }
    }

    private fun playEngineStopSound(): Unit {
        engineStopSound?.let { player ->
            if (player.isPlaying) {
                player.seekTo(0)
            }
            player.start()
        }
    }

    private fun initializeSession(): Unit {
        val prefs: SharedPreferences = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val storedSessionId: String? = prefs.getString(KEY_SESSION_ID, null)
        if (storedSessionId.isNullOrBlank()) {
            sessionId = generateNewSessionId()
            saveSessionId(sessionId)
        } else {
            sessionId = storedSessionId
        }
    }

    private fun generateNewSessionId(): String {
        return UUID.randomUUID().toString()
    }

    private fun saveSessionId(id: String): Unit {
        val prefs: SharedPreferences = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit().putString(KEY_SESSION_ID, id).apply()
    }

    private fun startNewSession(): Unit {
        sessionId = generateNewSessionId()
        saveSessionId(sessionId)
        updateOutputText(getString(R.string.output_new_session, sessionId))
    }

    private fun displaySessionId(): Unit {
        appendOutputText(getString(R.string.output_session_id, sessionId))
    }

    override fun onDestroy(): Unit {
        stopZerobusStream()
        backgroundExecutor.shutdown()
        shutdownTextToSpeech()
        shutdownSpeechRecognizer()
        releaseEngineSounds()
        super.onDestroy()
    }

    private fun initializeViews(): Unit {
        tpmsFrontLeftInput = findViewById(R.id.input_tpms_front_left)
        tpmsFrontRightInput = findViewById(R.id.input_tpms_front_right)
        tpmsBackRightInput = findViewById(R.id.input_tpms_back_right)
        tpmsBackLeftInput = findViewById(R.id.input_tpms_back_left)
        acTemperatureInput = findViewById(R.id.input_ac_temperature)
        engineTemperatureInput = findViewById(R.id.input_engine_temperature)
        driverNameInput = findViewById(R.id.input_driver_name)
        vehicleSpinner = findViewById(R.id.spinner_vehicle)
        voiceButton = findViewById(R.id.button_voice_record)
        diagnoseButton = findViewById(R.id.button_diagnose)
        newSessionButton = findViewById(R.id.button_new_session)
        engineToggleButton = findViewById(R.id.button_engine_toggle)
        outputText = findViewById(R.id.output_text)
        initializeVehicleSpinner()
        applyDefaultValues()
    }

    private fun initializeVehicleSpinner(): Unit {
        val adapter: ArrayAdapter<CharSequence> = ArrayAdapter.createFromResource(
            this,
            R.array.vehicle_options,
            android.R.layout.simple_spinner_item
        )
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item)
        vehicleSpinner.adapter = adapter
        vehicleSpinner.setSelection(0)
    }

    private fun applyDefaultValues(): Unit {
        tpmsFrontLeftInput.setText(DEFAULT_TPMS_VALUE)
        tpmsFrontRightInput.setText(DEFAULT_TPMS_VALUE)
        tpmsBackRightInput.setText(DEFAULT_TPMS_VALUE)
        tpmsBackLeftInput.setText(DEFAULT_TPMS_VALUE)
        acTemperatureInput.setText(DEFAULT_AC_TEMPERATURE)
        engineTemperatureInput.setText(DEFAULT_ENGINE_TEMPERATURE)
        driverNameInput.setText(DEFAULT_DRIVER_NAME)
    }

    private fun bindActions(): Unit {
        voiceButton.setOnTouchListener { _: View, event: MotionEvent ->
            if (event.action == MotionEvent.ACTION_DOWN) {
                handleVoiceButtonPressed()
                return@setOnTouchListener true
            }
            if (event.action == MotionEvent.ACTION_UP || event.action == MotionEvent.ACTION_CANCEL) {
                handleVoiceButtonReleased()
                return@setOnTouchListener true
            }
            false
        }
        diagnoseButton.setOnClickListener {
            val inputValues: DiagnoseInput? = readDiagnoseInput()
            if (inputValues == null) {
                return@setOnClickListener
            }
            executeDiagnoseRequest(inputValues)
        }
        newSessionButton.setOnClickListener { startNewSession() }
        engineToggleButton.setOnClickListener { toggleEngine() }
    }

    private fun toggleEngine(): Unit {
        isEngineRunning = !isEngineRunning
        if (isEngineRunning) {
            engineToggleButton.setImageResource(R.drawable.engine_on)
            playEngineStartSound()
            appendOutputText(getString(R.string.output_engine_started))
            startZerobusStream()
        } else {
            engineToggleButton.setImageResource(R.drawable.engine_off)
            playEngineStopSound()
            appendOutputText(getString(R.string.output_engine_stopped))
            stopZerobusStream()
        }
    }

    private fun startZerobusStream(): Unit {
        appendOutputText("Telemetry streaming started (Zerobus REST API)")
        backgroundExecutor.execute {
            try {
                fetchZerobusOAuthTokenIfNeeded()
                mainHandler.post(telemetryRunnable)
            } catch (err: Exception) {
                appendOutputText("Failed to start telemetry: ${err.message}")
            }
        }
    }

    private fun stopZerobusStream(): Unit {
        mainHandler.removeCallbacks(telemetryRunnable)
        appendOutputText("Telemetry streaming stopped")
    }

    private fun fetchZerobusOAuthTokenIfNeeded(): Unit {
        val currentTime: Long = System.currentTimeMillis()
        if (zerobusAccessToken != null && currentTime < zerobusTokenExpiryTime) {
            return
        }
        val tokenUrl: String = "$DATABRICKS_HOST/oidc/v1/token"
        val authDetails: JSONArray = JSONArray()
        val catalogPrivilege: JSONObject = JSONObject()
        catalogPrivilege.put("type", "unity_catalog_privileges")
        catalogPrivilege.put("privileges", JSONArray().put("USE CATALOG"))
        catalogPrivilege.put("object_type", "CATALOG")
        catalogPrivilege.put("object_full_path", ZEROBUS_CATALOG)
        authDetails.put(catalogPrivilege)
        val schemaPrivilege: JSONObject = JSONObject()
        schemaPrivilege.put("type", "unity_catalog_privileges")
        schemaPrivilege.put("privileges", JSONArray().put("USE SCHEMA"))
        schemaPrivilege.put("object_type", "SCHEMA")
        schemaPrivilege.put("object_full_path", "$ZEROBUS_CATALOG.$ZEROBUS_SCHEMA")
        authDetails.put(schemaPrivilege)
        val tablePrivilege: JSONObject = JSONObject()
        tablePrivilege.put("type", "unity_catalog_privileges")
        tablePrivilege.put("privileges", JSONArray().put("SELECT").put("MODIFY"))
        tablePrivilege.put("object_type", "TABLE")
        tablePrivilege.put("object_full_path", TELEMETRY_TABLE_NAME)
        authDetails.put(tablePrivilege)
        val requestBody: String = "grant_type=client_credentials" +
                "&scope=all-apis" +
                "&resource=api://databricks/workspaces/$ZEROBUS_WORKSPACE_ID/zerobusDirectWriteApi" +
                "&authorization_details=${java.net.URLEncoder.encode(authDetails.toString(), "UTF-8")}"
        val url: URL = URL(tokenUrl)
        val connection: HttpURLConnection = url.openConnection() as HttpURLConnection
        connection.requestMethod = "POST"
        connection.setRequestProperty("Content-Type", "application/x-www-form-urlencoded")
        val credentials: String = "$ZEROBUS_CLIENT_ID:$ZEROBUS_CLIENT_SECRET"
        val encodedCredentials: String = android.util.Base64.encodeToString(credentials.toByteArray(Charsets.UTF_8), android.util.Base64.NO_WRAP)
        connection.setRequestProperty("Authorization", "Basic $encodedCredentials")
        connection.connectTimeout = NETWORK_TIMEOUT_MS
        connection.readTimeout = NETWORK_TIMEOUT_MS
        connection.doOutput = true
        connection.outputStream.use { stream -> stream.write(requestBody.toByteArray(Charsets.UTF_8)) }
        val responseText: String = readHttpResponse(connection)
        if (connection.responseCode != 200) {
            throw Exception("OAuth token fetch failed: $responseText")
        }
        val responseJson: JSONObject = JSONObject(responseText)
        zerobusAccessToken = responseJson.getString("access_token")
        val expiresIn: Long = responseJson.optLong("expires_in", 3600)
        zerobusTokenExpiryTime = currentTime + (expiresIn * 1000) - 60000
        appendOutputText("Zerobus OAuth token acquired")
    }

    private fun sendTelemetryDataViaZerobus(): Unit {
        val inputValues: DiagnoseInput? = readDiagnoseInputSilent()
        if (inputValues == null) {
            return
        }
        val sendTimestamp: String = SimpleDateFormat("HH:mm:ss", Locale.getDefault()).format(Date())
        appendOutputText(getString(R.string.output_telemetry_sent, sendTimestamp))
        backgroundExecutor.execute {
            try {
                fetchZerobusOAuthTokenIfNeeded()
                val token: String = zerobusAccessToken ?: throw Exception("No Zerobus token available")
                val endpoint: String = "$ZEROBUS_URI/ingest-record?table_name=$TELEMETRY_TABLE_NAME"
                val url: URL = URL(endpoint)
                val connection: HttpURLConnection = url.openConnection() as HttpURLConnection
                connection.requestMethod = "POST"
                connection.setRequestProperty("Content-Type", "application/json")
                connection.setRequestProperty("Authorization", "Bearer $token")
                connection.setRequestProperty("unity-catalog-endpoint", DATABRICKS_HOST)
                connection.setRequestProperty("x-databricks-zerobus-table-name", TELEMETRY_TABLE_NAME)
                connection.connectTimeout = ZEROBUS_TIMEOUT_MS
                connection.readTimeout = ZEROBUS_TIMEOUT_MS
                connection.doOutput = true
                val timestampMicros: Long = System.currentTimeMillis() * 1000
                val payload: JSONObject = JSONObject()
                payload.put("timestamp", timestampMicros)
                payload.put("ac_temp", inputValues.acTemperature)
                payload.put("engine_temp", inputValues.engineTemperature)
                payload.put("tpms_fl", inputValues.tpmsFrontLeft.toInt())
                payload.put("tpms_fr", inputValues.tpmsFrontRight.toInt())
                payload.put("tpms_bl", inputValues.tpmsBackLeft.toInt())
                payload.put("tpms_br", inputValues.tpmsBackRight.toInt())
                connection.outputStream.use { stream -> stream.write(payload.toString().toByteArray(Charsets.UTF_8)) }
                val responseCode: Int = connection.responseCode
                if (responseCode !in 200..204) {
                    val responseText: String = readHttpResponse(connection)
                    appendOutputText("Telemetry error ($responseCode): $responseText")
                }
            } catch (err: Exception) {
                appendOutputText("Telemetry error: ${err.message}")
            }
        }
    }

    private fun readDiagnoseInputSilent(): DiagnoseInput? {
        val tpmsFrontLeft: Double = tpmsFrontLeftInput.text.toString().trim().toDoubleOrNull() ?: return null
        val tpmsFrontRight: Double = tpmsFrontRightInput.text.toString().trim().toDoubleOrNull() ?: return null
        val tpmsBackRight: Double = tpmsBackRightInput.text.toString().trim().toDoubleOrNull() ?: return null
        val tpmsBackLeft: Double = tpmsBackLeftInput.text.toString().trim().toDoubleOrNull() ?: return null
        val acTemperature: Double = acTemperatureInput.text.toString().trim().toDoubleOrNull() ?: return null
        val engineTemperature: Double = engineTemperatureInput.text.toString().trim().toDoubleOrNull() ?: return null
        return DiagnoseInput(tpmsFrontLeft, tpmsFrontRight, tpmsBackRight, tpmsBackLeft, acTemperature, engineTemperature)
    }

    private fun handleVoiceButtonPressed(): Unit {
        if (isSpeechRecognitionActive) {
            return
        }
        if (hasAudioPermission()) {
            startSpeechRecognition()
            return
        }
        isVoiceStartPending = true
        requestMicrophonePermission()
    }

    private fun handleVoiceButtonReleased(): Unit {
        if (!isSpeechRecognitionActive) {
            return
        }
        stopSpeechRecognition()
    }

    private fun hasAudioPermission(): Boolean {
        val permissionState: Int = ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
        return permissionState == PackageManager.PERMISSION_GRANTED
    }

    private fun requestMicrophonePermission(): Unit {
        microphonePermissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
    }

    private fun initializeSpeechRecognizer(): Unit {
        speechRecognizer = SpeechRecognizer.createSpeechRecognizer(this)
        speechRecognizer?.setRecognitionListener(object : RecognitionListener {
            override fun onReadyForSpeech(params: Bundle?): Unit {
                appendOutputText(getString(R.string.output_recording_started))
            }

            override fun onResults(results: Bundle?): Unit {
                isSpeechRecognitionActive = false
                val matches: ArrayList<String> = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION) ?: arrayListOf()
                if (matches.isEmpty()) {
                    appendOutputText(getString(R.string.output_missing_voice))
                    return
                }
                val recognizedText: String = matches.first()
                appendOutputText(getString(R.string.output_speech_recognized, recognizedText))
                executeSpeechTextRequest(recognizedText)
            }

            override fun onError(error: Int): Unit {
                isSpeechRecognitionActive = false
                val errorMessage: String = when (error) {
                    SpeechRecognizer.ERROR_NO_MATCH -> "No speech detected. Please speak clearly and try again."
                    SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "No speech input. Please try again."
                    SpeechRecognizer.ERROR_NETWORK -> "Network error. Check your internet connection."
                    SpeechRecognizer.ERROR_NETWORK_TIMEOUT -> "Network timeout. Check your internet connection."
                    SpeechRecognizer.ERROR_AUDIO -> "Audio recording error. Check microphone."
                    SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> "Microphone permission denied."
                    SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> "Recognizer busy. Please wait and try again."
                    SpeechRecognizer.ERROR_SERVER -> "Server error. Please try again later."
                    else -> "Speech error (code: $error)"
                }
                appendOutputText(errorMessage)
            }

            override fun onBeginningOfSpeech(): Unit = Unit
            override fun onBufferReceived(buffer: ByteArray?): Unit = Unit
            override fun onEndOfSpeech(): Unit {
                appendOutputText(getString(R.string.output_recording_stopped))
            }
            override fun onEvent(eventType: Int, params: Bundle?): Unit = Unit
            override fun onPartialResults(partialResults: Bundle?): Unit = Unit
            override fun onRmsChanged(rmsdB: Float): Unit = Unit
        })
    }

    private fun shutdownSpeechRecognizer(): Unit {
        val recognizer: SpeechRecognizer? = speechRecognizer
        if (recognizer == null) {
            return
        }
        recognizer.destroy()
        speechRecognizer = null
    }

    private fun startSpeechRecognition(): Unit {
        val recognizer: SpeechRecognizer? = speechRecognizer
        if (recognizer == null) {
            appendOutputText(getString(R.string.output_speech_unavailable))
            return
        }
        val intent: Intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
        intent.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false)
        isSpeechRecognitionActive = true
        recognizer.startListening(intent)
    }

    private fun stopSpeechRecognition(): Unit {
        val recognizer: SpeechRecognizer? = speechRecognizer
        if (recognizer == null) {
            return
        }
        recognizer.stopListening()
    }

    private fun executeSpeechTextRequest(recognizedText: String): Unit {
        val inputValues: DiagnoseInput? = readDiagnoseInputSilent()
        val selectedVehicle: String = vehicleSpinner.selectedItem?.toString() ?: "XUV 700"
        val userId: String = formatUserId(driverNameInput.text.toString())
        appendOutputText(getString(R.string.output_request_sending_text, recognizedText))
        backgroundExecutor.execute { sendSpeechTextRequest(recognizedText, inputValues, selectedVehicle, userId) }
    }

    private fun sendSpeechTextRequest(recognizedText: String, inputValues: DiagnoseInput?, vehicleModel: String, userId: String): Unit {
        try {
            val url: URL = URL(TEXT_ENDPOINT_URL)
            val connection: HttpURLConnection = url.openConnection() as HttpURLConnection
            connection.requestMethod = "POST"
            connection.setRequestProperty("Content-Type", "application/json")
            connection.setRequestProperty("Authorization", "Bearer $DATABRICKS_TOKEN")
            connection.connectTimeout = NETWORK_TIMEOUT_MS
            connection.readTimeout = NETWORK_TIMEOUT_MS
            connection.doOutput = true
            val payload: String = createSpeechPayload(recognizedText, inputValues, vehicleModel, userId)
            appendOutputText("Request payload:\n$payload")
            connection.outputStream.use { stream -> stream.write(payload.toByteArray(Charsets.UTF_8)) }
            val responseText: String = readHttpResponse(connection)
            appendOutputText("API Response:\n$responseText")
            val voiceText: String = parseAssistantText(responseText)
            appendOutputText(getString(R.string.output_voice_response, voiceText))
            speakOutput(voiceText)
        } catch (err: Exception) {
            appendOutputText(getString(R.string.output_request_failed, err.message ?: "Unknown error"))
        }
    }

    private fun createSpeechPayload(recognizedText: String, inputValues: DiagnoseInput?, vehicleModel: String, userId: String): String {
        val inputMessage: JSONObject = JSONObject()
        inputMessage.put("role", "user")
        inputMessage.put("content", recognizedText)
        val inputArray: JSONArray = JSONArray()
        inputArray.put(inputMessage)
        val telemetry: JSONObject = JSONObject()
        if (inputValues != null) {
            telemetry.put("engine_temperature", inputValues.engineTemperature)
            telemetry.put("tpms_fl", inputValues.tpmsFrontLeft)
            telemetry.put("tpms_fr", inputValues.tpmsFrontRight)
            telemetry.put("tpms_bl", inputValues.tpmsBackLeft)
            telemetry.put("tpms_br", inputValues.tpmsBackRight)
            telemetry.put("ac_temperature", inputValues.acTemperature)
        }
        val customInputs: JSONObject = JSONObject()
        customInputs.put("vehicle_model", vehicleModel)
        customInputs.put("telemetry", telemetry)
        customInputs.put("user_id", userId)
        customInputs.put("conversation_id", sessionId)
        val payload: JSONObject = JSONObject()
        payload.put("input", inputArray)
        payload.put("custom_inputs", customInputs)
        return payload.toString()
    }

    private fun parseAssistantText(responseText: String): String {
        return try {
            val responseJson: JSONObject = JSONObject(responseText)
            if (responseJson.has("error_code")) {
                return FALLBACK_ERROR_MESSAGE
            }
            val outputArray: JSONArray? = responseJson.optJSONArray("output")
            if (outputArray != null && outputArray.length() > 0) {
                val lastItem: JSONObject? = outputArray.optJSONObject(outputArray.length() - 1)
                if (lastItem != null) {
                    val contentArray: JSONArray? = lastItem.optJSONArray("content")
                    if (contentArray != null && contentArray.length() > 0) {
                        val firstContent: JSONObject? = contentArray.optJSONObject(0)
                        val text: String? = firstContent?.optString("text", null)
                        if (!text.isNullOrBlank()) {
                            return text
                        }
                    }
                }
            }
            FALLBACK_ERROR_MESSAGE
        } catch (err: Exception) {
            FALLBACK_ERROR_MESSAGE
        }
    }

    private fun executeDiagnoseRequest(inputValues: DiagnoseInput): Unit {
        val selectedVehicle: String = vehicleSpinner.selectedItem?.toString() ?: "XUV 700"
        val userId: String = formatUserId(driverNameInput.text.toString())
        backgroundExecutor.execute {
            try {
                val url: URL = URL(DIAGNOSE_ENDPOINT_URL)
                val connection: HttpURLConnection = url.openConnection() as HttpURLConnection
                connection.requestMethod = "POST"
                connection.setRequestProperty("Content-Type", "application/json")
                connection.setRequestProperty("Authorization", "Bearer $DATABRICKS_TOKEN")
                connection.connectTimeout = NETWORK_TIMEOUT_MS
                connection.readTimeout = NETWORK_TIMEOUT_MS
                connection.doOutput = true
                val payload: String = createDiagnosePayload(inputValues, selectedVehicle, userId)
                updateOutputText(getString(R.string.output_diagnose_payload, payload))
                connection.outputStream.use { stream -> stream.write(payload.toByteArray(Charsets.UTF_8)) }
                val responseText: String = readHttpResponse(connection)
                appendOutputText("API Response:\n$responseText")
                val voiceText: String = parseAssistantText(responseText)
                appendOutputText(getString(R.string.output_voice_response, voiceText))
                speakOutput(voiceText)
            } catch (err: Exception) {
                updateOutputText(getString(R.string.output_request_failed, err.message ?: "Unknown error"))
            }
        }
    }

    private fun createDiagnosePayload(inputValues: DiagnoseInput, vehicleModel: String, userId: String): String {
        val inputMessage: JSONObject = JSONObject()
        inputMessage.put("role", "user")
        inputMessage.put("content", DIAGNOSE_PROMPT)
        val inputArray: JSONArray = JSONArray()
        inputArray.put(inputMessage)
        val telemetry: JSONObject = JSONObject()
        telemetry.put("engine_temperature", inputValues.engineTemperature)
        telemetry.put("tpms_fl", inputValues.tpmsFrontLeft)
        telemetry.put("tpms_fr", inputValues.tpmsFrontRight)
        telemetry.put("tpms_bl", inputValues.tpmsBackLeft)
        telemetry.put("tpms_br", inputValues.tpmsBackRight)
        telemetry.put("ac_temperature", inputValues.acTemperature)
        val customInputs: JSONObject = JSONObject()
        customInputs.put("vehicle_model", vehicleModel)
        customInputs.put("telemetry", telemetry)
        customInputs.put("user_id", userId)
        customInputs.put("conversation_id", sessionId)
        val payload: JSONObject = JSONObject()
        payload.put("input", inputArray)
        payload.put("custom_inputs", customInputs)
        return payload.toString()
    }

    private fun formatUserId(driverName: String): String {
        val trimmed: String = driverName.trim()
        if (trimmed.isEmpty()) {
            return DEFAULT_USER_ID
        }
        return trimmed.lowercase().replace(" ", "_")
    }

    private fun readDiagnoseInput(): DiagnoseInput? {
        val tpmsFrontLeft: Double? = readNumericInput(tpmsFrontLeftInput, getString(R.string.label_tpms_front_left))
        if (tpmsFrontLeft == null) {
            return null
        }
        val tpmsFrontRight: Double? = readNumericInput(tpmsFrontRightInput, getString(R.string.label_tpms_front_right))
        if (tpmsFrontRight == null) {
            return null
        }
        val tpmsBackRight: Double? = readNumericInput(tpmsBackRightInput, getString(R.string.label_tpms_back_right))
        if (tpmsBackRight == null) {
            return null
        }
        val tpmsBackLeft: Double? = readNumericInput(tpmsBackLeftInput, getString(R.string.label_tpms_back_left))
        if (tpmsBackLeft == null) {
            return null
        }
        val acTemperature: Double? = readNumericInput(acTemperatureInput, getString(R.string.label_ac_temperature))
        if (acTemperature == null) {
            return null
        }
        val engineTemperature: Double? = readNumericInput(engineTemperatureInput, getString(R.string.label_engine_temperature))
        if (engineTemperature == null) {
            return null
        }
        return DiagnoseInput(tpmsFrontLeft, tpmsFrontRight, tpmsBackRight, tpmsBackLeft, acTemperature, engineTemperature)
    }

    private fun readNumericInput(inputField: EditText, fieldName: String): Double? {
        val rawValue: String = inputField.text.toString().trim()
        if (rawValue.isEmpty()) {
            updateOutputText(getString(R.string.output_missing_value, fieldName))
            return null
        }
        val parsedValue: Double? = rawValue.toDoubleOrNull()
        if (parsedValue == null) {
            updateOutputText(getString(R.string.output_invalid_value, fieldName))
            return null
        }
        return parsedValue
    }

    private fun readHttpResponse(connection: HttpURLConnection): String {
        val responseCode: Int = connection.responseCode
        val responseStream: InputStream = if (responseCode in 200..299) {
            connection.inputStream
        } else {
            connection.errorStream ?: connection.inputStream
        }
        return responseStream.bufferedReader().use { reader -> reader.readText() }
    }

    private fun updateOutputText(message: String): Unit {
        mainHandler.post { outputText.text = message }
    }

    private fun appendOutputText(message: String): Unit {
        mainHandler.post {
            val existingText: String = outputText.text?.toString() ?: ""
            if (existingText.isBlank()) {
                outputText.text = message
                return@post
            }
            outputText.text = existingText + "\n\n" + message
        }
    }

    private fun initializeTextToSpeech(): Unit {
        textToSpeech = TextToSpeech(this) { status: Int ->
            isTextToSpeechReady = status == TextToSpeech.SUCCESS
        }
    }

    private fun shutdownTextToSpeech(): Unit {
        val engine: TextToSpeech? = textToSpeech
        if (engine == null) {
            return
        }
        engine.stop()
        engine.shutdown()
        textToSpeech = null
        isTextToSpeechReady = false
    }

    private fun speakOutput(message: String): Unit {
        mainHandler.post {
            if (!isTextToSpeechReady) {
                return@post
            }
            val engine: TextToSpeech? = textToSpeech
            if (engine == null) {
                return@post
            }
            engine.speak(message, TextToSpeech.QUEUE_FLUSH, null, "voice_response")
        }
    }

    data class DiagnoseInput(
        val tpmsFrontLeft: Double,
        val tpmsFrontRight: Double,
        val tpmsBackRight: Double,
        val tpmsBackLeft: Double,
        val acTemperature: Double,
        val engineTemperature: Double
    )

    companion object {
        private const val PREFS_NAME: String = "bricksy_prefs"
        private const val KEY_SESSION_ID: String = "session_id"
        private const val DEFAULT_USER_ID: String = "<your-user-id>"
        private const val DEFAULT_DRIVER_NAME: String = "Hussain Jagirdar"
        private const val FALLBACK_ERROR_MESSAGE: String = "Facing technical issues connecting with Bricksy. Please connect to Hussain."
        private const val DIAGNOSE_PROMPT: String = "Diagnose my vehicle with these mentioned data. Output should be short, crisp and to the point. Also provide or recommend next steps to be taken."
        private const val DATABRICKS_HOST: String = "https://adb-<workspace-id>.<suffix>.azuredatabricks.net"
        private const val DATABRICKS_ENDPOINT_NAME: String = "<your-stt-endpoint-name>"
        private const val DATABRICKS_TOKEN: String = "<your-databricks-pat-token>"
        private const val VOICE_ENDPOINT_URL: String = "$DATABRICKS_HOST/serving-endpoints/$DATABRICKS_ENDPOINT_NAME/invocations"
        private const val TEXT_ENDPOINT_URL: String = "https://adb-<workspace-id>.<suffix>.azuredatabricks.net/serving-endpoints/<your-agent-endpoint-name>/invocations"
        private const val DIAGNOSE_ENDPOINT_URL: String = "https://adb-<workspace-id>.<suffix>.azuredatabricks.net/serving-endpoints/<your-agent-endpoint-name>/invocations"
        // Zerobus REST API configuration for low-latency telemetry ingestion
        private const val ZEROBUS_CLIENT_ID: String = "<your-service-principal-client-id>"
        private const val ZEROBUS_CLIENT_SECRET: String = "<your-service-principal-client-secret>"
        private const val ZEROBUS_WORKSPACE_ID: String = "<your-workspace-id>"
        private const val ZEROBUS_REGION: String = "eastus2"
        private const val ZEROBUS_CATALOG: String = "<your-user-id>"
        private const val ZEROBUS_SCHEMA: String = "bricksy"
        private const val ZEROBUS_URI: String = "https://$ZEROBUS_WORKSPACE_ID.zerobus.$ZEROBUS_REGION.azuredatabricks.net"
        private const val TELEMETRY_TABLE_NAME: String = "$ZEROBUS_CATALOG.$ZEROBUS_SCHEMA.car_telemetry"
        private const val ZEROBUS_TIMEOUT_MS: Int = 5000
        private const val NETWORK_TIMEOUT_MS: Int = 15000
        private const val TELEMETRY_INTERVAL_MS: Long = 5000
        private const val DEFAULT_TPMS_VALUE: String = "35"
        private const val DEFAULT_AC_TEMPERATURE: String = "20"
        private const val DEFAULT_ENGINE_TEMPERATURE: String = "95"
    }
}
