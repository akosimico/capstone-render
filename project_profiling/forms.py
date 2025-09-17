from django import forms
from django.db.models import Q
from .models import ProjectProfile, ProjectBudget, ProjectType, ProjectScope, CostCategory
from authentication.models import UserProfile
from manage_client.models import Client



class ProjectProfileForm(forms.ModelForm):
    class Meta:
        model = ProjectProfile
        fields = [
            "project_manager",
            "project_source",
            "project_id",
            "project_name",
            "project_type",
            "project_category",
            "description",
            "client",
            "location",
            "gps_coordinates",
            "city_province",
            "start_date",
            "target_completion_date",
            "actual_completion_date",
            "estimated_cost",
            "expense",
            "payment_terms",
            "site_engineer",
            "subcontractors",
            "contract_agreement",
            "permits_licenses",
            "status",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "target_completion_date": forms.DateInput(attrs={"type": "date"}),
            "actual_completion_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        # Extract pre-selected client ID BEFORE calling super()
        self.pre_selected_client_id = kwargs.pop('pre_selected_client_id', None)
        
        super().__init__(*args, **kwargs)

        # ----------------------------
        # Handle Project Manager field
        # ----------------------------
        self.fields["project_manager"].required = False
        pm_qs = UserProfile.objects.filter(role="PM")

        if self.instance and self.instance.project_manager:
            pm_qs = pm_qs | UserProfile.objects.filter(id=self.instance.project_manager.id)

        pm_id = self.data.get("project_manager")
        if pm_id and pm_id.isdigit():
            pm_qs = pm_qs | UserProfile.objects.filter(id=int(pm_id))

        self.fields["project_manager"].queryset = pm_qs.distinct()
        self.fields["project_manager"].widget.attrs.update({
            "class": "w-full rounded-lg border border-gray-300 bg-white px-3 py-2 shadow-sm "
                     "focus:border-blue-500 focus:ring-2 focus:ring-blue-500 text-gray-700",
        })

        # ----------------------------
        # Handle pre-selected client logic FIRST
        # ----------------------------
        if self.pre_selected_client_id and not self.instance.pk:
            try:
                client = Client.objects.get(id=self.pre_selected_client_id)
                
                # Remove client field from form since it's handled in template
                if 'client' in self.fields:
                    del self.fields['client']
                
                # Filter project types to only show client's available types
                client_project_types = client.project_types.filter(is_active=True)
                if client_project_types.exists():
                    self.fields["project_type"].queryset = client_project_types
                    
                    # Add styling to indicate filtered options
                    self.fields["project_type"].widget.attrs.update({
                        "class": "w-full rounded-lg border border-blue-300 bg-blue-50 px-3 py-2 shadow-sm "
                                 "focus:border-blue-500 focus:ring-2 focus:ring-blue-500 text-gray-700",
                        "data-filtered-by-client": "true"
                    })
                else:
                    # No project types available for this client
                    self.fields["project_type"].queryset = ProjectType.objects.none()
                    self.fields["project_type"].widget.attrs.update({
                        "class": "w-full rounded-lg border border-red-300 bg-red-50 px-3 py-2 shadow-sm text-gray-700",
                        "disabled": True
                    })
                    
            except Client.DoesNotExist:
                pass
        else:
            # ----------------------------
            # Handle Client field (normal case)
            # ----------------------------
            client_qs = Client.objects.filter(is_active=True)

            # Always allow the current client even if inactive
            if self.instance and self.instance.client:
                client_qs = client_qs | Client.objects.filter(id=self.instance.client.id)

            # Also allow posted client ID (when editing via hidden input)
            client_id = self.data.get("client")
            if client_id and client_id.isdigit():
                client_qs = client_qs | Client.objects.filter(id=int(client_id))

            self.fields["client"].queryset = client_qs.distinct()
            self.fields["client"].widget.attrs.update({
                "class": "w-full rounded-lg border border-gray-300 bg-white px-3 py-2 shadow-sm "
                         "focus:border-blue-500 focus:ring-2 focus:ring-blue-500 text-gray-700",
                "data-autofill-target": "true",
                "onchange": "handleClientChange(this.value)"
            })
            
            # ----------------------------
            # Handle Project Type field (normal case)
            # ----------------------------
            self.fields["project_type"].queryset = ProjectType.objects.filter(is_active=True)
            self.fields["project_type"].widget.attrs.update({
                "class": "w-full rounded-lg border border-gray-300 bg-white px-3 py-2 shadow-sm "
                         "focus:border-blue-500 focus:ring-2 focus:ring-blue-500 text-gray-700"
            })

        # ----------------------------
        # Style payment terms field
        # ----------------------------
        if "payment_terms" in self.fields:
            self.fields["payment_terms"].widget.attrs.update({
                "class": "w-full rounded-lg border border-gray-300 bg-white px-3 py-2 shadow-sm "
                         "focus:border-blue-500 focus:ring-2 focus:ring-blue-500 text-gray-700"
            })
            
            # Add special styling for auto-filled fields
            if self.pre_selected_client_id:
                self.fields["payment_terms"].widget.attrs.update({
                    "data-auto-fillable": "true"
                })

class ProjectBudgetForm(forms.ModelForm):
    class Meta:
        model = ProjectBudget
        fields = ['scope', 'category','category_other', 'planned_amount']
        widgets = {
            'scope': forms.Select(attrs={
                'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500',
            }),
            'category': forms.Select(attrs={
                'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500',
            }),
            'category_other': forms.TextInput(attrs={
                'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500',
                'placeholder': 'Specify category if Other',
            }),
            'planned_amount': forms.NumberInput(attrs={
                'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            })
        }

    def __init__(self, *args, **kwargs):
        project = kwargs.pop('project', None)
        super().__init__(*args, **kwargs)
        
        # Limit scope choices to this project's scopes
        if project:
            self.fields['scope'].queryset = ProjectScope.objects.filter(project=project)
        
        # Add labels
        self.fields['scope'].label = 'Project Scope'
        self.fields['category'].label = 'Cost Category'
        self.fields['planned_amount'].label = 'Planned Amount (₱)'
        
        # Add help text
        self.fields['scope'].help_text = 'Select the project scope for this budget item'
        self.fields['category'].help_text = 'Select the cost category within this scope'
        self.fields['planned_amount'].help_text = 'Enter the planned budget amount for this scope/category'
        
        # If editing, disable scope/category to prevent duplicate combinations
        if self.instance.pk:
            self.fields['scope'].disabled = True
            self.fields['category'].disabled = True
            
    def clean(self):
        cleaned_data = super().clean()
        scope = cleaned_data.get('scope')
        category = cleaned_data.get('category')
        
        # Check for duplicate scope-category combination (only for new instances)
        if not self.instance.pk and scope and category:
            if ProjectBudget.objects.filter(scope=scope, category=category).exists():
                raise forms.ValidationError(
                    f"A budget for {scope.name} - {self.get_category_display(category)} already exists."
                )
        
        return cleaned_data
    
    def get_category_display(self, category_code):
        """Helper method to get category display name"""
        for code, name in CostCategory.choices:
            if code == category_code:
                return name
        return category_code
