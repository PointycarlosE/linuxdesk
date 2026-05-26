package com.linuxdesk

import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.MotionEvent
import android.view.SurfaceView
import android.view.View
import android.view.WindowManager
import android.widget.Button
import androidx.appcompat.app.AppCompatActivity

class MainActivity : AppCompatActivity() {

    private lateinit var surfaceView: SurfaceView
    private lateinit var btnConnect: Button
    private var streamClient: StreamClient? = null
    private var inputClient: InputClient? = null
    private val handler = Handler(Looper.getMainLooper())
    private var isConnected = false
    private var autoReconnect = true

    private val hideButton = Runnable {
        btnConnect.animate().alpha(0f).setDuration(300).withEndAction {
            btnConnect.visibility = View.GONE
        }.start()
    }

    private val reconnectRunnable = Runnable {
        if (!isConnected && autoReconnect) connect()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        window.decorView.systemUiVisibility = (
            View.SYSTEM_UI_FLAG_FULLSCREEN or
            View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or
            View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
        )

        setContentView(R.layout.activity_main)

        surfaceView = findViewById(R.id.surfaceView)
        btnConnect = findViewById(R.id.btnConnect)

        // Captura eventos de toque e caneta no SurfaceView
        surfaceView.setOnTouchListener { v, event ->
            if (!isConnected) return@setOnTouchListener false

            val toolType = event.getToolType(event.actionIndex)

            when (toolType) {
                MotionEvent.TOOL_TYPE_STYLUS,
                MotionEvent.TOOL_TYPE_ERASER -> {
                    inputClient?.sendPenEvent(event, v.width, v.height)
                }
                else -> {
                    // Detecta scroll com 2 dedos
                    if (event.pointerCount == 2 &&
                        event.actionMasked == MotionEvent.ACTION_MOVE) {
                        // simplificado: envia como scroll
                        inputClient?.sendScrollEvent(0f, event.getY(0) - event.getY(1))
                    } else {
                        inputClient?.sendTouchEvent(event, v.width, v.height)
                    }
                }
            }

            // Mostra botão ao tocar se conectado
            if (event.pointerCount == 3) showButtonTemporarily()
            true
        }

        // Hover da S Pen (quando a caneta está perto mas não tocando)
        surfaceView.setOnHoverListener { v, event ->
            if (!isConnected) return@setOnHoverListener false
            val toolType = event.getToolType(0)
            if (toolType == MotionEvent.TOOL_TYPE_STYLUS ||
                toolType == MotionEvent.TOOL_TYPE_ERASER) {
                inputClient?.sendPenEvent(event, v.width, v.height)
            }
            true
        }

        btnConnect.setOnClickListener {
            if (!isConnected) {
                autoReconnect = true
                connect()
            } else {
                autoReconnect = false
                handler.removeCallbacks(reconnectRunnable)
                streamClient?.stop()
                inputClient?.stop()
                inputClient = null
            }
        }

        handler.postDelayed({ connect() }, 1500)
    }

    private fun connect() {
        if (isConnected || streamClient?.isRunning() == true) return

        btnConnect.text = getString(R.string.connecting)
        btnConnect.isEnabled = false
        btnConnect.visibility = View.VISIBLE
        btnConnect.alpha = 1f
        handler.removeCallbacks(hideButton)

        // Inicia cliente de input
        inputClient = InputClient()
        inputClient!!.start()

        streamClient = StreamClient(surfaceView) { connected ->
            runOnUiThread {
                isConnected = connected
                if (connected) {
                    btnConnect.text = getString(R.string.disconnect)
                    btnConnect.isEnabled = true
                    showButtonTemporarily()
                } else {
                    inputClient?.stop()
                    inputClient = null
                    streamClient = null
                    btnConnect.text = getString(R.string.connect)
                    btnConnect.isEnabled = true
                    btnConnect.visibility = View.VISIBLE
                    btnConnect.alpha = 1f
                    handler.removeCallbacks(hideButton)

                    if (autoReconnect) {
                        btnConnect.text = getString(R.string.connecting)
                        btnConnect.isEnabled = false
                        handler.postDelayed(reconnectRunnable, 3000)
                    }
                }
            }
        }
        streamClient!!.start()
    }

    private fun showButtonTemporarily() {
        handler.removeCallbacks(hideButton)
        btnConnect.visibility = View.VISIBLE
        btnConnect.animate().alpha(1f).setDuration(200).start()
        handler.postDelayed(hideButton, 3000)
    }

    override fun onDestroy() {
        super.onDestroy()
        autoReconnect = false
        handler.removeCallbacks(hideButton)
        handler.removeCallbacks(reconnectRunnable)
        inputClient?.stop()
        streamClient?.stop()
    }
}
