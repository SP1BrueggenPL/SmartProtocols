"""
Jednorazowy import danych z Power Apps (SharePoint Lists) do serwerowni.

Użycie:
    python manage.py import_powerapps /ścieżka/do/folderu/z/csvkami

Oczekiwane pliki:
    Audits.csv, Requirements.csv, Inspections.csv, InspectionResults.csv
"""
import csv
import os
from datetime import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from serwerownia.models import AuditInspection, AuditRequirement, InspectionResult, ServerAudit

User = get_user_model()


def _parse_dt(s):
    """Parsuje datę z Power Apps (np. '1/29/2026 12:08 PM') → aware datetime."""
    s = (s or '').strip()
    if not s:
        return None
    for fmt in ('%m/%d/%Y %I:%M %p', '%m/%d/%Y %H:%M', '%Y-%m-%d %H:%M:%S'):
        try:
            return timezone.make_aware(datetime.strptime(s, fmt))
        except ValueError:
            pass
    return None


def _find_user(name):
    """Szuka użytkownika po imieniu i nazwisku (np. 'Sebastian Paszkowski')."""
    name = (name or '').strip()
    if not name:
        return None
    parts = name.split(maxsplit=1)
    if len(parts) == 2:
        first, last = parts
        qs = User.objects.filter(first_name__iexact=first, last_name__iexact=last)
        if qs.exists():
            return qs.first()
        qs = User.objects.filter(last_name__iexact=first, first_name__iexact=last)
        if qs.exists():
            return qs.first()
    return None


class Command(BaseCommand):
    help = 'Import danych z Power Apps CSV do modeli serwerowni / AuditManager'

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_dir',
            type=str,
            help='Folder zawierający pliki: Audits.csv, Requirements.csv, Inspections.csv, InspectionResults.csv',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Symulacja importu bez zapisu do bazy',
        )

    def handle(self, *args, **options):
        csv_dir  = options['csv_dir']
        dry_run  = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('=== TRYB PODGLĄDU (dry-run) – brak zapisu do bazy ===\n'))

        for fname in ('Audits.csv', 'Requirements.csv', 'Inspections.csv', 'InspectionResults.csv'):
            path = os.path.join(csv_dir, fname)
            if not os.path.exists(path):
                raise CommandError(f'Brak pliku: {path}')

        # ── 1. Audyty ────────────────────────────────────────────────────
        self.stdout.write('--- Audyty ---')
        audits_map = {}  # name → ServerAudit
        with open(os.path.join(csv_dir, 'Audits.csv'), encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                name = row['Name'].strip()
                if not name:
                    continue
                if not dry_run:
                    obj, created = ServerAudit.objects.get_or_create(
                        name=name,
                        defaults={'description': row.get('Description', '').strip()},
                    )
                    audits_map[name] = obj
                else:
                    created = True
                    audits_map[name] = None
                self.stdout.write(f"  {'[NEW]' if created else '[OK] '} Audyt: {name}")

        self.stdout.write(self.style.SUCCESS(f"Audyty: {len(audits_map)}\n"))

        # ── 2. Wymagania ─────────────────────────────────────────────────
        self.stdout.write('--- Wymagania ---')
        reqs_by_audit = {}  # audit_name → [AuditRequirement] (kolejność z CSV)
        with open(os.path.join(csv_dir, 'Requirements.csv'), encoding='utf-8-sig') as f:
            for i, row in enumerate(csv.DictReader(f)):
                audit_name = row['Audit'].strip()
                text       = row['Text'].strip()
                if not audit_name or not text or audit_name not in audits_map:
                    continue
                if not dry_run:
                    req, created = AuditRequirement.objects.get_or_create(
                        audit=audits_map[audit_name],
                        text=text,
                        defaults={'order': i},
                    )
                    reqs_by_audit.setdefault(audit_name, []).append(req)
                else:
                    reqs_by_audit.setdefault(audit_name, []).append(text)
                    created = True
                if created:
                    self.stdout.write(f"  [NEW] [{audit_name}] {text[:60]}")

        req_total = sum(len(v) for v in reqs_by_audit.values())
        self.stdout.write(self.style.SUCCESS(f"Wymagania: {req_total}\n"))

        # ── 3. Załaduj surowe dane (Inspections + Results) ───────────────
        insps_raw = {}  # SP ID str → row dict
        with open(os.path.join(csv_dir, 'Inspections.csv'), encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                sid = row['Identyfikator'].strip()
                if sid:
                    insps_raw[sid] = row

        results_raw = []
        with open(os.path.join(csv_dir, 'InspectionResults.csv'), encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                if row['Inspection'].strip() and row['Requirement'].strip():
                    results_raw.append(row)

        self.stdout.write(f'Załadowano {len(insps_raw)} inspekcji i {len(results_raw)} wyników z CSV\n')

        # ── 4. Zbuduj mapę SP req_id → AuditRequirement ─────────────────
        # Strategia: dla każdego audytu zbierz unikalny zbiór SP ID wymagań,
        # posortuj, przypisz pozycyjnie do wymagań z CSV (które też są posortowane).
        self.stdout.write('--- Mapowanie wymagań (SP ID → Django) ---')
        audit_sp_req_ids = {}  # audit_name → set of int SP req IDs
        for row in results_raw:
            insp_raw = insps_raw.get(row['Inspection'].strip())
            if not insp_raw:
                continue
            audit_name = insp_raw['Audit'].strip()
            if not audit_name:
                continue
            req_str = row['Requirement'].strip()
            if req_str.isdigit():
                audit_sp_req_ids.setdefault(audit_name, set()).add(int(req_str))

        sp_req_map = {}  # int SP req ID → AuditRequirement (or text in dry-run)
        for audit_name, sp_ids in audit_sp_req_ids.items():
            sorted_sp   = sorted(sp_ids)
            django_reqs = reqs_by_audit.get(audit_name, [])
            if len(sorted_sp) != len(django_reqs):
                self.stdout.write(self.style.WARNING(
                    f"  WARN [{audit_name}]: {len(sorted_sp)} SP IDs vs "
                    f"{len(django_reqs)} wymagań Django – wyniki dla tego audytu "
                    f"zostaną zaimportowane bez linku do wymagania"
                ))
                continue
            for sp_id, req in zip(sorted_sp, django_reqs):
                sp_req_map[sp_id] = req
                label = req.text[:50] if not dry_run else req[:50]
                self.stdout.write(f"  SP {sp_id} → {label}")

        self.stdout.write(self.style.SUCCESS(f"Zmapowano {len(sp_req_map)} wymagań\n"))

        # ── 5. Inspekcje ─────────────────────────────────────────────────
        self.stdout.write('--- Inspekcje ---')
        insp_map     = {}  # SP ID str → AuditInspection
        created_c    = 0
        existing_c   = 0
        skipped_c    = 0

        for sp_id, row in insps_raw.items():
            audit_name = row['Audit'].strip()
            if not audit_name or audit_name not in audits_map:
                skipped_c += 1
                continue

            created_at   = _parse_dt(row.get('CreatedAt', ''))
            completed_at = _parse_dt(row.get('CompletedAt', '')) if row.get('Status') == 'Finished' else None
            user         = _find_user(row.get('UserUPN', ''))
            comment      = row.get('Comment', '').strip()
            audit        = audits_map[audit_name]

            if not dry_run:
                # Dedup: szukaj po (audit, created_at)
                existing = None
                if created_at:
                    existing = AuditInspection.objects.filter(
                        audit=audit, created_at=created_at
                    ).first()

                if existing:
                    insp_map[sp_id] = existing
                    existing_c += 1
                    continue

                insp = AuditInspection.objects.create(audit=audit, user=user, comment=comment)
                # Nadpisz auto_now_add datą historyczną
                upd = {}
                if created_at:
                    upd['created_at']  = created_at
                if completed_at:
                    upd['completed_at'] = completed_at
                if upd:
                    AuditInspection.objects.filter(pk=insp.pk).update(**upd)
                    insp.refresh_from_db()
                insp_map[sp_id] = insp
            else:
                insp_map[sp_id] = sp_id  # placeholder dla dry-run
            created_c += 1

        self.stdout.write(self.style.SUCCESS(
            f"Inspekcje: {created_c} nowych, {existing_c} istniejących, {skipped_c} pominięto\n"
        ))

        # ── 6. Wyniki inspekcji ──────────────────────────────────────────
        self.stdout.write('--- Wyniki inspekcji ---')
        res_created  = 0
        res_existing = 0
        res_skipped  = 0

        for row in results_raw:
            insp_sp = row['Inspection'].strip()
            req_str = row['Requirement'].strip()

            if insp_sp not in insp_map:
                res_skipped += 1
                continue

            req = sp_req_map.get(int(req_str)) if req_str.isdigit() else None
            if req is None:
                res_skipped += 1
                continue

            is_met  = row['IsMet'].strip() not in ('Fałsz', 'False', 'false', '0')
            comment = row.get('Comment', '').strip()

            if not dry_run:
                insp = insp_map[insp_sp]
                _, created = InspectionResult.objects.get_or_create(
                    inspection=insp,
                    requirement=req,
                    defaults={'is_met': is_met, 'comment': comment},
                )
                if created:
                    res_created += 1
                else:
                    res_existing += 1
            else:
                res_created += 1

        self.stdout.write(self.style.SUCCESS(
            f"Wyniki: {res_created} nowych, {res_existing} istniejących, {res_skipped} pominięto\n"
        ))

        self.stdout.write(self.style.SUCCESS('✓ Import zakończony pomyślnie!'))
