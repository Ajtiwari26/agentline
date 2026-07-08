package com.agentline.audiobridge

import android.telecom.CallScreeningService
import android.telecom.Call
import android.util.Log

class CallScreeningServiceImpl : CallScreeningService() {
    override fun onScreenCall(callDetails: Call.Details) {
        Log.i("CallScreeningService", "Screening incoming call from: ${callDetails.handle?.schemeSpecificPart}")
        
        // Respond to Telecom to let the call proceed normally with system UI
        val response = CallResponse.Builder()
            .setDisallowCall(false)
            .setRejectCall(false)
            .setSkipCallLog(false)
            .setSkipNotification(false)
            .build()
        respondToCall(callDetails, response)
    }
}
