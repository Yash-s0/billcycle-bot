package com.example.billcycle_mobile

import android.content.Intent
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification

class TransactionNotificationListenerService : NotificationListenerService() {
  override fun onNotificationPosted(sbn: StatusBarNotification) {
    val extras = sbn.notification.extras ?: return
    val title = extras.getCharSequence("android.title")?.toString().orEmpty()
    val text = extras.getCharSequence("android.text")?.toString().orEmpty()

    if (title.isBlank() && text.isBlank()) {
      return
    }

    val intent = Intent(ACTION_TXN_NOTIFICATION).apply {
      setPackage(packageName)
      putExtra("key", sbn.key)
      putExtra("package", sbn.packageName)
      putExtra("title", title)
      putExtra("text", text)
      putExtra("postedAt", sbn.postTime)
    }
    sendBroadcast(intent)
  }

  companion object {
    const val ACTION_TXN_NOTIFICATION = "com.example.billcycle_mobile.TXN_NOTIFICATION"
  }
}
