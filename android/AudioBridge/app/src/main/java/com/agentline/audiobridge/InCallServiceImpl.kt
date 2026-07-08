package com.agentline.audiobridge

import android.content.Intent
import android.telecom.Call
import android.telecom.InCallService
import android.util.Log

class InCallServiceImpl : InCallService() {

    companion object {
        private const val TAG = "InCallServiceImpl"
    }

    private val callCallback = object : Call.Callback() {
        override fun onStateChanged(call: Call?, state: Int) {
            super.onStateChanged(call, state)
            Log.d(TAG, "Call state changed: $state")
            
            if (state == Call.STATE_ACTIVE) {
                val phoneNumber = call?.details?.handle?.schemeSpecificPart ?: "unknown"
                Log.d(TAG, "Call active with $phoneNumber. Starting Audio Bridge Service...")
                
                // Start the foreground service with phone number extra
                val intent = Intent(this@InCallServiceImpl, AudioBridgeService::class.java).apply {
                    action = AudioBridgeService.ACTION_START_BRIDGE
                    putExtra("EXTRA_PHONE_NUMBER", phoneNumber)
                }
                startForegroundService(intent)
            }
        }
    }

    override fun onCallAdded(call: Call?) {
        super.onCallAdded(call)
        Log.d(TAG, "Call added")
        call?.registerCallback(callCallback)
        
        // If the call is already active when added (e.g. answered immediately)
        if (call?.state == Call.STATE_ACTIVE) {
            val phoneNumber = call.details?.handle?.schemeSpecificPart ?: "unknown"
            val intent = Intent(this, AudioBridgeService::class.java).apply {
                action = AudioBridgeService.ACTION_START_BRIDGE
                putExtra("EXTRA_PHONE_NUMBER", phoneNumber)
            }
            startForegroundService(intent)
        }
    }

    override fun onCallRemoved(call: Call?) {
        super.onCallRemoved(call)
        Log.d(TAG, "Call removed")
        call?.unregisterCallback(callCallback)
        
        // Notify call ended and stop service using standard startService (not startForegroundService)
        AudioBridgeService.instance?.notifyCallEnded()
        val intent = Intent(this, AudioBridgeService::class.java).apply {
            action = AudioBridgeService.ACTION_STOP_BRIDGE
        }
        startService(intent)
    }
}
