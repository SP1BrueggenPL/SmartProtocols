import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication


def send_email(settings, to_emails, subject, body, pdf_bytes=None, pdf_filename=None):
    """
    Send an email using SMTP settings from the database settings dict.
    Returns (success: bool, message: str).
    """
    smtp_host = settings.get('smtp_host', '').strip()
    smtp_port = int(settings.get('smtp_port', 587) or 587)
    smtp_user = settings.get('smtp_user', '').strip()
    smtp_pass = settings.get('smtp_pass', '').strip()
    smtp_from = settings.get('smtp_from', '').strip()
    smtp_from_name = settings.get('smtp_from_name', 'Dzial IT Brueggen Polska').strip()
    use_tls = settings.get('smtp_use_tls', '1') == '1'

    if not smtp_host:
        return False, 'Serwer SMTP nie jest skonfigurowany. Sprawdź ustawienia.'
    if not smtp_from:
        return False, 'Adres nadawcy (From) nie jest skonfigurowany.'

    # Filter out empty addresses
    recipients = [e.strip() for e in to_emails if e and e.strip()]
    if not recipients:
        return False, 'Brak adresów odbiorców.'

    try:
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = f'{smtp_from_name} <{smtp_from}>' if smtp_from_name else smtp_from
        msg['To'] = ', '.join(recipients)

        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        if pdf_bytes and pdf_filename:
            part = MIMEApplication(pdf_bytes, Name=pdf_filename)
            part['Content-Disposition'] = f'attachment; filename="{pdf_filename}"'
            msg.attach(part)

        context = ssl.create_default_context()

        if use_tls:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                if smtp_user:
                    server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_from, recipients, msg.as_bytes())
        else:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context, timeout=15) as server:
                if smtp_user:
                    server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_from, recipients, msg.as_bytes())

        return True, 'Wysłano pomyślnie.'

    except smtplib.SMTPAuthenticationError:
        return False, 'Błąd autoryzacji SMTP. Sprawdź login i hasło.'
    except smtplib.SMTPConnectError:
        return False, f'Nie można połączyć z serwerem {smtp_host}:{smtp_port}.'
    except Exception as e:
        return False, str(e)
