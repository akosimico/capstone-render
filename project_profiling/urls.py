from django.urls import path
from . import views
urlpatterns = [
    # ==============================================
    # DEFAULT & AUTHENTICATION
    # ==============================================
    path('', views.project_list_default, name='project_list_default'),

    # ==============================================
    # PROJECT MANAGEMENT
    # ==============================================
    # Signed project list with role
    path('<str:token>/list/<str:role>/', views.project_list_signed_with_role, name='project_list'),
    
    # General / Direct project lists
    path('general/<str:token>/<str:role>/', views.general_projects_list, name='project_list_general_contractor'),
    path('direct/<str:token>/<str:role>/', views.direct_projects_list, name='project_list_direct_client'),

    # Create project
    path('<str:token>/create/<str:role>/<str:project_type>/<str:client_id>/', views.project_create, name='project_create'),

    # Edit project
    path('<str:token>/edit/<str:role>/<int:pk>/', views.project_edit_signed_with_role, name='project_edit'),
    
    # View project
    path('<str:token>/view/<str:role>/<str:project_source>/<int:pk>/', views.project_view, name='project_view'),
    
    # Update project status
    path('projects/<int:project_id>/update-status/', views.update_project_status, name='update_project_status'),

    # Archive/Unarchive project
    path('<str:token>/delete/<str:role>/<str:project_type>/<int:pk>/', views.project_archive_signed_with_role, name='project_archive'),
    path('<str:token>/unarchive/<str:role>/<str:project_type>/<int:pk>/', views.project_unarchive_signed_with_role, name='project_unarchive'),
    path('archived/<str:token>/<str:role>/<str:project_type>/', views.archived_projects_list, name='archived_projects_list'),

    # ==============================================
# BUDGET WORKFLOW (Simplified - No Token)
# ==============================================

# Step 1: Budget Approval
path('<int:project_id>/approve-budget/', views.approve_budget, name='approve_budget'),

# Step 2: Budget Planning (define scopes and categories)
path('<int:project_id>/budget-planning/', views.budget_planning, name='budget_planning'),

# Budget management
path('<int:project_id>/budgets/<int:budget_id>/edit-ajax/', views.edit_budget_ajax, name='edit_budget_ajax'),
path('<int:project_id>/budgets/<int:budget_id>/delete/', views.delete_budget, name='delete_budget'),

# ==============================================
# FUND ALLOCATION (Simplified - No Token)
# ==============================================
path('<int:project_id>/scopes/delete/', views.delete_scope, name='delete_scope'),
path('<int:project_id>/scopes/restore/', views.restore_scope, name='restore_scope'),
path('<int:project_id>/scopes/<int:scope_id>/edit/', views.edit_scope, name='edit_scope'),
# Fund Allocation Overview
path('<int:project_id>/allocate/', views.project_allocate_budget, name='project_allocate_budget'),


# Allocate funds to specific category
path('<int:project_id>/budgets/<int:budget_id>/allocate/', views.allocate_fund_to_category, name='allocate_fund_to_category'),

# Delete allocation
path('<int:project_id>/budgets/<int:budget_id>/allocations/<int:allocation_id>/soft-delete/', 
         views.soft_delete_allocation, 
         name='soft_delete_allocation'),
         
    path('<int:project_id>/budgets/<int:budget_id>/allocations/<int:allocation_id>/hard-delete/', 
         views.hard_delete_allocation, 
         name='hard_delete_allocation'),
 path('<int:project_id>/budgets/<int:budget_id>/allocations/<int:allocation_id>/restore/', 
         views.restore_allocation, 
         name='restore_allocation'),
 
 path('<int:project_id>/add-expense/', views.add_expense, name='add_expense'),
path('<int:project_id>/categories/<int:category_id>/allocation/', views.get_category_allocation, name='get_category_allocation'),
    # ==============================================
    # DASHBOARD & REPORTING
    # ==============================================
    # Project costing dashboard
    path('<str:token>/costing/<str:role>/', views.project_costing_dashboard, name='project_costing_dashboard'),

    # ==============================================
    # STAGING & REVIEW
    # ==============================================
    # Review staging project list
    path('staging/', views.review_staging_project_list, name='review_staging_project_list'),
    
    # Review a single staging project
    path('staging/<str:token>/<int:project_id>/<str:role>/review/', views.review_staging_project, name='review_staging_project'),

    # ==============================================
    # UTILITIES
    # ==============================================
    # Search project managers
    path('search/project-managers/', views.search_project_managers, name='search_project_managers'),
]