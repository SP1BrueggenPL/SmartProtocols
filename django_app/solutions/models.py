import os

from django.contrib.auth.models import User
from django.db import models


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

ENVIRONMENT_CHOICES = [
    ('test', 'Testowe'),
    ('prod', 'Produkcyjne'),
]


class Department(models.Model):
    name   = models.CharField(max_length=255, verbose_name='Nazwa działu')
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE,
                               related_name='children', verbose_name='Nadrzędny dział')
    order  = models.PositiveIntegerField(default=0, verbose_name='Kolejność')

    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'Dział'
        verbose_name_plural = 'Działy'

    def __str__(self):
        if self.parent:
            return f'{self.parent.name} / {self.name}'
        return self.name


class Solution(models.Model):
    name           = models.CharField(max_length=255, verbose_name='Nazwa projektu')
    department     = models.ForeignKey(Department, null=True, blank=True, on_delete=models.SET_NULL,
                                       related_name='solutions', verbose_name='Dział')
    category       = models.CharField(max_length=20, choices=CATEGORY_CHOICES, verbose_name='Kategoria')
    technology     = models.CharField(max_length=20, choices=TECHNOLOGY_CHOICES, blank=True, default='',
                                      verbose_name='Technologia')
    description    = models.TextField(blank=True, default='', verbose_name='Opis zapotrzebowania')
    app_url        = models.URLField(blank=True, default='', verbose_name='Link do aplikacji')
    admin_login    = models.CharField(max_length=255, blank=True, default='', verbose_name='Login administracyjny')
    admin_password = models.CharField(max_length=255, blank=True, default='', verbose_name='Hasło administracyjne')
    start_date     = models.DateField(null=True, blank=True, verbose_name='Data rozpoczęcia prac')
    production_date = models.DateField(null=True, blank=True, verbose_name='Data wdrożenia produkcyjnego')
    completed_steps = models.JSONField(default=list, verbose_name='Ukończone kroki')
    created_at     = models.DateTimeField(auto_now_add=True)
    created_by     = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='solutions_created')

    class Meta:
        ordering = ['name']
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
        return None

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


DOCUMENT_CATEGORY_CHOICES = [
    ('documentation', 'Dokumentacja/Instrukcja'),
    ('backup',        'Backup'),
]


def _doc_upload_path(instance, filename):
    return f'solution_docs/{instance.solution_id}/{filename}'


class SolutionDocument(models.Model):
    solution    = models.ForeignKey(Solution, on_delete=models.CASCADE, related_name='documents')
    category    = models.CharField(max_length=20, choices=DOCUMENT_CATEGORY_CHOICES, default='documentation',
                                   verbose_name='Kategoria')
    environment = models.CharField(max_length=10, choices=ENVIRONMENT_CHOICES, blank=True, default='',
                                   verbose_name='Środowisko (dla backupów)')
    title       = models.CharField(max_length=255, verbose_name='Tytuł dokumentu')
    file        = models.FileField(upload_to=_doc_upload_path, verbose_name='Plik')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='uploaded_docs')

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'Dokument'

    def __str__(self):
        return self.title

    @property
    def is_pdf(self):
        return self.file.name.lower().endswith('.pdf')

    @property
    def filename(self):
        return os.path.basename(self.file.name)


class SolutionLog(models.Model):
    solution           = models.ForeignKey(Solution, on_delete=models.CASCADE, related_name='logs')
    version            = models.CharField(max_length=20, blank=True, default='', verbose_name='Wersja')
    goal               = models.CharField(max_length=500, blank=True, default='', verbose_name='Cel aktualizacji')
    update_start_date  = models.DateField(null=True, blank=True, verbose_name='Data rozpoczęcia aktualizacji')
    log_date           = models.DateField(null=True, blank=True, verbose_name='Data wdrożenia aktualizacji')
    responsible_person = models.CharField(max_length=255, blank=True, default='', verbose_name='Osoba odpowiedzialna')
    environment        = models.CharField(max_length=10, choices=ENVIRONMENT_CHOICES, default='prod',
                                          verbose_name='Środowisko')
    deployed           = models.BooleanField(default=False, verbose_name='Wdrożono?')
    user_notified      = models.BooleanField(default=False, verbose_name='Informacja do użytkownika końcowego?')
    change_type        = models.CharField(max_length=20, choices=LOG_TYPE_CHOICES, blank=True, default='',
                                          verbose_name='Typ zmiany')
    description        = models.TextField(blank=True, default='', verbose_name='Opis aktualizacji')
    blockers           = models.TextField(blank=True, default='',
                                          verbose_name='Blokery/Problemy techniczne podczas procesowania aktualizacji lub jej wdrażania')
    author             = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                           related_name='solution_logs')

    class Meta:
        ordering = ['-update_start_date', '-log_date', '-pk']
        verbose_name = 'Wpis kontroli wersji (UpdateLog)'

    def __str__(self):
        v = f' v{self.version}' if self.version else ''
        return f'{self.solution.name}{v} ({self.log_date or self.update_start_date})'
