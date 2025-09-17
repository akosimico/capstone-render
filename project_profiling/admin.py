from django.contrib import admin
from .models import ProjectProfile, ProjectBudget, ProjectCost, ProjectStaging, ProjectType, Expense

@admin.register(ProjectProfile)
class ProjectProfileAdmin(admin.ModelAdmin):
    list_display = (
        "project_name",              # changed from project_title
        "project_id",
        "project_type",
        "project_manager",
        "site_engineer",  
        "start_date",
        "target_completion_date",    # changed from end_date
        "approved_budget",
    )
    list_filter = ('project_source', 'project_type', 'status')
    search_fields = (
        'project_id', 
        'project_name', 
        'client_name', 
        'gc_company_name'
    )
    ordering = ('-created_at',)
    
@admin.register(ProjectBudget)
class ProjectBudgetAdmin(admin.ModelAdmin):
    list_display = ("project", "category", "planned_amount")
    list_filter = ("category", "project")
    search_fields = ("project__name",)
    ordering = ("project", "category")


@admin.register(ProjectCost)
class ProjectCostAdmin(admin.ModelAdmin):
    list_display = ("project", "category", "description", "amount", "date_incurred", "linked_task", "created_at")
    list_filter = ("category", "date_incurred", "project")
    search_fields = ("project__name", "description", "linked_task__task_name")
    date_hierarchy = "date_incurred"
    ordering = ("-date_incurred",)

@admin.register(ProjectStaging)
class ProjectStagingAdmin(admin.ModelAdmin):
    list_display = ['id', 'project_source', 'created_by', 'submitted_at', 'status']
    
    
@admin.register(ProjectType)
class ProjectTypeAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "is_active",
        "created_by",
        "created_at",
        "updated_at",
        "usage_count",
    )
    list_filter = ("is_active", "created_at", "updated_at")
    search_fields = ("name", "code", "description")
    ordering = ("name",)
    readonly_fields = ("created_at", "updated_at", "usage_count")

    fieldsets = (
        (None, {
            "fields": ("name", "code", "description", "is_active")
        }),
        ("Audit Info", {
            "fields": ("created_by", "created_at", "updated_at", "usage_count"),
        }),
    )

    def usage_count(self, obj):
        return obj.get_usage_count()
    usage_count.short_description = "Usage Count"
    
@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = (
        'project',
        'budget_category',
        'expense_type',
        'expense_other',
        'amount',
        'vendor',
        'expense_date',
        'created_by',
        'created_at',
    )
    
    list_filter = (
        'expense_type',
        'project',
        'budget_category',
        'expense_date',
    )
    
    search_fields = (
        'project__name',
        'budget_category__name',
        'vendor',
        'receipt_number',
        'description',
        'expense_other',
    )
    
    readonly_fields = ('created_at',)
    
    fieldsets = (
        (None, {
            'fields': (
                'project',
                'budget_category',
                'expense_type',
                'expense_other',
                'amount',
                'vendor',
                'receipt_number',
                'expense_date',
                'description',
            )
        }),
        ('Audit Info', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user.userprofile  # Assuming UserProfile is linked via OneToOne to User
        super().save_model(request, obj, form, change)