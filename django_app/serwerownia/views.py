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
    # Reuse brand fonts, colors and helpers from pdf_gen (do NOT modify pdf_gen.py)
    from pdf_gen import (
        _reg_fonts, BRAND, DARK, BORDER, CW, MARGIN,
        _S, _th, _td, _table_style_base, _sec_hdr, LOGO_PATH,
    )
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib.colors import HexColor, white, black
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Table, TableStyle,
        Spacer, Image as RLImage, HRFlowable,
    )
    from reportlab.lib.utils import ImageReader

    _reg_fonts()

    results = list(inspection.results.select_related('requirement').all())
    audit   = inspection.audit

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN,  bottomMargin=MARGIN,
    )

    inspector = inspection.user.get_full_name() if inspection.user else '—'
    started   = inspection.created_at.strftime('%Y-%m-%d %H:%M') if inspection.created_at else '—'
    finished  = inspection.completed_at.strftime('%Y-%m-%d %H:%M') if inspection.completed_at else 'W trakcie'

    story = []

    # ── Logo + nagłówek firmy ───────────────────────────────────────────
    LOGO_H = 33
    logo_cell = None
    if os.path.exists(LOGO_PATH):
        try:
            iw, ih = ImageReader(LOGO_PATH).getSize()
            logo_cell = RLImage(LOGO_PATH, width=iw * LOGO_H / ih, height=LOGO_H)
        except Exception:
            pass
    if logo_cell is None:
        logo_cell = Paragraph(
            "<font name='Arial-Bold' size='18' color='#9b1c2e'>Brüggen</font>",
            _S('hl', alignment=TA_RIGHT),
        )

    hdr_row = Table(
        [[
            Paragraph("Brueggen Polska Sp. z o.o. | Celejów 59, 08-470 Wilga",
                       _S('hdr_l', fontSize=7.5, textColor=black)),
            logo_cell,
        ]],
        colWidths=[CW * 0.65, CW * 0.35],
    )
    hdr_row.setStyle(TableStyle([
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('ALIGN',         (1, 0), (1,  0),  'RIGHT'),
        ('LEFTPADDING',   (0, 0), (-1, -1), 0),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 0),
        ('TOPPADDING',    (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(hdr_row)

    # ── Tytuł ──────────────────────────────────────────────────────────
    story.append(Paragraph(
        'Raport z inspekcji AuditManager',
        _S('h1', fontName='Arial-Bold', fontSize=17, leading=21,
           textColor=BRAND, spaceBefore=2),
    ))
    story.append(HRFlowable(width=CW, thickness=2, color=BRAND, spaceAfter=8))

    # ── Informacje o inspekcji ──────────────────────────────────────────
    story.append(_sec_hdr('Informacje o inspekcji'))

    lbl_st = _S('ml', fontName='Arial-Bold', fontSize=9, textColor=white, leading=11)
    val_st = _S('mv', fontSize=9, leading=11)

    meta_data = [
        ('Audyt',       audit.name),
        ('Inspektor',   inspector),
        ('Start',       started),
        ('Zakończenie', finished),
    ]
    if inspection.comment:
        meta_data.append(('Komentarz ogólny', inspection.comment))

    meta_rows = [[Paragraph(lbl, lbl_st), Paragraph(val, val_st)] for lbl, val in meta_data]
    meta_table = Table(meta_rows, colWidths=[CW * 0.28, CW * 0.72])
    meta_table.setStyle(TableStyle([
        ('FONTSIZE',      (0, 0), (-1, -1), 9),
        ('GRID',          (0, 0), (-1, -1), 0.5, BORDER),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING',   (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
        ('BACKGROUND',    (0, 0), (0, -1), DARK),
        ('BACKGROUND',    (1, 0), (1, -1), white),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 8))

    # ── Wyniki kontroli ─────────────────────────────────────────────────
    story.append(_sec_hdr('Wyniki kontroli'))

    IMG_W = 3.0 * cm
    IMG_H = 2.2 * cm

    has_images = any(
        r.image and hasattr(r.image, 'path') and os.path.exists(r.image.path)
        for r in results
    )

    if has_images:
        col_w      = [0.8*cm, 6.0*cm, 2.0*cm, 5.5*cm, 3.9*cm]
        header_row = [_th('#'), _th('Punkt kontrolny'), _th('Status'), _th('Komentarz'), _th('Zdjęcie')]
    else:
        col_w      = [0.8*cm, 7.0*cm, 2.0*cm, 8.4*cm]
        header_row = [_th('#'), _th('Punkt kontrolny'), _th('Status'), _th('Komentarz')]

    data_rows  = [header_row]
    style_cmds = _table_style_base()
    style_cmds += [('ALIGN', (2, 0), (2, -1), 'CENTER')]

    for i, result in enumerate(results, 1):
        req_text = result.requirement.text if result.requirement else '—'
        status   = 'OK' if result.is_met else 'NOK'
        comment  = result.comment or '—'

        img_cell = Paragraph('', _S(f'ic{i}'))
        if has_images and result.image and hasattr(result.image, 'path') and os.path.exists(result.image.path):
            try:
                img_cell = RLImage(result.image.path, width=IMG_W, height=IMG_H)
            except Exception:
                pass

        row = [
            Paragraph(str(i), _S(f'n{i}', fontSize=9, alignment=TA_CENTER)),
            _td(req_text),
            Paragraph(status, _S(f'st{i}', fontName='Arial-Bold', fontSize=9, alignment=TA_CENTER)),
            _td(comment),
        ]
        if has_images:
            row.append(img_cell)
        data_rows.append(row)

        if not result.is_met:
            style_cmds.append(('BACKGROUND', (0, i), (-1, i), HexColor('#fde8ea')))

    results_table = Table(data_rows, colWidths=col_w, repeatRows=1)
    results_table.setStyle(TableStyle(style_cmds))
    story.append(results_table)

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
        f'Inspekcja AuditManager – wykryto niezgodności\n\n'
        f'Audyt:     {audit.name}\n'
        f'Inspektor: {inspector}\n'
        f'Data:      {finished}\n\n'
        f'Niezgodne punkty:\n{failed_lines}\n\n'
        f'Proszę o weryfikację i podjęcie działań naprawczych.'
    )

    pdf_bytes    = _generate_inspection_pdf(inspection)
    pdf_filename = f'inspekcja_{audit.name}_{inspection.pk}.pdf'

    return send_email(
        settings=settings_data,
        to_emails=[helpdesk_email],
        subject=f'[AuditManager] Niezgodności – {audit.name} – {finished}',
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
