from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.signing import BadSignature, SignatureExpired
from authentication.utils.tokens import parse_dashboard_token, make_dashboard_token
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from datetime import timedelta
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from decimal import Decimal, InvalidOperation
from django.db import models
from django.db.models import Sum, Max
from datetime import date, datetime
from django.urls import reverse
from django.utils.timezone import localtime
import json
from django.conf import settings
from django.core.files import File
import os
import random
from django.views.decorators.http import require_POST
from notifications.utils import send_notification
from notifications.models import Notification, NotificationStatus
from authentication.models import UserProfile
from authentication.views import verify_user_token
from django.forms.models import model_to_dict
from authentication.utils.decorators import verified_email_required, role_required
from .forms import ProjectProfileForm, ProjectBudgetForm
from django.urls import resolve
from .models import ProjectProfile, ProjectFile, ProjectBudget, FundAllocation, ProjectStaging, ProjectType, ProjectScope, Expense
from manage_client.models import Client
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from powermason_capstone.utils.calculate_progress import calculate_progress
# ----------------------------------------
# FUNCTION
# ----------------------------------------
@login_required
@verified_email_required
@role_required('OM', 'EG')
def search_project_managers(request):
    query = request.GET.get('q', '')
    project_managers = UserProfile.objects.filter(role='PM').select_related("user")

    if query:
        # Filter by actual database fields only
        project_managers = project_managers.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(user__email__icontains=query)
        )

    data = []
    for u in project_managers:
        # Construct full_name from the related User model
        full_name = f"{u.user.first_name} {u.user.last_name}".strip()
        # If that results in empty string, use username as fallback
        if not full_name:
            full_name = u.user.username
            
        data.append({
            "id": u.id,
            "full_name": full_name,
            "email": u.user.email,
            "avatar": str(u.avatar) if u.avatar else None,  # Add avatar field
        })
    
    return JsonResponse(data, safe=False)


# ----------------------------------------
# PROJECTS LISTS / CREATE / EDIT / DELETE
# ----------------------------------------

@login_required
def project_list_default(request):
    
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    token = make_dashboard_token(profile)
    role = profile.role

    # Redirect to /projects/<token>/list/<role>/
    return redirect('project_list', token=token, role=role)

@login_required
@verified_email_required
@role_required('PM', 'OM', 'EG', 'VO')
def project_list_signed_with_role(request, token, role):
    
    verified_profile = verify_user_token(request, token, role)
    if not verified_profile:
        return redirect("unauthorized")

    # Handle file upload
    if request.method == "POST" and "project_id" in request.POST:
        project_id = request.POST.get("project_id")
        project = get_object_or_404(ProjectProfile, id=project_id)

        if role == "PM" and project.project_manager != verified_profile:
            return HttpResponse("Unauthorized upload")
        if role == "OM" and not (project.created_by == verified_profile or project.assigned_to == verified_profile):
            return HttpResponse("Unauthorized upload")

        files = request.FILES.getlist("file")
        for f in files:
            ProjectFile.objects.create(project=project, file=f)

        return redirect("project_list_signed_with_role", token=token, role=role)

    # Fetch projects (exclude archived ones)
    if verified_profile.role in ['EG', 'OM']:
        projects = ProjectProfile.objects.filter(archived=False)

    elif verified_profile.role == 'PM':
        projects = ProjectProfile.objects.filter(
        project_manager=verified_profile,
        archived=False
    )

    elif verified_profile.role == 'VO':
    # Match client by email
        client_email = verified_profile.user.email
        try:
            client = Client.objects.get(email__iexact=client_email)
            projects = ProjectProfile.objects.filter(
            client=client,
            archived=False
            )
        except Client.DoesNotExist:
        # No client matching this email
            projects = ProjectProfile.objects.none()

    context = {
        'token': token,
        'user_uuid': verified_profile.user.id,
        'role': role,
        'projects': projects,
    }
    return render(request, 'project_profiling/project_list.html', context)

@login_required
@verified_email_required
@role_required('OM', 'EG')
def project_costing_dashboard(request, token, role):
    verified_profile = verify_user_token(request, token, role)
    if isinstance(verified_profile, HttpResponse):
        return verified_profile

    projects = ProjectProfile.objects.all()

    projects_with_totals = []
    grand_total_planned = 0
    grand_total_allocated = 0

    for project in projects:
        # Sum of planned amounts
        total_planned = project.budgets.aggregate(total=Sum('planned_amount'))['total'] or 0

        # Sum of all allocations across categories
        total_allocated = sum(
            budget.allocations.aggregate(total=Sum('amount'))['total'] or 0
            for budget in project.budgets.all()
        )

        projects_with_totals.append({
            "project": project,
            "total_planned": total_planned,
            "total_allocated": total_allocated,
            "remaining": total_planned - total_allocated,
        })

        grand_total_planned += total_planned
        grand_total_allocated += total_allocated

    context = {
        "projects_with_totals": projects_with_totals,
        "grand_total_budget": grand_total_planned,
        "grand_total_allocated": grand_total_allocated,
        "token": token,
        "role": role,
    }
    return render(request, "project_profiling/project_costing_dashboard.html", context)


def general_projects_list(request, token, role):
    verified_profile = verify_user_token(request, token, role)
    if not verified_profile:
        return redirect("unauthorized")

    # Toggle: show archived or active projects
    show_archived = request.GET.get('archived') == '1'
    projects = ProjectProfile.objects.filter(
        archived=show_archived,
        project_source="GC"
    )
    return render(request, "project_profiling/general_project_list.html", {
        "projects": projects,
        "token": token,
        "role": role,
        "url_name": resolve(request.path_info).url_name,  
        "project_type": "GC",
        "show_archived": show_archived
    })
    
@role_required('OM', 'EG')
def project_unarchive_signed_with_role(request, token, role, project_type, pk):
    verified_profile = verify_user_token(request, token, role)
    if isinstance(verified_profile, HttpResponse):
        return verified_profile

    # --- Fetch project ---
    if request.user.is_superuser or verified_profile.role in ['EG', 'OM']:
        # Superusers, Engineers, and Operations Managers can unarchive any project
        project = get_object_or_404(ProjectProfile, pk=pk)
    else:  # PM (Project Manager) can only unarchive their own projects
        project = get_object_or_404(
            ProjectProfile.objects.filter(
                Q(created_by=verified_profile) |
                Q(project_manager=verified_profile),
                pk=pk
            )
        )

    # --- Handle unarchive action ---
    if request.method == 'POST':
        project.archived = False
        project.save()
        messages.success(request, f"Project '{project.project_name}' has been unarchived.")

        if project.project_source == "GC":
            return redirect("project_list_general_contractor", token=token, role=role)
        else:
            return redirect("project_list_direct_client", token=token, role=role)

    return render(request, 'project_profiling/project_confirm_unarchive.html', {
        'project': project,
        'token': token,
        'role': role,
        'project_type': project_type,
    })

    
def archived_projects_list(request, token, role, project_type):
    verified_profile = verify_user_token(request, token, role)
    if not verified_profile:
        return redirect("unauthorized")

    projects = ProjectProfile.objects.filter(archived=True, project_source=project_type)
    
    return render(request, "project_profiling/general_project_list.html", {
        "projects": projects,
        "token": token,
        "role": role,
        "project_type": project_type,
        
    })

def direct_projects_list(request, token, role):
    verified_profile = verify_user_token(request, token, role)
    if not verified_profile:
        return redirect("unauthorized")

    # Toggle: show archived or active projects
    show_archived = request.GET.get('archived') == '1'
    projects = ProjectProfile.objects.filter(
        archived=show_archived,
        project_source="DC"
    )
    return render(request, "project_profiling/direct_project_list.html", {
        "projects": projects,
        "token": token,
        "role": role,
        "url_name": resolve(request.path_info).url_name,  
        "project_type": "DC",
        "show_archived": show_archived
    })

def update_project_status(request, project_id):
    if request.method == "POST":
        # Get token and role from the form
        token = request.POST.get("token")
        role = request.POST.get("role")

        # Verify the user
        verified_profile = verify_user_token(request, token, role)
        if isinstance(verified_profile, HttpResponseRedirect):
            return verified_profile
        if verified_profile is None or getattr(verified_profile, 'role', None) is None:
            return redirect('unauthorized')  # safe fallback

        # Fetch the project
        project = get_object_or_404(ProjectProfile, id=project_id)

        # Update status if valid
        new_status = request.POST.get("status")
        if new_status in dict(ProjectProfile.STATUS_CHOICES):
            project.status = new_status
            project.save()
            messages.success(request, f"Status updated to {project.get_status_display()}.")
        else:
            messages.error(request, "Invalid status selected.")

    # Redirect back to the referring page
    return redirect(request.META.get('HTTP_REFERER', 'project_list'))


@login_required
@verified_email_required
def project_view(request, token, role, project_source, pk):
    # Verify the user
    verified_profile = verify_user_token(request, token, role)
    
    if isinstance(verified_profile, HttpResponseRedirect):
        return verified_profile

    if verified_profile is None:
        return redirect('unauthorized') 

    user_role = getattr(verified_profile, 'role', None)
    if user_role is None:
        return redirect('unauthorized')  

    # Use user_role instead of role
    if user_role == "PM":
        project = get_object_or_404(ProjectProfile, pk=pk, project_manager=verified_profile)
    else:
        project = get_object_or_404(ProjectProfile, pk=pk)

    project.timeline_progress = calculate_progress(project.start_date, project.target_completion_date)
    request.session['project_return_url'] = request.get_full_path()
    request.session['task_list_return_url'] = request.get_full_path()
    
    return render(request, 'project_profiling/project_view.html', {
        'project': project,
        'token': token,
        'role': user_role,  # always valid
        'project_source': project_source,
        'current_project_id': pk,
    })


@login_required
@verified_email_required
@role_required("EG")
def review_staging_project_list(request):
    # Only allow logged-in users
    if not request.user.is_authenticated:
        return redirect('login')

    try:
        user_profile = request.user.userprofile  # get linked UserProfile
    except UserProfile.DoesNotExist:
        messages.error(request, "Profile not found.")
        return redirect('unauthorized')

    if user_profile.role != "EG":
        messages.error(request, "You do not have permission to access this page.")
        return redirect('unauthorized')

    # Fetch pending staging projects
    projects = ProjectStaging.objects.filter(status="PL")

    # Ordering logic
    order = request.GET.get("order", "desc")
    if order == "asc":
        projects = sorted(projects, key=lambda p: localtime(p.submitted_at))
    else:
        projects = sorted(projects, key=lambda p: localtime(p.submitted_at), reverse=True)

    return render(request, "project_profiling/staging_project_list.html", {
        "projects": projects,
        "order": order,
        "role": user_profile.role,
    })



@login_required
@verified_email_required
def review_staging_project(request, token, project_id, role):
    staging_id = project_id
    print("=== ENTERED review_staging_project VIEW ===")
    print(f"DEBUG: token = {token}, staging_id = {staging_id}")
    print(f"DEBUG: user = {request.user}, is_superuser = {request.user.is_superuser}")

    # --- Verify token ---
    verified_profile = verify_user_token(request, token)
    print(f"DEBUG: verified_profile = {verified_profile}")
    if not verified_profile:
        print("DEBUG: Token verification failed -> redirect unauthorized")
        return redirect("unauthorized")

    # --- Role check ---
    print(f"DEBUG: verified_profile.role = {getattr(verified_profile, 'role', None)}")
    if not (verified_profile.role == "EG" or request.user.is_superuser):
        print("DEBUG: Role check failed -> redirect unauthorized")
        messages.error(request, "You do not have permission to access this page.")
        return redirect("unauthorized")

    # --- Get staging project ---
    try:
        project = get_object_or_404(ProjectStaging, pk=staging_id)
        print(f"DEBUG: Loaded staging project ID={project.id}")
    except Exception as e:
        print(f"ERROR: Could not load ProjectStaging {staging_id} -> {e}")
        raise

    # --- Normalize project_data ---
    if isinstance(project.project_data, str):
        try:
            project.project_data = json.loads(project.project_data)
            print("DEBUG: Parsed project_data JSON successfully")
        except Exception as e:
            print(f"ERROR: Failed to parse project_data JSON -> {e}")
            project.project_data = {}

    # --- POST: Approve / Reject ---
    if request.method == "POST":
        action = request.POST.get("action")
        print(f"DEBUG: Received POST with action = {action}")

        if action == "approve":
            try:
                # --- Create approved project ---
                new_profile = ProjectProfile.objects.create(
                    project_name=project.project_data.get("project_name", "Untitled Project"),
                    project_type=project.project_data.get("project_type"),
                    project_category=project.project_data.get("project_category"),
                    location=project.project_data.get("location"),
                    client_name=project.project_data.get("client_name"),
                    budget=project.project_data.get("budget", 0),
                    start_date=project.project_data.get("start_date"),
                    end_date=project.project_data.get("end_date"),
                    status="Not Started",
                    source=project.project_source,
                    created_by=project.created_by,
                )
                print(f"DEBUG: Created new ProjectProfile ID={new_profile.id}")

                # --- Handle contract file ---
                contract_path = project.project_data.get("contract_agreement")
                print(f"DEBUG: contract_path = {contract_path}")
                if contract_path and default_storage.exists(contract_path):
                    with default_storage.open(contract_path, "rb") as f:
                        new_profile.contract_agreement.save(os.path.basename(contract_path), File(f), save=True)
                    print("DEBUG: Contract agreement file copied")

                # --- Create notifications ---
                oms = UserProfile.objects.filter(role="OM")
                print(f"DEBUG: Found {oms.count()} OMs")
                if oms.exists():
                    om = random.choice(list(oms))
                    notif = Notification.objects.create(
                        user=om,
                        message=f"A new project '{new_profile.project_name}' has been approved.",
                        link=f"/projects/{new_profile.pk}/details/",
                    )
                    print(f"DEBUG: Notification created ID={notif.id}")

                # --- Delete staging project ---
                project.delete()
                print("DEBUG: Deleted staging project after approval")

                messages.success(request, f"Project '{new_profile.project_name}' has been approved.")
                return redirect("review_staging_project_list")

            except Exception as e:
                print(f"ERROR during approve flow -> {e}")
                messages.error(request, "An error occurred while approving the project.")

        elif action == "reject":
            print("DEBUG: Reject action triggered")
            project.delete()
            print("DEBUG: Deleted staging project after rejection")
            messages.success(request, f"Project '{project.project_data.get('project_name', 'Untitled')}' has been rejected.")
            return redirect("review_staging_project_list")

        else:
            print("DEBUG: Unknown action received")

    # --- Render template ---
    print("DEBUG: Rendering template with project data")
    return render(request, "project_profiling/review_staging_project.html", {"project": project})




SOURCE_LABELS = {
    "GC": "General Contractor",
    "DC": "Direct Client",
}

def serialize_field(value):
    """Convert unserializable types (date, decimal, files, etc.) into JSON-safe format for staging."""
    if value is None:
        return None

    # Dates
    if isinstance(value, (date, datetime)):
        return value.isoformat()

    # Decimals
    if isinstance(value, Decimal):
        return float(value)

    # UserProfile (custom)
    if hasattr(value, 'full_name') and hasattr(value, 'id'):
        return value.id  # store ID, not full_name

    # Client (custom)
    if isinstance(value, Client):
        return {
            "id": value.id,
            "company_name": value.company_name,
            "contact_name": value.contact_name,
        }

    # Choice fields (with .name)
    if hasattr(value, 'name') and not hasattr(value, 'read'):
        return str(value.name)

    # FileField / ImageField (store relative path)
    if hasattr(value, 'url') and hasattr(value, 'name'):
        return value.name  # e.g. "contracts/file.pdf"

    # UploadedFile objects (during POST)
    if hasattr(value, 'read') and hasattr(value, 'name'):
        return value.name

    return value


@login_required
@verified_email_required
@role_required('EG', 'OM')
def project_create(request, token, role, project_type, client_id):
    """Create a new project."""
    verified_profile = verify_user_token(request, token, role)
    if isinstance(verified_profile, HttpResponse):
        return verified_profile

    client = get_object_or_404(Client, id=client_id)
    
    FormClass = ProjectProfileForm
    initial_source = project_type

    # --- Generate Next Project ID ---
    last_project = ProjectProfile.objects.filter(project_source=project_type).aggregate(Max("project_id"))
    last_id = last_project["project_id__max"]
    if last_id:
        try:
            prefix = project_type
            number = int(str(last_id).replace(f"{prefix}-", ""))
            next_id = f"{prefix}-{number+1:03d}"
        except Exception:
            next_id = f"{project_type}-001"
    else:
        next_id = f"{project_type}-001"

    if request.method == "POST":
        form = FormClass(request.POST, request.FILES, pre_selected_client_id=client_id)
        if form.is_valid():
            cleaned_data = {}
            for k, v in form.cleaned_data.items():
                if hasattr(v, "read") and hasattr(v, "name"):
                    file_path = default_storage.save(f"{k}/{v.name}", v)
                    cleaned_data[k] = file_path
                else:
                    cleaned_data[k] = serialize_field(v)

            project_manager_instance = form.cleaned_data.get("project_manager")
            
            # Handle client assignment for pre-selected clients
            # Since client field is removed from form when pre-selected, get it from URL
            client_instance = client  # Use the client from URL parameter
            
            # Handle project type
            project_type_name = cleaned_data.get("project_type")
            project_type_instance = None
            if project_type_name:
                project_type_instance, _ = ProjectType.objects.get_or_create(
                    name=str(project_type_name),
                    defaults={
                        "code": str(project_type_name)[:3].upper(),
                        "created_by": verified_profile,
                    },
                )

            if verified_profile.role == "EG":
                # --- Direct creation for EG ---
                project = ProjectProfile.objects.create(
                    project_id=next_id,
                    created_by=verified_profile,
                    project_source=project_type,
                    project_name=cleaned_data.get("project_name"),
                    description=cleaned_data.get("description"),
                    project_type=project_type_instance,
                    project_category=cleaned_data.get("project_category"),
                    project_manager=project_manager_instance,
                    client=client_instance,  # Use the client from URL parameter
                    site_engineer=cleaned_data.get("site_engineer"),
                    location=cleaned_data.get("location"),
                    gps_coordinates=cleaned_data.get("gps_coordinates"),
                    city_province=cleaned_data.get("city_province"),
                    start_date=cleaned_data.get("start_date"),
                    target_completion_date=cleaned_data.get("target_completion_date"),
                    actual_completion_date=cleaned_data.get("actual_completion_date"),
                    estimated_cost=cleaned_data.get("estimated_cost"),
                    expense=cleaned_data.get("expense"),
                    payment_terms=cleaned_data.get("payment_terms"),
                    subcontractors=cleaned_data.get("subcontractors"),
                    contract_agreement=cleaned_data.get("contract_agreement"),
                    permits_licenses=cleaned_data.get("permits_licenses"),
                    status=cleaned_data.get("status"),
                )

                messages.success(request, f"Project '{project.project_name}' created successfully. (auto-saved)")
                redirect_url = "project_list_general_contractor" if project_type == "GC" else "project_list_direct_client"
                return redirect(redirect_url, token=token, role=role)

            else:
                # --- Save to staging for OM ---
                project = ProjectStaging.objects.create(
                    created_by=verified_profile,
                    project_source=project_type,
                    project_data={
                        **{k: serialize_field(v) for k, v in cleaned_data.items()},
                        "project_manager_id": project_manager_instance.id if project_manager_instance else None,
                        "client_id": client_instance.id if client_instance else None,  # Use client from URL
                    },
                    submitted_at=timezone.now(),
                )

                # --- Notify EGs ---
                eg_users = UserProfile.objects.filter(role="EG")
                for eg_user in eg_users:
                    notif = Notification.objects.create(
                        message=f"{verified_profile.full_name} submitted a new project '{cleaned_data.get('project_name', 'Unnamed')}' for approval.",
                        link=reverse("review_staging_project_list")
                    )
                    NotificationStatus.objects.create(notification=notif, user=eg_user)

                # --- Notify the OM themselves ---
                notif_self = Notification.objects.create(
                    message=f"You submitted the project '{cleaned_data.get('project_name', 'Unnamed')}'. Waiting for approval from Engineers.",
                    link=reverse(
                        "project_list_direct_client" if project_type == "DC" else "project_list_general_contractor",
                        kwargs={"token": token, "role": role}
                    )
                )
                NotificationStatus.objects.create(notification=notif_self, user=verified_profile)

                messages.success(
                    request,
                    f"Project '{cleaned_data.get('project_name', 'Unnamed')}' submitted successfully. Waiting for approval."
                )
                redirect_url = "project_list_general_contractor" if project_type == "GC" else "project_list_direct_client"
                return redirect(redirect_url, token=token, role=role)

        else:
            messages.error(request, "There were errors in your form. Please check and try again.")

    else:
        # Create initial data with auto-fill from client
        initial_data = {
            "project_source": initial_source,
            "project_id": next_id,
            # Don't include client in initial_data since the field is removed from form
        }
            
        # Auto-fill payment terms based on client type
        if client.client_type == 'GC':
            initial_data["payment_terms"] = "Net 30 days"
        elif client.client_type == 'DC':
            initial_data["payment_terms"] = "Net 15 days"
            
        # Auto-select first available project type for this client
        client_project_types = client.project_types.filter(is_active=True)
        if client_project_types.exists():
            initial_data["project_type"] = client_project_types.first()

        form = FormClass(initial=initial_data, pre_selected_client_id=client_id)

    return render(request, "project_profiling/project_form.html", {
        "form": form,
        "project_type": initial_source,
        "token": token,
        "role": role,
        "source_label": SOURCE_LABELS.get(initial_source, "Unknown"),
        "next_id": next_id,
        "pre_selected_client": client,  # Pass client to template
        "auto_fill_mode": True,  # Flag to indicate auto-fill is active
    })



@verified_email_required
@role_required('EG', 'OM')
def project_edit_signed_with_role(request, token, role, pk):
    """Edit an existing approved project."""
    print("DEBUG: project_edit_signed_with_role called")
    print(f"DEBUG: Method={request.method}, Token={token}, Role={role}, ProjectID={pk}")

    verified_profile = verify_user_token(request, token, role)
    if isinstance(verified_profile, HttpResponse):
        print("DEBUG: verify_user_token returned HttpResponse (unauthorized)")
        return verified_profile

    print(f"DEBUG: Verified profile -> {verified_profile}")

    project = get_object_or_404(ProjectProfile, id=pk)
    print(f"DEBUG: Loaded project -> {project}")

    FormClass = ProjectProfileForm

    if request.method == "POST":
        print("DEBUG: Handling POST submission")
        form = FormClass(request.POST, request.FILES, instance=project)
        print(f"DEBUG: Form is valid? {form.is_valid()}")

        if form.is_valid():
            updated_project = form.save(commit=False)

            contract_file = request.FILES.get("contract_agreement")
            if contract_file:
                print(f"DEBUG: New contract file uploaded -> {contract_file.name}")
                updated_project.contract_agreement.save(
                    contract_file.name, contract_file, save=False
                )

            permits_file = request.FILES.get("permits_licenses")
            if permits_file:
                print(f"DEBUG: New permits file uploaded -> {permits_file.name}")
                updated_project.permits_licenses.save(
                    permits_file.name, permits_file, save=False
                )

            updated_project.save()
            print(f"DEBUG: Project updated -> ID={updated_project.id}")
            messages.success(request, f"Project '{project.project_name}' updated successfully.")
            return redirect(
                "project_view",
                token=token,
                role=role,
                project_source=project.project_source,
                pk=project.id,
            )
        else:
            print(f"DEBUG: Form errors -> {form.errors}")
            messages.error(request, "There were errors in your form. Please check and try again.")
    else:
        print("DEBUG: GET request -> rendering edit form")
        form = FormClass(instance=project)

    return render(request, "project_profiling/project_edit.html", {
        "form": form,
        "project_type": project.project_source,
        "token": token,
        "role": role,
        "project": project,
        "source_label": SOURCE_LABELS.get(project.project_source, "Unknown"),
    })


@login_required
@verified_email_required
@role_required('EG', 'OM')
def project_archive_signed_with_role(request, token, role, project_type, pk):
    verified_profile = verify_user_token(request, token, role)
    if isinstance(verified_profile, HttpResponse):
        return verified_profile

    # --- Fetch project ---
    if request.user.is_superuser or verified_profile.role in ['EG', 'OM']:
        # Superusers, Engineers, and Operations Managers can access any project
        project = get_object_or_404(ProjectProfile, pk=pk)
    else:  # PM (Project Manager) can only access their own projects
        project = get_object_or_404(
            ProjectProfile.objects.filter(
                Q(created_by=verified_profile) |
                Q(project_manager=verified_profile),
                pk=pk
            )
        )

    # --- Handle archive action ---
    if request.method == 'POST':
        project.archived = True
        project.save()
        messages.success(request, "Project archived successfully.")

        if project.project_source == "GC":
            return redirect("project_list_general_contractor", token=token, role=role)
        else:
            return redirect("project_list_direct_client", token=token, role=role)

    return render(request, 'project_profiling/project_confirm_archieve.html', {
        'project': project,
        'token': token,
        'role': role,
        'project_type': project_type,
    })

    

# ----------------------------------------------
# PROJECTS BUDGET 
# ----------------------------------------------
@login_required
@verified_email_required
@role_required('EG', 'OM')
def approve_budget(request, project_id):
    project = get_object_or_404(ProjectProfile, id=project_id)
    
    if request.method == 'POST':
        approved_budget = request.POST.get('approved_budget')
        if approved_budget:
            try:
                project.approved_budget = float(approved_budget)
                project.save()
                messages.success(request, f'Budget of ₱{float(approved_budget):,.2f} approved successfully! You can now proceed with budget planning.')
                return redirect('budget_planning', project_id=project_id)
            except ValueError:
                messages.error(request, 'Invalid budget amount entered.')
    
    return redirect('project_detail', project_id=project_id)

@login_required
@verified_email_required
@role_required("EG", "OM")
def budget_planning(request, project_id):
    """
    Main budget planning interface - this is where users define categories
    after budget approval
    """
    project = get_object_or_404(ProjectProfile, id=project_id)
    project_scopes = project.scopes.all()
    
    # Check if budget is approved
    if not project.approved_budget:
        messages.warning(request, "Budget must be approved before planning can begin.")
        return redirect('project_detail', project_id=project_id)
    
    # Get all budget categories for this project - INCLUDE category_other field
    budgets = project.budgets.select_related('scope').all().order_by('scope__name', 'category')
    
    # Get all scopes for this project
    project_scopes = project.scopes.all()
    
    # Calculate totals
    total_planned = budgets.aggregate(total=Sum("planned_amount"))["total"] or 0
    remaining_budget = project.approved_budget - total_planned
    
    # Group budgets by scope for better display
    scopes_data = {}
    for scope in project_scopes:
        scope_budgets = budgets.filter(scope=scope)
        scope_total = scope_budgets.aggregate(total=Sum("planned_amount"))["total"] or 0
        
        scopes_data[scope.name] = {
            'scope': scope,
            'categories': scope_budgets,  # This now includes category_other
            'total': scope_total
        }

    if request.method == "POST":
        form = ProjectBudgetForm(request.POST, project=project)
        if form.is_valid():
            budget = form.save(commit=False)
            budget.project = project
            
            # Handle category_other field
            if budget.category == 'OTH' and form.cleaned_data.get('category_other'):
                budget.category_other = form.cleaned_data['category_other']
            else:
                budget.category_other = None  # Clear if not "Other"
            
            # Check if total would exceed approved budget (but allow it)
            new_total = total_planned + budget.planned_amount
            if new_total > project.approved_budget:
                budget.save()
                messages.warning(request, f"Budget added successfully, but total planned (₱{new_total:,.2f}) exceeds approved budget (₱{project.approved_budget:,.2f}) by ₱{new_total - project.approved_budget:,.2f}")
                return redirect("budget_planning", project_id=project.id)
            else:
                budget.save()
                messages.success(request, f"Budget for {budget.scope.name} - {budget.get_category_display()} added successfully. Remaining budget: ₱{project.approved_budget - new_total:,.2f}")
                return redirect("budget_planning", project_id=project.id)
        else:
            messages.error(request, "There was an error adding the budget. Please check the form.")
    else:
        form = ProjectBudgetForm(project=project)

    return render(request, "budgets/budget_planning.html", {
        "project": project,
        "budgets": budgets,
        "scopes": scopes_data,
        "project_scopes": project_scopes,
        "form": form,
        "total_planned": total_planned,
        "remaining_budget": remaining_budget,
        "budget_utilization": (total_planned / project.approved_budget * 100) if project.approved_budget > 0 else 0,
    })

@login_required
@verified_email_required
@role_required("EG", "OM")
@require_http_methods(["POST"])
def edit_budget_ajax(request, project_id, budget_id):
    """
    AJAX endpoint for editing budget amounts
    """
    try:
        # Get the project and budget
        project = get_object_or_404(ProjectProfile, id=project_id)
        budget = get_object_or_404(ProjectBudget, id=budget_id, project=project)
        
        # Parse JSON data from request
        data = json.loads(request.body)
        planned_amount = data.get('planned_amount')
        
        # Validate the planned amount
        if not planned_amount:
            return JsonResponse({'error': 'Planned amount is required'}, status=400)
        
        try:
            planned_amount = float(planned_amount)
            if planned_amount < 0:
                return JsonResponse({'error': 'Planned amount cannot be negative'}, status=400)
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Invalid planned amount format'}, status=400)
        
        # Check if the change would exceed approved budget
        other_budgets_total = project.budgets.exclude(id=budget_id).aggregate(
            total=Sum("planned_amount")
        )["total"] or 0
        new_total = float(other_budgets_total) + planned_amount
        
        if new_total > float(project.approved_budget):
            return JsonResponse({
                'error': f'This change would exceed the approved budget of ₱{project.approved_budget:,.2f}. '
                        f'Current total would be ₱{new_total:,.2f}'
            }, status=400)
        
        # Store old amount and convert to float
        old_amount = float(budget.planned_amount)
        
        # Update the budget
        budget.planned_amount = planned_amount
        budget.save()
        
        # Return success response - all calculations now use floats
        return JsonResponse({
            'success': True,
            'message': 'Budget updated successfully',
            'old_amount': old_amount,
            'new_amount': planned_amount,
            'change': planned_amount - old_amount,
            'total_planned': new_total,
            'remaining_budget': float(project.approved_budget) - new_total
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'An error occurred: {str(e)}'}, status=500)

@login_required
@verified_email_required
@role_required("EG", "OM")
def delete_budget(request, project_id, budget_id):
    project = get_object_or_404(ProjectProfile, id=project_id)
    budget = get_object_or_404(ProjectBudget, id=budget_id, project=project)

    if request.method == "POST":
        # Check if there are any allocations
        allocation_count = budget.allocations.count()
        if allocation_count > 0:
            messages.warning(request, f"Cannot delete budget with {allocation_count} existing allocations. Remove allocations first.")
            return redirect("budget_planning", project_id=project.id)
        
        scope_category = f"{budget.scope.name} - {budget.get_category_display()}"
        budget.delete()
        messages.success(request, f"Budget entry '{scope_category}' deleted successfully.")
        return redirect("budget_planning", project_id=project.id)

    return render(request, "project_profiling/confirm_delete_budget.html", {
        "project": project,
        "budget": budget,
    })

# ----------------------------------------
# PROJECTS ALLOCATION
# ----------------------------------------    

@login_required
@verified_email_required
@role_required("EG", "OM")
def allocate_fund_to_category(request, project_id, budget_id):
    project = get_object_or_404(ProjectProfile, id=project_id)
    budget = get_object_or_404(ProjectBudget, id=budget_id, project=project)
    
    if request.method == "POST":
        amount_str = request.POST.get("amount")
        note = request.POST.get("note", "")
        
        if not amount_str:
            messages.error(request, "Please enter an allocation amount.")
        else:
            try:
                amount = Decimal(amount_str)
                if amount <= 0:
                    messages.error(request, "Amount must be greater than zero.")
                elif amount > 9999999999999.99: 
                    messages.error(request, "Amount exceeds the maximum allowed (₱9,999,999,999,999.99).")
                else:
                    FundAllocation.objects.create(
                        project_budget=budget,
                        amount=amount,
                        note=note
                    )
                    messages.success(
                        request, 
                        f"₱{amount:,.2f} allocated to {budget.get_category_display()} successfully."
                    )
                    return redirect("allocate_fund_to_category", project_id=project.id, budget_id=budget.id)
            except InvalidOperation:
                messages.error(request, "Invalid amount entered. Please enter a valid number.")

    # Get active allocations (not soft deleted)
    all_allocations = budget.allocations.filter(is_deleted=False).order_by('-date_allocated')
    
    # Get soft-deleted allocations for restore functionality
    deleted_allocations = budget.allocations.filter(is_deleted=True).order_by('-deleted_at')
    
    # Sum of all non-deleted allocations for this category
    total_allocated = all_allocations.aggregate(total=models.Sum("amount"))["total"] or 0
    remaining = budget.planned_amount - total_allocated
    remaining_abs = abs(remaining)

    # Calculate allocation percentage for progress bar
    if budget.planned_amount > 0:
        allocation_percent = min((total_allocated / budget.planned_amount) * 100, 100)
    else:
        allocation_percent = 0

    # Pagination for active allocations
    paginator = Paginator(all_allocations, 10)
    page = request.GET.get('page', 1)

    try:
        allocations = paginator.page(page)
    except PageNotAnInteger:
        allocations = paginator.page(1)
    except EmptyPage:
        allocations = paginator.page(paginator.num_pages)

    return render(request, "budgets/allocate_fund_category.html", {
        "project": project,
        "budget": budget,
        "total_allocated": total_allocated,
        "remaining": remaining,
        "remaining_abs": remaining_abs,      
        "allocation_percent": allocation_percent,
        "allocations": allocations,
        "deleted_allocations": deleted_allocations,
        "total_allocations": all_allocations.count(),
    })

@require_POST 
def soft_delete_allocation(request, project_id, budget_id, allocation_id):
    """Soft delete an allocation"""
    project = get_object_or_404(ProjectProfile, id=project_id)
    budget = get_object_or_404(ProjectBudget, id=budget_id, project=project)
    allocation = get_object_or_404(
        FundAllocation, 
        id=allocation_id, 
        project_budget=budget,
        is_deleted=False
    )
    
    allocation.soft_delete()
    return JsonResponse({
        'status': 'success', 
        'message': 'Allocation soft deleted successfully',
        'allocation_id': allocation_id
    })

@require_POST
def hard_delete_allocation(request, project_id, budget_id, allocation_id):
    """Hard delete an allocation"""
    project = get_object_or_404(ProjectProfile, id=project_id)
    budget = get_object_or_404(ProjectBudget, id=budget_id, project=project)
    allocation = get_object_or_404(
        FundAllocation, 
        id=allocation_id, 
        project_budget=budget
    )
    
    allocation.delete()  # Permanently delete
    return JsonResponse({
        'status': 'success', 
        'message': 'Allocation permanently deleted',
        'allocation_id': allocation_id
    })

@require_POST
def restore_allocation(request, project_id, budget_id, allocation_id):
    """Restore a soft-deleted allocation"""
    project = get_object_or_404(ProjectProfile, id=project_id)
    budget = get_object_or_404(ProjectBudget, id=budget_id, project=project)
    allocation = get_object_or_404(
        FundAllocation, 
        id=allocation_id, 
        project_budget=budget,
        is_deleted=True  # Only restore soft-deleted items
    )
    
    allocation.restore()
    return JsonResponse({
        'status': 'success', 
        'message': 'Allocation restored successfully',
        'allocation_id': allocation_id
    })
    
    
@login_required
@verified_email_required
@role_required("EG", "OM")    
def project_allocate_budget(request, project_id):
    """
    Overview of all budget categories for allocation
    """
    project = get_object_or_404(ProjectProfile, id=project_id)
    budgets = project.budgets.all().order_by('scope__name', 'category')
    
    # Calculate allocation summary for each budget
    budget_summary = []
    for budget in budgets:
        total_allocated = budget.allocations.aggregate(total=models.Sum("amount"))["total"] or 0
        remaining = budget.planned_amount - total_allocated
        allocation_percent = (total_allocated / budget.planned_amount * 100) if budget.planned_amount > 0 else 0
        
        budget_summary.append({
            'budget': budget,
            'total_allocated': total_allocated,
            'remaining': remaining,
            'allocation_percent': allocation_percent,
            'status': 'over' if remaining < 0 else 'complete' if remaining == 0 else 'partial'
        })
    
    return render(request, "budgets/allocate_funds_overview.html", {
        "project": project,
        "budget_summary": budget_summary,
    })
    
@require_http_methods(["POST"])
def delete_scope(request, project_id):
    """
    Delete or soft-delete a project scope
    """
    try:
        project = get_object_or_404(ProjectProfile, id=project_id)
        data = json.loads(request.body)
        scope_id = data.get('scope_id')
        force_delete = data.get('force_delete', False)
        
        scope = get_object_or_404(ProjectScope, id=scope_id, project=project)
        
        # Check if scope has associated tasks
        has_tasks = scope.tasks.exists()  # Assuming you have a related name 'tasks'
        
        if has_tasks and force_delete:
            return JsonResponse({
                'error': 'Cannot permanently delete scope with associated tasks. Use soft delete instead.'
            }, status=400)
        
        if has_tasks:
            # Soft delete - mark as deleted but keep data
            scope.is_deleted = True
            scope.save()
            message = f"Scope '{scope.name}' has been soft deleted (hidden but preserved for existing tasks)."
        else:
            # Hard delete - actually remove the scope and related data
            scope_name = scope.name
            
            # Delete related budget categories first
            scope.budget_categories.all().delete()
            
            # Delete the scope
            scope.delete()
            message = f"Scope '{scope_name}' has been permanently deleted."
        
        return JsonResponse({
            'success': True,
            'message': message
        })
        
    except Exception as e:
        return JsonResponse({
            'error': f'An error occurred: {str(e)}'
        }, status=500)

@require_http_methods(["POST"])
def restore_scope(request, project_id):
    """
    Restore a soft-deleted project scope
    """
    try:
        project = get_object_or_404(ProjectProfile, id=project_id)
        data = json.loads(request.body)
        scope_id = data.get('scope_id')
        
        scope = get_object_or_404(ProjectScope, id=scope_id, project=project)
        
        if not scope.is_deleted:
            return JsonResponse({
                'error': 'Scope is not deleted and cannot be restored.'
            }, status=400)
        
        scope.is_deleted = False
        scope.save()
        
        return JsonResponse({
            'success': True,
            'message': f"Scope '{scope.name}' has been restored successfully."
        })
        
    except Exception as e:
        return JsonResponse({
            'error': f'An error occurred: {str(e)}'
        }, status=500)
        
@require_http_methods(["POST"])
def edit_scope(request, project_id, scope_id):
    """Edit a project scope"""
    try:
        project = get_object_or_404(ProjectProfile, id=project_id)
        scope = get_object_or_404(ProjectScope, id=scope_id, project=project)
        data = json.loads(request.body)
        
        name = data.get('name', '').strip()
        weight = data.get('weight')
        
        if not name:
            return JsonResponse({'error': 'Scope name is required.'}, status=400)
        
        try:
            weight = float(weight)
            if weight <= 0 or weight > 100:
                return JsonResponse({'error': 'Weight must be between 0.01 and 100.'}, status=400)
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Invalid weight value.'}, status=400)
        
        # Check if name already exists for this project (excluding current scope)
        if project.scopes.filter(name=name).exclude(id=scope_id).exists():
            return JsonResponse({'error': f'A scope with name "{name}" already exists.'}, status=400)
        
        scope.name = name
        scope.weight = weight
        scope.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Scope "{name}" updated successfully.'
        })
        
    except Exception as e:
        return JsonResponse({'error': f'An error occurred: {str(e)}'}, status=500)
    
def add_expense(request, project_id):
    if request.method == 'POST':
        try:
            project = get_object_or_404(ProjectProfile, id=project_id)
            category = get_object_or_404(ProjectBudget, id=request.POST['category_id'])
            
            # Check if there's any allocation for this category - use Decimal
            total_allocated = category.allocations.filter(
                is_deleted=False
            ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
            
            if total_allocated == 0:
                return JsonResponse({
                    'error': 'No allocation found for this category. Please allocate funds first.'
                })
            
            # Calculate current spent amount - use Decimal
            total_spent = category.expenses.aggregate(
                total=models.Sum('amount')
            )['total'] or Decimal('0')
            
            expense_amount = Decimal(str(request.POST['amount']))  # Convert to Decimal
            new_total_spent = total_spent + expense_amount
            
            # Warning if over-allocation (but still allow)
            warning = ""
            if new_total_spent > total_allocated:
                overage = new_total_spent - total_allocated
                warning = f" (Over-allocated by ₱{overage:,.2f})"
            
            expense = Expense.objects.create(
                project=project,
                budget_category=category,
                expense_type=request.POST['expense_type'],
                expense_other=request.POST.get('expense_other', ''),
                amount=expense_amount,
                vendor=request.POST.get('vendor', ''),
                receipt_number=request.POST.get('receipt_number', ''),
                expense_date=request.POST['expense_date'],
                description=request.POST.get('description', ''),
                created_by=request.user.userprofile  # Fixed this line
            )
            
            return JsonResponse({
                'success': True,
                'message': f'Expense of ₱{expense.amount:,.2f} added successfully{warning}'
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)})
    
    return JsonResponse({'error': 'Invalid request method'})

def get_category_allocation(request, project_id, category_id):
    print(f"DEBUG: Starting with project_id={project_id}, category_id={category_id}")
    
    try:
        # Step 1: Check if project exists
        project = get_object_or_404(ProjectProfile, id=project_id)
        print(f"DEBUG: Found project: {project.project_name} (id: {project.id})")
        
        # Step 2: Check if category exists (without project filter)
        try:
            category = ProjectBudget.objects.get(id=category_id)
            print(f"DEBUG: Found category: {category.get_category_display()}")
            print(f"DEBUG: Category scope: {category.scope.name}")
            print(f"DEBUG: Category scope project: {category.scope.project.project_name} (id: {category.scope.project.id})")
            print(f"DEBUG: Project match? {category.scope.project.id == project.id}")
            
            # Step 3: Check if the category belongs to the right project
            if category.scope.project.id != project.id:
                return JsonResponse({
                    'error': f'Category belongs to project {category.scope.project.project_name}, not {project.project_name}',
                    'allocated_amount': 0,
                    'spent_amount': 0,
                    'remaining_amount': 0
                })
                
        except ProjectBudget.DoesNotExist:
            return JsonResponse({
                'error': f'No ProjectBudget with id {category_id} exists',
                'allocated_amount': 0,
                'spent_amount': 0,
                'remaining_amount': 0
            })
        
        # Step 4: Get allocations and expenses with proper Decimal handling
        allocations = category.allocations.filter(is_deleted=False)
        print(f"DEBUG: Found {allocations.count()} allocations")
        
        # Use Decimal(0) instead of 0 for proper type consistency
        total_allocated = allocations.aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0')
        
        print(f"DEBUG: Total allocated: {total_allocated} (type: {type(total_allocated)})")
        
        expenses = category.expenses.all()
        print(f"DEBUG: Found {expenses.count()} expenses")
        
        total_spent = expenses.aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0')
        
        print(f"DEBUG: Total spent: {total_spent} (type: {type(total_spent)})")
        
        # Calculate remaining (both are now Decimal types)
        remaining_amount = total_allocated - total_spent
        print(f"DEBUG: Remaining: {remaining_amount} (type: {type(remaining_amount)})")
        
        return JsonResponse({
            'allocated_amount': float(total_allocated),
            'spent_amount': float(total_spent),
            'remaining_amount': float(remaining_amount),
            'category_name': category.get_category_display(),
            'debug': f"Allocations: {allocations.count()}, Expenses: {expenses.count()}"
        })
        
    except Exception as e:
        print(f"DEBUG ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'error': str(e),
            'allocated_amount': 0,
            'spent_amount': 0,
            'remaining_amount': 0
        })