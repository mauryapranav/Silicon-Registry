from django.urls import path
from . import views

app_name = 'registry'

urlpatterns = [
    # Core pages
    path('',                               views.homepage,        name='homepage'),
    path('about/',                         views.about,           name='about'),
    path('search/',                        views.search,          name='search'),

    # Machines
    path('machines/',                      views.machine_list,    name='machine_list'),
    path('machines/add/',                  views.machine_add,     name='machine_add'),
    path('machines/<int:pk>/',             views.machine_detail,  name='machine_detail'),

    # Reports
    path('reports/submit/',                views.report_submit,   name='report_submit'),
    path('reports/<int:pk>/',              views.report_detail,   name='report_detail'),

    # Users
    path('profile/edit/',                  views.profile_edit,    name='profile_edit'),
    path('profile/<str:username>/',        views.user_profile,    name='user_profile'),

    # Actions (HTMX endpoints)
    path('reports/<int:pk>/flag/',         views.flag_report,     name='flag_report'),
    path('reports/<int:pk>/comment/',      views.add_comment,     name='add_comment'),
    path('machines/<int:pk>/suggest-spec/',views.suggest_spec,    name='suggest_spec'),

    # Moderator dashboard
    path('mod/',                           views.mod_dashboard,   name='mod_dashboard'),
    path('mod/reports/',                   views.mod_reports,     name='mod_reports'),
    path('mod/reports/<int:pk>/approve/',  views.mod_approve_report, name='mod_approve_report'),
    path('mod/reports/<int:pk>/reject/',   views.mod_reject_report,  name='mod_reject_report'),
    path('mod/specs/',                     views.mod_specs,       name='mod_specs'),
    path('mod/fixes/',                     views.mod_fixes,       name='mod_fixes'),
    path('mod/trust/',                     views.mod_trust,       name='mod_trust'),
    path('mod/groups/',                    views.mod_groups,      name='mod_groups'),
    path('mod/users/',                     views.mod_users,       name='mod_users'),

    # HTMX partials
    path('partials/machine-cards/',        views.partial_machine_cards,  name='partial_machine_cards'),
    path('partials/navbar-search/',        views.partial_navbar_search,  name='partial_navbar_search'),
    path('partials/load-more-reports/',    views.partial_load_more,      name='partial_load_more'),

    # API
    path('api/machines/',                  views.api_machines,    name='api_machines'),
    path('api/reports/',                   views.api_reports,     name='api_reports'),
    path('api/components/',                views.api_components,  name='api_components'),
    path('api/distros/',                   views.api_distros,     name='api_distros'),

    # Error pages
    path('404/',                           views.error_404,       name='error_404'),
    path('500/',                           views.error_500,       name='error_500'),
]
