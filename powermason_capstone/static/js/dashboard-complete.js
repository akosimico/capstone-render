// dashboard-complete.js - Enhanced Dashboard JavaScript with Real-time Task Updates

// ====================================================================
// UTILITY FUNCTIONS
// ====================================================================

function showLoadingOverlay() {
    const overlay = document.getElementById("loadingOverlay");
    if (overlay) {
        overlay.classList.remove("hidden");
    }
}

function hideLoadingOverlay() {
    const overlay = document.getElementById("loadingOverlay");
    if (overlay) {
        overlay.classList.add("hidden");
    }
}

function animateElements() {
    const animatedElements = document.querySelectorAll('.animate-fade-in, .animate-slide-up');
    animatedElements.forEach((el, index) => {
        setTimeout(() => {
            el.style.opacity = '1';
            el.style.transform = 'translateY(0)';
        }, index * 100);
    });
}

function showSuccessMessage(message) {
    showToast(message, 'success');
}

function showErrorMessage(message) {
    showToast(message, 'error');
}

function showInfoMessage(message) {
    showToast(message, 'info');
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    const colors = {
        success: 'bg-green-500',
        error: 'bg-red-500',
        info: 'bg-blue-500',
        warning: 'bg-yellow-500'
    };
    
    const icons = {
        success: 'fas fa-check-circle',
        error: 'fas fa-exclamation-circle',
        info: 'fas fa-info-circle',
        warning: 'fas fa-exclamation-triangle'
    };
    
    toast.className = `fixed top-4 right-4 ${colors[type]} text-white px-4 py-3 rounded-lg shadow-lg z-50 transition-all duration-300 transform translate-x-full opacity-0`;
    toast.innerHTML = `
        <div class="flex items-center space-x-2">
            <i class="${icons[type]}"></i>
            <span>${message}</span>
            <button onclick="this.parentElement.parentElement.remove()" class="ml-2 text-white hover:text-gray-200">
                <i class="fas fa-times text-sm"></i>
            </button>
        </div>
    `;
    
    document.body.appendChild(toast);
    
    requestAnimationFrame(() => {
        toast.style.transform = 'translateX(0)';
        toast.style.opacity = '1';
    });
    
    setTimeout(() => {
        toast.style.transform = 'translateX(100%)';
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, type === 'error' ? 6000 : 3000);
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function handleResize() {
    if (window.progressChart) {
        window.progressChart.resize();
    }
    if (window.budgetChart) {
        window.budgetChart.resize();
    }
    if (window.dashboardCalendar) {
        window.dashboardCalendar.updateSize();
    }
}

let resizeTimeout;
window.addEventListener('resize', () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(handleResize, 250);
});

window.addEventListener('error', function(e) {
    console.error('Dashboard error:', e.error);
    showErrorMessage('Something went wrong. Please refresh if issues persist.');
});

window.addEventListener('load', () => {
    if (window.performance) {
        const perfData = window.performance.timing;
        const loadTime = perfData.loadEventEnd - perfData.navigationStart;
        console.log(`Dashboard loaded in ${loadTime}ms`);
    }
});

// ====================================================================
// MAIN DASHBOARD INITIALIZATION
// ====================================================================

document.addEventListener("DOMContentLoaded", () => {
    console.log("Dashboard loading...");
    
    // Load project JSON data
    const dataEl = document.getElementById("projects-data");
    if (!dataEl) {
        console.error("No projects-data element found");
        showErrorMessage("Dashboard data not found. Please refresh the page.");
        return;
    }
    
    let projects = [];
    try {
        projects = JSON.parse(dataEl.textContent);
        console.log(`Loaded ${projects.length} projects`);
    } catch (err) {
        console.error("Failed to parse projects JSON:", err);
        showErrorMessage("Failed to load dashboard data. Please refresh the page.");
        return;
    }

    // Store projects globally for other modules
    window.dashboardData = { 
        projects,
        timestamp: Date.now()
    };

    // Initialize all components
    initializeDashboard();
});

function initializeDashboard() {
    try {
        // Extract and store token and role from URL path
        const pathParts = window.location.pathname.split('/');
        window.dashboardToken = pathParts[2] || ""; // Token is at index 2
        window.dashboardRole = pathParts[3] || "";   // Role is at index 3
        
        // Debug logging
        console.log('URL Path:', window.location.pathname);
        console.log('Path Parts:', pathParts);
        console.log('Stored Token:', window.dashboardToken);
        console.log('Stored Role:', window.dashboardRole);
        
        // Validate token and role are available
        if (!window.dashboardToken || !window.dashboardRole) {
            console.error('Token or role missing from URL');
            showErrorMessage('Authentication data missing. Please refresh the page.');
            return;
        }
        
        // Initialize components in order
        initializeCharts();
        initializeCalendar(); 
        initializeInteractions();
        initializeModals();
        
        // Start auto-refresh after everything is loaded
        setTimeout(() => {
            initializeAutoRefresh();
        }, 1500);
        
        // Add loading states and animations
        hideLoadingOverlay();
        animateElements();
        
        // Show success message
        showSuccessMessage("Dashboard loaded successfully");
        
        console.log("Dashboard initialized successfully");
        
    } catch (error) {
        console.error("Dashboard initialization failed:", error);
        showErrorMessage("Dashboard initialization failed. Please refresh the page.");
    }
}

// ====================================================================
// CHARTS FUNCTIONALITY
// ====================================================================

function initializeCharts() {
    if (!window.dashboardData?.projects) {
        console.error("No projects data available for charts");
        return;
    }

    const { projects } = window.dashboardData;
    
    initializeProgressChart(projects);
    initializeBudgetChart(projects);
}

// Progress Chart (Horizontal Bar)
function initializeProgressChart(projects) {
    const chartEl = document.getElementById("progressChart");
    if (!chartEl) return;

    const ctx = chartEl.getContext("2d");
    
    const config = {
        type: "bar",
        data: {
            labels: projects.map(p => p.name || p.project_name || 'Unnamed Project'),
            datasets: [
                {
                    label: "Estimate Progress",
                    data: projects.map(p => p.planned_progress || 0),
                    backgroundColor: "rgba(249, 115, 22, 0.8)",
                    borderColor: "rgba(249, 115, 22, 1)",
                    borderWidth: 2,
                    borderRadius: 8,
                    borderSkipped: false,
                },
                {
                    label: "Actual Progress",
                    data: projects.map(p => p.actual_progress || 0),
                    backgroundColor: "rgba(139, 92, 246, 0.8)",
                    borderColor: "rgba(139, 92, 246, 1)",
                    borderWidth: 2,
                    borderRadius: 8,
                    borderSkipped: false,
                }
            ]
        },
        options: {
            indexAxis: "y",
            responsive: true,
            maintainAspectRatio: false,
            layout: { padding: { top: 10, bottom: 10 } },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: 'white',
                    bodyColor: 'white',
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    borderWidth: 1,
                    cornerRadius: 12,
                    displayColors: true,
                    callbacks: {
                        label: function(context) {
                            return `${context.dataset.label}: ${context.parsed.x}%`;
                        },
                       afterLabel: function(context) {
    const chartData = context.chart.data;

    // dataset[0] = Planned Progress, dataset[1] = Actual Progress
    const planned = chartData.datasets[0].data[context.dataIndex] || 0;
    const actual = chartData.datasets[1].data[context.dataIndex] || 0;

    const variance = actual - planned;
    const status = variance >= 0 ? 'ahead' : 'behind';

    return variance !== 0
        ? `${Math.abs(variance)}% ${status} progress`
        : 'On track';
}

                    }
                }
            },
            scales: {
                x: {
                    beginAtZero: true,
                    max: 100,
                    grid: { color: 'rgba(0, 0, 0, 0.05)', drawBorder: false },
                    ticks: {
                        callback: value => value + "%",
                        font: { size: 12, weight: 'bold' },
                        color: '#6b7280'
                    }
                },
                y: {
                    grid: { display: false },
                    ticks: {
                        font: { size: 13, weight: 'bold' },
                        color: '#374151',
                        maxRotation: 0
                    }
                }
            },
            animation: { duration: 2000, easing: 'easeInOutQuart' },
            interaction: { intersect: false, mode: 'index' }
        }
    };

    window.progressChart = new Chart(ctx, config);
    console.log("Progress chart initialized");
}

// Budget Chart (Line Chart)
function initializeBudgetChart(projects) {
    const budgetChartEl = document.getElementById("budgetChart");
    if (!budgetChartEl) return;

    const ctx = budgetChartEl.getContext("2d");

    // Map project budget data with enhanced structure
    const estimatedData = projects.map(p => Number(p.budget_total?.estimated) || 0);
    const approvedData  = projects.map(p => Number(p.budget_total?.approved) || 0);
    const plannedData   = projects.map(p => Number(p.budget_total?.planned) || 0);
    const allocatedData = projects.map(p => Number(p.budget_total?.allocated) || 0);
    const spentData     = projects.map(p => Number(p.budget_total?.spent) || 0);

    const labels = projects.map(p => p.name || p.project_name || 'Unnamed Project');

    const config = {
        type: "line",
        data: {
            labels,
            datasets: [
                {
                    label: "Estimated Cost",
                    data: estimatedData,
                    borderColor: "rgba(255, 99, 132, 1)",
                    backgroundColor: "rgba(255, 99, 132, 0.1)",
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: "rgba(255, 99, 132, 1)",
                    pointBorderColor: "#ffffff",
                    pointBorderWidth: 3,
                    pointRadius: 6,
                    pointHoverRadius: 8
                },
                {
                    label: "Approved Budget",
                    data: approvedData,
                    borderColor: "rgba(59, 130, 246, 1)",
                    backgroundColor: "rgba(59, 130, 246, 0.1)",
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: "rgba(59, 130, 246, 1)",
                    pointBorderColor: "#ffffff",
                    pointBorderWidth: 3,
                    pointRadius: 6,
                    pointHoverRadius: 8
                },
                {
                    label: "Planned Budget",
                    data: plannedData,
                    borderColor: "rgba(249, 115, 22, 1)",
                    backgroundColor: "rgba(249, 115, 22, 0.1)",
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: "rgba(249, 115, 22, 1)",
                    pointBorderColor: "#ffffff",
                    pointBorderWidth: 3,
                    pointRadius: 6,
                    pointHoverRadius: 8
                },
                {
                    label: "Allocated Budget",
                    data: allocatedData,
                    borderColor: "rgba(139, 92, 246, 1)",
                    backgroundColor: "rgba(139, 92, 246, 0.1)",
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: "rgba(139, 92, 246, 1)",
                    pointBorderColor: "#ffffff",
                    pointBorderWidth: 3,
                    pointRadius: 6,
                    pointHoverRadius: 8
                },
                {
                    label: "Spent Budget",
                    data: spentData,
                    borderColor: "rgba(34, 197, 94, 1)",
                    backgroundColor: "rgba(34, 197, 94, 0.1)",
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: "rgba(34, 197, 94, 1)",
                    pointBorderColor: "#ffffff",
                    pointBorderWidth: 3,
                    pointRadius: 6,
                    pointHoverRadius: 8
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            layout: { padding: { top: 20, bottom: 10 } },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: 'white',
                    bodyColor: 'white',
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    borderWidth: 1,
                    cornerRadius: 12,
                    displayColors: true,
                    callbacks: {
                        label: function(context) {
                            return `${context.dataset.label}: ₱${context.parsed.y.toLocaleString()}`;
                        },
                        afterBody: function(tooltipItems) {
                            if (tooltipItems.length > 0) {
                                const dataIndex = tooltipItems[0].dataIndex;
                                const remaining = allocatedData[dataIndex] - spentData[dataIndex];
                                const utilization = allocatedData[dataIndex] > 0
                                    ? ((spentData[dataIndex] / allocatedData[dataIndex]) * 100).toFixed(1)
                                    : 0;

                                return [
                                    `Remaining: ₱${remaining.toLocaleString()}`,
                                    `Utilization: ${utilization}%`
                                ];
                            }
                            return [];
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(0, 0, 0, 0.05)', drawBorder: false },
                    ticks: { font: { size: 12, weight: 'bold' }, color: '#6b7280', maxRotation: 45 }
                },
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(0, 0, 0, 0.05)', drawBorder: false },
                    ticks: { callback: value => "₱" + value.toLocaleString(), font: { size: 12, weight: 'bold' }, color: '#6b7280' }
                }
            },
            animation: { duration: 2000, easing: 'easeInOutQuart' },
            interaction: { intersect: false, mode: 'index' }
        }
    };

    if (window.budgetChart && typeof window.budgetChart.update === "function") {
        window.budgetChart.data = config.data;
        window.budgetChart.options = config.options;
        window.budgetChart.update("active");
        console.log("Budget chart updated");
    } else {
        window.budgetChart = new Chart(ctx, config);
        console.log("Budget chart initialized");
    }
}

// ====================================================================
// ENHANCED CALENDAR FUNCTIONALITY  
// ====================================================================

function generateProjectColors(projects) {
    const projectColors = {};
    const palette = [
        "#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6",
        "#EC4899", "#14B8A6", "#F97316", "#84CC16", "#06B6D4",
        "#6366F1", "#8B5A2B"
    ];

    let colorIndex = 0;
    projects.forEach(project => {
        const projectName = project.project_name || project.name || "Unknown Project";
        if (!projectColors[projectName]) {
            projectColors[projectName] = palette[colorIndex % palette.length];
            colorIndex++;
        }
    });

    return projectColors;
}

function initializeCalendar() {
    const calendarEl = document.getElementById("taskCalendar");
    if (!calendarEl || !window.dashboardData?.projects) return;

    const { projects } = window.dashboardData;
    const projectColors = generateProjectColors(projects);
    const events = generateCalendarEvents(projects, projectColors);

    window.dashboardCalendar = new FullCalendar.Calendar(calendarEl, {
        initialView: "dayGridMonth",
        height: 'auto',
        contentHeight: 'auto',
        expandRows: true,

        headerToolbar: {
            left: "prev,next today",
            center: "title",
            right: "dayGridMonth,dayGridWeek,dayGridDay,listWeek"
        },

        dayMaxEvents: 3,
        eventDisplay: "block",
        eventTextColor: "#fff",

        events: events,

        // Enhanced Event Styling with Status Indicators
        eventDidMount: info => {
            const event = info.event;
            const props = event.extendedProps;
            
            // Base styling
            info.el.style.borderRadius = "6px";
            info.el.style.padding = "2px 6px";
            info.el.style.fontSize = "0.85rem";
            info.el.style.fontWeight = "500";
            info.el.style.boxShadow = "0 1px 2px rgba(0,0,0,0.1)";
            info.el.style.cursor = "pointer";
            info.el.style.position = "relative";

            // Status indicator
            const statusDot = document.createElement("div");
            statusDot.style.position = "absolute";
            statusDot.style.top = "2px";
            statusDot.style.right = "2px";
            statusDot.style.width = "6px";
            statusDot.style.height = "6px";
            statusDot.style.borderRadius = "50%";
            statusDot.style.border = "1px solid rgba(255,255,255,0.8)";
            
            // Status colors
            const statusColors = {
                'completed': '#10B981',
                'CP': '#10B981',
                'in_progress': '#F59E0B',
                'IP': '#F59E0B',
                'pending': '#6B7280',
                'PL': '#6B7280',
                'overdue': '#EF4444'
            };
            
            if (props.is_overdue) {
                statusDot.style.backgroundColor = statusColors.overdue;
                info.el.style.opacity = "0.8";
                info.el.style.borderLeft = "3px solid #EF4444";
            } else {
                statusDot.style.backgroundColor = statusColors[props.status] || statusColors.pending;
            }
            
            info.el.appendChild(statusDot);

            // Progress bar
            const progress = props.progress || 0;
            if (progress > 0) {
                const progressBar = document.createElement("div");
                progressBar.style.position = "absolute";
                progressBar.style.bottom = "0";
                progressBar.style.left = "0";
                progressBar.style.height = "2px";
                progressBar.style.backgroundColor = "rgba(255,255,255,0.8)";
                progressBar.style.width = `${progress}%`;
                progressBar.style.borderRadius = "0 0 6px 6px";
                info.el.appendChild(progressBar);
            }

            // Priority indicator
            if (props.priority === 'high') {
                info.el.style.borderTop = "2px solid #EF4444";
            } else if (props.priority === 'low') {
                info.el.style.borderTop = "2px solid #10B981";
            }

            // Enhanced tooltip
            const assignee = props.assignee ? ` | Assigned to: ${props.assignee.name}` : '';
            const daysRemaining = props.days_remaining !== null ? 
                (props.days_remaining < 0 ? ` | ${Math.abs(props.days_remaining)} days overdue` : 
                 props.days_remaining === 0 ? ' | Due today' : 
                 ` | ${props.days_remaining} days remaining`) : '';
            
            info.el.title = `${event.title} | ${props.project} | Progress: ${progress}%${assignee}${daysRemaining}`;
        },

        eventClick: info => showTaskModal(info.event),

        // Date click to show tasks for that day
        dateClick: info => showDayTasks(info.date, info.dayEl),

        locale: 'en',
        firstDay: 1,
        eventTimeFormat: { hour: 'numeric', minute: '2-digit', omitZeroMinute: true },

        // Loading state
        loading: function(isLoading) {
            const loadingEl = document.getElementById('calendar-loading');
            if (loadingEl) {
                loadingEl.style.display = isLoading ? 'block' : 'none';
            }
        }
    });

    window.dashboardCalendar.render();

    // Make responsive
    window.addEventListener('resize', () => {
        if (window.dashboardCalendar) window.dashboardCalendar.updateSize();
    });

    console.log("Enhanced calendar initialized");
}

function generateCalendarEvents(projects, projectColors) {
    const events = [];
    
    projects.forEach(project => {
        const projectName = project.project_name || project.name || "Unknown Project";
        const projectColor = projectColors[projectName] || "#6B7280";
        
        if (project.tasks && Array.isArray(project.tasks)) {
            project.tasks.forEach(task => {
                if (!task.start) return;
                
                const event = {
                    id: `task_${task.id}`,
                    title: task.title || "Untitled Task",
                    start: task.start,
                    end: task.end || null,
                    allDay: true,
                    color: projectColor,
                    borderColor: projectColor,
                    textColor: "#FFFFFF",
                    extendedProps: {
                        progress: task.progress || 0,
                        project: projectName,
                        projectId: project.id,
                        taskId: task.id,
                        description: task.description || "",
                        priority: task.priority || "normal",
                        status: task.status || "pending",
                        is_overdue: task.is_overdue || false,
                        days_remaining: task.days_remaining,
                        assignee: task.assignee || null,
                        weight: task.weight || 0,
                        manhours: task.manhours || 0,
                        scope: task.scope || null,
                        updated_at: task.updated_at
                    }
                };
                
                events.push(event);
            });
        }
    });
    
    return events;
}

function showDayTasks(date, dayEl) {
    if (!window.dashboardCalendar) return;
    
    const tasks = window.dashboardCalendar.getEvents().filter(event => {
        const eventDate = new Date(event.start);
        return eventDate.toDateString() === date.toDateString();
    });
    
    if (tasks.length === 0) return;
    
    // Create day tasks popup
    const popup = document.createElement('div');
    popup.className = 'absolute bg-white border border-gray-200 rounded-lg shadow-lg p-4 z-50 min-w-64 max-w-80';
    popup.style.top = '100%';
    popup.style.left = '0';
    popup.style.marginTop = '5px';
    
    const tasksList = tasks.map(task => {
        const props = task.extendedProps;
        const statusIcon = props.is_overdue ? '🔴' : 
                          props.status === 'completed' || props.status === 'CP' ? '✅' : 
                          props.status === 'in_progress' || props.status === 'IP' ? '🟡' : '⚪';
        
        return `
            <div class="flex items-center space-x-2 p-2 hover:bg-gray-50 rounded cursor-pointer" onclick="showTaskModal(window.dashboardCalendar.getEventById('${task.id}'))">
                <span>${statusIcon}</span>
                <div class="flex-1">
                    <div class="font-medium text-sm">${task.title}</div>
                    <div class="text-xs text-gray-500">${props.project} • ${props.progress}%</div>
                </div>
            </div>
        `;
    }).join('');
    
    popup.innerHTML = `
        <div class="flex items-center justify-between mb-3">
            <h3 class="font-semibold text-gray-900">${date.toLocaleDateString()} Tasks</h3>
            <button onclick="this.parentElement.parentElement.remove()" class="text-gray-400 hover:text-gray-600">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                </svg>
            </button>
        </div>
        ${tasksList}
    `;
    
    // Position relative to day cell
    dayEl.style.position = 'relative';
    dayEl.appendChild(popup);
    
    // Close when clicking outside
    setTimeout(() => {
        document.addEventListener('click', function closePopup(e) {
            if (!popup.contains(e.target)) {
                popup.remove();
                document.removeEventListener('click', closePopup);
            }
        });
    }, 100);
}
// ====================================================================
// ENHANCED MODAL FUNCTIONALITY
// ====================================================================

function initializeModals() {
    setupModalEventListeners();
    console.log('Modal system initialized');
}

function setupModalEventListeners() {
    document.addEventListener('click', (e) => {
        if (e.target.classList.contains('modal-backdrop') || 
            e.target.id === 'taskModal') {
            closeTaskModal();
        }
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeTaskModal();
        }
    });
}

function showTaskModal(event) {
    const modal = document.getElementById("taskModal");
    const modalTitle = document.getElementById("modalTitle");
    const modalBody = document.getElementById("modalBody");
    
    if (!modal || !modalTitle || !modalBody) {
        console.error("Modal elements not found");
        return;
    }
    
    const title = event.title;
    const props = event.extendedProps;
    const project = props.project;
    const progress = props.progress || 0;
    const startDate = event.start;
    const endDate = event.end;
    const description = props.description || "No description available";
    const priority = props.priority || "normal";
    const assignee = props.assignee;
    const weight = props.weight || 0;
    const manhours = props.manhours || 0;
    const scope = props.scope;
    
    const formatDate = (date) => {
        if (!date) return "Not set";
        return date.toLocaleDateString('en-US', {
            weekday: 'short',
            year: 'numeric', 
            month: 'short',
            day: 'numeric'
        });
    };
    
    const getDuration = () => {
        if (!startDate || !endDate) return "Not specified";
        const diffTime = Math.abs(endDate - startDate);
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
        return diffDays === 1 ? "1 day" : `${diffDays} days`;
    };
    
    const getProgressColor = (progress) => {
        if (progress >= 100) return "bg-green-500";
        if (progress >= 75) return "bg-blue-500";
        if (progress >= 50) return "bg-yellow-500";
        if (progress >= 25) return "bg-orange-500";
        return "bg-red-500";
    };
    
    const getPriorityBadge = (priority) => {
        const colors = {
            high: "bg-red-100 text-red-800 border border-red-200",
            medium: "bg-yellow-100 text-yellow-800 border border-yellow-200", 
            low: "bg-green-100 text-green-800 border border-green-200",
            normal: "bg-gray-100 text-gray-800 border border-gray-200"
        };
        return `<span class="px-3 py-1 text-xs rounded-full font-medium ${colors[priority] || colors.normal}">${priority.toUpperCase()}</span>`;
    };
    
    modalTitle.textContent = title;
    modalBody.innerHTML = `
    <div class="space-y-4">
        <!-- Header Row -->
        <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <div class="flex items-center space-x-2">
                <div class="w-3 h-3 rounded-full bg-blue-500"></div>
                <span class="text-sm font-medium text-gray-600">Project:</span>
                <span class="font-semibold text-gray-900">${project}</span>
            </div>
            ${getPriorityBadge(priority)}
        </div>

        <!-- Progress and Dates Row -->
        <div class="grid grid-cols-3 gap-4">
            <div class="text-center p-3 bg-gray-50 rounded-lg">
                <p class="text-xs text-gray-500 mb-1">Progress</p>
                <p class="text-xl font-bold text-gray-900 mb-2">${progress}%</p>
                <div class="w-full bg-gray-200 rounded-full h-2">
                    <div class="${getProgressColor(progress)} h-2 rounded-full transition-all duration-500" 
                         style="width: ${progress}%"></div>
                </div>
            </div>
            <div class="p-3 border border-gray-200 rounded-lg">
                <div class="flex items-center space-x-1 mb-1">
                    <i class="fas fa-play text-green-500 text-xs"></i>
                    <span class="text-xs font-medium text-gray-600">Start</span>
                </div>
                <p class="text-sm font-semibold text-gray-900">${formatDate(startDate)}</p>
            </div>
            <div class="p-3 border border-gray-200 rounded-lg">
                <div class="flex items-center space-x-1 mb-1">
                    <i class="fas fa-flag-checkered text-red-500 text-xs"></i>
                    <span class="text-xs font-medium text-gray-600">End</span>
                </div>
                <p class="text-sm font-semibold text-gray-900">${formatDate(endDate)}</p>
            </div>
        </div>

        <!-- Details Row -->
        <div class="grid grid-cols-${assignee ? '2' : '1'} gap-4">
            ${assignee ? `
            <div class="p-3 bg-blue-50 border border-blue-200 rounded-lg">
                <div class="flex items-center space-x-2">
                    <div class="w-8 h-8 rounded-full bg-gradient-to-r from-blue-400 to-purple-500 flex items-center justify-center text-white font-semibold text-sm flex-shrink-0">
                        ${assignee.name.charAt(0).toUpperCase()}
                    </div>
                    <div>
                        <p class="text-sm font-semibold text-gray-900">${assignee.name}</p>
                        <p class="text-xs text-gray-500">${assignee.email}</p>
                    </div>
                </div>
            </div>
            ` : ''}
            
            <div class="grid grid-cols-3 gap-2">
                <div class="text-center p-2 bg-gray-50 rounded">
                    <p class="text-xs text-gray-500">Weight</p>
                    <p class="text-sm font-semibold text-gray-900">${weight}%</p>
                </div>
                <div class="text-center p-2 bg-gray-50 rounded">
                    <p class="text-xs text-gray-500">Hours</p>
                    <p class="text-sm font-semibold text-gray-900">${manhours}h</p>
                </div>
                <div class="text-center p-2 bg-gray-50 rounded">
                    <p class="text-xs text-gray-500">Duration</p>
                    <p class="text-sm font-semibold text-gray-900">${getDuration()}</p>
                </div>
            </div>
        </div>

        ${scope ? `
        <div class="p-2 bg-purple-50 border border-purple-200 rounded-lg">
            <span class="text-xs font-medium text-purple-600">Scope: </span>
            <span class="text-sm font-semibold text-purple-900">${scope.name}</span>
        </div>
        ` : ''}
        
        ${description && description !== "No description available" ? `
        <div class="p-3 bg-gray-50 rounded-lg border-l-4 border-blue-500">
            <p class="text-xs font-medium text-gray-600 mb-1">Description</p>
            <p class="text-sm text-gray-700 leading-relaxed">${description}</p>
        </div>
        ` : ''}

        <!-- Footer Row -->
        <div class="flex items-center justify-between pt-3 border-t">
            <div class="flex space-x-4 text-xs text-gray-500">
                ${props.days_remaining !== null ? 
                    props.days_remaining < 0 ? `<span class="text-red-500 font-medium">${Math.abs(props.days_remaining)} days overdue</span>` :
                    props.days_remaining === 0 ? '<span class="text-yellow-500 font-medium">Due today</span>' :
                    `<span>${props.days_remaining} days remaining</span>` : ''
                }
            </div>
            <div class="flex space-x-2">
                <button onclick="closeTaskModal()" class="px-3 py-1 bg-gray-200 text-gray-800 text-sm rounded hover:bg-gray-300">Close</button>
                <a href="/projects/${props.projectId}/tasks/${props.taskId}/" class="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700">Details</a>
            </div>
        </div>
    </div>
`;
    
    modal.classList.remove("hidden");
    const modalContent = document.getElementById("modalContent");
    if (modalContent) {
        setTimeout(() => {
            modalContent.style.opacity = '1';
            modalContent.style.transform = 'scale(1)';
        }, 10);
    }
}

function closeTaskModal() {
    const modal = document.getElementById("taskModal");
    const modalContent = document.getElementById("modalContent");
    
    if (modalContent) {
        modalContent.style.opacity = '0';
        modalContent.style.transform = 'scale(0.95)';
    }
    
    setTimeout(() => {
        if (modal) modal.classList.add("hidden");
    }, 300);
}

// ====================================================================
// ENHANCED AUTO-REFRESH FUNCTIONALITY
// ====================================================================

function initializeAutoRefresh() {
    window.dashboardAutoRefresh = new DashboardAutoRefresh({
        interval: 30000, // 30 seconds
        apiEndpoint: '/api/dashboard/'
    });
}

class DashboardAutoRefresh {
    constructor(options = {}) {
        this.refreshInterval = options.interval || 30000;
        this.apiEndpoint = options.apiEndpoint || '/api/dashboard/';
        this.isActive = true;
        this.retryCount = 0;
        this.maxRetries = 3;
        this.intervalId = null;
        this.lastUpdateTimestamp = null;
        
        this.init();
    }

    init() {
        console.log('Auto-refresh initialized (30s interval)');
        this.startAutoRefresh();
        this.addEventListeners();
        this.showConnectionStatus('Auto-refresh active');
        this.lastUpdateTimestamp = window.dashboardData.timestamp;
    }

    startAutoRefresh() {
        if (this.intervalId) {
            clearInterval(this.intervalId);
        }

        this.intervalId = setInterval(() => {
            if (this.isActive && !document.hidden) {
                this.fetchAndUpdate();
            }
        }, this.refreshInterval);

        console.log(`Auto-refresh started (${this.refreshInterval / 1000}s interval)`);
    }

    async fetchAndUpdate() {
        try {
            console.log('Fetching fresh data...');

            // Use stored token and role
            const token = window.dashboardToken || "";
            const role = window.dashboardRole || "";
            
            // Validate token and role are available
            if (!token || !role) {
                throw new Error('Token or role not available. Please refresh the page.');
            }
            
            console.log('Using token:', token.substring(0, 10) + '...'); // Log first 10 chars for debugging
            console.log('Using role:', role);

            const response = await fetch(
                `/api/dashboard/?token=${encodeURIComponent(token)}&role=${encodeURIComponent(role)}`,
                {
                    method: 'GET',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'Content-Type': 'application/json',
                        'Cache-Control': 'no-cache'
                    },
                    credentials: 'same-origin',
                }
            );

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();

            if (data.success) {
                if (data.timestamp !== this.lastUpdateTimestamp) {
                    this.updateDashboard(data);
                    this.lastUpdateTimestamp = data.timestamp;
                    this.showNotification('success', 'Updated');
                }
                this.retryCount = 0;
            } else {
                throw new Error(data.message || 'Unknown error');
            }

        } catch (error) {
            console.error('Auto-refresh failed:', error);
            this.handleError(error);
        }
    }

    // ... rest of the class methods remain the same
    updateDashboard(data) {
        // Update status counts with animation
        if (data.status_counts) {
            this.animateStatusCards(data.status_counts);
        }

        // Update task status counts if available
        if (data.task_status_counts) {
            this.updateTaskStatusCounts(data.task_status_counts);
        }

        // Update global dashboard data
        if (data.projects) {
            window.dashboardData = { 
                projects: data.projects,
                timestamp: data.timestamp,
                metrics: data.metrics,
                status_counts: data.status_counts,
                task_status_counts: data.task_status_counts
            };
            this.updateCharts(data.projects);
            this.updateCalendar(data.projects);
        }

        console.log(`Dashboard updated - ${data.metrics?.total_projects || 0} projects loaded`);
    }

    animateStatusCards(statusCounts) {
        const cardSelectors = {
            planned: '[data-status="PL"] .text-3xl',
            ongoing: '[data-status="OG"] .text-3xl',
            completed: '[data-status="CP"] .text-3xl',
            cancelled: '[data-status="CN"] .text-3xl'
        };

        Object.entries(statusCounts).forEach(([status, count]) => {
            const element = document.querySelector(cardSelectors[status]);
            if (element) {
                const currentValue = parseInt(element.textContent) || 0;
                const newValue = parseInt(count) || 0;

                if (currentValue !== newValue) {
                    element.style.transform = 'scale(1.15)';
                    element.style.transition = 'all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)';
                    
                    const card = element.closest('.filter-card');
                    if (card) {
                        card.style.boxShadow = '0 0 20px rgba(59, 130, 246, 0.5)';
                    }
                    
                    setTimeout(() => {
                        element.textContent = newValue;
                        element.style.transform = 'scale(1)';
                        
                        if (card) {
                            card.style.boxShadow = '';
                        }
                    }, 200);
                }
            }
        });
    }

    updateTaskStatusCounts(taskStatusCounts) {
        // Update task metrics display if elements exist
        const elements = {
            total: document.querySelector('[data-task-metric="total"]'),
            completed: document.querySelector('[data-task-metric="completed"]'),
            in_progress: document.querySelector('[data-task-metric="in_progress"]'),
            pending: document.querySelector('[data-task-metric="pending"]'),
            overdue: document.querySelector('[data-task-metric="overdue"]')
        };

        Object.entries(taskStatusCounts).forEach(([status, count]) => {
            const element = elements[status];
            if (element) {
                const currentValue = parseInt(element.textContent) || 0;
                if (currentValue !== count) {
                    element.textContent = count;
                    element.style.transform = 'scale(1.1)';
                    element.style.transition = 'transform 0.3s ease';
                    setTimeout(() => {
                        element.style.transform = 'scale(1)';
                    }, 300);
                }
            }
        });
    }

    updateCharts(projects) {
        // Update progress chart
        if (window.progressChart) {
            const labels = projects.map(p => p.name || p.project_name);
            const plannedData = projects.map(p => p.planned_progress || 0);
            const actualData = projects.map(p => p.actual_progress || 0);
            
            const hasChanged = JSON.stringify(window.progressChart.data.labels) !== JSON.stringify(labels);
            
            if (hasChanged) {
                window.progressChart.data.labels = labels;
                window.progressChart.data.datasets[0].data = plannedData;
                window.progressChart.data.datasets[1].data = actualData;
                window.progressChart.update('none');
            }
        }

        // Update budget chart
        if (window.budgetChart) {
            const labels = projects.map(p => p.name || p.project_name);
            const estimatedBudget = projects.map(p => p.budget_total?.estimated || 0);
            const approvedBudget = projects.map(p => p.budget_total?.approved || 0);
            const plannedBudget = projects.map(p => p.budget_total?.planned || 0);
            const allocatedBudget = projects.map(p => p.budget_total?.allocated || 0);
            const spentBudget = projects.map(p => p.budget_total?.spent || 0);

            const hasChanged = JSON.stringify(window.budgetChart.data.labels) !== JSON.stringify(labels);

            if (hasChanged) {
                window.budgetChart.data.labels = labels;
                window.budgetChart.data.datasets[0].data = estimatedBudget;
                window.budgetChart.data.datasets[1].data = approvedBudget;
                window.budgetChart.data.datasets[2].data = plannedBudget;
                window.budgetChart.data.datasets[3].data = allocatedBudget;
                window.budgetChart.data.datasets[4].data = spentBudget;
                window.budgetChart.update('none');
            }
        }
    }

    updateCalendar(projects) {
        if (!window.dashboardCalendar) return;

        const projectColors = generateProjectColors(projects);
        const events = generateCalendarEvents(projects, projectColors);

        // Only update if events have changed
        const currentEventIds = window.dashboardCalendar.getEvents().map(e => e.id).sort();
        const newEventIds = events.map(e => e.id).sort();

        if (JSON.stringify(currentEventIds) !== JSON.stringify(newEventIds)) {
            window.dashboardCalendar.removeAllEvents();
            window.dashboardCalendar.addEventSource(events);
        }
    }

    handleError(error) {
        this.retryCount++;
        
        if (this.retryCount >= this.maxRetries) {
            this.showNotification('error', 'Updates unavailable');
            this.showConnectionStatus('Update failed');
            
            // Increase interval on failure
            this.refreshInterval = Math.min(this.refreshInterval * 1.5, 120000);
            this.startAutoRefresh();
        } else {
            console.log(`Retrying... (${this.retryCount}/${this.maxRetries})`);
            setTimeout(() => this.fetchAndUpdate(), 5000);
        }
    }

    showNotification(type, message) {
        const existing = document.querySelectorAll('.auto-refresh-notification');
        existing.forEach(el => el.remove());

        const notification = document.createElement('div');
        notification.className = 'auto-refresh-notification fixed top-4 right-4 px-4 py-2 rounded-lg text-white text-sm shadow-lg z-50 transition-all duration-300';
        
        const colors = {
            success: 'bg-green-500',
            error: 'bg-red-500',
            info: 'bg-blue-500'
        };
        
        notification.className += ` ${colors[type] || colors.info}`;
        notification.textContent = message;
        notification.style.opacity = '0';
        notification.style.transform = 'translateY(-10px)';
        
        document.body.appendChild(notification);
        
        requestAnimationFrame(() => {
            notification.style.opacity = '1';
            notification.style.transform = 'translateY(0)';
        });
        
        setTimeout(() => {
            notification.style.opacity = '0';
            notification.style.transform = 'translateY(-10px)';
            setTimeout(() => notification.remove(), 300);
        }, type === 'error' ? 5000 : 2000);
    }

    showConnectionStatus(status) {
        let statusEl = document.getElementById('autoRefreshStatus');
        if (!statusEl) {
            statusEl = document.createElement('div');
            statusEl.id = 'autoRefreshStatus';
            statusEl.className = 'fixed bottom-4 left-4 px-3 py-1 rounded-full text-xs text-white z-40 transition-all duration-300';
            document.body.appendChild(statusEl);
        }

        statusEl.textContent = status;
        statusEl.className = statusEl.className.replace(/bg-\w+-500/g, '');
        
        if (status.includes('active') || status.includes('online')) {
            statusEl.className += ' bg-green-500';
            setTimeout(() => {
                statusEl.style.opacity = '0.3';
            }, 3000);
        } else if (status.includes('failed') || status.includes('offline')) {
            statusEl.className += ' bg-red-500';
            statusEl.style.opacity = '1';
        } else {
            statusEl.className += ' bg-blue-500';
            statusEl.style.opacity = '1';
        }
    }

    addEventListeners() {
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden && this.isActive) {
                console.log('Page visible - refreshing data');
                this.fetchAndUpdate();
            }
        });

        window.addEventListener('online', () => {
            console.log('Back online');
            this.showConnectionStatus('Back online');
            this.fetchAndUpdate();
        });

        window.addEventListener('offline', () => {
            console.log('Gone offline');
            this.showConnectionStatus('Offline');
        });
    }

    pause() {
        this.isActive = false;
        this.showConnectionStatus('Paused');
        console.log('Auto-refresh paused');
    }

    resume() {
        this.isActive = true;
        this.showConnectionStatus('Resumed');
        this.fetchAndUpdate();
        console.log('Auto-refresh resumed');
    }

    destroy() {
        if (this.intervalId) {
            clearInterval(this.intervalId);
        }
        this.isActive = false;
        
        const statusEl = document.getElementById('autoRefreshStatus');
        if (statusEl) statusEl.remove();
        
        console.log('Auto-refresh destroyed');
    }
}
// ====================================================================
// INTERACTIONS & EVENT HANDLERS
// ====================================================================

function initializeInteractions() {
    initializeStatusCardFilters();
    initializeSearchFeatures();
    initializeKeyboardShortcuts();
}

function initializeStatusCardFilters() {
    const filterCards = document.querySelectorAll('.filter-card');
    let activeFilter = null;
    
    filterCards.forEach(card => {
        card.addEventListener('click', function() {
            const status = this.dataset.status;
            
            if (activeFilter === status) {
                activeFilter = null;
                filterCards.forEach(c => {
                    c.classList.remove('ring-4', 'ring-blue-300', 'ring-opacity-50');
                    c.style.transform = 'scale(1)';
                });
                showAllProjects();
            } else {
                activeFilter = status;
                
                filterCards.forEach(c => {
                    c.classList.remove('ring-4', 'ring-blue-300', 'ring-opacity-50');
                    c.style.transform = 'scale(1)';
                });
                
                this.classList.add('ring-4', 'ring-blue-300', 'ring-opacity-50');
                this.style.transform = 'scale(1.02)';
                this.style.transition = 'all 0.3s ease';
                
                filterProjectsByStatus(status);
            }
            
            this.style.transform = 'scale(0.95)';
            setTimeout(() => {
                this.style.transform = activeFilter === status ? 'scale(1.02)' : 'scale(1)';
            }, 150);
        });
        
        card.addEventListener('mouseenter', function() {
            if (activeFilter !== this.dataset.status) {
                this.style.transform = 'scale(1.02)';
            }
        });
        
        card.addEventListener('mouseleave', function() {
            if (activeFilter !== this.dataset.status) {
                this.style.transform = 'scale(1)';
            }
        });
    });
}

function filterProjectsByStatus(status) {
    console.log(`Filtering by status: ${status}`);
    
    if (!window.dashboardData?.projects) return;
    
    const filteredProjects = window.dashboardData.projects.filter(project => {
        const projectStatus = project.status || 'PL';
        return projectStatus === status;
    });
    
    updateChartsWithFilteredData(filteredProjects);
    updateCalendarWithFilteredData(filteredProjects);
    showFilterIndicator(status, filteredProjects.length);
}

function showAllProjects() {
    console.log('Showing all projects');
    
    if (!window.dashboardData?.projects) return;
    
    updateChartsWithFilteredData(window.dashboardData.projects);
    updateCalendarWithFilteredData(window.dashboardData.projects);
    hideFilterIndicator();
}

function updateChartsWithFilteredData(projects) {
    // Progress Chart
    if (window.progressChart) {
        window.progressChart.data.labels = projects.map(p => p.name || p.project_name);
        window.progressChart.data.datasets[0].data = projects.map(p => p.planned_progress || 0);
        window.progressChart.data.datasets[1].data = projects.map(p => p.actual_progress || 0);
        window.progressChart.update('active');
    }
    
    // Budget Chart
    if (window.budgetChart) {
        window.budgetChart.data.labels = projects.map(p => p.name || p.project_name);
        window.budgetChart.data.datasets[0].data = projects.map(p => p.budget_total?.estimated || 0);
        window.budgetChart.data.datasets[1].data = projects.map(p => p.budget_total?.approved || 0);
        window.budgetChart.data.datasets[2].data = projects.map(p => p.budget_total?.planned || 0);
        window.budgetChart.data.datasets[3].data = projects.map(p => p.budget_total?.allocated || 0);
        window.budgetChart.data.datasets[4].data = projects.map(p => p.budget_total?.spent || 0);
        window.budgetChart.update('active');
    }
}

function updateCalendarWithFilteredData(projects) {
    if (!window.dashboardCalendar) return;
    
    const projectColors = generateProjectColors(projects);
    const events = generateCalendarEvents(projects, projectColors);
    
    window.dashboardCalendar.removeAllEvents();
    window.dashboardCalendar.addEventSource(events);
}

function showFilterIndicator(status, count) {
    const statusNames = {
        'PL': 'Planned',
        'OG': 'Ongoing', 
        'CP': 'Completed',
        'CN': 'Cancelled'
    };
    
    let indicator = document.getElementById('filterIndicator');
    if (!indicator) {
        indicator = document.createElement('div');
        indicator.id = 'filterIndicator';
        indicator.className = 'fixed top-20 right-4 bg-blue-500 text-white px-4 py-2 rounded-lg shadow-lg z-40 transition-all duration-300';
        document.body.appendChild(indicator);
    }
    
    indicator.innerHTML = `
        <div class="flex items-center space-x-2">
            <i class="fas fa-filter"></i>
            <span>Showing ${statusNames[status]} (${count})</span>
            <button onclick="showAllProjects()" class="ml-2 text-white hover:text-gray-200">
                <i class="fas fa-times"></i>
            </button>
        </div>
    `;
    
    indicator.style.opacity = '1';
    indicator.style.transform = 'translateX(0)';
}

function hideFilterIndicator() {
    const indicator = document.getElementById('filterIndicator');
    if (indicator) {
        indicator.style.opacity = '0';
        indicator.style.transform = 'translateX(100%)';
        setTimeout(() => indicator.remove(), 300);
    }
}

function initializeSearchFeatures() {
    const searchInput = document.getElementById('projectSearch');
    if (searchInput) {
        searchInput.addEventListener('input', debounce(handleSearch, 300));
    }
}

function handleSearch(event) {
    const query = event.target.value.toLowerCase().trim();
    
    if (!query) {
        showAllProjects();
        return;
    }
    
    const filteredProjects = window.dashboardData.projects.filter(project =>
        (project.name || project.project_name || '').toLowerCase().includes(query) ||
        (project.description && project.description.toLowerCase().includes(query))
    );
    
    updateChartsWithFilteredData(filteredProjects);
    updateCalendarWithFilteredData(filteredProjects);
    
    console.log(`Search results: ${filteredProjects.length} projects found for "${query}"`);
}

function initializeKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
        
        switch (e.key) {
            case '1':
                if (e.ctrlKey || e.metaKey) {
                    e.preventDefault();
                    document.querySelector('[data-status="PL"]')?.click();
                }
                break;
            case '2':
                if (e.ctrlKey || e.metaKey) {
                    e.preventDefault();
                    document.querySelector('[data-status="OG"]')?.click();
                }
                break;
            case '3':
                if (e.ctrlKey || e.metaKey) {
                    e.preventDefault();
                    document.querySelector('[data-status="CP"]')?.click();
                }
                break;
            case '4':
                if (e.ctrlKey || e.metaKey) {
                    e.preventDefault();
                    document.querySelector('[data-status="CN"]')?.click();
                }
                break;
            case 'r':
                if (e.ctrlKey || e.metaKey) {
                    e.preventDefault();
                    if (window.dashboardAutoRefresh) {
                        window.dashboardAutoRefresh.fetchAndUpdate();
                    }
                }
                break;
            case 'Escape':
                // Close any open modals or filters
                closeTaskModal();
                showAllProjects();
                break;
        }
    });
}

// ====================================================================
// ADDITIONAL UTILITY FUNCTIONS
// ====================================================================

function refreshDashboard() {
    if (window.dashboardAutoRefresh) {
        window.dashboardAutoRefresh.fetchAndUpdate();
    }
}

function toggleAutoRefresh() {
    if (window.dashboardAutoRefresh) {
        if (window.dashboardAutoRefresh.isActive) {
            window.dashboardAutoRefresh.pause();
            showInfoMessage('Auto-refresh paused');
        } else {
            window.dashboardAutoRefresh.resume();
            showInfoMessage('Auto-refresh resumed');
        }
    }
}

function exportDashboardData() {
    if (!window.dashboardData) {
        showErrorMessage('No data available to export');
        return;
    }
    
    const data = {
        exported_at: new Date().toISOString(),
        projects: window.dashboardData.projects,
        metrics: window.dashboardData.metrics,
        status_counts: window.dashboardData.status_counts,
        task_status_counts: window.dashboardData.task_status_counts
    };
    
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `dashboard-data-${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    showSuccessMessage('Dashboard data exported successfully');
}

function printDashboard() {
    // Hide interactive elements before printing
    const elementsToHide = document.querySelectorAll('.no-print, button, .auto-refresh-notification');
    elementsToHide.forEach(el => el.style.display = 'none');
    
    window.print();
    
    // Restore elements after printing
    setTimeout(() => {
        elementsToHide.forEach(el => el.style.display = '');
    }, 1000);
}

// ====================================================================
// PERFORMANCE MONITORING
// ====================================================================

function monitorPerformance() {
    // Monitor chart render times
    const originalRender = Chart.prototype.render;
    Chart.prototype.render = function() {
        const start = performance.now();
        const result = originalRender.apply(this, arguments);
        const end = performance.now();
        console.log(`Chart render took ${(end - start).toFixed(2)}ms`);
        return result;
    };
    
    // Monitor calendar render times
    if (window.FullCalendar) {
        const originalCalendarRender = FullCalendar.Calendar.prototype.render;
        FullCalendar.Calendar.prototype.render = function() {
            const start = performance.now();
            const result = originalCalendarRender.apply(this, arguments);
            const end = performance.now();
            console.log(`Calendar render took ${(end - start).toFixed(2)}ms`);
            return result;
        };
    }
}

// Initialize performance monitoring in development
if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    monitorPerformance();
}

// ====================================================================
// GLOBAL EXPORTS & CLEANUP
// ====================================================================

// Global functions for template use
window.closeTaskModal = closeTaskModal;
window.showAllProjects = showAllProjects;
window.filterProjectsByStatus = filterProjectsByStatus;
window.refreshDashboard = refreshDashboard;
window.toggleAutoRefresh = toggleAutoRefresh;
window.exportDashboardData = exportDashboardData;
window.printDashboard = printDashboard;

// Utility exports
window.dashboardUtils = {
    showAllProjects,
    filterProjectsByStatus,
    showSuccessMessage,
    showErrorMessage,
    showInfoMessage,
    closeTaskModal,
    refreshDashboard,
    toggleAutoRefresh,
    exportDashboardData,
    printDashboard
};

// Control methods for debugging and testing
window.refreshControls = {
    pause: () => window.dashboardAutoRefresh?.pause(),
    resume: () => window.dashboardAutoRefresh?.resume(),
    refresh: () => window.dashboardAutoRefresh?.fetchAndUpdate(),
    setInterval: (seconds) => {
        if (window.dashboardAutoRefresh) {
            window.dashboardAutoRefresh.refreshInterval = seconds * 1000;
            window.dashboardAutoRefresh.startAutoRefresh();
        }
    },
    status: () => console.log({
        isActive: window.dashboardAutoRefresh?.isActive,
        interval: window.dashboardAutoRefresh?.refreshInterval,
        lastUpdate: window.dashboardAutoRefresh?.lastUpdateTimestamp,
        retryCount: window.dashboardAutoRefresh?.retryCount
    })
};

// Debug helpers
window.debugDashboard = {
    logData: () => console.log('Dashboard Data:', window.dashboardData),
    logCharts: () => console.log('Charts:', { progress: window.progressChart, budget: window.budgetChart }),
    logCalendar: () => console.log('Calendar:', window.dashboardCalendar),
    logAutoRefresh: () => console.log('Auto-refresh:', window.dashboardAutoRefresh),
    simulateError: () => window.dashboardAutoRefresh?.handleError(new Error('Simulated error')),
    clearCache: () => {
        window.dashboardData = null;
        showInfoMessage('Dashboard cache cleared');
    }
};

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (window.dashboardAutoRefresh) {
        window.dashboardAutoRefresh.destroy();
    }
    
    // Clean up any remaining intervals or timeouts
    if (window.progressChart) {
        window.progressChart.destroy();
    }
    if (window.budgetChart) {
        window.budgetChart.destroy();
    }
    if (window.dashboardCalendar) {
        window.dashboardCalendar.destroy();
    }
    
    console.log('Dashboard cleanup completed');
});

// Add CSS for print styles
const printStyles = `
    <style media="print">
        .no-print { display: none !important; }
        .filter-card { box-shadow: none !important; transform: none !important; }
        .auto-refresh-notification { display: none !important; }
        #autoRefreshStatus { display: none !important; }
        button { display: none !important; }
        .fixed { position: relative !important; }
        @page { margin: 1in; }
        body { font-size: 12px; }
        .text-3xl { font-size: 1.5rem !important; }
        .text-2xl { font-size: 1.25rem !important; }
        .text-xl { font-size: 1.125rem !important; }
    </style>
`;

document.head.insertAdjacentHTML('beforeend', printStyles);

console.log('Complete dashboard system loaded and ready!');
console.log('Available global functions:', Object.keys(window.dashboardUtils));
console.log('Debug tools available at: window.debugDashboard');
console.log('Refresh controls available at: window.refreshControls');