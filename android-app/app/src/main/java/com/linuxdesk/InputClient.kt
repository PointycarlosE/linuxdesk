package com.linuxdesk

import android.view.MotionEvent
import org.json.JSONObject
import java.io.PrintWriter
import java.net.Socket
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.LinkedBlockingQueue

class InputClient {
    private val running = AtomicBoolean(false)
    private var socket: Socket? = null
    private var writer: PrintWriter? = null
    private val queue = LinkedBlockingQueue<String>(1000)
    private var thread: Thread? = null

    fun start() {
        running.set(true)
        thread = Thread {
            try {
                socket = Socket("127.0.0.1", 7879)
                writer = PrintWriter(socket!!.getOutputStream(), true)
                while (running.get()) {
                    val event = queue.poll(100, java.util.concurrent.TimeUnit.MILLISECONDS)
                    event?.let { writer?.println(it) }
                }
            } catch (e: Exception) {
                e.printStackTrace()
            } finally {
                running.set(false)
                socket?.close()
            }
        }
        thread?.start()
    }

    fun stop() {
        running.set(false)
        thread?.interrupt()
        socket?.close()
    }

    fun isRunning() = running.get()

    private fun send(json: JSONObject) {
        if (running.get()) queue.offer(json.toString())
    }

    fun sendTouchEvent(event: MotionEvent, viewW: Int, viewH: Int) {
        val pointerIndex = event.actionIndex
        val slot = event.getPointerId(pointerIndex)
        val x = event.getX(pointerIndex)
        val y = event.getY(pointerIndex)

        val action = when (event.actionMasked) {
            MotionEvent.ACTION_DOWN, MotionEvent.ACTION_POINTER_DOWN -> "down"
            MotionEvent.ACTION_UP, MotionEvent.ACTION_POINTER_UP -> "up"
            MotionEvent.ACTION_MOVE -> "move"
            else -> return
        }

        // Envia todos os pointers em caso de move
        if (action == "move") {
            for (i in 0 until event.pointerCount) {
                send(JSONObject().apply {
                    put("type", "touch")
                    put("action", "move")
                    put("slot", event.getPointerId(i))
                    put("x", event.getX(i).toDouble())
                    put("y", event.getY(i).toDouble())
                    put("w", viewW)
                    put("h", viewH)
                    put("pointers", event.pointerCount)
                })
            }
        } else {
            send(JSONObject().apply {
                put("type", "touch")
                put("action", action)
                put("slot", slot)
                put("x", x.toDouble())
                put("y", y.toDouble())
                put("w", viewW)
                put("h", viewH)
                put("pointers", event.pointerCount)
            })
        }
    }

    fun sendScrollEvent(dx: Float, dy: Float) {
        send(JSONObject().apply {
            put("type", "touch")
            put("action", "scroll")
            put("dx", dx.toDouble())
            put("dy", dy.toDouble())
        })
    }

    fun sendPenEvent(event: MotionEvent, viewW: Int, viewH: Int) {
        val action = when (event.actionMasked) {
            MotionEvent.ACTION_DOWN -> "down"
            MotionEvent.ACTION_UP -> "up"
            MotionEvent.ACTION_MOVE -> "move"
            MotionEvent.ACTION_HOVER_MOVE -> "hover"
            MotionEvent.ACTION_HOVER_ENTER -> "hover"
            MotionEvent.ACTION_HOVER_EXIT -> "hover"
            else -> return
        }

        send(JSONObject().apply {
            put("type", "pen")
            put("action", action)
            put("x", event.x.toDouble())
            put("y", event.y.toDouble())
            put("w", viewW)
            put("h", viewH)
            put("pressure", event.pressure.toDouble())
            put("tilt_x", event.getAxisValue(MotionEvent.AXIS_TILT).toDouble())
            put("tilt_y", event.getAxisValue(MotionEvent.AXIS_ORIENTATION).toDouble())
            put("distance", event.getAxisValue(MotionEvent.AXIS_DISTANCE).toDouble())
            put("button1", event.getAxisValue(MotionEvent.AXIS_GENERIC_1) > 0.5f ||
                    (event.buttonState and MotionEvent.BUTTON_STYLUS_PRIMARY) != 0)
            put("button2", (event.buttonState and MotionEvent.BUTTON_STYLUS_SECONDARY) != 0)
        })
    }
}
