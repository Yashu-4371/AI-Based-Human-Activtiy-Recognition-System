
from app.alerts.whatsapp_notifier import send_alert_whatsapp

recipient = input(
    "Enter the WhatsApp number that joined your Twilio Sandbox (with country code): "
).strip()

success = send_alert_whatsapp(
    patient_name="Test Patient",
    alert_type="test",
    message="This is a test notification. No real fall has occurred.",
    to_whatsapp=recipient,
)

print("Message accepted by Twilio." if success else
      "Message not sent. Check the backend terminal logs.")
