from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class Document(models.Model):
    DOC_TYPE_CHOICES = [
        ('office', 'Office'),
        ('telefon', 'Telefon'),
        ('produkcja', 'Produkcja'),
    ]
    OPERATION_CHOICES = [
        ('wydanie', 'Wydanie'),
        ('zwrot', 'Zwrot'),
    ]

    doc_number     = models.CharField(max_length=30, unique=True, verbose_name='Nr dokumentu')
    doc_type       = models.CharField(max_length=10, choices=DOC_TYPE_CHOICES, verbose_name='Typ')
    operation      = models.CharField(max_length=10, choices=OPERATION_CHOICES, verbose_name='Operacja')
    doc_date       = models.DateField(verbose_name='Data')
    issuer_name    = models.CharField(max_length=200, verbose_name='Przekazujący')
    issuer_email   = models.EmailField(blank=True, default='', verbose_name='Email przekazującego')
    receiver_name  = models.CharField(max_length=200, verbose_name='Przyjmujący')
    receiver_email = models.EmailField(verbose_name='Email przyjmującego')
    network_name   = models.CharField(max_length=100, blank=True, default='', verbose_name='Nazwa sieciowa')
    sig_issuer     = models.TextField(blank=True, default='', verbose_name='Podpis przekazującego')
    sig_receiver   = models.TextField(blank=True, default='', verbose_name='Podpis przyjmującego')
    signed_at      = models.DateTimeField(null=True, blank=True)
    email_sent_at  = models.DateTimeField(null=True, blank=True)
    created_by     = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Protokół'
        verbose_name_plural = 'Protokoły'

    def __str__(self):
        return self.doc_number

    @property
    def is_signed(self):
        return bool(self.sig_issuer and self.sig_receiver)

    @property
    def is_sent(self):
        return bool(self.email_sent_at)

    @property
    def doc_type_label(self):
        return {'office': 'Office', 'telefon': 'Telefon', 'produkcja': 'Produkcja'}.get(self.doc_type, self.doc_type)

    @property
    def doc_date_str(self):
        return self.doc_date.strftime('%Y-%m-%d') if self.doc_date else ''


class DocumentItem(models.Model):
    document           = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='items')
    sort_order         = models.IntegerField(default=0)
    # Office / Produkcja
    equipment_type     = models.CharField(max_length=100, blank=True, default='')
    manufacturer_model = models.CharField(max_length=200, blank=True, default='')
    serial_number      = models.CharField(max_length=100, blank=True, default='')
    quantity           = models.IntegerField(default=1)
    internal_number    = models.CharField(max_length=100, blank=True, default='')
    # Telefon
    phone_type         = models.CharField(max_length=100, blank=True, default='')
    imei               = models.CharField(max_length=50,  blank=True, default='')
    internal_name      = models.CharField(max_length=100, blank=True, default='')
    phone_number       = models.CharField(max_length=50,  blank=True, default='')
    sim_number         = models.CharField(max_length=100, blank=True, default='')
    pin_phone          = models.CharField(max_length=20,  blank=True, default='')
    pin_sim            = models.CharField(max_length=20,  blank=True, default='')
    acc_foil           = models.BooleanField(default=False)
    acc_case           = models.BooleanField(default=False)
    acc_charger        = models.BooleanField(default=False)
    acc_headphones     = models.BooleanField(default=False)
    notes              = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['sort_order']


class AppSetting(models.Model):
    key   = models.CharField(max_length=100, primary_key=True)
    value = models.TextField(default='')

    class Meta:
        verbose_name = 'Ustawienie'

    def __str__(self):
        return self.key

    @classmethod
    def get(cls, key, default=''):
        try:
            return cls.objects.get(pk=key).value
        except cls.DoesNotExist:
            return default

    @classmethod
    def set(cls, key, value):
        cls.objects.update_or_create(pk=key, defaults={'value': value})

    @classmethod
    def as_dict(cls):
        return {s.key: s.value for s in cls.objects.all()}


class UserProfile(models.Model):
    user                 = models.OneToOneField(User, on_delete=models.CASCADE,
                                                related_name='profile')
    must_change_password = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Profil użytkownika'

    def __str__(self):
        return f'Profil: {self.user.username}'


@receiver(post_save, sender=User)
def _ensure_profile(sender, instance, created, **kwargs):
    """Automatycznie tworzy profil dla każdego nowego użytkownika."""
    if created:
        UserProfile.objects.get_or_create(user=instance)
