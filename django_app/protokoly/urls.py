from django.urls import path
from . import views

urlpatterns = [
    path('',                          views.index,           name='index'),
    path('login/',                    views.login_view,      name='login'),
    path('logout/',                   views.logout_view,     name='logout'),
    path('dashboard/',                views.dashboard,       name='dashboard'),
    path('documents/new/',            views.document_new,    name='document_new'),
    path('documents/create/',         views.document_create, name='document_create'),
    path('documents/<int:pk>/',       views.document_view,   name='document_view'),
    path('documents/<int:pk>/edit/',  views.document_edit,   name='document_edit'),
    path('documents/<int:pk>/sign/',  views.document_sign,   name='document_sign'),
    path('documents/<int:pk>/pdf/',   views.document_pdf,    name='document_pdf'),
    path('documents/<int:pk>/send/',  views.document_send,   name='document_send'),
    path('settings/',                 views.settings_view,          name='settings'),
    path('change-password/',          views.change_password_forced, name='change_password_forced'),
]
