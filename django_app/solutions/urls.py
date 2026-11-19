from django.urls import path
from . import views

urlpatterns = [
    path('',                                   views.solution_list,         name='solution_list'),
    path('nowy/',                              views.solution_new,          name='solution_new'),
    path('<int:pk>/',                          views.solution_detail,       name='solution_detail'),
    path('<int:pk>/edytuj/',                   views.solution_edit,         name='solution_edit'),
    path('<int:pk>/usun/',                     views.solution_delete,       name='solution_delete'),
    path('<int:pk>/krok/<int:step>/toggle/',   views.solution_toggle_step,  name='solution_toggle_step'),
    path('<int:pk>/log/dodaj/',                views.solution_log_add,      name='solution_log_add'),
    path('<int:pk>/log/<int:log_pk>/usun/',    views.solution_log_delete,   name='solution_log_delete'),
]
