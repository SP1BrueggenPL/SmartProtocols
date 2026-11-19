from django.urls import path
from . import views

urlpatterns = [
    path('',                                   views.solution_list,         name='solution_list'),
    path('nowy/',                              views.solution_new,          name='solution_new'),
    path('import/',                            views.solution_import,       name='solution_import'),
    path('dzialy/',                            views.department_list,       name='department_list'),
    path('dzialy/nowy/',                       views.department_new,        name='department_new'),
    path('dzialy/<int:pk>/usun/',              views.department_delete,     name='department_delete'),
    path('<int:pk>/',                          views.solution_view,         name='solution_view'),
    path('<int:pk>/zarzadzaj/',                views.solution_detail,       name='solution_detail'),
    path('<int:pk>/edytuj/',                   views.solution_edit,         name='solution_edit'),
    path('<int:pk>/usun/',                     views.solution_delete,       name='solution_delete'),
    path('<int:pk>/krok/<int:step>/toggle/',   views.solution_toggle_step,  name='solution_toggle_step'),
    path('<int:pk>/log/dodaj/',                views.solution_log_add,      name='solution_log_add'),
    path('<int:pk>/log/<int:log_pk>/usun/',    views.solution_log_delete,   name='solution_log_delete'),
    path('<int:pk>/dokument/dodaj/',           views.solution_doc_add,      name='solution_doc_add'),
    path('<int:pk>/dokument/<int:doc_pk>/usun/', views.solution_doc_delete, name='solution_doc_delete'),
    path('<int:pk>/import-danych/',            views.solution_data_import,  name='solution_data_import'),
]
