from django import forms
from .models import ProjectTask, ProgressUpdate, ProgressFile, ProjectScope
from authentication.models import UserProfile  # adjust if your user model is elsewhere
from datetime import timedelta

class ProjectTaskForm(forms.ModelForm):
    class Meta:
        model = ProjectTask
        fields = ["scope", "task_name", "assigned_to", "start_date", "end_date", "duration_days", "manhours", "weight"]

        labels = {
            "scope": "Project Scope",
            "task_name": "Task Name",
            "assigned_to": "Assign To",
            "start_date": "Start Date",
            "end_date": "End Date",
            "duration_days": "Duration (Days)",
            "manhours": "Man Hours",
            "weight": "Task Weight (%)",
        }
        
        widgets = {
            "task_name": forms.TextInput(attrs={
                "placeholder": "Enter task name...",
                "class": "w-full",
                "id": "id_task_name"
            }),
            "start_date": forms.DateInput(attrs={
                "type": "date", 
                "id": "id_start_date",
                "class": "w-full"
            }),
            "end_date": forms.DateInput(attrs={
                "type": "date", 
                "id": "id_end_date",
                "class": "w-full"
            }),
            "duration_days": forms.NumberInput(attrs={
                "readonly": "readonly",
                "class": "w-full bg-gray-50 cursor-not-allowed",
                "id": "id_duration_days",
                "placeholder": "Auto-calculated"
            }),
            "manhours": forms.NumberInput(attrs={
                "readonly": "readonly",
                "class": "w-full bg-gray-50 cursor-not-allowed",
                "id": "id_manhours",
                "placeholder": "Auto-calculated"
            }),
            "weight": forms.NumberInput(attrs={
                "placeholder": "0.00",
                "step": "0.01",
                "min": "0",
                "max": "100",
                "class": "w-full",
                "id": "id_weight"
            }),
        }

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop('project', None)
        super().__init__(*args, **kwargs)
        
        # Scope field - limit to current project's scopes
        if self.project:
            self.fields["scope"].queryset = ProjectScope.objects.filter(project=self.project)
            self.fields["scope"].empty_label = "Select a scope"
            self.fields["scope"].widget.attrs.update({
                "class": "w-full",
                "id": "id_scope"
            })
        
        # Assigned To field - only show Project Managers
        self.fields["assigned_to"].queryset = UserProfile.objects.filter(role="PM")
        self.fields["assigned_to"].required = False
        self.fields["assigned_to"].widget = forms.HiddenInput()  # We'll use custom JS widget
        
        # Add help text
        self.fields["weight"].help_text = "Percentage contribution of this task to its scope (0-100%)"
        self.fields["duration_days"].help_text = "Automatically calculated from start and end dates"
        self.fields["manhours"].help_text = "Automatically calculated (Duration × 8 hours/day)"

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("start_date")
        end = cleaned_data.get("end_date")
        weight = cleaned_data.get("weight")
        scope = cleaned_data.get("scope")

        # Validate dates
        if start and end:
            if end < start:
                self.add_error("end_date", "End date cannot be earlier than start date.")
            else:
                # Auto-calculate days (inclusive)
                duration = (end - start).days + 1
                cleaned_data["duration_days"] = duration
                # Auto-calculate manhours (8 hours per day)
                cleaned_data["manhours"] = duration * 8

        # Validate weight within scope
        if weight is not None and scope:
            if weight <= 0:
                self.add_error("weight", "Weight must be greater than 0.")
        elif weight > 100:
            self.add_error("weight", "Weight cannot exceed 100%.")
        else:
            # Check if total weight for scope would exceed 100%
            existing_tasks = ProjectTask.objects.filter(scope=scope).exclude(
                id=self.instance.id if self.instance else None
            )
            current_total = sum(task.weight for task in existing_tasks)

            if current_total + weight > 100:
                remaining = 100 - current_total
                self.add_error(
                    "weight",
                    f"This scope already has {current_total}%. "
                    f"Only {remaining}% remaining, but you entered {weight}%."
                )

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Ensure project is set
        if self.project:
            instance.project = self.project
            
        if commit:
            instance.save()
            
        return instance

class ProgressUpdateForm(forms.ModelForm):
    class Meta:
        model = ProgressUpdate
        fields = ["progress_percent", "remarks"]
        widgets = {
            "progress_percent": forms.NumberInput(attrs={
                "class": "w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500",
                "placeholder": "Enter % progress",
                "step": "0.01",
                "min": "0",
                "max": "100"
            }),
            "remarks": forms.Textarea(attrs={
                "class": "w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500",
                "placeholder": "Additional notes or remarks...",
                "rows": 3
            }),
        }