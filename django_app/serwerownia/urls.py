from django.urls import path
from . import views

urlpatterns = [
    path('',                                                views.audit_list,        name='audit_list'),
    path('nowy/',                                           views.audit_new,         name='audit_new'),
    path('<int:pk>/',                                       views.audit_detail,      name='audit_detail'),
    path('<int:pk>/edytuj/',                                views.audit_edit,        name='audit_edit'),
    path('<int:pk>/usun/',                                  views.audit_delete,      name='audit_delete'),
    path('<int:audit_pk>/inspekcja/start/',                 views.inspection_start,  name='inspection_start'),
    path('<int:audit_pk>/inspekcja/<int:pk>/',              views.inspection_detail, name='inspection_detail'),
    path('<int:audit_pk>/inspekcja/<int:pk>/wypelnij/',     views.inspection_fill,   name='inspection_fill'),
    path('<int:audit_pk>/inspekcja/<int:pk>/zakoncz/',      views.inspection_finish, name='inspection_finish'),
    path('<int:audit_pk>/inspekcja/<int:pk>/usun/',         views.inspection_delete, name='inspection_delete'),
    path('<int:audit_pk>/inspekcja/<int:pk>/pdf/',          views.inspection_pdf,    name='inspection_pdf'),
]
