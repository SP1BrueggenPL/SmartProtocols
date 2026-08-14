from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ServerAudit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='Nazwa audytu')),
                ('description', models.TextField(blank=True, default='', verbose_name='Opis')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Audyt serwerowni',
                'verbose_name_plural': 'Audyty serwerowni',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='AuditRequirement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.PositiveIntegerField(default=0)),
                ('text', models.CharField(max_length=500, verbose_name='Punkt kontrolny')),
                ('image', models.ImageField(blank=True, null=True, upload_to='audit_req/', verbose_name='Zdjęcie przykładowe')),
                ('audit', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='requirements', to='serwerownia.serveraudit')),
            ],
            options={
                'ordering': ['order', 'pk'],
            },
        ),
        migrations.CreateModel(
            name='AuditInspection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('comment', models.TextField(blank=True, default='', verbose_name='Komentarz ogólny')),
                ('audit', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='inspections', to='serwerownia.serveraudit')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='InspectionResult',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_met', models.BooleanField(default=False, verbose_name='Spełniony')),
                ('comment', models.TextField(blank=True, default='', verbose_name='Komentarz')),
                ('image', models.ImageField(blank=True, null=True, upload_to='inspection_img/', verbose_name='Zdjęcie')),
                ('inspection', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='results', to='serwerownia.auditinspection')),
                ('requirement', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='serwerownia.auditrequirement')),
            ],
            options={
                'ordering': ['requirement__order', 'requirement__pk'],
            },
        ),
    ]
