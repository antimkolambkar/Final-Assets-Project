// 4. Asset History Modal Handler
// Event delegation: works even when asset buttons are dynamically rendered.
document.addEventListener('click', function (event) {

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
        method: 'GET',
        headers: {
            'Accept': 'application/json'
        }
    })
    .then(function (response) {

        if (!response.ok) {
            throw new Error(
                `History request failed: ${response.status}`
            );
        }

        return response.json();
    })
    .then(function (data) {

        console.log('Asset history response:', data);

        // --------------------------------------------------
        // HEADER INFORMATION
        // --------------------------------------------------

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
                data.assigned_user || 'Unassigned';
        }

        if (vendorElement) {
            vendorElement.textContent =
                data.vendor || '-';
        }

        // --------------------------------------------------
        // HISTORY TABLE
        // --------------------------------------------------

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

        // No history
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

            history.forEach(function (h) {

                // --------------------------------------------------
                // ACTION BADGE
                // --------------------------------------------------

                let actionBadge = `
                    <span class="badge bg-secondary">
                        ${safeText(h.action || '-')}
                    </span>
                `;

                if (h.action === 'Assigned') {

                    actionBadge = `
                        <span class="badge bg-primary">
                            Assigned
                        </span>
                    `;
                }

                else if (h.action === 'Returned') {

                    actionBadge = `
                        <span class="badge bg-success">
                            Returned
                        </span>
                    `;
                }

                else if (h.action === 'Replaced') {

                    actionBadge = `
                        <span class="badge bg-warning text-dark">
                            <i class="fas fa-sync me-1"></i>
                            Replaced
                        </span>
                    `;
                }

                else if (
                    h.action === 'Send Back to Vendor'
                ) {

                    actionBadge = `
                        <span class="badge bg-danger">
                            <i class="fas fa-truck me-1"></i>
                            Sent to Vendor
                        </span>
                    `;
                }

                else if (
                    h.action === 'Stock'
                ) {

                    actionBadge = `
                        <span class="badge bg-success">
                            Stock
                        </span>
                    `;
                }

                // --------------------------------------------------
                // OLD / NEW LAPTOP DETAILS
                // --------------------------------------------------

                let oldNewInfo = '';

                if (h.old_asset || h.new_asset) {

                    function formatAsset(asset) {

                        if (!asset) {
                            return '-';
                        }

                        // Object format
                        if (
                            typeof asset === 'object'
                        ) {

                            const brandModel =
                                asset.brand_model ||
                                asset.model ||
                                '-';

                            const serial =
                                asset.serial_number ||
                                '-';

                            const vendor =
                                asset.vendor ||
                                '';

                            let html = `
                                <div class="border rounded p-2 mb-1 bg-light">

                                    <div>
                                        <strong>
                                            ${safeText(
                                                brandModel
                                            )}
                                        </strong>
                                    </div>

                                    <div class="text-muted">
                                        Serial Number:
                                        <strong>
                                            ${safeText(
                                                serial
                                            )}
                                        </strong>
                                    </div>
                            `;

                            if (vendor) {

                                html += `
                                    <div class="text-muted">
                                        Vendor:
                                        <strong>
                                            ${safeText(
                                                vendor
                                            )}
                                        </strong>
                                    </div>
                                `;
                            }

                            html += `
                                </div>
                            `;

                            return html;
                        }

                        // String format
                        return `
                            <div class="text-muted">
                                ${safeText(asset)}
                            </div>
                        `;
                    }

                    oldNewInfo = `
                        <div class="mt-2">

                            ${
                                h.old_asset
                                    ? `
                                        <div class="mb-2">
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
                                        <div class="mb-2">
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

                // --------------------------------------------------
                // VENDOR INFORMATION
                // --------------------------------------------------

                let vendorInfo = '';

                if (
                    h.vendor ||
                    h.vendor_name
                ) {

                    vendorInfo = `
                        <div class="mt-1">
                            <strong>Vendor:</strong>
                            ${safeText(
                                h.vendor ||
                                h.vendor_name
                            )}
                        </div>
                    `;
                }

                // --------------------------------------------------
                // VENDOR REASON
                // --------------------------------------------------

                let vendorReason = '';

                if (
                    h.vendor_return_reason
                ) {

                    vendorReason = `
                        <div class="mt-1">
                            <strong>
                                Vendor Reason:
                            </strong>
                            ${safeText(
                                h.vendor_return_reason
                            )}
                        </div>
                    `;
                }

                // --------------------------------------------------
                // EVENT DATE
                // --------------------------------------------------

                const eventDate =
                    h.event_date ||
                    h.timestamp ||
                    '-';

                // --------------------------------------------------
                // ROW
                // --------------------------------------------------

                const row = `
                    <tr>

                        <!-- Event Date -->
                        <td>
                            <small class="text-muted">
                                ${safeText(eventDate)}
                            </small>
                        </td>

                        <!-- Action -->
                        <td>
                            ${actionBadge}
                        </td>

                        <!-- Employee -->
                        <td>
                            <strong>
                                ${safeText(
                                    h.employee_name ||
                                    '-'
                                )}
                            </strong>
                        </td>

                        <!-- Notes -->
                        <td>

                            ${
                                h.notes
                                    ? `
                                        <div>
                                            ${safeText(
                                                h.notes
                                            )}
                                        </div>
                                      `
                                    : ''
                            }

                            ${oldNewInfo}

                            ${vendorInfo}

                            ${vendorReason}

                        </td>

                        <!-- Logged By -->
                        <td>
                            <small class="text-secondary">
                                ${safeText(
                                    h.performed_by ||
                                    '-'
                                )}
                            </small>
                        </td>

                        <!-- Recorded At -->
                        <td>
                            <small class="text-muted">
                                ${safeText(
                                    h.timestamp ||
                                    '-'
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

        // --------------------------------------------------
        // OPEN MODAL
        // --------------------------------------------------

        const modalElement =
            document.getElementById(
                'assetHistoryModal'
            );

        if (!modalElement) {

            throw new Error(
                'assetHistoryModal not found.'
            );
        }

        if (
            typeof bootstrap === 'undefined' ||
            !bootstrap.Modal
        ) {

            throw new Error(
                'Bootstrap JavaScript is not loaded.'
            );
        }

        const historyModal =
            bootstrap.Modal.getOrCreateInstance(
                modalElement
            );

        historyModal.show();

    })
    .catch(function (error) {

        console.error(
            'Asset History Error:',
            error
        );

        alert(
            'Unable to open Asset History. Please press F12 and check the Console for the error.'
        );
    });
});


// --------------------------------------------------
// SAFE HTML TEXT FUNCTION
// Prevents escapeHtml undefined error
// --------------------------------------------------

function safeText(value) {

    if (
        value === null ||
        value === undefined
    ) {
        return '';
    }

    const div =
        document.createElement('div');

    div.textContent =
        String(value);

    return div.innerHTML;
}
