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
            name='Solution',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='Nazwa projektu')),
                ('category', models.CharField(choices=[('support', 'Prośba o wsparcie'), ('simple', 'Prosty proces'), ('extensive', 'Rozległy proces')], max_length=20, verbose_name='Kategoria')),
                ('technology', models.CharField(blank=True, choices=[('power_platform', 'Power Platform'), ('vibe_coding', 'Vibe Coding'), ('other', 'Inne')], default='', max_length=20, verbose_name='Technologia')),
                ('description', models.TextField(blank=True, default='', verbose_name='Opis zapotrzebowania')),
                ('completed_steps', models.JSONField(default=list, verbose_name='Ukończone kroki')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='solutions_created', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Solution',
                'verbose_name_plural': 'Solutions',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='SolutionLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version', models.CharField(max_length=20, verbose_name='Wersja')),
                ('log_date', models.DateField(verbose_name='Data')),
                ('change_type', models.CharField(choices=[('feature', 'Nowa funkcja'), ('fix', 'Poprawka'), ('deployment', 'Wdrożenie'), ('test', 'Faza testowa'), ('other', 'Inne')], default='other', max_length=20, verbose_name='Typ zmiany')),
                ('description', models.TextField(verbose_name='Opis zmian')),
                ('solution', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='logs', to='solutions.solution')),
                ('author', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='solution_logs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Wpis kontroli wersji',
                'ordering': ['-log_date', '-pk'],
            },
        ),
    ]
