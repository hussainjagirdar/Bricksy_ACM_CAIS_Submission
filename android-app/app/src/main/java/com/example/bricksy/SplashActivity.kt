package com.example.bricksy

import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import androidx.activity.ComponentActivity

class SplashActivity : ComponentActivity() {
    private val mainHandler: Handler = Handler(Looper.getMainLooper())
    private val navigateRunnable: Runnable = Runnable {
        val intent: Intent = Intent(this, MainActivity::class.java)
        startActivity(intent)
        finish()
    }

    override fun onCreate(savedInstanceState: Bundle?): Unit {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_splash)
        mainHandler.postDelayed(navigateRunnable, SPLASH_DELAY_MS)
    }

    override fun onDestroy(): Unit {
        mainHandler.removeCallbacks(navigateRunnable)
        super.onDestroy()
    }

    companion object {
        private const val SPLASH_DELAY_MS: Long = 2000L
    }
}
