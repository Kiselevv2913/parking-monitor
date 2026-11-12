
import os
import smtplib
from email.message import EmailMessage

EMAIL_ADDRESS = "kiselev.dm.s@yandex.ru"
EMAIL_TO = "kiselev.dm.s@yandex.ru"
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

if not EMAIL_PASSWORD:
    raise RuntimeError("Не найден EMAIL_PASSWORD в GitHub Secrets")

email = EmailMessage()
email["Subject"] = "Тест отправки почты из GitHub"
email["From"] = EMAIL_ADDRESS
email["To"] = EMAIL_TO
email.set_content(
    "Поздравляю! Если ты получил это письмо, "
    "отправка через SMTP Яндекса из GitHub работает."
)

print("Подключаемся к Яндекс SMTP...")

with smtplib.SMTP_SSL("smtp.yandex.ru", 465, timeout=30) as server:
    server.login("kiselev.dm.s@yandex.ru", EMAIL_PASSWORD)
    print("Авторизация успешна!")

    server.send_message(email)
    print("Тестовое письмо отправлено!")

print("ТЕСТ ЗАВЕРШЁН УСПЕШНО")
