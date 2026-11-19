from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import PDM_STEPS, Solution, SolutionLog

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


# --- Views ---

@_require_view
def solution_list(request):
    solutions = Solution.objects.prefetch_related('logs').all()
    q = request.GET.get('q', '').strip()
    cat = request.GET.get('cat', '')
    if q:
        solutions = solutions.filter(name__icontains=q)
    if cat:
        solutions = solutions.filter(category=cat)
    return render(request, 'solutions/solution_list.html', {
        'solutions': solutions,
        'search_query': q,
        'filter_cat': cat,
        'can_edit': _can_edit(request.user),
    })


@_require_edit
def solution_detail(request, pk):
    sol = get_object_or_404(Solution, pk=pk)
    logs = sol.logs.select_related('author').all()
    return render(request, 'solutions/solution_detail.html', {
        'sol': sol,
        'logs': logs,
        'pdm_steps': PDM_STEPS,
    })


@_require_view
def solution_view(request, pk):
    """Read-only support view — visible to all T&I Wilga groups."""
    sol = get_object_or_404(Solution, pk=pk)
    logs = sol.logs.select_related('author').all()[:10]
    return render(request, 'solutions/solution_view.html', {
        'sol': sol,
        'logs': logs,
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
        if not name:
            messages.error(request, 'Nazwa projektu jest wymagana.')
            return render(request, 'solutions/solution_form.html', {'sol': None})
        sol = Solution.objects.create(
            name=name,
            category=category,
            technology=technology if category == 'extensive' else '',
            description=description,
            created_by=request.user,
        )
        messages.success(request, f'Solution „{sol.name}" zostało otwarte.')
        return redirect('solution_view', pk=sol.pk)
    return render(request, 'solutions/solution_form.html', {'sol': None})


@_require_edit
def solution_edit(request, pk):
    sol = get_object_or_404(Solution, pk=pk)
    if request.method == 'POST':
        sol.name = request.POST.get('name', '').strip() or sol.name
        sol.category = request.POST.get('category', sol.category)
        sol.technology = request.POST.get('technology', '') if sol.category == 'extensive' else ''
        sol.description = request.POST.get('description', '').strip()
        sol.save()
        messages.success(request, 'Solution zaktualizowane.')
        return redirect('solution_view', pk=sol.pk)
    return render(request, 'solutions/solution_form.html', {'sol': sol})


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
        version = request.POST.get('version', '').strip()
        log_date_str = request.POST.get('log_date', '').strip()
        change_type = request.POST.get('change_type', 'other')
        description = request.POST.get('description', '').strip()

        from datetime import date
        try:
            log_date = date.fromisoformat(log_date_str) if log_date_str else date.today()
        except ValueError:
            log_date = date.today()

        if version and description:
            SolutionLog.objects.create(
                solution=sol,
                version=version,
                log_date=log_date,
                change_type=change_type,
                description=description,
                author=request.user,
            )
            messages.success(request, 'Wpis kontroli wersji dodany.')
        else:
            messages.error(request, 'Wersja i opis są wymagane.')
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
    """Bulk import — create multiple solutions at once."""
    if request.method == 'POST':
        lines = request.POST.get('projects', '').strip().splitlines()
        category = request.POST.get('category', 'simple')
        technology = request.POST.get('technology', '')
        created = 0
        for line in lines:
            name = line.strip()
            if name:
                Solution.objects.create(
                    name=name,
                    category=category,
                    technology=technology if category == 'extensive' else '',
                    created_by=request.user,
                )
                created += 1
        if created:
            messages.success(request, f'Zaimportowano {created} projekt(ów).')
        return redirect('solution_list')
    return render(request, 'solutions/solution_import.html')
