import django
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'brueggen.settings')
django.setup()

from django.contrib.auth.models import User, Group
from protokoly.models import AppSetting, UserProfile

# Grupy
grp_admin, _ = Group.objects.get_or_create(name='Administratorzy')
grp_user,  _ = Group.objects.get_or_create(name='Użytkownicy')
print('Grupy: OK')

if not User.objects.exists():
    u = User.objects.create_user(
        username='admin', password='admin123',
        first_name='Administrator', last_name='IT',
        is_staff=True,
    )
    u.groups.set([grp_admin])
    print('Utworzono uzytkownika: admin / admin123 (Administratorzy)')
else:
    # Upewnij sie, ze konto 'admin' ma uprawnienia i grupe admina
    admin = User.objects.filter(username='admin').first()
    if admin:
        admin.is_staff = True
        admin.save()
        if not admin.groups.exists():
            admin.groups.set([grp_admin])
    names = list(User.objects.values_list('username', flat=True))
    print(f'Istniejacy uzytkownicy: {names}')

    # Uzytkownicy bez zadnej grupy → Uzytkownicy
    for u in User.objects.all():
        if not u.groups.exists():
            grp = grp_admin if u.is_staff else grp_user
            u.groups.set([grp])
            print(f'  Przypisano {u.username} → {grp.name}')

defaults = [
    ('accounting_email',        ''),
    ('azure_connection_string', ''),
    ('azure_sender_address',    ''),
    ('azure_from_name',         'Dzial IT Brueggen Polska'),
]
for key, value in defaults:
    AppSetting.objects.get_or_create(pk=key, defaults={'value': value})

# Profile dla istniejacych uzytkownikow (bez flagi must_change_password)
for u in User.objects.all():
    UserProfile.objects.get_or_create(user=u)
print('Profile uzytkownikow: OK')

print('Ustawienia domyslne: OK')
print('Inicjalizacja zakonczona pomyslnie.')
