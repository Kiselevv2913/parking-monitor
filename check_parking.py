
import os
import json
import smtplib
import traceback
from datetime import datetime
from zoneinfo import ZoneInfo
from email.message import EmailMessage
from playwright.sync_api import sync_playwright

# Настройки сайта
URL = "https://parking.mos.ru/parking/barrier/subscribe/"

PARKINGS = {
    "Черкизовская, участок 2": "112",
    "Черкизовская, участок 3": "118"
}

MONTHS = {
    "Текущий месяц": "parking-barries-checkbox1",
    "Следующий месяц": "parking-barries-checkbox2"
}

REGION_ID = "0400"
STATUS_FILE = "parking_status.json"

# Московское время
MOSCOW_TZ = ZoneInfo("Europe/Moscow")

# Почта
EMAIL_ADDRESS = "kiselev.dm.s@yandex.ru"
EMAIL_TO = "kiselev.dm.s@yandex.ru"
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")


def now_moscow():
    return datetime.now(MOSCOW_TZ)


def send_email(subject, message):
    if not EMAIL_PASSWORD:
        raise RuntimeError("Не задан секрет EMAIL_PASSWORD в GitHub.")

    email = EmailMessage()
    email["Subject"] = subject
    email["From"] = EMAIL_ADDRESS
    email["To"] = EMAIL_TO
    email.set_content(message)

    with smtplib.SMTP_SSL(
        "smtp.yandex.ru", 465, timeout=30
    ) as server:
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(email)

    print("Письмо успешно отправлено!")


def load_status():
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, "r", encoding="utf-8") as file:
                return json.load(file)
        except (json.JSONDecodeError, OSError):
            print("Не удалось прочитать старое состояние.")

    return {}


def save_status(status):
    with open(STATUS_FILE, "w", encoding="utf-8") as file:
        json.dump(status, file, ensure_ascii=False, indent=4)


def select_region(page):
    region_list = page.locator(".select-region--js")
    region_select = region_list.locator("xpath=..")

    region_select.locator(".select__header").click()

    region = region_list.locator(
        f'[data-value="{REGION_ID}"]'
    )

    region.wait_for(state="visible", timeout=15000)
    region.click()

    page.locator(
        '.select-parking--js [data-value="112"]'
    ).wait_for(state="attached", timeout=20000)

    page.wait_for_timeout(1000)


def check_parkings(page, month_name, checkbox_id):
    checkbox = page.locator(f"#{checkbox_id}")

    if not checkbox.is_checked():
        page.locator(
            f'label[for="{checkbox_id}"]'
        ).click()

    page.wait_for_timeout(1500)

    select_region(page)

    results = {}

    for name, parking_id in PARKINGS.items():
        element = page.locator(
            f'.select-parking--js [data-value="{parking_id}"]'
        )

        if element.count() == 0:
            raise RuntimeError(f"Не найден участок: {name}")

        classes = element.first.get_attribute("class") or ""

        available = "disabledVar" not in classes.split()

        results[name] = available

        print(
            f"{name}: "
            f"{'ДОСТУПЕН' if available else 'НЕДОСТУПЕН'}"
        )

    return results


def send_daily_report(current_status):
    current_time = now_moscow()

    report = [
        "Ежедневный контрольный отчёт мониторинга парковок.",
        "",
        f"Дата и время: {current_time.strftime('%d.%m.%Y %H:%M:%S')}",
        "",
        "Результаты проверки:"
    ]

    for key, available in current_status.items():
        if key.startswith("__"):
            continue

        month_name, parking_name = key.split("|", 1)

        report.append(
            f"{month_name}, {parking_name}: "
            f"{'ДОСТУПЕН' if available else 'НЕДОСТУПЕН'}"
        )

    report.extend([
        "",
        "Проверка сайта завершилась успешно.",
        "Мониторинг работает."
    ])

    send_email(
        "Мониторинг парковок — ежедневный отчёт",
        "\n".join(report)
    )


def main():
    print("=" * 55)
    print("МОНИТОРИНГ ПАРКОВОК")
    print("Время проверки:", now_moscow().strftime("%d.%m.%Y %H:%M:%S"))
    print("=" * 55)

    old_status = load_status()
    current_status = {}

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            try:
                page = browser.new_page()

                page.goto(
                    URL,
                    wait_until="domcontentloaded",
                    timeout=60000
                )

                page.wait_for_timeout(5000)

                for month_name, checkbox_id in MONTHS.items():
                    print(f"\nПроверяем: {month_name}")

                    results = check_parkings(
                        page, month_name, checkbox_id
                    )

                    for parking_name, available in results.items():
                        key = f"{month_name}|{parking_name}"
                        current_status[key] = available

                        if old_status.get(key) is False and available:
                            print("ОБНАРУЖЕНА ДОСТУПНОСТЬ!")

                            send_email(
                                "Появилось место на парковке!",
                                f"Обнаружена доступность:\n"
                                f"{month_name}\n"
                                f"{parking_name}\n\n"
                                f"Время проверки: "
                                f"{now_moscow().strftime('%d.%m.%Y %H:%M:%S')}"
                            )

            finally:
                browser.close()

        print("\nПроверка завершена успешно.")

        # Проверяем необходимость ежедневного письма
        current_time = now_moscow()
        today = current_time.strftime("%Y-%m-%d")

        last_report_date = old_status.get("__last_daily_report_date")

        if current_time.hour >= 7 and last_report_date != today:
            print("\nВремя отправить ежедневный отчёт.")

            send_daily_report(current_status)

            current_status["__last_daily_report_date"] = today

        elif last_report_date == today:
            current_status["__last_daily_report_date"] = today

        save_status(current_status)

        print("Результаты сохранены.")
        print("Работа завершена успешно.")

    except Exception as error:
        print("\nОШИБКА МОНИТОРИНГА:")
        traceback.print_exc()

        error_message = (
            "Во время проверки парковок произошла ошибка.\n\n"
            f"Время: {now_moscow().strftime('%d.%m.%Y %H:%M:%S')}\n\n"
            f"Описание ошибки:\n{str(error)}\n\n"
            "Подробности:\n"
            f"{traceback.format_exc()}"
        )

        try:
            send_email(
                "ОШИБКА мониторинга парковок!",
                error_message
            )
        except Exception as email_error:
            print("Не удалось отправить письмо об ошибке:")
            print(email_error)

        raise


if __name__ == "__main__":
    main()
