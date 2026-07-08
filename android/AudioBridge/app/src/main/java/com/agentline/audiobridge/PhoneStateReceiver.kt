package com.agentline.audiobridge

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.telephony.TelephonyManager
import android.util.Log

class PhoneStateReceiver : BroadcastReceiver() {
    
    companion object {
        private var isIncoming = false
    }

    override fun onReceive(context: Context, intent: Intent) {
        val action = intent.action
        if (action == TelephonyManager.ACTION_PHONE_STATE_CHANGED || 
            action == "com.agentline.audiobridge.TEST_PHONE_STATE") {
            
            val state = intent.getStringExtra(TelephonyManager.EXTRA_STATE)
            // Note: EXTRA_INCOMING_NUMBER requires READ_PHONE_STATE and READ_CALL_LOG permissions
            val phoneNumber = intent.getStringExtra(TelephonyManager.EXTRA_INCOMING_NUMBER) ?: "unknown"
            Log.i("PhoneStateReceiver", "Phone state changed (Action: $action): $state, number: $phoneNumber")

            when (state) {
                TelephonyManager.EXTRA_STATE_RINGING -> {
                    isIncoming = true
                    Log.i("PhoneStateReceiver", "Call is ringing... Setting direction to inbound")
                }
                TelephonyManager.EXTRA_STATE_OFFHOOK -> {
                    val direction = if (isIncoming) "inbound" else "outbound"
                    Log.i("PhoneStateReceiver", "Call connected (OFFHOOK). Direction: $direction, number: $phoneNumber")
                    
                    val startIntent = Intent(context, AudioBridgeService::class.java)
                    startIntent.action = AudioBridgeService.ACTION_START_BRIDGE
                    startIntent.putExtra("EXTRA_PHONE_NUMBER", phoneNumber)
                    startIntent.putExtra("EXTRA_CALL_DIRECTION", direction)
                    context.startForegroundService(startIntent)
                }
                TelephonyManager.EXTRA_STATE_IDLE -> {
                    isIncoming = false
                    Log.i("PhoneStateReceiver", "Call ended (IDLE). Stopping Audio Bridge Service...")
                    val stopIntent = Intent(context, AudioBridgeService::class.java)
                    stopIntent.action = AudioBridgeService.ACTION_STOP_BRIDGE
                    context.startService(stopIntent)
                }
            }
        }
    }
}
