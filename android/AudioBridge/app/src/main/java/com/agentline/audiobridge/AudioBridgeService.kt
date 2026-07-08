package com.agentline.audiobridge

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioTrack
import android.os.Build
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import rikka.shizuku.Shizuku
import java.io.InputStream
import java.io.PrintWriter
import java.net.ServerSocket
import java.net.Socket
import kotlin.concurrent.thread

class AudioBridgeService : Service() {

    companion object {
        private const val TAG = "AudioBridgeService"
        private const val CHANNEL_ID = "AudioBridgeChannel"
        private const val NOTIFICATION_ID = 1
        
        // Broadcast actions
        const val ACTION_START_BRIDGE = "com.agentline.audiobridge.START"
        const val ACTION_STOP_BRIDGE = "com.agentline.audiobridge.STOP"
        
        // Local Ports
        private const val PORT_CAPTURE = 9001
        private const val PORT_PLAYBACK = 9002
        private const val PORT_CONTROL = 9003
        
        // Keep a static reference so the InCallService can notify us
        var instance: AudioBridgeService? = null
    }

    private var audioTrack: AudioTrack? = null
    private var isPlaying = false
    private var playbackServerSocket: ServerSocket? = null
    private var controlServerSocket: ServerSocket? = null
    
    private var controlWriter: PrintWriter? = null

    // Shizuku Connection
    private var binder: IShizukuAudioBridge? = null
    private val shizukuConnection = object : ServiceConnection {
        override fun onServiceConnected(name: ComponentName?, service: IBinder?) {
            binder = IShizukuAudioBridge.Stub.asInterface(service)
            Log.d(TAG, "ShizukuUserService connected!")
            // Start recording immediately
            try {
                binder?.startRecord(PORT_CAPTURE)
            } catch (e: Exception) {
                Log.e(TAG, "Error starting record: ${e.message}")
            }
        }

        override fun onServiceDisconnected(name: ComponentName?) {
            binder = null
            Log.d(TAG, "ShizukuUserService disconnected!")
        }
    }

    private val shizukuArgs = Shizuku.UserServiceArgs(
        ComponentName("com.agentline.audiobridge", ShizukuUserService::class.java.name)
    ).daemon(false).processNameSuffix("shizuku_bridge")

    override fun onCreate() {
        super.onCreate()
        instance = this
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val action = intent?.action
        if (action == ACTION_START_BRIDGE) {
            startForegroundService()
            startBridge()
            val phoneNumber = intent.getStringExtra("EXTRA_PHONE_NUMBER")
            val direction = intent.getStringExtra("EXTRA_CALL_DIRECTION") ?: "outbound"
            if (phoneNumber != null) {
                notifyCallStarted(phoneNumber, direction)
            }
        } else if (action == ACTION_STOP_BRIDGE) {
            stopBridge()
            stopSelf()
        }
        return START_NOT_STICKY
    }

    private fun startForegroundService() {
        val notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("AudioBridge Active")
            .setContentText("Routing call audio locally...")
            .setSmallIcon(android.R.drawable.ic_media_play)
            .build()
        startForeground(NOTIFICATION_ID, notification)
    }

    private fun startBridge() {
        Log.d(TAG, "Starting Audio Bridge...")
        
        // 1. Bind to Shizuku User Service
        if (Shizuku.checkSelfPermission() == android.content.pm.PackageManager.PERMISSION_GRANTED) {
            try {
                Shizuku.bindUserService(shizukuArgs, shizukuConnection)
            } catch (e: Exception) {
                Log.e(TAG, "Failed to bind Shizuku service: ${e.message}", e)
            }
        } else {
            Log.w(TAG, "Shizuku permission not granted!")
        }

        // 2. Setup AudioTrack for Playback into call
        setupAudioTrack()

        // 3. Start TCP Server for Playback (receiving audio from Python)
        startPlaybackServer()

        // 4. Start TCP Server for Control Events
        startControlServer()
    }

    private fun setupAudioTrack() {
        val audioManager = getSystemService(Context.AUDIO_SERVICE) as AudioManager
        audioManager.mode = AudioManager.MODE_IN_CALL
        
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            val devices = audioManager.getDevices(AudioManager.GET_DEVICES_OUTPUTS)
            val telephonyDevice = devices.find { it.type == android.media.AudioDeviceInfo.TYPE_TELEPHONY }
            val earpieceDevice = devices.find { it.type == android.media.AudioDeviceInfo.TYPE_BUILTIN_EARPIECE }
            val targetDevice = telephonyDevice ?: earpieceDevice
            if (targetDevice != null) {
                try {
                    audioManager.clearCommunicationDevice()
                    audioManager.setCommunicationDevice(targetDevice)
                    Log.i(TAG, "Routing call audio output to: ${targetDevice.productName} (Type: ${targetDevice.type})")
                } catch (e: Exception) {
                    Log.e(TAG, "Failed to set communication device: ${e.message}")
                }
            }
        }
        
        val sampleRate = 8000 // Sarvam TTS output rate
        val bufferSize = AudioTrack.getMinBufferSize(
            sampleRate,
            AudioFormat.CHANNEL_OUT_MONO,
            AudioFormat.ENCODING_PCM_16BIT
        )

        audioTrack = AudioTrack.Builder()
            .setAudioAttributes(
                AudioAttributes.Builder()
                    .setLegacyStreamType(AudioManager.STREAM_VOICE_CALL)
                    .build()
            )
            .setAudioFormat(
                AudioFormat.Builder()
                    .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                    .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                    .setSampleRate(sampleRate)
                    .build()
            )
            .setBufferSizeInBytes(bufferSize * 2)
            .setTransferMode(AudioTrack.MODE_STREAM)
            .build()

        audioTrack?.play()
    }

    private fun startPlaybackServer() {
        isPlaying = true
        thread(start = true) {
            try {
                playbackServerSocket = ServerSocket(PORT_PLAYBACK)
                Log.d(TAG, "Playback Server listening on port $PORT_PLAYBACK")
                
                while (isPlaying) {
                    val socket = playbackServerSocket?.accept() ?: break
                    thread {
                        var inputStream: InputStream? = null
                        try {
                            inputStream = socket.getInputStream()
                            val buffer = ByteArray(2048)
                            while (isPlaying) {
                                val read = inputStream.read(buffer)
                                if (read == -1) break
                                if (read > 0) {
                                    audioTrack?.write(buffer, 0, read)
                                }
                            }
                        } catch (e: Exception) {
                            Log.e(TAG, "Error in playback stream: ${e.message}")
                        } finally {
                            inputStream?.close()
                            socket.close()
                        }
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "Playback server error: ${e.message}")
            }
        }
    }

    private fun startControlServer() {
        thread(start = true) {
            try {
                controlServerSocket = ServerSocket(PORT_CONTROL)
                Log.d(TAG, "Control Server listening on port $PORT_CONTROL")
                
                while (isPlaying) {
                    val socket = controlServerSocket?.accept() ?: break
                    controlWriter = PrintWriter(socket.getOutputStream(), true)
                    Log.d(TAG, "Control channel connected with Python agent")
                    
                    // Simple keepalive/command reader
                    val reader = socket.getInputStream().bufferedReader()
                    while (isPlaying) {
                        val line = reader.readLine() ?: break
                        Log.d(TAG, "Received command from Python: $line")
                    }
                    controlWriter = null
                    socket.close()
                }
            } catch (e: Exception) {
                Log.e(TAG, "Control server error: ${e.message}")
            }
        }
    }

    fun notifyCallStarted(phoneNumber: String, direction: String) {
        thread {
            // Wait up to 3 seconds for Python connection if not already connected
            for (i in 1..30) {
                if (controlWriter != null) break
                Thread.sleep(100)
            }
            controlWriter?.println("CALL_STARTED:$phoneNumber:$direction")
            Log.d(TAG, "Sent CALL_STARTED to Python agent with direction: $direction")
        }
    }

    fun notifyCallEnded() {
        controlWriter?.println("CALL_ENDED")
        Log.d(TAG, "Sent CALL_ENDED to Python agent")
    }

    private fun stopBridge() {
        Log.d(TAG, "Stopping Audio Bridge...")
        isPlaying = false
        
        // Reset AudioMode
        val audioManager = getSystemService(Context.AUDIO_SERVICE) as AudioManager
        audioManager.mode = AudioManager.MODE_NORMAL
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            try {
                audioManager.clearCommunicationDevice()
            } catch (e: Exception) {}
        }
        
        // Stop Shizuku capture
        try {
            binder?.stopRecord()
            Shizuku.unbindUserService(shizukuArgs, shizukuConnection, true)
        } catch (e: Exception) {
            Log.e(TAG, "Error unbinding Shizuku: ${e.message}")
        }
        
        // Stop playback Track
        try {
            audioTrack?.stop()
            audioTrack?.release()
        } catch (e: Exception) {}
        audioTrack = null

        // Close sockets
        try {
            playbackServerSocket?.close()
            controlServerSocket?.close()
        } catch (e: Exception) {}
        
        stopForeground(true)
        instance = null
    }

    override fun onDestroy() {
        stopBridge()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val serviceChannel = NotificationChannel(
                CHANNEL_ID,
                "Audio Bridge Foreground Channel",
                NotificationManager.IMPORTANCE_LOW
            )
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(serviceChannel)
        }
    }
}
