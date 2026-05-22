from django.apps import AppConfig


class ProtokolyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'protokoly'
    verbose_name = 'Protokoły IT'

    def ready(self):
        from django.db.models.signals import post_migrate
        post_migrate.connect(_create_initial_data, sender=self)


def _create_initial_data(sender, **kwargs):
    from django.contrib.auth.models import User
    from .models import AppSetting

    if not User.objects.exists():
        User.objects.create_user(
            username='admin',
            password='admin123',
            first_name='Administrator',
            last_name='IT',
        )
        print('Utworzono domyslnego uzytkownika: admin / admin123')

    defaults = [
        ('accounting_email',        ''),
        ('azure_connection_string', ''),
        ('azure_sender_address',    ''),
        ('azure_from_name',         'Dzial IT Brueggen Polska'),
    ]
    for key, value in defaults:
        AppSetting.objects.get_or_create(pk=key, defaults={'value': value})
