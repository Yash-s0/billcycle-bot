package com.example.billcycle_mobile

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.Build
import android.provider.Settings
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
  private val controlChannelName = "billcycle/notification_control"
  private val eventsChannelName = "billcycle/notification_events"
  private var receiver: BroadcastReceiver? = null

  override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
    super.configureFlutterEngine(flutterEngine)

    MethodChannel(flutterEngine.dartExecutor.binaryMessenger, controlChannelName)
      .setMethodCallHandler { call, result ->
        when (call.method) {
          "openNotificationListenerSettings" -> {
            startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
            result.success(null)
          }

          "isNotificationListenerEnabled" -> {
            result.success(isNotificationListenerEnabled())
          }

          else -> result.notImplemented()
        }
      }

    EventChannel(flutterEngine.dartExecutor.binaryMessenger, eventsChannelName)
      .setStreamHandler(object : EventChannel.StreamHandler {
        override fun onListen(arguments: Any?, events: EventChannel.EventSink?) {
          if (receiver != null) {
            return
          }
          receiver = object : BroadcastReceiver() {
            override fun onReceive(context: Context?, intent: Intent?) {
              if (events == null || intent == null) {
                return
              }
              val payload = mapOf(
                "key" to intent.getStringExtra("key").orEmpty(),
                "package" to intent.getStringExtra("package").orEmpty(),
                "title" to intent.getStringExtra("title").orEmpty(),
                "text" to intent.getStringExtra("text").orEmpty(),
                "postedAt" to intent.getLongExtra("postedAt", 0L),
              )
              events.success(payload)
            }
          }

          val filter = IntentFilter(TransactionNotificationListenerService.ACTION_TXN_NOTIFICATION)
          if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(receiver, filter, RECEIVER_NOT_EXPORTED)
          } else {
            @Suppress("DEPRECATION")
            registerReceiver(receiver, filter)
          }
        }

        override fun onCancel(arguments: Any?) {
          if (receiver != null) {
            unregisterReceiver(receiver)
            receiver = null
          }
        }
      })
  }

  private fun isNotificationListenerEnabled(): Boolean {
    val enabled = Settings.Secure.getString(contentResolver, "enabled_notification_listeners") ?: return false
    return enabled.contains(packageName)
  }
}
