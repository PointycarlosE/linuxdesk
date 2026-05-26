package com.linuxdesk

import android.graphics.BitmapFactory
import android.view.SurfaceView
import java.io.BufferedReader
import java.io.DataInputStream
import java.io.InputStreamReader
import java.io.PrintWriter
import java.net.Socket
import java.util.concurrent.atomic.AtomicBoolean

class StreamClient(
    private val surfaceView: SurfaceView,
    private val onStatusChange: (Boolean) -> Unit
) {
    private val running = AtomicBoolean(false)
    private var thread: Thread? = null

    fun isRunning() = running.get()

    fun start() {
        running.set(true)
        thread = Thread {
            try {
                val socket = Socket("127.0.0.1", 7878)
                val input = DataInputStream(socket.getInputStream())
                val output = PrintWriter(socket.getOutputStream(), true)
                val reader = BufferedReader(InputStreamReader(socket.getInputStream()))

                // Handshake: envia HELLO e aguarda OK
                output.println("HELLO")
                val response = reader.readLine()
                if (response == null || !response.startsWith("OK")) {
                    socket.close()
                    onStatusChange(false)
                    return@Thread
                }

                onStatusChange(true)

                while (running.get()) {
                    // Lê 4 bytes do tamanho do frame
                    val size = input.readInt()
                    if (size <= 0) break

                    // Lê os bytes do frame JPEG
                    val buffer = ByteArray(size)
                    input.readFully(buffer)

                    val bitmap = BitmapFactory.decodeByteArray(buffer, 0, size) ?: continue

                    val holder = surfaceView.holder
                    val canvas = holder.lockCanvas() ?: continue
                    try {
                        canvas.drawBitmap(
                            bitmap, null,
                            android.graphics.Rect(0, 0, canvas.width, canvas.height),
                            null
                        )
                    } finally {
                        holder.unlockCanvasAndPost(canvas)
                    }
                    bitmap.recycle()
                }

                output.println("BYE")
                socket.close()
            } catch (e: Exception) {
                e.printStackTrace()
            } finally {
                running.set(false)
                onStatusChange(false)
            }
        }
        thread?.start()
    }

    fun stop() {
        running.set(false)
        thread?.interrupt()
    }
}
