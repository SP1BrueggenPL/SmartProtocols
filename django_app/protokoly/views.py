import sys
import os
import secrets
import string

from datetime import date

# Mapowanie: klucz DB → nazwa zmiennej środowiskowej (Azure App Service)
_ENV_MAP = {
    'accounting_email':        'ACCOUNTING_EMAIL',
    'azure_connection_string': 'AZURE_CONNECTION_STRING',
    'azure_sender_address':    'AZURE_SENDER_ADDRESS',
    'azure_from_name':         'AZURE_FROM_NAME',
}

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User, Group
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import AppSetting, Document, DocumentItem, UserProfile

# pdf_gen and email_sender live in the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pdf_gen import generate_pdf
from email_sender import send_email


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_admin(user):
    """Tylko użytkownicy z flagą is_staff mają dostęp do ustawień."""
    return user.is_authenticated and user.is_staff


def _effective_settings():
    """Zwraca ustawienia email: env var ma priorytet nad bazą danych."""
    data = AppSetting.as_dict()
    for db_key, env_key in _ENV_MAP.items():
        val = os.environ.get(env_key, '').strip()
        if val:
            data[db_key] = val
    return data


def _env_overrides():
    """Zwraca słownik {db_key: True/False} — które pola są nadpisane przez env var."""
    return {db_key: bool(os.environ.get(env_key, '').strip())
            for db_key, env_key in _ENV_MAP.items()}

def _generate_temp_password(length=10):
    """Generuje bezpieczne tymczasowe hasło."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def _validate_password(pw):
    """Zwraca komunikat błędu lub None gdy hasło spełnia wymagania."""
    import re
    if len(pw) < 12:
        return 'Hasło musi mieć co najmniej 12 znaków.'
    if not re.search(r'[A-Z]', pw):
        return 'Hasło musi zawierać co najmniej jedną wielką literę.'
    if not re.search(r'[a-z]', pw):
        return 'Hasło musi zawierać co najmniej jedną małą literę.'
    if not re.search(r'\d', pw):
        return 'Hasło musi zawierać co najmniej jedną cyfrę.'
    if not re.search(r'[^A-Za-z0-9]', pw):
        return 'Hasło musi zawierać co najmniej jeden znak specjalny (np. !@#$%).'
    return None


def _generate_doc_number(doc_type):
    year = timezone.now().year
    prefix = {'office': 'OFF', 'telefon': 'TEL', 'produkcja': 'PRD'}.get(doc_type, 'DOC')
    count = Document.objects.filter(doc_type=doc_type, created_at__year=year).count()
    return f'IT-{prefix}-{year}-{str(count + 1).zfill(3)}'


def _save_items(request, doc):
    if doc.doc_type == 'telefon':
        DocumentItem.objects.create(
            document=doc,
            sort_order=0,
            phone_type=request.POST.get('phone_type', ''),
            imei=request.POST.get('imei', ''),
            serial_number=request.POST.get('serial_number', ''),
            internal_name=request.POST.get('internal_name', ''),
            phone_number=request.POST.get('phone_number', ''),
            sim_number=request.POST.get('sim_number', ''),
            pin_phone=request.POST.get('pin_phone', ''),
            pin_sim=request.POST.get('pin_sim', ''),
            acc_foil=bool(request.POST.get('acc_foil')),
            acc_case=bool(request.POST.get('acc_case')),
            acc_charger=bool(request.POST.get('acc_charger')),
            acc_headphones=bool(request.POST.get('acc_headphones')),
            notes=request.POST.get('notes', ''),
        )
    else:
        eq_types  = request.POST.getlist('equipment_type[]')
        mfr_list  = request.POST.getlist('manufacturer_model[]')
        serials   = request.POST.getlist('serial_number[]')
        qtys      = request.POST.getlist('quantity[]')
        internals = request.POST.getlist('internal_number[]')

        for i, eq_type in enumerate(eq_types):
            if eq_type.strip():
                qty_str = qtys[i] if i < len(qtys) else '1'
                DocumentItem.objects.create(
                    document=doc,
                    sort_order=i,
                    equipment_type=eq_type.strip(),
                    manufacturer_model=mfr_list[i] if i < len(mfr_list) else '',
                    serial_number=serials[i] if i < len(serials) else '',
                    quantity=int(qty_str) if qty_str.isdigit() else 1,
                    internal_number=internals[i] if i < len(internals) else '',
                )


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def index(request):
    return redirect('dashboard' if request.user.is_authenticated else 'login')


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user and user.is_active:
            login(request, user)
            return redirect('dashboard')
        error = 'Nieprawidłowa nazwa użytkownika lub hasło.'

    return render(request, 'login.html', {'error': error})


def logout_view(request):
    logout(request)
    return redirect('login')


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@login_required
def dashboard(request):
    doc_type      = request.GET.get('type', '')
    filter_status = request.GET.get('status', '')
    search_query  = request.GET.get('q', '').strip()

    qs = Document.objects.all()
    if doc_type:
        qs = qs.filter(doc_type=doc_type)
    if filter_status == 'draft':
        qs = qs.filter(sig_issuer='')
    elif filter_status == 'signed':
        qs = qs.exclude(sig_issuer='').filter(email_sent_at__isnull=True)
    elif filter_status == 'sent':
        qs = qs.filter(email_sent_at__isnull=False)

    if search_query:
        from django.db.models import Q
        qs = qs.filter(
            Q(doc_number__icontains=search_query) |
            Q(receiver_name__icontains=search_query) |
            Q(issuer_name__icontains=search_query) |
            Q(receiver_email__icontains=search_query) |
            Q(network_name__icontains=search_query)
        )

    stats = {
        'total':  qs.count(),
        'draft':  qs.filter(sig_issuer='').count(),
        'signed': qs.exclude(sig_issuer='').filter(email_sent_at__isnull=True).count(),
        'sent':   qs.filter(email_sent_at__isnull=False).count(),
    }

    return render(request, 'dashboard.html', {
        'documents':     qs,
        'filter_type':   doc_type,
        'filter_status': filter_status,
        'search_query':  search_query,
        'stats':         stats,
    })


# ---------------------------------------------------------------------------
# Document – new
# ---------------------------------------------------------------------------

@login_required
def document_new(request):
    return render(request, 'document_form.html',
                  {'document': None, 'items': [], 'mode': 'new'})


@login_required
def document_create(request):
    if request.method != 'POST':
        return redirect('document_new')

    doc_type = request.POST.get('doc_type', 'office')
    doc = Document(
        doc_number    = _generate_doc_number(doc_type),
        doc_type      = doc_type,
        operation     = request.POST.get('operation', 'wydanie'),
        doc_date      = request.POST.get('doc_date', str(date.today())),
        issuer_name   = request.POST.get('issuer_name', '').strip(),
        issuer_email  = request.POST.get('issuer_email', '').strip(),
        receiver_name = request.POST.get('receiver_name', '').strip(),
        receiver_email= request.POST.get('receiver_email', '').strip(),
        network_name  = request.POST.get('network_name', '').strip() if doc_type == 'office' else '',
        created_by    = request.user,
    )
    doc.save()
    _save_items(request, doc)

    messages.success(request, f'Protokół {doc.doc_number} został utworzony.')
    return redirect('document_view', pk=doc.pk)


# ---------------------------------------------------------------------------
# Document – view
# ---------------------------------------------------------------------------

@login_required
def document_view(request, pk):
    doc   = get_object_or_404(Document, pk=pk)
    items = doc.items.order_by('sort_order')
    return render(request, 'document_view.html', {'document': doc, 'items': items})


# ---------------------------------------------------------------------------
# Document – edit
# ---------------------------------------------------------------------------

@login_required
def document_edit(request, pk):
    doc = get_object_or_404(Document, pk=pk)
    if doc.sig_issuer:
        messages.warning(request, 'Dokument jest już podpisany i nie może być edytowany.')
        return redirect('document_view', pk=pk)

    if request.method == 'POST':
        doc.operation      = request.POST.get('operation', 'wydanie')
        doc.doc_date       = request.POST.get('doc_date', str(date.today()))
        doc.issuer_name    = request.POST.get('issuer_name', '').strip()
        doc.issuer_email   = request.POST.get('issuer_email', '').strip()
        doc.receiver_name  = request.POST.get('receiver_name', '').strip()
        doc.receiver_email = request.POST.get('receiver_email', '').strip()
        doc.network_name   = request.POST.get('network_name', '').strip() if doc.doc_type == 'office' else ''
        doc.save()

        doc.items.all().delete()
        _save_items(request, doc)

        messages.success(request, 'Dokument został zaktualizowany.')
        return redirect('document_view', pk=pk)

    items = doc.items.order_by('sort_order')
    return render(request, 'document_form.html',
                  {'document': doc, 'items': items, 'mode': 'edit'})


# ---------------------------------------------------------------------------
# Document – sign
# ---------------------------------------------------------------------------

@login_required
def document_sign(request, pk):
    doc   = get_object_or_404(Document, pk=pk)
    items = doc.items.order_by('sort_order')

    if request.method == 'POST':
        sig_issuer   = request.POST.get('sig_issuer', '').strip()
        sig_receiver = request.POST.get('sig_receiver', '').strip()

        if not sig_issuer or not sig_receiver:
            messages.warning(request, 'Oba podpisy są wymagane.')
            return render(request, 'document_sign.html', {'document': doc, 'items': items})

        doc.sig_issuer   = sig_issuer
        doc.sig_receiver = sig_receiver
        doc.signed_at    = timezone.now()
        doc.save()

        messages.success(request, 'Podpisy zostały zapisane pomyślnie.')
        return redirect('document_view', pk=pk)

    return render(request, 'document_sign.html', {'document': doc, 'items': items})


# ---------------------------------------------------------------------------
# Document – PDF download
# ---------------------------------------------------------------------------

@login_required
def document_pdf(request, pk):
    doc   = get_object_or_404(Document, pk=pk)
    items = list(doc.items.order_by('sort_order'))

    pdf_bytes = generate_pdf(doc, items)
    response  = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{doc.doc_number}.pdf"'
    return response


# ---------------------------------------------------------------------------
# Document – send email
# ---------------------------------------------------------------------------

@login_required
def document_send(request, pk):
    if request.method != 'POST':
        return redirect('document_view', pk=pk)

    doc = get_object_or_404(Document, pk=pk)

    if not doc.is_signed:
        messages.warning(request, 'Dokument musi być podpisany przed wysłaniem.')
        return redirect('document_view', pk=pk)

    items         = list(doc.items.order_by('sort_order'))
    settings_data = _effective_settings()
    pdf_bytes     = generate_pdf(doc, items)

    op_label   = 'wydania'  if doc.operation == 'wydanie' else 'zwrotu'
    type_label = doc.doc_type_label

    subject = f'Protokół {op_label} sprzętu IT ({type_label}) – {doc.doc_number}'
    body = (
        f'Szanowni Państwo,\n\n'
        f'W załączniku przesyłamy podpisany protokół {op_label} sprzętu IT ({type_label}).\n\n'
        f'Numer dokumentu: {doc.doc_number}\n'
        f'Data: {doc.doc_date_str}\n'
        f'Przekazujący: {doc.issuer_name}\n'
        f'Przyjmujący: {doc.receiver_name}\n\n'
        f'Z poważaniem,\nDział IT Brueggen Polska Sp. z o.o.'
    )

    seen, to_list = set(), []
    for addr in [doc.receiver_email, doc.issuer_email,
                 settings_data.get('accounting_email', '')]:
        addr = addr.strip()
        if addr and addr not in seen:
            seen.add(addr)
            to_list.append(addr)
    success, msg = send_email(
        settings=settings_data,
        to_emails=to_list,
        subject=subject,
        body=body,
        pdf_bytes=pdf_bytes,
        pdf_filename=f'{doc.doc_number}.pdf',
    )

    if success:
        doc.email_sent_at = timezone.now()
        doc.save()
        messages.success(request, f'Protokół wysłany do: {", ".join(to_list)}')
    else:
        messages.error(request, f'Błąd wysyłki: {msg}')

    return redirect('document_view', pk=pk)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Wymuszona zmiana hasła (po resecie przez admina)
# ---------------------------------------------------------------------------

@login_required
def change_password_forced(request):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        return redirect('dashboard')

    if not profile.must_change_password:
        return redirect('dashboard')

    error = None
    if request.method == 'POST':
        new_pw      = request.POST.get('new_password', '').strip()
        confirm_pw  = request.POST.get('confirm_password', '').strip()
        if not new_pw:
            error = 'Hasło nie może być puste.'
        elif new_pw != confirm_pw:
            error = 'Hasła nie są zgodne.'
        else:
            error = _validate_password(new_pw)
        if not error:
            request.user.set_password(new_pw)
            request.user.save()
            profile.must_change_password = False
            profile.save()
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, request.user)
            messages.success(request, 'Hasło zostało zmienione. Witaj w systemie!')
            return redirect('dashboard')

    return render(request, 'change_password.html', {'error': error})


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@user_passes_test(_is_admin, login_url='dashboard')
def settings_view(request):
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'email_settings':
            for key in ['accounting_email', 'azure_connection_string',
                        'azure_sender_address', 'azure_from_name']:
                AppSetting.set(key, request.POST.get(key, ''))
            messages.success(request, 'Ustawienia zostały zapisane.')

        elif action == 'test_email':
            test_addr = request.POST.get('test_email', '').strip()
            if test_addr:
                ok, err = send_email(
                    settings=_effective_settings(),
                    to_emails=[test_addr],
                    subject='Test – IT Protokoly Brueggen Polska',
                    body='Wiadomość testowa z systemu IT Protokoly (Django).',
                    pdf_bytes=None,
                    pdf_filename=None,
                )
                if ok:
                    messages.success(request, f'Email testowy wysłany do {test_addr}')
                else:
                    messages.error(request, f'Błąd: {err}')

        elif action == 'add_user':
            username   = request.POST.get('new_username', '').strip()
            full_name  = request.POST.get('new_full_name', '').strip()
            password   = request.POST.get('new_password', '').strip()
            group_name = request.POST.get('new_group', 'Użytkownicy').strip()
            if username and full_name and password:
                if User.objects.filter(username=username).exists():
                    messages.error(request, f'Użytkownik "{username}" już istnieje.')
                else:
                    first, _, last = full_name.partition(' ')
                    is_admin_grp = (group_name == 'Administratorzy')
                    new_user = User.objects.create_user(
                        username=username, password=password,
                        first_name=first, last_name=last,
                        is_staff=is_admin_grp,
                    )
                    try:
                        grp = Group.objects.get(name=group_name)
                        new_user.groups.set([grp])
                    except Group.DoesNotExist:
                        pass
                    # Wymusz zmianę hasła przy pierwszym logowaniu
                    profile, _ = UserProfile.objects.get_or_create(user=new_user)
                    profile.must_change_password = True
                    profile.save()
                    messages.success(request, f'Użytkownik {username} dodany do grupy „{group_name}". Przy pierwszym logowaniu zostanie poproszony o zmianę hasła.')
            else:
                messages.warning(request, 'Wypełnij wszystkie pola.')

        elif action == 'reset_password':
            user_id  = request.POST.get('user_id')
            temp     = request.POST.get('temp_password', '').strip()
            pw_error = _validate_password(temp) if temp else 'Podaj tymczasowe hasło.'
            if pw_error:
                messages.error(request, pw_error)
            elif user_id and int(user_id) != request.user.pk:
                try:
                    u = User.objects.get(pk=user_id)
                    u.set_password(temp)
                    u.save()
                    profile, _ = UserProfile.objects.get_or_create(user=u)
                    profile.must_change_password = True
                    profile.save()
                    name = u.get_full_name() or u.username
                    messages.success(request, f'Hasło użytkownika „{name}" zostało zresetowane.')
                except User.DoesNotExist:
                    pass
            else:
                messages.warning(request, 'Nie możesz zresetować własnego hasła.')

        elif action == 'toggle_user':
            user_id = request.POST.get('user_id')
            if user_id and int(user_id) != request.user.pk:
                try:
                    u = User.objects.get(pk=user_id)
                    u.is_active = not u.is_active
                    u.save()
                    messages.success(request, 'Status użytkownika zmieniony.')
                except User.DoesNotExist:
                    pass
            else:
                messages.warning(request, 'Nie możesz dezaktywować własnego konta.')

        elif action == 'delete_user':
            user_id = request.POST.get('user_id')
            if user_id and int(user_id) != request.user.pk:
                try:
                    u    = User.objects.get(pk=user_id)
                    name = u.get_full_name() or u.username
                    u.delete()
                    messages.success(request, f'Użytkownik „{name}" został usunięty.')
                except User.DoesNotExist:
                    pass
            else:
                messages.warning(request, 'Nie możesz usunąć własnego konta.')

        elif action == 'assign_group':
            user_id    = request.POST.get('user_id')
            group_name = request.POST.get('group_name', '').strip()
            if user_id and int(user_id) != request.user.pk:
                try:
                    u   = User.objects.get(pk=user_id)
                    grp = Group.objects.get(name=group_name)
                    u.groups.set([grp])
                    u.is_staff = (group_name == 'Administratorzy')
                    u.save()
                    messages.success(request, f'Użytkownik {u.get_full_name() or u.username} przypisany do grupy „{group_name}".')
                except (User.DoesNotExist, Group.DoesNotExist):
                    messages.error(request, 'Błąd przypisania grupy.')
            else:
                messages.warning(request, 'Nie możesz zmienić własnej grupy.')

        return redirect('settings')

    users_qs = list(
        User.objects.prefetch_related('groups', 'profile')
                    .order_by('first_name', 'last_name')
    )
    for u in users_qs:
        grp = u.groups.first()
        u.current_group = grp.name if grp else ''
        try:
            u.must_change_pw = u.profile.must_change_password
        except UserProfile.DoesNotExist:
            u.must_change_pw = False

    env_ov       = _env_overrides()
    azure_in_env = all(env_ov.get(k) for k in
                       ['azure_connection_string', 'azure_sender_address'])

    return render(request, 'settings.html', {
        'settings':      AppSetting.as_dict(),   # wartości z bazy (do pól edytowalnych)
        'env_overrides': env_ov,                  # które pola ma env var
        'azure_in_env':  azure_in_env,            # czy Azure w pełni skonfigurowane z env
        'users':         users_qs,
        'groups':        Group.objects.order_by('name'),
    })
