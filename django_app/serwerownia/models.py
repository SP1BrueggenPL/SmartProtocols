from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class ServerAudit(models.Model):
    name        = models.CharField(max_length=255, verbose_name='Nazwa audytu')
    description = models.TextField(blank=True, default='', verbose_name='Opis')
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Audyt serwerowni'
        verbose_name_plural = 'Audyty serwerowni'

    def __str__(self):
        return self.name


class AuditRequirement(models.Model):
    audit = models.ForeignKey(ServerAudit, on_delete=models.CASCADE, related_name='requirements')
    order = models.PositiveIntegerField(default=0)
    text  = models.CharField(max_length=500, verbose_name='Punkt kontrolny')
    image = models.ImageField(upload_to='audit_req/', blank=True, null=True, verbose_name='Zdjęcie przykładowe')

    class Meta:
        ordering = ['order', 'pk']

    def __str__(self):
        return self.text


class AuditInspection(models.Model):
    audit        = models.ForeignKey(ServerAudit, on_delete=models.CASCADE, related_name='inspections')
    user         = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    comment      = models.TextField(blank=True, default='', verbose_name='Komentarz ogólny')

    class Meta:
        ordering = ['-created_at']

    @property
    def is_completed(self):
        return bool(self.completed_at)

    @property
    def has_failures(self):
        return self.results.filter(is_met=False).exists()


class InspectionResult(models.Model):
    inspection  = models.ForeignKey(AuditInspection, on_delete=models.CASCADE, related_name='results')
    requirement = models.ForeignKey(AuditRequirement, on_delete=models.SET_NULL, null=True)
    is_met      = models.BooleanField(default=False, verbose_name='Spełniony')
    comment     = models.TextField(blank=True, default='', verbose_name='Komentarz')
    image       = models.ImageField(upload_to='inspection_img/', blank=True, null=True, verbose_name='Zdjęcie')

    class Meta:
        ordering = ['requirement__order', 'requirement__pk']
