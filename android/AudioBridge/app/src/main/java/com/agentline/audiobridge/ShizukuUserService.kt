package com.agentline.audiobridge

import android.os.Build
import android.os.IBinder
import android.media.AudioRecord
import android.media.MediaRecorder
import android.media.AudioFormat
import android.util.Log
import org.lsposed.hiddenapibypass.HiddenApiBypass
import java.io.OutputStream
import java.net.Socket
import kotlin.concurrent.thread

class ShizukuUserService : IShizukuAudioBridge.Stub {

    constructor() : super() {
        Log.i("ShizukuUserService", "ShizukuUserService initializing...")
        bypassHiddenApiRestrictions()
        overridePackageName()
    }

    private var audioRecord: AudioRecord? = null
    private var isRecording = false
    private var recordThread: Thread? = null

    private fun bypassHiddenApiRestrictions() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            try {
                // Wildcard "L" exempts ALL hidden API checks on Android
                HiddenApiBypass.addHiddenApiExemptions("L")
                Log.i("ShizukuUserService", "Bypassed all hidden API restrictions successfully")
            } catch (e: Exception) {
                Log.e("ShizukuUserService", "Failed to bypass hidden API restrictions: ${e.message}", e)
            }
        }
    }

    private fun overridePackageName() {
        try {
            val activityThreadClass = Class.forName("android.app.ActivityThread")
            
            // 1. Get or create sCurrentActivityThread static instance
            val sCurrentActivityThreadField = activityThreadClass.getDeclaredField("sCurrentActivityThread")
            sCurrentActivityThreadField.isAccessible = true
            var activityThread = sCurrentActivityThreadField.get(null)
            if (activityThread == null) {
                val constructor = activityThreadClass.getDeclaredConstructor()
                constructor.isAccessible = true
                activityThread = constructor.newInstance()
                sCurrentActivityThreadField.set(null, activityThread)
                Log.i("ShizukuUserService", "Created new sCurrentActivityThread instance")
            }

            // 2. Create or get mBoundApplication inner instance on ActivityThread
            val mBoundApplicationField = activityThreadClass.getDeclaredField("mBoundApplication")
            mBoundApplicationField.isAccessible = true
            var mBoundApplication = mBoundApplicationField.get(activityThread)
            if (mBoundApplication == null) {
                val appBindDataClass = Class.forName("android.app.ActivityThread\$AppBindData")
                val appBindDataConstructor = appBindDataClass.getDeclaredConstructor()
                appBindDataConstructor.isAccessible = true
                mBoundApplication = appBindDataConstructor.newInstance()
                mBoundApplicationField.set(activityThread, mBoundApplication)
                Log.i("ShizukuUserService", "Created new mBoundApplication instance")
            }

            // 3. Create or get appInfo ApplicationInfo instance on AppBindData
            val appInfoField = mBoundApplication.javaClass.getDeclaredField("appInfo")
            appInfoField.isAccessible = true
            var appInfo = appInfoField.get(mBoundApplication)
            if (appInfo == null) {
                val appInfoClass = Class.forName("android.content.pm.ApplicationInfo")
                val appInfoConstructor = appInfoClass.getDeclaredConstructor()
                appInfoConstructor.isAccessible = true
                appInfo = appInfoConstructor.newInstance()
                appInfoField.set(mBoundApplication, appInfo)
                Log.i("ShizukuUserService", "Created new ApplicationInfo instance")
            }

            // 4. Overwrite all String fields in ActivityThread containing target package name
            val fields = activityThreadClass.getDeclaredFields()
            for (field in fields) {
                if (field.type == String::class.java) {
                    field.isAccessible = true
                    val value = field.get(activityThread) as? String
                    if (value == "com.agentline.audiobridge") {
                        field.set(activityThread, "com.android.shell")
                        Log.i("ShizukuUserService", "Overrote ActivityThread field ${field.name} to com.android.shell")
                    }
                }
            }

            // 5. Overwrite target package name inside AppBindData fields
            val appBindDataFields = mBoundApplication.javaClass.getDeclaredFields()
            for (field in appBindDataFields) {
                if (field.type == String::class.java) {
                    field.isAccessible = true
                    val value = field.get(mBoundApplication) as? String
                    if (value == "com.agentline.audiobridge") {
                        field.set(mBoundApplication, "com.android.shell")
                        Log.i("ShizukuUserService", "Overrote AppBindData field ${field.name} to com.android.shell")
                    }
                }
            }

            // 6. Overwrite target package name inside ApplicationInfo fields (public & declared)
            val appInfoFields = appInfo.javaClass.fields
            for (field in appInfoFields) {
                if (field.type == String::class.java) {
                    field.isAccessible = true
                    val value = field.get(appInfo) as? String
                    if (value == "com.agentline.audiobridge") {
                        field.set(appInfo, "com.android.shell")
                        Log.i("ShizukuUserService", "Overrote ApplicationInfo public field ${field.name} to com.android.shell")
                    }
                }
            }
            val appInfoDeclaredFields = appInfo.javaClass.getDeclaredFields()
            for (field in appInfoDeclaredFields) {
                if (field.type == String::class.java) {
                    field.isAccessible = true
                    val value = field.get(appInfo) as? String
                    if (value == "com.agentline.audiobridge") {
                        field.set(appInfo, "com.android.shell")
                        Log.i("ShizukuUserService", "Overrote ApplicationInfo declared field ${field.name} to com.android.shell")
                    }
                }
            }

            // 7. Overwrite Application context's package names and AttributionSource inside ContextImpl
            val mInitialApplicationField = activityThreadClass.getDeclaredField("mInitialApplication")
            mInitialApplicationField.isAccessible = true
            val application = mInitialApplicationField.get(activityThread) as? android.app.Application
            if (application != null) {
                val contextWrapperClass = Class.forName("android.content.ContextWrapper")
                val mBaseField = contextWrapperClass.getDeclaredField("mBase")
                mBaseField.isAccessible = true
                val contextImpl = mBaseField.get(application)
                if (contextImpl != null) {
                    val contextImplClass = Class.forName("android.app.ContextImpl")
                    
                    val mOpPackageNameField = contextImplClass.getDeclaredField("mOpPackageName")
                    mOpPackageNameField.isAccessible = true
                    mOpPackageNameField.set(contextImpl, "com.android.shell")
                    
                    val mBasePackageNameField = contextImplClass.getDeclaredField("mBasePackageName")
                    mBasePackageNameField.isAccessible = true
                    mBasePackageNameField.set(contextImpl, "com.android.shell")
                    Log.i("ShizukuUserService", "Successfully set ContextImpl package names to com.android.shell")

                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                        val attributionSource = android.content.AttributionSource.Builder(2000)
                            .setPackageName("com.android.shell")
                            .build()
                        
                        val mAttributionSourceField = contextImplClass.getDeclaredField("mAttributionSource")
                        mAttributionSourceField.isAccessible = true
                        mAttributionSourceField.set(contextImpl, attributionSource)
                        Log.i("ShizukuUserService", "Successfully overridden mAttributionSource in ContextImpl to com.android.shell")
                    }
                }
            }

            Log.i("ShizukuUserService", "Successfully completed dynamic ActivityThread override!")
            
            // Verification check
            val currentOpPackageNameMethod = activityThreadClass.getDeclaredMethod("currentOpPackageName")
            currentOpPackageNameMethod.isAccessible = true
            val verifiedPkgName = currentOpPackageNameMethod.invoke(null)
            Log.i("ShizukuUserService", "Verification: ActivityThread.currentOpPackageName() = $verifiedPkgName")
            
        } catch (e: Exception) {
            Log.e("ShizukuUserService", "Failed to mock ActivityThread: ${e.message}", e)
        }
    }

    override fun startRecord(port: Int) {
        if (isRecording) return
        isRecording = true
        Log.i("ShizukuUserService", "Starting VOICE_CALL record on port $port")

        recordThread = thread(start = true) {
            var socket: Socket? = null
            var outputStream: OutputStream? = null
            try {
                // Connect to the local Termux Python script
                socket = Socket("127.0.0.1", port)
                outputStream = socket.getOutputStream()

                // Create AudioRecord with VOICE_CALL (captures both uplink and downlink)
                // 16kHz, mono, 16-bit PCM
                val sampleRate = 16000
                val channelConfig = AudioFormat.CHANNEL_IN_MONO
                val audioFormat = AudioFormat.ENCODING_PCM_16BIT
                val bufferSize = AudioRecord.getMinBufferSize(sampleRate, channelConfig, audioFormat)

                audioRecord = AudioRecord(
                    MediaRecorder.AudioSource.VOICE_CALL,
                    sampleRate,
                    channelConfig,
                    audioFormat,
                    bufferSize * 2
                )

                if (audioRecord?.state != AudioRecord.STATE_INITIALIZED) {
                    Log.e("ShizukuUserService", "AudioRecord initialization failed. Retrying with VOICE_COMMUNICATION...")
                    // Fallback to VOICE_COMMUNICATION (mic only)
                    audioRecord = AudioRecord(
                        MediaRecorder.AudioSource.VOICE_COMMUNICATION,
                        sampleRate,
                        channelConfig,
                        audioFormat,
                        bufferSize * 2
                    )
                }

                if (audioRecord?.state != AudioRecord.STATE_INITIALIZED) {
                    Log.e("ShizukuUserService", "Fallback AudioRecord failed as well.")
                    isRecording = false
                    return@thread
                }

                audioRecord?.startRecording()
                val buffer = ByteArray(2048)
                var silentChunksCount = 0
                var totalChunksCount = 0

                while (isRecording) {
                    val read = audioRecord?.read(buffer, 0, buffer.size) ?: 0
                    if (read > 0) {
                        totalChunksCount++
                        var isSilent = true
                        for (i in 0 until read) {
                            if (buffer[i] != 0.toByte()) {
                                isSilent = false
                                break
                            }
                        }
                        if (isSilent) {
                            silentChunksCount++
                        }
                        if (totalChunksCount % 200 == 0) {
                            Log.i("ShizukuUserService", "Audio capture status: total chunks = $totalChunksCount, silent chunks = $silentChunksCount")
                        }
                        outputStream.write(buffer, 0, read)
                        outputStream.flush()
                    }
                }

            } catch (e: Exception) {
                Log.e("ShizukuUserService", "Error in record thread: ${e.message}", e)
            } finally {
                try {
                    audioRecord?.stop()
                    audioRecord?.release()
                } catch (e: Exception) {}
                audioRecord = null
                try {
                    outputStream?.close()
                    socket?.close()
                } catch (e: Exception) {}
                isRecording = false
                Log.i("ShizukuUserService", "Record thread stopped")
            }
        }
    }

    override fun stopRecord() {
        Log.i("ShizukuUserService", "Stopping record")
        isRecording = false
        recordThread?.join(1000)
        recordThread = null
    }

    override fun isRecording(): Boolean {
        return isRecording
    }

    override fun destroy() {
        stopRecord()
        Log.i("ShizukuUserService", "UserService destroy")
        System.exit(0)
    }
}
