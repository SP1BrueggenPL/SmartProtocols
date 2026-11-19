from django.db import migrations


def create_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    for name in ['T&I Wilga', 'T&I Wilga Viewer']:
        Group.objects.get_or_create(name=name)


def remove_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name__in=['T&I Wilga', 'T&I Wilga Viewer']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('solutions', '0002_alter_solution_options_alter_solutionlog_options_and_more'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(create_groups, remove_groups),
    ]
