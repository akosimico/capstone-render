from django.db import models
from authentication.models import UserProfile
from django.db.models import Sum
from decimal import Decimal
from django.utils import timezone
from manage_client.models import Client
from django.apps import apps
from scheduling.models import ProjectScope

class ProjectType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)  # e.g., 'GC', 'DC', 'RES'
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Project Type'
        verbose_name_plural = 'Project Types'
    
    def __str__(self):
        return self.name
    
    def get_usage_count(self):
        return self.projects.count()

class Expense(models.Model):
    EXPENSE_TYPES = [
        ('material', 'Material Purchase'),
        ('labor', 'Labor Payment'),
        ('equipment', 'Equipment Rental'),
        ('service', 'Service/Contractor'),
        ('other', 'Other'),
    ]
    
    project = models.ForeignKey('ProjectProfile', on_delete=models.CASCADE, related_name='expenses')
    budget_category = models.ForeignKey('ProjectBudget', on_delete=models.CASCADE, related_name='expenses')
    expense_type = models.CharField(max_length=20, choices=EXPENSE_TYPES)
    expense_other = models.CharField(max_length=255, blank=True, null=True, help_text="Specify if expense type is other")
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    vendor = models.CharField(max_length=255, blank=True)
    receipt_number = models.CharField(max_length=100, blank=True)
    expense_date = models.DateField()
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    
    class Meta:
        ordering = ['-expense_date', '-created_at']
        
class ProjectProfile(models.Model):
    # ----------------------------
    # Choice Definitions
    # ----------------------------
    PROJECT_SOURCES = [
        ("GC", "General Contractor"),
        ("DC", "Direct Client"),
    ]

    PROJECT_CATEGORIES = [
        ("PUB", "Public"),
        ("PRI", "Private"),
        ("REN", "Renovation"),
        ("NEW", "New Build"),
    ]
    STATUS_CHOICES = [
        ("PL", "Planned"),
        ("OG", "Ongoing"),
        ("CP", "Completed"),
        ("CN", "Cancelled"),
    ]

    # ----------------------------
    # 1. User Assignments
    # ----------------------------
    created_by = models.ForeignKey(
        UserProfile,
        on_delete=models.SET_NULL,
        null=True,
        related_name="projects_created",
    )
    assigned_to = models.ForeignKey(
        UserProfile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="projects_assigned",
    )
    project_manager = models.ForeignKey(
        UserProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={"role": "PM"},
    )
    client = models.ForeignKey(
        Client,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="projects"
    )

    # ----------------------------
    # 2. General Project Information
    # ----------------------------
    project_source = models.CharField(max_length=20, choices=PROJECT_SOURCES)
    project_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    project_name = models.CharField(max_length=200)
    project_type = models.ForeignKey(ProjectType, on_delete=models.SET_NULL, null=True, related_name="projects")
    project_category = models.CharField(max_length=10, choices=PROJECT_CATEGORIES, blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    # ----------------------------
    # 4. Location
    # ----------------------------
    location = models.CharField(max_length=300)
    gps_coordinates = models.CharField(max_length=100, blank=True, null=True)
    city_province = models.CharField(max_length=200, blank=True, null=True)

    # ----------------------------
    # 5. Timeline
    # ----------------------------
    start_date = models.DateField(blank=True, null=True)
    target_completion_date = models.DateField(blank=True, null=True)
    actual_completion_date = models.DateField(blank=True, null=True)

    # ----------------------------
    # 6. Financials
    # ----------------------------
    estimated_cost = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    approved_budget = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    expense = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    payment_terms = models.TextField(blank=True, null=True)
    
    # ----------------------------
    # 7. Stakeholders
    # ----------------------------
    site_engineer = models.CharField(max_length=200, blank=True, null=True)
    subcontractors = models.TextField(blank=True, null=True)

    # ----------------------------
    # 8. Documentation
    # ----------------------------
    contract_agreement = models.FileField(upload_to="contracts/", blank=True, null=True)
    permits_licenses = models.FileField(upload_to="permits/", blank=True, null=True)

    # ----------------------------
    # 9. Status & Tracking
    # ----------------------------
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PL")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archived = models.BooleanField(default=False)
    progress = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Overall project progress (%)"
    )
    class Meta:
        ordering = ["-created_at", "project_name"]

    # ----------------------------
    # Properties / Business Logic
    # ----------------------------
    def __str__(self):
        return f"{self.project_id or 'NoCode'} - {self.project_name}"
    
    def active(self):
        return not self.archived

    @property
    def total_expenses(self):
        return sum(cost.amount for cost in self.costs.all())

    @property
    def cost_performance(self):
        """Return % of budget spent"""
        if not self.approved_budget or self.approved_budget == 0:
            return None
        return (self.total_expenses / self.approved_budget) * 100

    @property
    def total_task_allocations(self):
        TaskCost = apps.get_model("scheduling", "TaskCost")
        return sum(tc.allocated_amount for tc in TaskCost.objects.filter(task__project=self))

    @property
    def remaining_budget(self):
        return (self.approved_budget or 0) - self.total_task_allocations

    def save(self, *args, **kwargs):
        # --- Progress logic ---
        # Clamp progress between 0 and 100
        self.progress = max(0, min(self.progress, 100))
        self.is_completed = self.progress >= 100

        # --- Project ID logic ---
        is_new = self.pk is None
        super().save(*args, **kwargs)  # First save to get auto-incremented id

        if is_new and not self.project_id:
            prefix = self.project_source or "PRJ"
            self.project_id = f"{prefix}-{self.id:03d}"  # e.g., GC-001
            kwargs['force_insert'] = False
            super().save(*args, **kwargs)
        
    def update_progress_from_tasks(self):
        tasks = self.tasks.all()
        if tasks.exists():
            total_progress = sum(
            (task.progress or Decimal(0)) * (Decimal(task.weight) / Decimal(100))
            for task in tasks
            )
            self.progress = min(total_progress, Decimal(100))
        else:
            self.progress = Decimal(0)

    # Auto-update project status
        if self.progress >= 100:
            self.status = "CP"
        elif self.progress > 0:
            self.status = "OG"
        else:
            self.status = "PL"

        self.save(update_fields=["progress", "status"])
        
#Temporary for projects that needs to be approved
class ProjectStaging(models.Model):
    created_by = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True)
    project_data = models.JSONField()
    project_source = models.CharField(max_length=20, choices=[("GC", "General Contractor"), ("DC", "Direct Client")])
    project_id_placeholder = models.CharField(max_length=20, blank=True, null=True)
    status = models.CharField(max_length=2, choices=[("PL", "Pending"), ("AP", "Approved"), ("RJ", "Rejected")], default="PL")
    submitted_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.project_data.get('project_name', 'Unnamed')} ({self.project_source_display})"

    @property
    def project_source_display(self):
        return dict([("GC", "General Contractor"), ("DC", "Direct Client")]).get(self.project_source, self.project_source)
    
    class Meta:
        ordering = ["-submitted_at"] 


class ProjectStagingHistory(models.Model):
    project_staging = models.ForeignKey("ProjectStaging", related_name="history_logs", on_delete=models.CASCADE)
    created_by = models.ForeignKey("authentication.UserProfile", on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=2, choices=[("PL","Pending"),("AP","Approved"),("RJ","Rejected")])
    comments = models.TextField(blank=True, null=True)  # optional notes from reviewer
    submitted_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-submitted_at"]
        
class ProjectFile(models.Model):
    project = models.ForeignKey(ProjectProfile, on_delete=models.CASCADE, related_name="files")
    file = models.FileField(upload_to="project_files/")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
class CostCategory(models.TextChoices):
    LABOR = "LAB", "Labor"
    MATERIALS = "MAT", "Materials"
    EQUIPMENT = "EQP", "Equipment"
    SUBCONTRACTOR = "SUB", "Subcontractor"
    OTHER = "OTH", "Other"


# 1️⃣ Planned budget
class ProjectBudget(models.Model):
    project = models.ForeignKey("ProjectProfile", on_delete=models.CASCADE, related_name="budgets")
    
    # Use the existing ProjectScope model
    scope = models.ForeignKey(ProjectScope, on_delete=models.CASCADE, related_name="budget_categories")
    
    # Cost category within the scope
    category = models.CharField(max_length=3, choices=CostCategory.choices)
    category_other = models.CharField(max_length=255, blank=True, null=True, help_text="Specify if category is Other")
    
    planned_amount = models.DecimalField(max_digits=15, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['scope', 'category']  # Prevent duplicate scope-category combinations
        ordering = ['scope__name', 'category']

    def __str__(self):
        return f"[BUDGET] {self.scope.name} > {self.get_category_display()} (₱{self.planned_amount:,.2f})"

    @property
    def total_allocated(self):
        """Calculate total amount allocated for this budget category"""
        return self.allocations.aggregate(total=models.Sum('amount'))['total'] or 0

    @property
    def remaining_amount(self):
        """Calculate remaining amount available for allocation"""
        return self.planned_amount - self.total_allocated

    @property
    def allocation_percentage(self):
        """Calculate percentage of budget that has been allocated"""
        if self.planned_amount > 0:
            return (self.total_allocated / self.planned_amount) * 100
        return 0

    @property
    def is_over_budget(self):
        """Check if allocations exceed planned amount"""
        return self.total_allocated > self.planned_amount



# 2️⃣ Actual expenditures (linked to tasks if needed)
class ProjectCost(models.Model):
    project = models.ForeignKey("ProjectProfile", on_delete=models.CASCADE, related_name="costs")
    category = models.CharField(max_length=3, choices=CostCategory.choices)
    description = models.CharField(max_length=255, blank=True, null=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    date_incurred = models.DateField(default=timezone.now)
    linked_task = models.ForeignKey(
        "scheduling.ProjectTask",
        on_delete=models.SET_NULL,
        blank=True,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_incurred"]

    def __str__(self):
        return f"[ACTUAL] {self.project.project_name} - {self.get_category_display()} ({self.amount})"

class FundAllocation(models.Model):
    project_budget = models.ForeignKey(
        "ProjectBudget", 
        on_delete=models.CASCADE,
        related_name="allocations"
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    date_allocated = models.DateField(default=timezone.now)
    note = models.CharField(max_length=255, blank=True, null=True)

    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        ordering = ["-date_allocated"]
        
    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()
        
    def restore(self):
        """Restore a soft-deleted allocation"""
        self.is_deleted = False
        self.deleted_at = None
        self.save()

    def __str__(self):
        return f"[ALLOC] {self.project_budget.project.project_name} - {self.project_budget.get_category_display()} ({self.amount})"
