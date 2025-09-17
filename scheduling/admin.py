from django.contrib import admin
from .models import ProjectTask, ProgressUpdate, ProgressFile, SystemReport, TaskCost

@admin.register(ProjectTask)
class ProjectTaskAdmin(admin.ModelAdmin):
    list_display = ("id", "task_name", "project", "start_date", "end_date", "get_progress")
    search_fields = ("task_name", "project__project_name")
    list_filter = ("project", "assigned_to")


    def get_progress(self, obj):
        # Get latest approved update
        latest_update = obj.updates.filter(status="A").order_by("-created_at").first()
        return f"{latest_update.progress_percent}%" if latest_update else "No updates"
    
    get_progress.short_description = "Progress"

 
@admin.register(TaskCost)
class TaskCostAdmin(admin.ModelAdmin):
    list_display = ("task", "cost", "allocated_amount")
    search_fields = ("task__task_name", "cost__name")  # adjust if your ProjectCost has "name"
    
    from django.contrib import admin
from .models import ProjectScope

@admin.register(ProjectScope)
class ProjectScopeAdmin(admin.ModelAdmin):
    list_display = ('name', 'project', 'weight', 'is_deleted', 'has_tasks')
    list_filter = ('project', 'is_deleted')
    search_fields = ('name', 'project__project_name')
    readonly_fields = ('has_tasks',)

    def has_tasks(self, obj):
        """Display if the scope has tasks"""
        return obj.has_tasks
    has_tasks.boolean = True
    has_tasks.short_description = "Has Tasks?"

    def get_queryset(self, request):
        """Optionally, you can exclude deleted items by default"""
        qs = super().get_queryset(request)
        return qs  # For default: show all, or use qs.filter(is_deleted=False) to hide deleted