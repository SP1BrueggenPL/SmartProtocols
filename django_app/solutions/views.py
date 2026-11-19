from datetime import date as _date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .imports import parse_checklist_docx, parse_updatelogs_xlsx
from .models import PDM_STEPS, Department, Solution, SolutionDocument, SolutionLog

# --- Access helpers ---

def _can_view(user):
    """Read-only: T&I Wilga Viewer / T&I Wilga / staff."""
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    return user.groups.filter(name__in=['T&I Wilga', 'T&I Wilga Viewer']).exists()


def _can_edit(user):
    """Full access: T&I Wilga / staff."""
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    return user.groups.filter(name='T&I Wilga').exists()


def _require_view(view_fn):
    @login_required
    def wrapper(request, *args, **kwargs):
        if not _can_view(request.user):
            messages.error(request, 'Brak dostępu do sekcji T&I Solutions.')
            return redirect('dashboard')
        return view_fn(request, *args, **kwargs)
    wrapper.__name__ = view_fn.__name__
    return wrapper


def _require_edit(view_fn):
    @login_required
    def wrapper(request, *args, **kwargs):
        if not _can_edit(request.user):
            messages.error(request, 'Nie masz uprawnień do edycji T&I Solutions.')
            return redirect('dashboard')
        return view_fn(request, *args, **kwargs)
    wrapper.__name__ = view_fn.__name__
    return wrapper


def _parse_date(raw):
    raw = (raw or '').strip()
    if not raw:
        return None
    try:
        return _date.fromisoformat(raw)
    except ValueError:
        return None


# --- Solution list (grouped by department) ---

@_require_view
def solution_list(request):
    solutions = Solution.objects.select_related('department').prefetch_related('logs')
    q = request.GET.get('q', '').strip()
    cat = request.GET.get('cat', '')
    if q:
        solutions = solutions.filter(name__icontains=q)
    if cat:
        solutions = solutions.filter(category=cat)
    solutions = list(solutions)

    by_dept = {}
    no_dept = []
    for sol in solutions:
        if sol.department_id:
            by_dept.setdefault(sol.department_id, []).append(sol)
        else:
            no_dept.append(sol)

    filtering = bool(q or cat)
    groups = []
    top_departments = Department.objects.filter(parent__isnull=True).prefetch_related('children')
    for dept in top_departments:
        dept_solutions = by_dept.get(dept.pk, [])
        subgroups = []
        for sub in dept.children.all():
            sub_solutions = by_dept.get(sub.pk, [])
            if sub_solutions or not filtering:
                subgroups.append({'dept': sub, 'solutions': sub_solutions})
        if dept_solutions or subgroups or not filtering:
            groups.append({'dept': dept, 'solutions': dept_solutions, 'subgroups': subgroups})

    return render(request, 'solutions/solution_list.html', {
        'groups': groups,
        'no_dept': no_dept,
        'solutions': solutions,
        'search_query': q,
        'filter_cat': cat,
        'can_edit': _can_edit(request.user),
    })


# --- Department management (editors only) ---

@_require_edit
def department_list(request):
    departments = Department.objects.select_related('parent').all()
    return render(request, 'solutions/department_list.html', {
        'departments': departments,
        'top_departments': Department.objects.filter(parent__isnull=True),
    })


@_require_edit
def department_new(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        parent_id = request.POST.get('parent', '').strip()
        if name:
            parent = Department.objects.filter(pk=parent_id).first() if parent_id else None
            Department.objects.create(name=name, parent=parent)
            messages.success(request, f'Dział „{name}" dodany.')
        else:
            messages.error(request, 'Nazwa działu jest wymagana.')
    return redirect('department_list')


@_require_edit
def department_delete(request, pk):
    dept = get_object_or_404(Department, pk=pk)
    if request.method == 'POST':
        name = dept.name
        dept.delete()
        messages.success(request, f'Dział „{name}" usunięty.')
    return redirect('department_list')


# --- Solution management view (full edit) ---

@_require_edit
def solution_detail(request, pk):
    sol = get_object_or_404(Solution, pk=pk)
    logs = sol.logs.select_related('author').all()
    documents = sol.documents.select_related('uploaded_by').all()
    return render(request, 'solutions/solution_detail.html', {
        'sol': sol,
        'logs': logs,
        'documents': documents,
        'pdm_steps': PDM_STEPS,
    })


@_require_view
def solution_view(request, pk):
    """Read-only support/admin view — visible to all T&I Wilga groups."""
    sol = get_object_or_404(Solution, pk=pk)
    logs = sol.logs.select_related('author').all()
    documents = sol.documents.select_related('uploaded_by').all()
    return render(request, 'solutions/solution_view.html', {
        'sol': sol,
        'logs': logs,
        'documents': documents,
        'pdm_steps': PDM_STEPS,
        'can_edit': _can_edit(request.user),
    })


@_require_edit
def solution_new(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        category = request.POST.get('category', 'simple')
        technology = request.POST.get('technology', '')
        description = request.POST.get('description', '').strip()
        department_id = request.POST.get('department', '').strip()
        if not name:
            messages.error(request, 'Nazwa projektu jest wymagana.')
            return render(request, 'solutions/solution_form.html', {
                'sol': None, 'departments': Department.objects.all(),
            })
        sol = Solution.objects.create(
            name=name,
            department=Department.objects.filter(pk=department_id).first() if department_id else None,
            category=category,
            technology=technology if category == 'extensive' else '',
            description=description,
            app_url=request.POST.get('app_url', '').strip(),
            admin_login=request.POST.get('admin_login', '').strip(),
            admin_password=request.POST.get('admin_password', '').strip(),
            start_date=_parse_date(request.POST.get('start_date')),
            production_date=_parse_date(request.POST.get('production_date')),
            created_by=request.user,
        )
        messages.success(request, f'Solution „{sol.name}" zostało otwarte.')
        return redirect('solution_view', pk=sol.pk)
    return render(request, 'solutions/solution_form.html', {
        'sol': None, 'departments': Department.objects.all(),
    })


@_require_edit
def solution_edit(request, pk):
    sol = get_object_or_404(Solution, pk=pk)
    if request.method == 'POST':
        sol.name = request.POST.get('name', '').strip() or sol.name
        department_id = request.POST.get('department', '').strip()
        sol.department = Department.objects.filter(pk=department_id).first() if department_id else None
        sol.category = request.POST.get('category', sol.category)
        sol.technology = request.POST.get('technology', '') if sol.category == 'extensive' else ''
        sol.description = request.POST.get('description', '').strip()
        sol.app_url = request.POST.get('app_url', '').strip()
        sol.admin_login = request.POST.get('admin_login', '').strip()
        sol.admin_password = request.POST.get('admin_password', '').strip()
        sol.start_date = _parse_date(request.POST.get('start_date'))
        sol.production_date = _parse_date(request.POST.get('production_date'))
        sol.save()
        messages.success(request, 'Solution zaktualizowane.')
        return redirect('solution_view', pk=sol.pk)
    return render(request, 'solutions/solution_form.html', {
        'sol': sol, 'departments': Department.objects.all(),
    })


@_require_edit
def solution_toggle_step(request, pk, step):
    sol = get_object_or_404(Solution, pk=pk)
    if request.method == 'POST':
        steps = list(sol.completed_steps or [])
        if step in steps:
            steps.remove(step)
        else:
            steps.append(step)
        sol.completed_steps = steps
        sol.save()
    return redirect('solution_detail', pk=pk)


@_require_edit
def solution_log_add(request, pk):
    sol = get_object_or_404(Solution, pk=pk)
    if request.method == 'POST':
        goal = request.POST.get('goal', '').strip()
        description = request.POST.get('description', '').strip()
        responsible_person = request.POST.get('responsible_person', '').strip()
        update_start_date = _parse_date(request.POST.get('update_start_date'))

        if not (goal and description and responsible_person and update_start_date):
            messages.error(request, 'Cel aktualizacji, opis, osoba odpowiedzialna i data rozpoczęcia są wymagane.')
            return redirect('solution_detail', pk=pk)

        SolutionLog.objects.create(
            solution=sol,
            version=request.POST.get('version', '').strip(),
            goal=goal,
            update_start_date=update_start_date,
            responsible_person=responsible_person,
            environment=request.POST.get('environment', 'prod'),
            deployed=request.POST.get('deployed') == 'on',
            log_date=_parse_date(request.POST.get('log_date')),
            user_notified=request.POST.get('user_notified') == 'on',
            change_type=request.POST.get('change_type', ''),
            description=description,
            blockers=request.POST.get('blockers', '').strip(),
            author=request.user,
        )
        messages.success(request, 'Wpis UpdateLog dodany.')
    return redirect('solution_detail', pk=pk)


@_require_edit
def solution_log_delete(request, pk, log_pk):
    sol = get_object_or_404(Solution, pk=pk)
    log = get_object_or_404(SolutionLog, pk=log_pk, solution=sol)
    if request.method == 'POST':
        log.delete()
        messages.success(request, 'Wpis usunięty.')
    return redirect('solution_detail', pk=pk)


@_require_edit
def solution_delete(request, pk):
    sol = get_object_or_404(Solution, pk=pk)
    if request.method == 'POST':
        name = sol.name
        sol.delete()
        messages.success(request, f'Solution „{name}" zostało usunięte.')
        return redirect('solution_list')
    return render(request, 'solutions/solution_confirm_delete.html', {'sol': sol})


@_require_edit
def solution_import(request):
    """Quick bulk import — create project shells from a list of names."""
    if request.method == 'POST':
        lines = request.POST.get('projects', '').strip().splitlines()
        category = request.POST.get('category', 'simple')
        technology = request.POST.get('technology', '')
        department_id = request.POST.get('department', '').strip()
        department = Department.objects.filter(pk=department_id).first() if department_id else None
        created = 0
        for line in lines:
            name = line.strip()
            if name:
                Solution.objects.create(
                    name=name,
                    department=department,
                    category=category,
                    technology=technology if category == 'extensive' else '',
                    created_by=request.user,
                )
                created += 1
        if created:
            messages.success(request, f'Zaimportowano {created} projekt(ów). Uzupełnij dla nich dane szczegółowe (UpdateLogi, checklistę, dokumentację) w widoku zarządzania każdego projektu.')
        return redirect('solution_list')
    return render(request, 'solutions/solution_import.html', {
        'departments': Department.objects.all(),
    })


# --- Documents (documentation / backups) ---

@_require_edit
def solution_doc_add(request, pk):
    sol = get_object_or_404(Solution, pk=pk)
    if request.method == 'POST':
        category = request.POST.get('category', 'documentation')
        environment = request.POST.get('environment', '') if category == 'backup' else ''
        files = request.FILES.getlist('files')
        title_override = request.POST.get('title', '').strip()
        if not files:
            messages.error(request, 'Wybierz przynajmniej jeden plik.')
            return redirect('solution_detail', pk=pk)
        for f in files:
            SolutionDocument.objects.create(
                solution=sol,
                category=category,
                environment=environment,
                title=title_override or f.name,
                file=f,
                uploaded_by=request.user,
            )
        messages.success(request, f'Dodano {len(files)} plik(ów).')
    return redirect('solution_detail', pk=pk)


@_require_edit
def solution_doc_delete(request, pk, doc_pk):
    sol = get_object_or_404(Solution, pk=pk)
    doc = get_object_or_404(SolutionDocument, pk=doc_pk, solution=sol)
    if request.method == 'POST':
        doc.file.delete(save=False)
        doc.delete()
        messages.success(request, 'Dokument usunięty.')
    return redirect('solution_detail', pk=pk)


# --- Rich data import from the Teams/SharePoint PDM templates ---

@_require_edit
def solution_data_import(request, pk):
    sol = get_object_or_404(Solution, pk=pk)
    if request.method == 'POST':
        xlsx_file = request.FILES.get('updatelogs_xlsx')
        docx_file = request.FILES.get('checklist_docx')
        doc_files = request.FILES.getlist('doc_files')
        backup_files = request.FILES.getlist('backup_files')
        backup_env = request.POST.get('backup_environment', '')

        imported_logs = 0
        if xlsx_file:
            try:
                rows = parse_updatelogs_xlsx(xlsx_file)
            except Exception:
                messages.error(request, 'Nie udało się odczytać pliku UpdateLogs.xlsx — sprawdź, czy to oryginalny szablon PDM.')
                rows = []
            for row in rows:
                SolutionLog.objects.create(solution=sol, author=request.user, **row)
                imported_logs += 1

        checklist_applied = False
        if docx_file:
            try:
                completed = parse_checklist_docx(docx_file)
                sol.completed_steps = completed
                sol.save()
                checklist_applied = True
            except Exception:
                messages.error(request, 'Nie udało się odczytać pliku SolutionChecklist.docx — sprawdź, czy to oryginalny szablon PDM.')

        for f in doc_files:
            SolutionDocument.objects.create(
                solution=sol, category='documentation', title=f.name,
                file=f, uploaded_by=request.user,
            )

        for f in backup_files:
            SolutionDocument.objects.create(
                solution=sol, category='backup', environment=backup_env,
                title=f.name, file=f, uploaded_by=request.user,
            )

        parts = []
        if imported_logs:
            parts.append(f'{imported_logs} wpis(ów) UpdateLog')
        if checklist_applied:
            parts.append('checklista PDM')
        if doc_files:
            parts.append(f'{len(doc_files)} plik(ów) dokumentacji')
        if backup_files:
            parts.append(f'{len(backup_files)} plik(ów) backupu')
        if parts:
            messages.success(request, 'Zaimportowano: ' + ', '.join(parts) + '.')
        else:
            messages.warning(request, 'Nie wybrano żadnych plików do importu.')
    return redirect('solution_detail', pk=pk)
