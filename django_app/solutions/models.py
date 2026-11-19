from django.db import models
from django.contrib.auth.models import User


PDM_STEPS = [
    (1, 'Informacja o potrzebie'),
    (2, 'Oficjalne zgłoszenie zapotrzebowania'),
    (3, 'Mapowanie zapotrzebowania'),
    (4, 'Kategoryzacja zapotrzebowania'),
    (5, 'Oficjalne otwarcie projektu'),
    (6, 'Developerka'),
    (7, 'Faza testowa'),
    (8, 'Wdrożenie produkcyjne'),
    (9, 'Opieka powdrożeniowa'),
]

CATEGORY_CHOICES = [
    ('support',   'Prośba o wsparcie'),
    ('simple',    'Prosty proces'),
    ('extensive', 'Rozległy proces'),
]

TECHNOLOGY_CHOICES = [
    ('power_platform', 'Power Platform'),
    ('vibe_coding',    'Vibe Coding'),
    ('other',          'Inne'),
]

LOG_TYPE_CHOICES = [
    ('feature',    'Nowa funkcja'),
    ('fix',        'Poprawka'),
    ('deployment', 'Wdrożenie'),
    ('test',       'Faza testowa'),
    ('other',      'Inne'),
]


class Solution(models.Model):
    name        = models.CharField(max_length=255, verbose_name='Nazwa projektu')
    category    = models.CharField(max_length=20, choices=CATEGORY_CHOICES, verbose_name='Kategoria')
    technology  = models.CharField(max_length=20, choices=TECHNOLOGY_CHOICES, blank=True, default='',
                                   verbose_name='Technologia')
    description = models.TextField(blank=True, default='', verbose_name='Opis zapotrzebowania')
    completed_steps = models.JSONField(default=list, verbose_name='Ukończone kroki')
    created_at  = models.DateTimeField(auto_now_add=True)
    created_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='solutions_created')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Solution'
        verbose_name_plural = 'Solutions'

    def __str__(self):
        return self.name

    @property
    def current_step(self):
        done = set(self.completed_steps or [])
        for n, _ in PDM_STEPS:
            if n not in done:
                return n
        return None  # all done

    @property
    def status_label(self):
        step = self.current_step
        if step is None:
            return 'Zakończony'
        if step <= 2:
            return 'Nowy'
        if step <= 5:
            return 'Otwieranie'
        if step <= 7:
            return 'W trakcie'
        if step == 8:
            return 'Wdrożenie'
        return 'Opieka'

    @property
    def status_badge_class(self):
        step = self.current_step
        if step is None:
            return 'bg-success-subtle text-success border-success-subtle'
        if step <= 2:
            return 'bg-secondary-subtle text-secondary border-secondary-subtle'
        if step <= 5:
            return 'bg-info-subtle text-info border-info-subtle'
        if step <= 7:
            return 'bg-warning-subtle text-warning border-warning-subtle'
        return 'bg-primary-subtle text-primary border-primary-subtle'

    @property
    def progress_pct(self):
        done = len(set(self.completed_steps or []) & {n for n, _ in PDM_STEPS})
        return round(done / len(PDM_STEPS) * 100)

    def is_step_done(self, step_num):
        return step_num in (self.completed_steps or [])


class SolutionLog(models.Model):
    solution    = models.ForeignKey(Solution, on_delete=models.CASCADE, related_name='logs')
    version     = models.CharField(max_length=20, verbose_name='Wersja')
    log_date    = models.DateField(verbose_name='Data')
    change_type = models.CharField(max_length=20, choices=LOG_TYPE_CHOICES, default='other',
                                   verbose_name='Typ zmiany')
    description = models.TextField(verbose_name='Opis zmian')
    author      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='solution_logs')

    class Meta:
        ordering = ['-log_date', '-pk']
        verbose_name = 'Wpis kontroli wersji'

    def __str__(self):
        return f'{self.solution.name} v{self.version} ({self.log_date})'
