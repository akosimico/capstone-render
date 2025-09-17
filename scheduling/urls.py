from django.urls import path
from . import views

urlpatterns = [
    # ---------------------------
    # Scheduling / Tasks
    # ---------------------------
    path('<int:project_id>/<str:token>/<str:role>/tasks/', views.task_list, name='task_list'),
    path("<int:project_id>/<str:token>/<str:role>/tasks/add/", views.task_create, name="task_create"),
    # path("<int:project_id>/<str:token>/<str:role>/tasks/save-imported/", views.save_imported_tasks, name="save_imported_tasks"),
    path("<int:project_id>/<str:token>/<str:role>/tasks/<int:task_id>/update/",views.task_update, name="task_update"),
    path("<int:project_id>/<str:token>/<str:role>/tasks/<int:task_id>/delete/",views.task_archive, name="task_archive"),
    path("<int:project_id>/<str:token>/<str:role>/tasks/bulk-delete/",views.task_bulk_archive, name="task_bulk_archive"),
    path("<int:project_id>/<str:token>/<str:role>/<int:task_id>/unarchive/", views.task_unarchive, name="task_unarchive"),
    path("<int:project_id>/<str:token>/<str:role>/tasks/unarchive-selected/", views.task_bulk_unarchive, name="task_bulk_unarchive"),
    path("<str:token>/task/<int:task_id>/submit-progress/<str:role>/", views.submit_progress_update, name="submit_progress"),
path('<int:project_id>/create-scope/', views.create_scope_ajax, name='create_scope_ajax'),
    # ---------------------------
    # Progress Review
    # ---------------------------
    path('progress/review/', views.review_updates, name='review_updates'),
    path('progress/approve/<int:update_id>/', views.approve_update, name='approve_update'),
    path('progress/reject/<int:update_id>/', views.reject_update, name='reject_update'),
    path("progress/history/", views.progress_history, name="progress_history"),

    path("api/pending-count/", views.get_pending_count, name="get_pending_count"),
    
]
