from plyer import notification
import time

def send_desktop_notification(title, message):
    """Triggers a native Windows desktop notification."""
    try:
        notification.notify(
            title=title,
            message=message,
            app_name="SlothContributor",
            timeout=10 
        )
    except Exception as e:
        print(f"Failed to send notification: {e}")