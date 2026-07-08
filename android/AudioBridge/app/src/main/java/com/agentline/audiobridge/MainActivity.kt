package com.agentline.audiobridge

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.telecom.TelecomManager
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import rikka.shizuku.Shizuku

class MainActivity : AppCompatActivity() {

    private lateinit var statusText: TextView
    private lateinit var btnPermission: Button
    private lateinit var btnToggleBridge: Button
    private lateinit var btnDefaultSpam: Button

    private val permissionListener = Shizuku.OnRequestPermissionResultListener { _, grantResult ->
        val granted = grantResult == PackageManager.PERMISSION_GRANTED
        updateShizukuStatus(granted)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        // Dynamic UI layout creation so we don't need xml files
        val layout = android.widget.LinearLayout(this).apply {
            orientation = android.widget.LinearLayout.VERTICAL
            setPadding(50, 100, 50, 50)
            gravity = android.view.Gravity.CENTER_HORIZONTAL
        }

        statusText = TextView(this).apply {
            text = "Checking Shizuku..."
            textSize = 20f
            setPadding(0, 0, 0, 50)
        }
        layout.addView(statusText)

        btnPermission = Button(this).apply {
            text = "Request Shizuku Permission"
            layoutParams = android.widget.LinearLayout.LayoutParams(
                android.widget.LinearLayout.LayoutParams.MATCH_PARENT,
                android.widget.LinearLayout.LayoutParams.WRAP_CONTENT
            ).apply { setMargins(0, 0, 0, 20) }
            setOnClickListener {
                requestShizukuPermission()
            }
        }
        layout.addView(btnPermission)

        btnDefaultSpam = Button(this).apply {
            text = "Set as Caller ID & Spam App"
            layoutParams = android.widget.LinearLayout.LayoutParams(
                android.widget.LinearLayout.LayoutParams.MATCH_PARENT,
                android.widget.LinearLayout.LayoutParams.WRAP_CONTENT
            ).apply { setMargins(0, 0, 0, 20) }
            setOnClickListener {
                requestCallScreeningRole()
            }
        }
        layout.addView(btnDefaultSpam)

        btnToggleBridge = Button(this).apply {
            text = "Start Manual Bridge (Test)"
            layoutParams = android.widget.LinearLayout.LayoutParams(
                android.widget.LinearLayout.LayoutParams.MATCH_PARENT,
                android.widget.LinearLayout.LayoutParams.WRAP_CONTENT
            )
            setOnClickListener {
                toggleManualBridge()
            }
        }
        layout.addView(btnToggleBridge)

        setContentView(layout)

        // Request standard dangerous permissions
        requestDangerousPermissions()

        // Register Shizuku listener
        Shizuku.addRequestPermissionResultListener(permissionListener)
        checkShizuku()
    }

    private fun checkShizuku() {
        if (!Shizuku.pingBinder()) {
            statusText.text = "Shizuku is NOT running!\nPlease start Shizuku first."
            btnPermission.isEnabled = false
            return
        }

        val hasPermission = Shizuku.checkSelfPermission() == PackageManager.PERMISSION_GRANTED
        updateShizukuStatus(hasPermission)
    }

    private fun updateShizukuStatus(granted: Boolean) {
        if (granted) {
            statusText.text = "Shizuku Status: PERMISSION GRANTED\nReady to capture calls."
            btnPermission.isEnabled = false
        } else {
            statusText.text = "Shizuku Status: PERMISSION DENIED\nPlease grant permission."
            btnPermission.isEnabled = true
        }
    }

    private fun requestShizukuPermission() {
        if (Shizuku.pingBinder()) {
            Shizuku.requestPermission(1001)
        } else {
            Toast.makeText(this, "Shizuku not running", Toast.LENGTH_SHORT).show()
        }
    }

    private fun requestCallScreeningRole() {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                val roleManager = getSystemService(android.app.role.RoleManager::class.java)
                if (roleManager != null && roleManager.isRoleAvailable(android.app.role.RoleManager.ROLE_CALL_SCREENING)) {
                    if (!roleManager.isRoleHeld(android.app.role.RoleManager.ROLE_CALL_SCREENING)) {
                        val intent = roleManager.createRequestRoleIntent(android.app.role.RoleManager.ROLE_CALL_SCREENING)
                        startActivityForResult(intent, 1004)
                    } else {
                        Toast.makeText(this, "Already the Caller ID & Spam App", Toast.LENGTH_SHORT).show()
                    }
                }
            } else {
                Toast.makeText(this, "Android 10+ required for background call interception", Toast.LENGTH_LONG).show()
            }
        } catch (e: Exception) {
            Toast.makeText(this, "Error: ${e.message}", Toast.LENGTH_LONG).show()
        }
    }

    private fun requestDangerousPermissions() {
        val permissions = arrayOf(
            Manifest.permission.RECORD_AUDIO,
            Manifest.permission.READ_PHONE_STATE,
            Manifest.permission.READ_CALL_LOG
        )
        val toRequest = permissions.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }
        if (toRequest.isNotEmpty()) {
            ActivityCompat.requestPermissions(this, toRequest.toTypedArray(), 1002)
        }
    }

    private var isManualBridgeRunning = false
    private fun toggleManualBridge() {
        if (!isManualBridgeRunning) {
            val intent = Intent(this, AudioBridgeService::class.java).apply {
                action = AudioBridgeService.ACTION_START_BRIDGE
            }
            startForegroundService(intent)
            btnToggleBridge.text = "Stop Manual Bridge"
            isManualBridgeRunning = true
            Toast.makeText(this, "Manual Bridge Started", Toast.LENGTH_SHORT).show()
        } else {
            val intent = Intent(this, AudioBridgeService::class.java).apply {
                action = AudioBridgeService.ACTION_STOP_BRIDGE
            }
            startForegroundService(intent)
            btnToggleBridge.text = "Start Manual Bridge (Test)"
            isManualBridgeRunning = false
            Toast.makeText(this, "Manual Bridge Stopped", Toast.LENGTH_SHORT).show()
        }
    }

    override fun onDestroy() {
        Shizuku.removeRequestPermissionResultListener(permissionListener)
        super.onDestroy()
    }
}
