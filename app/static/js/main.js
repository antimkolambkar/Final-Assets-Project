/* Enterprise ITAM & Helpdesk System Main JavaScript */

document.addEventListener('DOMContentLoaded', function() {
    // 1. Dark / Light Theme Handler
    const themeToggleBtn = document.getElementById('theme-toggle-btn');
    const themeIcon = document.getElementById('theme-icon');

    const savedTheme = localStorage.getItem('itam_theme') || 'light';
    setTheme(savedTheme);

    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', function() {
            const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
            const newTheme = currentTheme === 'light' ? 'dark' : 'light';
            setTheme(newTheme);
        });
    }

    function setTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('itam_theme', theme);
        if (themeIcon) {
            if (theme === 'dark') {
                themeIcon.className = 'fas fa-sun text-warning';
            } else {
                themeIcon.className = 'fas fa-moon text-secondary';
            }
        }
    }

    // 2. Initialize Bootstrap Tooltips & Toasts
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    var toastElList = [].slice.call(document.querySelectorAll('.toast'));
    toastElList.map(function (toastEl) {
        var toast = new bootstrap.Toast(toastEl, { delay: 5000 });
        toast.show();
    });

    // 3. Employee Detail Modal Handler
    const viewEmpButtons = document.querySelectorAll('.btn-view-employee');
    viewEmpButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            const empId = this.getAttribute('data-emp-id');
            fetch(`/employees/${empId}/json`)
                .then(res => res.json())
                .then(data => {
                    document.getElementById("editProfileBtn").dataset.empId = data.id;
                    document.getElementById('modal-emp-name').textContent = data.name;
                    document.getElementById('modal-emp-id').textContent = data.employee_id;
                    document.getElementById('modal-emp-email').textContent = data.email;
                    document.getElementById('modal-emp-dept').textContent = data.department;
                    document.getElementById('modal-emp-desig').textContent = data.designation;
                    document.getElementById('modal-emp-manager').textContent = data.manager;
                    document.getElementById('modal-emp-office').textContent = data.office_location;
                    
                    const statusBadge = document.getElementById('modal-emp-status');
                    statusBadge.textContent = data.account_status;
                    statusBadge.className = `badge badge-status badge-${data.account_status.toLowerCase()}`;

                    const assetsTableBody = document.getElementById("modal-emp-assets-body");
assetsTableBody.innerHTML = "";

if (data.assigned_assets.length === 0) {

    assetsTableBody.innerHTML = `
        <div class="alert alert-secondary text-center">
            No company assets assigned.
        </div>
    `;

} else {

    data.assigned_assets.forEach(ast => {

        const row = `
            <div class="card border shadow-sm mb-3">

                <div class="card-header bg-light d-flex justify-content-between align-items-center">

                    <strong>
                        💻 ${ast.asset_type || "Laptop"}
                    </strong>

                    <span class="badge bg-success">
                        Assigned
                    </span>

                </div>

                <div class="card-body">

                    <h5 class="fw-bold mb-3">
                        ${ast.brand} ${ast.model}
                    </h5>

                    <div class="row">

                        <div class="col-md-6 mb-2">
                            <strong>Asset ID</strong><br>
                            ${ast.asset_id}
                        </div>

                        <div class="col-md-6 mb-2">
                            <strong>Serial Number</strong><br>
                            ${ast.serial_number}
                        </div>

                        <div class="col-md-6 mb-2">
                            <strong>Processor</strong><br>
                            ${ast.processor}
                        </div>

                        <div class="col-md-6 mb-2">
                            <strong>RAM / SSD</strong><br>
                            ${ast.ram} / ${ast.ssd}
                        </div>

                        <div class="col-md-6 mb-2">
                            <strong>Vendor</strong><br>
                            ${ast.vendor_name}
                        </div>

                        <div class="col-md-6 mb-2">
                            <strong>Assigned Date</strong><br>
                            ${ast.assignment_date}
                        </div>

                    </div>

                </div>

            </div>
        `;

        assetsTableBody.innerHTML += row;

    });

}

const empModal = new bootstrap.Modal(
    document.getElementById("employeeDetailModal")
);

empModal.show();
                })
                .catch(err => console.error('Error fetching employee details:', err));
        });
    });

    // 4. Asset History Modal Handler
    const viewAssetHistButtons = document.querySelectorAll('.btn-view-asset-history');
    viewAssetHistButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            const assetId = this.getAttribute('data-asset-id');
            fetch(`/assets/${assetId}/history`)
                .then(res => res.json())
                .then(data => {
                    document.getElementById('modal-hist-asset-id').textContent = data.asset_id;
                    document.getElementById('modal-hist-brand-model').textContent = data.brand_model;
                    document.getElementById('modal-hist-serial').textContent = data.serial_number;
                    document.getElementById('modal-hist-user').textContent = data.assigned_user;

                    const histTableBody = document.getElementById('modal-asset-hist-body');
                    histTableBody.innerHTML = '';

                    if (data.history.length === 0) {
                        histTableBody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-3">No history logs recorded for this asset yet.</td></tr>';
                    } else {
                        data.history.forEach(h => {
                            let actionBadge = `<span class="badge bg-secondary">${h.action}</span>`;
                            if (h.action === 'Assigned') actionBadge = `<span class="badge bg-primary">Assigned</span>`;
                            if (h.action === 'Returned') actionBadge = `<span class="badge bg-success">Returned</span>`;
                            if (h.action === 'Replaced') actionBadge = `<span class="badge bg-warning text-dark"><i class="fas fa-sync me-1"></i>Replaced</span>`;

                            const oldNewInfo = (h.old_asset && h.new_asset) ? 
                                `<small class="text-muted">Old: ${h.old_asset} &rarr; New: ${h.new_asset}</small>` : '';

                          const row = `
    <tr>
        <td><small class="text-muted">${h.timestamp}</small></td>
        <td>${actionBadge}</td>
        <td><strong>${h.employee_name}</strong></td>
        <td>${h.notes} ${oldNewInfo}</td>
        <td><small class="text-secondary">${h.performed_by}</small></td>
    </tr>
`;

histTableBody.innerHTML += row;
                        });
                    }

                    var histModal = new bootstrap.Modal(document.getElementById('assetHistoryModal'));
                    histModal.show();
                })
                .catch(err => console.error('Error fetching asset history:', err));
        });
    });
    const editBtn = document.getElementById("editProfileBtn");

if (editBtn) {

    editBtn.addEventListener("click", function () {

        const empId = this.dataset.empId;

        if (!empId) {
            alert("Open an employee first.");
            return;
        }

        fetch(`/employees/${empId}/json`)
            .then(r => r.json())
            .then(emp => {

                document.getElementById("editName").value = emp.name;
                document.getElementById("editDepartment").value = emp.department;
                document.getElementById("editDesignation").value = emp.designation;
                document.getElementById("editManager").value = emp.manager;
                document.getElementById("editOffice").value = emp.office_location;
                document.getElementById("editStatus").value = emp.account_status;

                document.getElementById("editEmployeeForm").action =
                    `/employees/${empId}/edit`;

                new bootstrap.Modal(
                    document.getElementById("editEmployeeModal")
                ).show();

            });

    });

}
  // =======================
// Save Employee Edit Form
// =======================
const editForm = document.getElementById("editEmployeeForm");

if (editForm) {
    editForm.addEventListener("submit", function (e) {
        e.preventDefault();

        fetch(this.action, {
            method: "POST",
            body: new FormData(this)
        })
        .then(response => response.json())
        .then(data => {

            if (data.success) {

                alert(data.message);

                bootstrap.Modal.getInstance(
                    document.getElementById("editEmployeeModal")
                ).hide();

                location.reload();

            } else {
                alert(data.message);
            }

        })
        .catch(error => {
            console.error(error);
            alert("Error updating employee.");
        });
    });
}
});
