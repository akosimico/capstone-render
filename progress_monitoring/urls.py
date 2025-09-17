from django.urls import path
from .views import progress_monitoring
from . import views

urlpatterns = [
    path("<str:token>/<str:role>/", views.progress_monitoring, name="progress_monitoring"),

   
]
