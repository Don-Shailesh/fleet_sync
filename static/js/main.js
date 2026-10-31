/**
 * FleetSync - Main Client Script
 * Handles UI interactions, line-item calculator, SweetAlert modals, and AJAX helpers
 */

document.addEventListener('DOMContentLoaded', function () {
  // Initialize Bootstrap Tooltips
  const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  tooltipTriggerList.map(function (el) {
    return new bootstrap.Tooltip(el);
  });

  // Auto-dismiss alerts after 5 seconds
  setTimeout(function () {
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(function (alert) {
      const bsAlert = new bootstrap.Alert(alert);
      bsAlert.close();
    });
  }, 5000);

  // Initialize Line Items Dynamic Calculator in Work Order Form
  setupWorkOrderCalculator();

  // Setup Vehicle change listener in Work Order form to auto-fill odometer
  setupVehicleOdometerAutofill();

  // Setup SweetAlert confirmation for delete actions
  setupDeleteConfirmations();

  // Setup Mobile Sidebar Toggle
  const sidebarToggle = document.getElementById('sidebar-toggle');
  const sidebar = document.querySelector('.app-sidebar');
  if (sidebarToggle && sidebar) {
    sidebarToggle.addEventListener('click', function () {
      sidebar.classList.toggle('show');
    });
    document.addEventListener('click', function (e) {
      if (window.innerWidth <= 768 && sidebar.classList.contains('show')) {
        if (!sidebar.contains(e.target) && !sidebarToggle.contains(e.target)) {
          sidebar.classList.remove('show');
        }
      }
    });
  }
});

/**
 * SweetAlert confirmation helper
 */
function confirmAction(title, text, confirmButtonText, callback) {
  if (typeof Swal !== 'undefined') {
    Swal.fire({
      title: title || 'Are you sure?',
      text: text || "You won't be able to revert this!",
      icon: 'warning',
      showCancelButton: true,
      confirmButtonColor: '#4f46e5',
      cancelButtonColor: '#ef4444',
      confirmButtonText: confirmButtonText || 'Yes, proceed',
      cancelButtonText: 'Cancel',
      customClass: {
        popup: 'rounded-4 shadow-lg'
      }
    }).then((result) => {
      if (result.isConfirmed) {
        callback();
      }
    });
  } else {
    if (confirm(text || 'Are you sure you want to proceed?')) {
      callback();
    }
  }
}

function setupDeleteConfirmations() {
  document.querySelectorAll('.btn-delete-confirm').forEach(function (button) {
    button.addEventListener('click', function (e) {
      e.preventDefault();
      const form = this.closest('form');
      const itemTitle = this.getAttribute('data-item-title') || 'this item';

      confirmAction(
        `Delete ${itemTitle}?`,
        `This will permanently remove this record from the system.`,
        'Yes, delete',
        function () {
          form.submit();
        }
      );
    });
  });
}

/**
 * Line Items Calculator for Work Orders
 */
function setupWorkOrderCalculator() {
  const container = document.getElementById('line-items-container');
  const addBtn = document.getElementById('btn-add-item');
  if (!container || !addBtn) return;

  function recalculateTotals() {
    let partsTotal = 0;
    let laborTotal = 0;

    const rows = container.querySelectorAll('.line-item-row');
    rows.forEach(function (row) {
      const typeSelect = row.querySelector('.item-type');
      const qtyInput = row.querySelector('.item-quantity');
      const priceInput = row.querySelector('.item-price');
      const totalDisplay = row.querySelector('.item-total-display');

      const qty = parseFloat(qtyInput.value) || 0;
      const price = parseFloat(priceInput.value) || 0;
      const rowTotal = qty * price;

      if (totalDisplay) {
        totalDisplay.innerText = '₹' + rowTotal.toFixed(2);
      }

      if (typeSelect && typeSelect.value === 'Labor') {
        laborTotal += rowTotal;
      } else {
        partsTotal += rowTotal;
      }
    });

    const taxAmount = (partsTotal + laborTotal) * 0.08;
    const grandTotal = partsTotal + laborTotal + taxAmount;

    const partsEl = document.getElementById('calc-parts-cost');
    const laborEl = document.getElementById('calc-labor-cost');
    const taxEl = document.getElementById('calc-tax-amount');
    const grandEl = document.getElementById('calc-grand-total');

    if (partsEl) partsEl.innerText = '₹' + partsTotal.toFixed(2);
    if (laborEl) laborEl.innerText = '₹' + laborTotal.toFixed(2);
    if (taxEl) taxEl.innerText = '₹' + taxAmount.toFixed(2);
    if (grandEl) grandEl.innerText = '₹' + grandTotal.toFixed(2);
  }

  // Bind change/input events for existing rows
  container.addEventListener('input', function (e) {
    if (e.target.matches('.item-quantity, .item-price, .item-type')) {
      recalculateTotals();
    }
  });

  // Remove row handler
  container.addEventListener('click', function (e) {
    const removeBtn = e.target.closest('.btn-remove-item');
    if (removeBtn) {
      const row = removeBtn.closest('.line-item-row');
      const rows = container.querySelectorAll('.line-item-row');
      if (rows.length > 1) {
        row.remove();
        recalculateTotals();
      } else {
        // Clear instead of removing last row
        row.querySelector('.item-name').value = '';
        row.querySelector('.item-quantity').value = '1';
        row.querySelector('.item-price').value = '0.00';
        recalculateTotals();
      }
    }
  });

  // Add new row handler
  addBtn.addEventListener('click', function () {
    const newRow = document.createElement('tr');
    newRow.className = 'line-item-row align-middle';
    newRow.innerHTML = `
      <td>
        <select name="item_type[]" class="form-select form-select-sm item-type">
          <option value="Part">Part / Material</option>
          <option value="Labor">Labor</option>
          <option value="Inspection">Inspection</option>
          <option value="Fee">Fee / Misc</option>
        </select>
      </td>
      <td>
        <input type="text" name="item_name[]" class="form-control form-control-sm item-name" placeholder="e.g. Brake Rotor, Oil Filter" required>
      </td>
      <td style="width: 110px;">
        <input type="number" step="0.25" min="0" name="item_quantity[]" class="form-control form-control-sm item-quantity text-end" value="1.00">
      </td>
      <td style="width: 140px;">
        <div class="input-group input-group-sm">
          <span class="input-group-text">₹</span>
          <input type="number" step="0.01" min="0" name="item_price[]" class="form-control item-price text-end" value="0.00">
        </div>
      </td>
      <td class="text-end fw-semibold item-total-display" style="width: 120px;">
        ₹0.00
      </td>
      <td class="text-center" style="width: 50px;">
        <button type="button" class="btn btn-sm btn-outline-danger border-0 btn-remove-item">
          <i class="fa-solid fa-trash-can"></i>
        </button>
      </td>
    `;
    container.appendChild(newRow);
  });

  // Run on page load
  recalculateTotals();
}

/**
 * Fetch vehicle current odometer when selected in Work Order form
 */
function setupVehicleOdometerAutofill() {
  const vehicleSelect = document.getElementById('work-order-vehicle-select');
  const odometerInput = document.getElementById('work-order-odometer-input');
  if (!vehicleSelect || !odometerInput) return;

  vehicleSelect.addEventListener('change', function () {
    const vehicleId = this.value;
    if (!vehicleId) return;

    fetch(`/api/vehicles/${vehicleId}`)
      .then(res => res.json())
      .then(data => {
        if (data.success && data.vehicle) {
          odometerInput.value = data.vehicle.current_odometer || 0;
          const hint = document.getElementById('odometer-last-reading-hint');
          if (hint) {
            hint.innerText = `Current record: ${Number(data.vehicle.current_odometer).toLocaleString()} km`;
          }
        }
      })
      .catch(err => console.error("Error fetching vehicle details:", err));
  });
}
