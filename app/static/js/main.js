// 4. Asset History Modal Handler
// Event delegation: works even when asset buttons are dynamically rendered.
document.addEventListener('click', function(event) {

    const btn = event.target.closest('.btn-view-asset-history');

    if (!btn) {
        return;
    }

    event.preventDefault();
    event.stopPropagation();

    const assetId = btn.getAttribute('data-asset-id');

    if (!assetId) {
        console.error('Asset history button is missing data-asset-id.');
        return;
    }

    fetch(`/assets/${encodeURIComponent(assetId)}/history`, {
        headers: {
            'Accept': 'application/json'
        }
    })
    .then(async response => {

        if (!response.ok) {
            throw new Error(
                `History request failed: ${response.status}`
            );
        }

        return response.json();
    })
    .then(data => {

        // Header information
        const assetIdElement =
            document.getElementById('modal-hist-asset-id');

        const brandModelElement =
            document.getElementById('modal-hist-brand-model');

        const serialElement =
            document.getElementById('modal-hist-serial');

        const userElement =
            document.getElementById('modal-hist-user');

        const vendorElement =
            document.getElementById('modal-hist-vendor');

        if (assetIdElement) {
            assetIdElement.textContent =
                data.asset_id || '-';
        }

        if (brandModelElement) {
            brandModelElement.textContent =
                data.brand_model || '-';
        }

        if (serialElement) {
            serialElement.textContent =
                data.serial_number || '-';
        }

        if (userElement) {
            userElement.textContent =
                data.assigned_user || '-';
        }

        if (vendorElement) {
            vendorElement.textContent =
                data.vendor || '-';
        }

        // History table
        const histTableBody =
            document.getElementById(
                'modal-asset-hist-body'
            );

        if (!histTableBody) {
            throw new Error(
                'modal-asset-hist-body not found.'
            );
        }

        histTableBody.innerHTML = '';

        const history =
            Array.isArray(data.history)
                ? data.history
                : [];

        if (history.length === 0) {

            histTableBody.innerHTML = `
                <tr>
                    <td colspan="6"
                        class="text-center text-muted py-3">
                        No history logs recorded for this asset yet.
                    </td>
                </tr>
            `;

        } else {

            history.forEach(function(h) {

                let actionBadge = `
                    <span class="badge bg-secondary">
                        ${escapeHtml(h.action || '-')}
                    </span>
                `;

                if (h.action === 'Assigned') {
                    actionBadge = `
                        <span class="badge bg-primary">
                            Assigned
                        </span>
                    `;
                }

                if (h.action === 'Returned') {
                    actionBadge = `
                        <span class="badge bg-success">
                            Returned
                        </span>
                    `;
                }

                if (h.action === 'Replaced') {
                    actionBadge = `
                        <span class="badge bg-warning text-dark">
                            <i class="fas fa-sync me-1"></i>
                            Replaced
                        </span>
                    `;
                }

                if (h.action === 'Send Back to Vendor') {
                    actionBadge = `
                        <span class="badge bg-danger">
                            <i class="fas fa-truck me-1"></i>
                            Sent to Vendor
                        </span>
                    `;
                }

                let oldNewInfo = '';

                if (h.old_asset || h.new_asset) {

                    function formatAsset(asset) {

                        if (!asset) {
                            return '-';
                        }

                        // New format: object containing
                        // serial number, model and vendor.
                        if (typeof asset === 'object') {

                            const model =
                                asset.brand_model ||
                                asset.model ||
                                '-';

                            const serial =
                                asset.serial_number ||
                                '-';

                            const vendor =
                                asset.vendor ||
                                '';

                            return `
                                <div>
                                    <strong>
                                        ${escapeHtml(model)}
                                    </strong>

                                    <span class="text-muted">
                                        | Serial:
                                        ${escapeHtml(serial)}
                                    </span>
                                </div>

                                ${
                                    vendor
                                        ? `
                                            <div class="text-muted">
                                                Vendor:
                                                ${escapeHtml(vendor)}
                                            </div>
                                          `
                                        : ''
                                }
                            `;
                        }

                        // Old format
                        return escapeHtml(asset);
                    }

                    oldNewInfo = `
                        <div class="mt-2 small">

                            ${
                                h.old_asset
                                    ? `
                                        <div>
                                            <strong>
                                                Old Laptop:
                                            </strong>

                                            ${formatAsset(
                                                h.old_asset
                                            )}
                                        </div>
                                      `
                                    : ''
                            }

                            ${
                                h.new_asset
                                    ? `
                                        <div class="mt-1">
                                            <strong>
                                                New Laptop:
                                            </strong>

                                            ${formatAsset(
                                                h.new_asset
                                            )}
                                        </div>
                                      `
                                    : ''
                            }

                        </div>
                    `;
                }

                const row = `
                    <tr>

                        <td>
                            <small class="text-muted">
                                ${escapeHtml(
                                    h.event_date ||
                                    h.timestamp ||
                                    '-'
                                )}
                            </small>
                        </td>

                        <td>
                            ${actionBadge}
                        </td>

                        <td>
                            <strong>
                                ${escapeHtml(
                                    h.employee_name || '-'
                                )}
                            </strong>
                        </td>

                        <td>
                            ${escapeHtml(
                                h.notes || ''
                            )}

                            ${oldNewInfo}
                        </td>

                        <td>
                            <small class="text-secondary">
                                ${escapeHtml(
                                    h.performed_by || '-'
                                )}
                            </small>
                        </td>

                    </tr>
                `;

                histTableBody.insertAdjacentHTML(
                    'beforeend',
                    row
                );

            });
        }

        // Open modal
        const modalElement =
            document.getElementById(
                'assetHistoryModal'
            );

        if (!modalElement) {
            throw new Error(
                'assetHistoryModal not found.'
            );
        }

        const historyModal =
            bootstrap.Modal.getOrCreateInstance(
                modalElement
            );

        historyModal.show();

    })
    .catch(function(error) {

        console.error(
            'Error fetching asset history:',
            error
        );

        alert(
            'Unable to open Asset History. Please check the Flask terminal for the error.'
        );
    });
});
