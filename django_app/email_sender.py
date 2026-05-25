"""
Email sender using Azure Communication Services Email SDK.

Required setting keys (stored in AppSetting):
  azure_connection_string  – full connection string from Azure portal
  azure_sender_address     – verified sender, e.g. DoNotReply@yourdomain.azurecomm.net
  azure_from_name          – display name for From header (optional)
  accounting_email         – always CC'd on every sent protocol
"""
import base64


def send_email(settings, to_emails, subject, body, pdf_bytes=None, pdf_filename=None):
    """
    Send email via Azure Communication Services.
    Returns (success: bool, message: str).
    """
    connection_string = settings.get('azure_connection_string', '').strip()
    sender_address    = settings.get('azure_sender_address', '').strip()

    if not connection_string:
        return False, ('Azure Communication Services connection string nie jest skonfigurowany. '
                       'Przejdź do Ustawień i uzupełnij dane Azure.')
    if not sender_address:
        return False, ('Adres nadawcy Azure nie jest skonfigurowany. '
                       'Uzupełnij "Azure Sender Address" w Ustawieniach.')

    recipients = [e.strip() for e in to_emails if e and e.strip()]
    if not recipients:
        return False, 'Brak adresów odbiorców.'

    try:
        from azure.communication.email import EmailClient

        client = EmailClient.from_connection_string(connection_string)

        message = {
            'senderAddress': sender_address,
            'recipients': {
                'to': [{'address': addr} for addr in recipients],
            },
            'content': {
                'subject': subject,
                'plainText': body,
            },
        }

        if pdf_bytes and pdf_filename:
            message['attachments'] = [
                {
                    'name':          pdf_filename,
                    'contentType':   'application/pdf',
                    'contentInBase64': base64.b64encode(pdf_bytes).decode('ascii'),
                }
            ]

        poller = client.begin_send(message)
        result = poller.result()

        # SDK >= 1.0 returns EmailSendResult object; older versions return a dict
        status = str(getattr(result, 'status', None) or result.get('status', ''))
        if status == 'Succeeded':
            return True, 'Wysłano pomyślnie przez Azure Communication Services.'

        error_detail = ''
        err = getattr(result, 'error', None)
        if err:
            error_detail = getattr(err, 'message', str(err))
        elif callable(getattr(result, 'get', None)) and result.get('error'):
            error_detail = result['error'].get('message', str(result['error']))
        return False, f'Azure zwróciło status "{status}". {error_detail}'.strip()

    except ImportError:
        return False, ('Pakiet azure-communication-email nie jest zainstalowany. '
                       'Uruchom: pip install azure-communication-email')
    except Exception as exc:
        return False, str(exc)
