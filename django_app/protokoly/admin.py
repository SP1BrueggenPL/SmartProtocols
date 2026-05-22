from django.contrib import admin
from .models import Document, DocumentItem, AppSetting


class DocumentItemInline(admin.TabularInline):
    model = DocumentItem
    extra = 0


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display  = ['doc_number', 'doc_type', 'operation', 'doc_date',
                     'receiver_name', 'is_signed', 'is_sent', 'created_at']
    list_filter   = ['doc_type', 'operation']
    search_fields = ['doc_number', 'receiver_name', 'issuer_name']
    readonly_fields = ['doc_number', 'created_by', 'created_at', 'signed_at', 'email_sent_at']
    inlines = [DocumentItemInline]


@admin.register(AppSetting)
class AppSettingAdmin(admin.ModelAdmin):
    list_display = ['key', 'value']
