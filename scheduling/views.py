# Standard library
import os
import json
import tempfile
from decimal import Decimal

# Third-party libraries
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from django.core.serializers.json import DjangoJSONEncoder

# Django imports
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden, HttpResponseRedirect
from django.views.decorators.http import require_http_methods
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.db.models import Q
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from notifications.models import Notification, NotificationStatus
from authentication.utils.tokens import parse_dashboard_token, make_dashboard_token

# Authentication utils & decorators
from authentication.views import verify_user_token
from authentication.models import UserProfile
from authentication.utils.tokens import parse_dashboard_token, SignatureExpired, BadSignature
from authentication.utils.decorators import verified_email_required, role_required
from authentication.templatetags.role_tags import has_role
from notifications.utils import send_notification

# Local app imports
from .models import ProjectTask, ProgressFile, ProgressUpdate, ProjectScope

from .forms import ProjectTaskForm, ProgressUpdateForm
from .utils.pdf_reader import extract_project_info
from project_profiling.models import ProjectProfile
from project_profiling.utils import recalc_project_progress
@login_required
def progress_history(request):
    """
    Global progress history with filters.
    """
    updates = ProgressUpdate.objects.select_related(
        "task__project", "reported_by", "reviewed_by"
    ).prefetch_related("attachments").order_by("-created_at")

    # --- Filters ---
    project_id = request.GET.get("project")
    status = request.GET.get("status")
    reporter_id = request.GET.get("reporter")

    if project_id and project_id.isdigit():
        updates = updates.filter(task__project_id=project_id)

    if status in ["P", "A", "R"]:
        updates = updates.filter(status=status)

    if reporter_id and reporter_id.isdigit():
        updates = updates.filter(reported_by_id=reporter_id)

    projects = ProjectProfile.objects.all()
    reporters = UserProfile.objects.all()

    return render(request, "progress/progress_history.html", {
        "updates": updates,
        "projects": projects,
        "reporters": reporters,
        "selected_project": project_id,
        "selected_status": status,
        "selected_reporter": reporter_id,
    })


@login_required
def submit_progress_update(request, token, task_id, role):
    # Verify user token & role
    verified_profile = verify_user_token(request, token, role)
    if isinstance(verified_profile, HttpResponseRedirect):
        return verified_profile

    task = get_object_or_404(ProjectTask, id=task_id)

    if request.method == "POST":
        form = ProgressUpdateForm(request.POST)
        files = request.FILES.getlist("attachments")

        if form.is_valid():
            # Save progress update
            update = form.save(commit=False)
            update.task = task
            update.reported_by = verified_profile
            update.save()

            # Save attachments
            for f in files:
                ProgressFile.objects.create(update=update, file=f)

            # Notify OMs and EGs
            om_eg_users = UserProfile.objects.filter(role__in=["OM", "EG"])
            notif_message = (
                f"{verified_profile.full_name} submitted a progress report "
                f"for Project '{task.project.project_name}' (Task: {task.task_name})"
            )

            if om_eg_users.exists():
                notif = Notification.objects.create(
                    message=notif_message,
                    link=reverse("review_updates")
                )
                for user in om_eg_users:
                    NotificationStatus.objects.create(notification=notif, user=user)

            # Notify the PM themselves
            notif_pm = Notification.objects.create(
                message=f"You submitted a progress report for Project '{task.project.project_name}' (Task: {task.task_name})",
                link=reverse("task_list", kwargs={
                    "project_id": task.project.id,
                    "token": token,
                    "role": role
                })
            )
            NotificationStatus.objects.create(notification=notif_pm, user=verified_profile)

            # Success message for PM
            messages.success(
                request,
                "Your report has been submitted. Operations Managers / Engineers have been notified, and you also have a record in your notifications."
            )

            # Redirect back to task list
            return redirect(reverse("task_list", kwargs={
                "project_id": task.project.id,
                "token": token,
                "role": role
            }))
        else:
            messages.error(request, "Failed to submit report. Please check the form.")

    else:
        form = ProgressUpdateForm()

    return render(request, "progress/submit_update.html", {
        "form": form,
        "task": task,
        "role": role,
        "token": token,
    })


@login_required
def get_pending_count(request):
    if has_role(request.user, "OM") or has_role(request.user, "EG") or request.user.is_superuser:
        pending_count = ProgressUpdate.objects.filter(status="P").count()
    else:
        pending_count = 0
    return JsonResponse({"pending_count": pending_count})


@login_required
@verified_email_required
@role_required("EG", "OM")
def review_updates(request):
    """
    Global view for OM/EG and superusers to see all pending updates.
    """
    pending_updates = ProgressUpdate.objects.filter(status="P")
    context = {
        "updates": pending_updates,
    }
    return render(request, "progress/review_updates.html", context)

@login_required
@verified_email_required
@role_required("EG", "OM")
def approve_update(request, update_id):
    update = get_object_or_404(ProgressUpdate, id=update_id)

    update.status = "A"
    update.reviewed_by = request.user.userprofile
    update.reviewed_at = timezone.now()
    update.save(update_fields=["status", "reviewed_by", "reviewed_at"])

    task = update.task
    approved_updates = task.updates.filter(status="A")
    total_progress = sum(u.progress_percent for u in approved_updates)
    task.progress = min(total_progress, 100)

    if task.progress >= 100:
        task.is_completed = True
        task.status = "CP"
    elif task.progress > 0:
        task.is_completed = False
        task.status = "OG"
    else:
        task.is_completed = False
        task.status = "PL"

    task.save(update_fields=["progress", "is_completed", "status"])

    task.project.update_progress_from_tasks()

    messages.success(request, f"Progress update for '{task.task_name}' approved successfully.")
    return redirect("review_updates")

@login_required
@verified_email_required
@role_required("EG", "OM")
def reject_update(request, update_id):
    update = get_object_or_404(ProgressUpdate, id=update_id)
    update.status = "R"
    update.reviewed_by = request.user.userprofile
    update.reviewed_at = timezone.now()
    update.save()
    messages.warning(request, f"Progress update for '{update.task.task_name}' has been rejected.")

    return redirect("review_updates")


@login_required
@verified_email_required
@role_required("PM", "OM", "EG")
def task_list(request, project_id, token, role):
    verified_profile = verify_user_token(request, token, role)
    if isinstance(verified_profile, HttpResponse):  
        return verified_profile

    project = get_object_or_404(ProjectProfile, id=project_id)
    
    show_archived = request.GET.get("show") == "archived"
    
    if role == "PM":
        tasks = project.tasks.filter(assigned_to=request.user.userprofile)
    else:
        tasks = project.tasks.all()
    
    # ✅ Only archived OR only active
    if show_archived:
        tasks = tasks.filter(is_archived=True)
    else:
        tasks = tasks.filter(is_archived=False)

    # Prefetch the latest approved progress for each task
    for task in tasks:
        latest_update = task.updates.filter(status='A').order_by('-created_at').first()
        task.latest_progress = latest_update.progress_percent if latest_update else 0
        task.is_completed = task.latest_progress >= 100  # mark as completed if 100%

    return_url = request.GET.get('return_url') or f"scheduling/{token}/view/{role}/client/{project_id}/"

     
    return render(request, "scheduling/task_list.html", {
        "project": project,
        "tasks": tasks,
        "token": token,
        "role": role,
        "show_archived": show_archived,
        "return_url": return_url,
    })



def parse_excel(file):
    df = pd.read_excel(file)
    tasks = []
    for _, row in df.iterrows():
        tasks.append({
            "task_name": row.get("Task"),
            "start_date": row.get("Start"),
            "end_date": row.get("End"),
            "duration_days": row.get("Days"),
            "manhours": row.get("MH"),
            "scope": row.get("Scope"),
        })
    return tasks

@require_http_methods(["POST"])
def create_scope_ajax(request, project_id):
    try:
        project = get_object_or_404(ProjectProfile, id=project_id)
        
        # Parse JSON data
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        weight = float(data.get('weight', 0))
        
        # Validation
        if not name:
            return JsonResponse({'error': 'Scope name is required'}, status=400)
        
        if weight <= 0 or weight > 100:
            return JsonResponse({'error': 'Weight must be between 0 and 100'}, status=400)
        
        # Check if total weight would exceed 100%
        existing_total = sum(float(scope.weight) for scope in project.scopes.all())
        if existing_total + weight > 100:
            remaining = 100 - existing_total
            return JsonResponse({
                'error': f'Total weight would exceed 100%. Maximum available: {remaining:.2f}%'
            }, status=400)
        
        # Create the scope
        scope = ProjectScope.objects.create(
            project=project,
            name=name,
            weight=weight
        )
        
        return JsonResponse({
            'id': scope.id,
            'name': scope.name,
            'weight': str(scope.weight)
        })
        
    except ValueError:
        return JsonResponse({'error': 'Invalid weight value'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
@login_required
@verified_email_required
@role_required("EG", "OM")
def task_create(request, project_id, token, role):
    verified_profile = verify_user_token(request, token, role)
    if isinstance(verified_profile, HttpResponse):
        return verified_profile

    project = get_object_or_404(ProjectProfile, id=project_id)
    
    # Filter scopes to only show those that have budget planning data
    # This ensures only scopes created during budget planning are available
    budget_scopes = ProjectScope.objects.filter(
        project=project,
        is_deleted=False,
        budget_categories__isnull=False  # Only scopes with budget entries
    ).distinct().order_by('name')
    
    # Calculate remaining weights for budget planning scopes only
    scope_remaining = {}
    for scope in budget_scopes:
        total_weight = sum(t.weight for t in scope.tasks.all())
        scope_remaining[scope.id] = max(0, scope.weight - total_weight)

    form = ProjectTaskForm(project=project)  # Pass project to form

    if request.method == "POST":
        form = ProjectTaskForm(request.POST, project=project)
        if form.is_valid():
            task = form.save(commit=False)
            task.project = project
            task.save()
            form.save_m2m()
            messages.success(request, f"Task '{task.task_name}' was successfully created.")
            return redirect("task_list", project.id, token, role)
        else:
            messages.error(request, "Failed to create task. Please check the form and try again.")

    return render(request, "scheduling/task_form.html", {
        "form": form,
        "project": project,
        "budget_scopes": budget_scopes,  # Pass filtered scopes
        "token": token,
        "role": role,
        "scope_remaining_json": json.dumps(scope_remaining, cls=DjangoJSONEncoder),
    })

# @login_required
# @verified_email_required
# @role_required("EG", "OM")
# def save_imported_tasks(request, project_id, token, role):
#     verified_profile = verify_user_token(request, token, role)
#     if isinstance(verified_profile, HttpResponse):
#         return verified_profile

#     project = get_object_or_404(ProjectProfile, id=project_id)

#     if request.method == "POST":
#         task_count = int(request.POST.get("task_count", 0))

#         global_scope = request.POST.get("global_scope") or None
#         assigned_to_id = request.POST.get("global_assigned_to") or None
#         assigned_user_global = (
#             UserProfile.objects.filter(id=assigned_to_id).first()
#             if assigned_to_id else None
#         )

#         task_objs = []
#         for i in range(task_count):
#             task_name = request.POST.get(f"task_name_{i}")
#             if not task_name: 
#                 continue

#             start_date = parse_date(request.POST.get(f"start_date_{i}"))
#             end_date = parse_date(request.POST.get(f"end_date_{i}"))
#             duration = request.POST.get(f"duration_days_{i}")
#             manhours = request.POST.get(f"manhours_{i}")

#             # Weight
#             weight_str = request.POST.get(f"weight_{i}", "").strip()
#             weight = float(weight_str) if weight_str else 0.0

#             # Scope (per-task overrides global)
#             scope_i = request.POST.get(f"scope_{i}") or None
#             scope = scope_i if scope_i else global_scope

#             # Assigned to (per-task overrides global)
#             assigned_to_id_i = request.POST.get(f"assigned_to_{i}") or None
#             assigned_user = (
#                 UserProfile.objects.filter(id=assigned_to_id_i).first()
#                 if assigned_to_id_i else assigned_user_global
#             )

#             task_objs.append(ProjectTask(
#                 project=project,
#                 task_name=task_name,
#                 start_date=start_date,
#                 end_date=end_date,
#                 duration_days=duration,
#                 manhours=manhours,
#                 weight=weight,
#                 scope=scope,
#                 assigned_to=assigned_user,
#             ))

#         if task_objs:
#             ProjectTask.objects.bulk_create(task_objs)
#         else:
#             print("No tasks to save.")  # DEBUG

#         return redirect("task_list", project.id, token, role)

    # return redirect("task_create", project.id, token, role)


@login_required
@verified_email_required
@role_required("EG", "OM")
def task_update(request, project_id, token, role, task_id):
    verified_profile = verify_user_token(request, token, role)
    if isinstance(verified_profile, HttpResponse):
        return verified_profile

    project = get_object_or_404(ProjectProfile, id=project_id)
    task = get_object_or_404(ProjectTask, id=task_id, project=project)
    
    # Filter scopes to only show those that have budget planning data
    # This ensures only scopes created during budget planning are available
    budget_scopes = ProjectScope.objects.filter(
        project=project,
        is_deleted=False,
        budget_categories__isnull=False  # Only scopes with budget entries
    ).distinct().order_by('name')
    
    # Calculate remaining weights for budget planning scopes only
    scope_remaining = {}
    for scope in budget_scopes:
        # Exclude current task's weight when calculating remaining
        total_weight = sum(t.weight for t in scope.tasks.exclude(id=task.id))
        scope_remaining[scope.id] = max(0, scope.weight - total_weight)

    if request.method == "POST":
        form = ProjectTaskForm(request.POST, instance=task, project=project)
        assigned_to_id = request.POST.get("assigned_to")

        if form.is_valid():
            try:
                task = form.save(commit=False)
                if assigned_to_id:
                    assigned_user = UserProfile.objects.filter(id=assigned_to_id).first()
                    task.assigned_to = assigned_user
                task.save()
                form.save_m2m()
                messages.success(request, f"Task '{task.task_name}' updated successfully!")
                return redirect("task_list", project.id, token, role)
            except Exception as e:
                messages.error(request, f"Error updating task: {str(e)}")
        else:
            messages.error(request, "Invalid form data. Please correct the errors below.")
    else:
        form = ProjectTaskForm(instance=task, project=project)

    context = {
        "form": form,
        "project": project,
        "task": task,
        "token": token,
        "role": role,
        "budget_scopes": budget_scopes,  # Pass filtered scopes
        "project_managers": UserProfile.objects.filter(role="PM"),
        "scope_remaining_json": json.dumps(scope_remaining, cls=DjangoJSONEncoder),
    }
    return render(request, "scheduling/task_edit.html", context)


@login_required
@verified_email_required
@role_required("EG", "OM")
def task_bulk_archive(request, project_id, token, role):
    verified_profile = verify_user_token(request, token, role)
    if isinstance(verified_profile, HttpResponse):
        return verified_profile

    project = get_object_or_404(ProjectProfile, id=project_id)

    if request.method == "POST":
        task_ids = request.POST.getlist("task_ids")
        if task_ids:
            updated_count = ProjectTask.objects.filter(
                id__in=task_ids, project=project
            ).update(is_archived=True)
            messages.success(request, f"Archived {updated_count} task(s).")
        else:
            messages.warning(request, "No tasks were selected.")

    return redirect("task_list", project.id, token, role)

def task_bulk_unarchive(request, project_id, token, role):
    if request.method == "POST":
        task_ids = request.POST.getlist("task_ids")
        ProjectTask.objects.filter(id__in=task_ids).update(is_archived=False)
        messages.success(request, "Selected tasks unarchived successfully.")
    return redirect("task_list", project_id=project_id, token=token, role=role)


@login_required
@verified_email_required
@role_required("EG", "OM")
def task_archive(request, project_id, token, role, task_id):
    verified_profile = verify_user_token(request, token, role)
    if isinstance(verified_profile, HttpResponse):
        return verified_profile

    project = get_object_or_404(ProjectProfile, id=project_id)
    task = get_object_or_404(ProjectTask, id=task_id, project=project)

    if request.method == "POST":
        try:
            task_name = task.task_name
            task.is_archived = True
            task.save()
            messages.success(request, f"Task '{task_name}' has been archived successfully.")
        except Exception as e:
            messages.error(request, f"Error archiving task: {str(e)}")
        return redirect("task_list", project.id, token, role)

    return render(request, "scheduling/task_confirm_archive.html", {
        "task": task,
        "project": project,
        "token": token,
        "role": role,
    })

@login_required
@verified_email_required
@role_required("OM", "EG")
def task_unarchive(request, project_id, token, role, task_id):
    verified_profile = verify_user_token(request, token, role)
    if isinstance(verified_profile, HttpResponse):  
        return verified_profile

    project = get_object_or_404(ProjectProfile, id=project_id)
    task = get_object_or_404(ProjectTask, id=task_id, project=project)

    task.is_archived = False
    task.save()

    messages.success(request, f"Task '{task.name}' has been unarchived.")
    return redirect("task_list", project_id=project.id, token=token, role=role)
