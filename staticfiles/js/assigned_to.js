document.addEventListener("DOMContentLoaded", () => {
    const container = document.getElementById("pm_container");
    if (!container) return;

    const input = container.querySelector("#project_manager_input");
    const hiddenField = container.querySelector("project_manager_id");
    const suggestionsBox = container.querySelector("pm_suggestions");
    const assignedDisplay = container.querySelector("assigned_pm_display");

    async function fetchProjectManagers(query) {
        const response = await fetch(`/projects/search/project-managers/?q=${encodeURIComponent(query)}`);
        if (!response.ok) return [];
        return await response.json();
    }

    input.addEventListener("input", async () => {
        const query = input.value.trim();
        suggestionsBox.innerHTML = "";

        if (!query) {
            suggestionsBox.classList.add("hidden");
            return;
        }

        const results = await fetchProjectManagers(query);
        if (results.length === 0) {
            suggestionsBox.classList.add("hidden");
            return;
        }

        results.forEach(pm => {
            const li = document.createElement("li");
            li.className = "px-3 py-2 cursor-pointer hover:bg-gray-100";
            li.textContent = `${pm.full_name} (${pm.email})`; // full name + email only
            li.addEventListener("click", () => {
                input.value = pm.full_name;
                hiddenField.value = String(pm.id);
                assignedDisplay.textContent = `Assigned to: ${pm.full_name} (${pm.email})`;
                suggestionsBox.classList.add("hidden");
            });
            suggestionsBox.appendChild(li);
        });

        suggestionsBox.classList.remove("hidden");
    });

    document.addEventListener("click", (e) => {
        if (!container.contains(e.target)) {
            suggestionsBox.classList.add("hidden");
        }
    });
});
