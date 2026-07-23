from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('protokoly', '0004_add_send_to_accounting'),
    ]

    operations = [
        migrations.AlterField(
            model_name='document',
            name='doc_date',
            field=models.DateField(blank=True, null=True, verbose_name='Data'),
        ),
    ]
