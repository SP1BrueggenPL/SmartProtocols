import io
import os
import sys

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.forms import inlineformset_factory
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import AuditInspection, AuditRequirement, InspectionResult, ServerAudit

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Helpers ──────────────────────────────────────────────────────────────────

def _is_admin(user):
    return user.is_authenticated and user.is_staff


def _is_audit_manager(user):
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    return user.groups.filter(name='AuditManager').exists()


def _effective_settings():
    from protokoly.models import AppSetting
    ENV_MAP = {
        'azure_connection_string': 'AZURE_CONNECTION_STRING',
        'azure_sender_address':    'AZURE_SENDER_ADDRESS',
        'azure_from_name':         'AZURE_FROM_NAME',
        'helpdesk_email':          'HELPDESK_EMAIL',
    }
    data = AppSetting.as_dict()
    for db_key, env_key in ENV_MAP.items():
        val = os.environ.get(env_key, '').strip()
        if val:
            data[db_key] = val
    return data


def _generate_inspection_pdf(inspection):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.enums import TA_CENTER

    results = list(inspection.results.select_related('requirement').all())
    audit   = inspection.audit

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles     = getSampleStyleSheet()
    cell_style = ParagraphStyle('Cell', parent=styles['Normal'], fontSize=8, leading=10)
    meta_style = ParagraphStyle('Meta', parent=styles['Normal'], fontSize=10, spaceAfter=2)
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=14,
                                  alignment=TA_CENTER, spaceAfter=6)

    inspector = inspection.user.get_full_name() if inspection.user else '—'
    started   = inspection.created_at.strftime('%Y-%m-%d %H:%M') if inspection.created_at else '—'
    finished  = inspection.completed_at.strftime('%Y-%m-%d %H:%M') if inspection.completed_at else 'W trakcie'

    story = [
        Paragraph('Raport inspekcji serwerowni', title_style),
        Paragraph(f'<b>Audyt:</b> {audit.name}', meta_style),
        Paragraph(f'<b>Inspektor:</b> {inspector}', meta_style),
        Paragraph(f'<b>Start:</b> {started}', meta_style),
        Paragraph(f'<b>Zakończenie:</b> {finished}', meta_style),
        Spacer(1, 0.5 * cm),
    ]

    style_cmds = [
        ('BACKGROUND',    (0, 0), (-1,  0), colors.HexColor('#2c5282')),
        ('TEXTCOLOR',     (0, 0), (-1,  0), colors.white),
        ('FONTNAME',      (0, 0), (-1,  0), 'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, -1), 8),
        ('ALIGN',         (2, 0), (2,  -1), 'CENTER'),
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('GRID',          (0, 0), (-1, -1), 0.5, colors.grey),
        ('TOPPADDING',    (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]

    data = [['#', 'Punkt kontrolny', 'Status', 'Komentarz']]
    for i, result in enumerate(results, 1):
        req_text = result.requirement.text if result.requirement else '—'
        status   = 'OK' if result.is_met else 'NOK'
        comment  = result.comment or '—'
        data.append([str(i), Paragraph(req_text, cell_style), status, Paragraph(comment, cell_style)])
        if not result.is_met:
            style_cmds.append(('BACKGROUND', (0, i), (-1, i), colors.Color(1, 0.88, 0.88)))

    col_w = [1*cm, 7.5*cm, 2*cm, 6.5*cm]
    table = Table(data, colWidths=col_w, repeatRows=1)
    table.setStyle(TableStyle(style_cmds))
    story.append(table)

    doc.build(story)
    return buf.getvalue()


def _send_failure_email(inspection):
    """Wysyła raport o niezgodnościach do helpdesk przez Azure."""
    from email_sender import send_email
    settings_data = _effective_settings()
    helpdesk_email = settings_data.get('helpdesk_email', '').strip()
    if not helpdesk_email:
        return False, 'Brak adresu helpdesk w ustawieniach.'

    audit = inspection.audit
    failed = inspection.results.filter(is_met=False).select_related('requirement')
    failed_lines = '\n'.join(
        f'  • {r.requirement.text if r.requirement else "—"}: {r.comment or "(brak komentarza)"}'
        for r in failed
    )
    inspector = inspection.user.get_full_name() if inspection.user else '—'
    finished  = inspection.completed_at.strftime('%Y-%m-%d %H:%M') if inspection.completed_at else '—'

    body = (
        f'Inspekcja serwerowni – wykryto niezgodności\n\n'
        f'Audyt:     {audit.name}\n'
        f'Inspektor: {inspector}\n'
        f'Data:      {finished}\n\n'
        f'Niezgodne punkty:\n{failed_lines}\n\n'
        f'Proszę o weryfikację i podjęcie działań naprawczych.\n\n'
        f'Z poważaniem,\nIT Tools Wilga – Brueggen Polska Sp. z o.o.'
    )

    pdf_bytes    = _generate_inspection_pdf(inspection)
    pdf_filename = f'inspekcja_{audit.name}_{inspection.pk}.pdf'

    return send_email(
        settings=settings_data,
        to_emails=[helpdesk_email],
        subject=f'[Serwerownia] Niezgodności – {audit.name} – {finished}',
        body=body,
        pdf_bytes=pdf_bytes,
        pdf_filename=pdf_filename,
    )


# ── Forms ─────────────────────────────────────────────────────────────────────

class ServerAuditForm(forms.ModelForm):
    class Meta:
        model  = ServerAudit
        fields = ['name', 'description']
        labels = {'name': 'Nazwa audytu', 'description': 'Opis'}
        widgets = {
            'name':        forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'np. Audyt serwerowni – Hala A'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Opcjonalny opis…'}),
        }


RequirementFormSet = inlineformset_factory(
    ServerAudit, AuditRequirement,
    fields=['text', 'image'],
    extra=3,
    can_delete=True,
    labels={'text': 'Punkt kontrolny', 'image': 'Zdjęcie przykładowe'},
    widgets={
        'text':  forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'np. Zasilanie UPS sprawne'}),
        'image': forms.ClearableFileInput(attrs={'class': 'form-control form-control-sm'}),
    },
)


# ── Audit CRUD ────────────────────────────────────────────────────────────────

@user_passes_test(_is_audit_manager, login_url='dashboard')
def audit_list(request):
    audits = ServerAudit.objects.all()
    return render(request, 'serwerownia/audit_list.html', {'audits': audits})


@user_passes_test(_is_audit_manager, login_url='dashboard')
def audit_detail(request, pk):
    audit      = get_object_or_404(ServerAudit, pk=pk)
    inspections = audit.inspections.select_related('user').all()
    for insp in inspections:
        insp.fail_count = insp.results.filter(is_met=False).count()
    return render(request, 'serwerownia/audit_detail.html', {
        'audit': audit, 'inspections': inspections,
    })


@user_passes_test(_is_admin, login_url='audit_list')
def audit_new(request):
    if request.method == 'POST':
        form    = ServerAuditForm(request.POST)
        formset = RequirementFormSet(request.POST, request.FILES)
        if form.is_valid():
            audit           = form.save()
            formset.instance = audit
            if formset.is_valid():
                reqs = formset.save(commit=False)
                for i, req in enumerate(reqs):
                    req.order = i
                    req.save()
                for obj in formset.deleted_objects:
                    obj.delete()
                messages.success(request, f'Audyt „{audit.name}" został utworzony.')
                return redirect('audit_detail', pk=audit.pk)
    else:
        form    = ServerAuditForm()
        formset = RequirementFormSet(instance=ServerAudit())
    return render(request, 'serwerownia/audit_form.html', {
        'form': form, 'formset': formset, 'mode': 'new',
    })


@user_passes_test(_is_admin, login_url='audit_list')
def audit_edit(request, pk):
    audit = get_object_or_404(ServerAudit, pk=pk)
    if request.method == 'POST':
        form    = ServerAuditForm(request.POST, instance=audit)
        formset = RequirementFormSet(request.POST, request.FILES, instance=audit)
        if form.is_valid() and formset.is_valid():
            form.save()
            reqs = formset.save(commit=False)
            for i, req in enumerate(reqs):
                req.order = i
                req.save()
            for obj in formset.deleted_objects:
                obj.delete()
            messages.success(request, 'Audyt został zaktualizowany.')
            return redirect('audit_detail', pk=audit.pk)
    else:
        form    = ServerAuditForm(instance=audit)
        formset = RequirementFormSet(instance=audit)
    return render(request, 'serwerownia/audit_form.html', {
        'form': form, 'formset': formset, 'mode': 'edit', 'audit': audit,
    })


@user_passes_test(_is_admin, login_url='audit_list')
def audit_delete(request, pk):
    audit = get_object_or_404(ServerAudit, pk=pk)
    if request.method == 'POST':
        name = audit.name
        audit.delete()
        messages.success(request, f'Audyt „{name}" został usunięty.')
        return redirect('audit_list')
    return render(request, 'serwerownia/audit_confirm_delete.html', {'audit': audit})


# ── Inspection ────────────────────────────────────────────────────────────────

@user_passes_test(_is_audit_manager, login_url='dashboard')
def inspection_start(request, audit_pk):
    """Tworzy nową inspekcję NATYCHMIAST (timer startuje od tego momentu) i przekierowuje do formularza."""
    audit = get_object_or_404(ServerAudit, pk=audit_pk)
    reqs  = list(audit.requirements.all())

    if not reqs:
        messages.warning(request, 'Audyt nie ma żadnych punktów kontrolnych. Dodaj je przed inspekcją.')
        return redirect('audit_detail', pk=audit_pk)

    inspection = AuditInspection.objects.create(audit=audit, user=request.user)
    for req in reqs:
        InspectionResult.objects.create(inspection=inspection, requirement=req, is_met=False)

    return redirect('inspection_fill', audit_pk=audit_pk, pk=inspection.pk)


@user_passes_test(_is_audit_manager, login_url='dashboard')
def inspection_fill(request, audit_pk, pk):
    audit      = get_object_or_404(ServerAudit, pk=audit_pk)
    inspection = get_object_or_404(AuditInspection, pk=pk, audit=audit)

    if inspection.is_completed:
        return redirect('inspection_detail', audit_pk=audit_pk, pk=pk)

    results = list(inspection.results.select_related('requirement').all())

    if request.method == 'POST':
        errors = []
        for result in results:
            is_met  = request.POST.get(f'is_met_{result.pk}') == 'true'
            comment = request.POST.get(f'comment_{result.pk}', '').strip()
            if not is_met and not comment:
                req_text = result.requirement.text if result.requirement else '—'
                errors.append(f'Komentarz wymagany dla punktu: „{req_text}"')

        if errors:
            for result in results:
                result.is_met  = request.POST.get(f'is_met_{result.pk}') == 'true'
                result.comment = request.POST.get(f'comment_{result.pk}', '').strip()
            for e in errors:
                messages.warning(request, e)
            return render(request, 'serwerownia/inspection_fill.html', {
                'audit': audit, 'inspection': inspection, 'results': results,
                'general_comment': request.POST.get('general_comment', ''),
            })

        for result in results:
            result.is_met  = request.POST.get(f'is_met_{result.pk}') == 'true'
            result.comment = request.POST.get(f'comment_{result.pk}', '').strip()
            img = request.FILES.get(f'image_{result.pk}')
            if img:
                result.image = img
            result.save()

        inspection.comment = request.POST.get('general_comment', '').strip()
        inspection.save()

        messages.success(request, 'Wyniki zapisane. Możesz teraz zakończyć inspekcję po upływie 3 minut od jej startu.')
        return redirect('inspection_detail', audit_pk=audit_pk, pk=pk)

    return render(request, 'serwerownia/inspection_fill.html', {
        'audit': audit, 'inspection': inspection, 'results': results,
        'general_comment': inspection.comment,
    })


@user_passes_test(_is_audit_manager, login_url='dashboard')
def inspection_detail(request, audit_pk, pk):
    audit      = get_object_or_404(ServerAudit, pk=audit_pk)
    inspection = get_object_or_404(AuditInspection, pk=pk, audit=audit)
    results    = inspection.results.select_related('requirement').all()
    return render(request, 'serwerownia/inspection_detail.html', {
        'audit': audit, 'inspection': inspection, 'results': results,
    })


@user_passes_test(_is_audit_manager, login_url='dashboard')
def inspection_finish(request, audit_pk, pk):
    if request.method != 'POST':
        return redirect('inspection_detail', audit_pk=audit_pk, pk=pk)

    audit      = get_object_or_404(ServerAudit, pk=audit_pk)
    inspection = get_object_or_404(AuditInspection, pk=pk, audit=audit)

    if inspection.is_completed:
        messages.info(request, 'Inspekcja jest już zakończona.')
        return redirect('inspection_detail', audit_pk=audit_pk, pk=pk)

    elapsed = (timezone.now() - inspection.created_at).total_seconds()
    if elapsed < 180:
        remaining = int(180 - elapsed)
        messages.warning(request, f'Za wcześnie. Odczekaj jeszcze {remaining} sekund.')
        return redirect('inspection_detail', audit_pk=audit_pk, pk=pk)

    inspection.completed_at = timezone.now()
    inspection.save()

    if inspection.has_failures:
        ok, msg = _send_failure_email(inspection)
        if ok:
            messages.success(request, 'Inspekcja zakończona. Wykryto niezgodności – raport wysłany do helpdesk.')
        else:
            messages.warning(request, f'Inspekcja zakończona z niezgodnościami. Nie udało się wysłać emaila: {msg}')
    else:
        messages.success(request, 'Inspekcja zakończona. Wszystkie punkty kontrolne spełnione.')

    return redirect('inspection_detail', audit_pk=audit_pk, pk=pk)


@user_passes_test(_is_admin, login_url='dashboard')
def inspection_delete(request, audit_pk, pk):
    audit      = get_object_or_404(ServerAudit, pk=audit_pk)
    inspection = get_object_or_404(AuditInspection, pk=pk, audit=audit)
    if request.method == 'POST':
        inspection.delete()
        messages.success(request, 'Inspekcja została usunięta.')
        return redirect('audit_detail', pk=audit_pk)
    return render(request, 'serwerownia/inspection_confirm_delete.html', {
        'audit': audit, 'inspection': inspection,
    })


@user_passes_test(_is_audit_manager, login_url='dashboard')
def inspection_pdf(request, audit_pk, pk):
    audit      = get_object_or_404(ServerAudit, pk=audit_pk)
    inspection = get_object_or_404(AuditInspection, pk=pk, audit=audit)
    pdf_bytes  = _generate_inspection_pdf(inspection)
    filename   = f'inspekcja_{audit.name}_{inspection.pk}.pdf'
    response   = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
