// ============================================================================
// SUPER_ADMIN.JS - Lógica del Panel de Super Administrador
// ============================================================================

let currentClinicId = null;
let credentialsData = null;
let currentAdminUserId = null; // ✨ NUEVO: Para almacenar el ID del admin al resetear contraseña
let passwordResetData = null;  // ✨ NUEVO: Para almacenar datos del reset de contraseña

// ============================================================================
// INICIALIZACIÓN
// ============================================================================
document.addEventListener('DOMContentLoaded', function() {
    loadGlobalStatistics();
    loadClinics();
});

// ============================================================================
// CARGAR ESTADÍSTICAS GLOBALES
// ============================================================================
function loadGlobalStatistics() {
    fetch('/super-admin/api/stats/global')
        .then(response => response.json())
        .then(data => {
            // Total Clínicas
            document.getElementById('totalClinics').textContent = data.clinics.total || 0;
            document.getElementById('clinicsTrend').textContent = data.clinics.active || 0;
            
            // Total Usuarios
            document.getElementById('totalUsers').textContent = data.users.total || 0;
            document.getElementById('usersTrend').textContent = data.users.by_role.professional || 0;
            
            // Total Citas
            document.getElementById('totalAppointments').textContent = data.appointments.total || 0;
            document.getElementById('appointmentsTrend').textContent = data.appointments.last_30_days || 0;
            
            // Total Pacientes
            document.getElementById('totalPatients').textContent = data.patients.total || 0;
            
            // Animar contadores
            animateStatsCounters();
        })
        .catch(error => {
            console.error('Error loading statistics:', error);
            showToast('Error al cargar estadísticas', 'danger');
        });
}

// ============================================================================
// ANIMAR CONTADORES
// ============================================================================
function animateStatsCounters() {
    document.querySelectorAll('.stat-value-large').forEach(el => {
        const target = parseInt(el.textContent) || 0;
        let current = 0;
        const increment = Math.max(1, Math.ceil(target / 30));
        const duration = 1000;
        const stepTime = duration / (target / increment);
        
        const timer = setInterval(() => {
            current += increment;
            if (current >= target) {
                el.textContent = target;
                clearInterval(timer);
            } else {
                el.textContent = Math.floor(current);
            }
        }, stepTime);
    });
}

// ============================================================================
// CARGAR LISTA DE CLÍNICAS
// ============================================================================
function loadClinics() {
    const tbody = document.getElementById('clinicsTableBody');
    tbody.innerHTML = '<tr><td colspan="8" class="text-center py-4"><div class="spinner-border text-primary"></div></td></tr>';
    
    fetch('/super-admin/api/clinics')
        .then(response => response.json())
        .then(clinics => {
            if (clinics.length === 0) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="8">
                            <div class="empty-clinics">
                                <i class="fas fa-hospital-alt"></i>
                                <h5>No hay clínicas registradas</h5>
                                <p class="text-muted">Haz clic en "Nueva Clínica" para comenzar</p>
                            </div>
                        </td>
                    </tr>
                `;
                return;
            }
            
            tbody.innerHTML = '';
            
            clinics.forEach(clinic => {
                const row = document.createElement('tr');
                
                // Logo o placeholder
                const logoHtml = clinic.logo_url 
                    ? `<img src="${clinic.logo_url}" class="clinic-logo" alt="${clinic.name}">`
                    : `<div class="clinic-logo-placeholder">${clinic.name.charAt(0).toUpperCase()}</div>`;
                
                // Fecha de creación formateada
                const createdDate = new Date(clinic.created_at).toLocaleDateString('es-PE', {
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit'
                });
                
                // Badge de plan
                const planBadge = `<span class="badge-plan ${clinic.plan}">${clinic.plan.toUpperCase()}</span>`;
                
                // Status badge
                const statusBadge = clinic.is_active 
                    ? '<span class="status-badge active">Activa</span>'
                    : '<span class="status-badge inactive">Suspendida</span>';
                
                // Botones de acción
                const toggleText = clinic.is_active ? 'Suspender' : 'Activar';
                const toggleIcon = clinic.is_active ? 'fa-ban' : 'fa-check';
                const toggleClass = clinic.is_active ? 'btn-warning' : 'btn-success';
                
                row.innerHTML = `
                    <td><strong>#${clinic.id}</strong></td>
                    <td>
                        <div class="clinic-name-cell">
                            ${logoHtml}
                            <div class="clinic-info">
                                <h6 class="mb-0">${clinic.name}</h6>
                                <small class="text-muted">Creada: ${createdDate}</small>
                            </div>
                        </div>
                    </td>
                    <td>${planBadge}</td>
                    <td><span class="badge bg-primary">${clinic.users_count || 0}</span></td>
                    <td><span class="badge bg-info">${clinic.patients_count || 0}</span></td>
                    <td><span class="badge bg-success">${clinic.appointments_count || 0}</span></td>
                    <td>${statusBadge}</td>
                    <td>
                        <div class="action-buttons">
                            <button class="btn btn-action-sm btn-info" onclick="viewClinic(${clinic.id})" title="Ver detalles">
                                <i class="fas fa-eye"></i>
                            </button>
                            <button class="btn btn-action-sm btn-primary" onclick="editClinic(${clinic.id})" title="Editar">
                                <i class="fas fa-edit"></i>
                            </button>
                            <button class="btn btn-action-sm ${toggleClass}" onclick="toggleClinicStatus(${clinic.id})" title="${toggleText}">
                                <i class="fas ${toggleIcon}"></i>
                            </button>
                            <button class="btn btn-action-sm btn-danger" onclick="deleteClinic(${clinic.id}, '${clinic.name}')" title="Eliminar">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    </td>
                `;
                
                tbody.appendChild(row);
            });
        })
        .catch(error => {
            console.error('Error loading clinics:', error);
            tbody.innerHTML = `
                <tr>
                    <td colspan="8" class="text-center text-danger py-4">
                        <i class="fas fa-exclamation-triangle me-2"></i>
                        Error al cargar clínicas
                    </td>
                </tr>
            `;
        });
}

// ============================================================================
// MODAL: CREAR CLÍNICA (SIN CAMBIOS)
// ============================================================================
function openCreateClinicModal() {
    const modal = new bootstrap.Modal(document.getElementById('createClinicModal'));
    document.getElementById('createClinicForm').reset();
    
    // Establecer color por defecto
    document.getElementById('clinic_theme_color').value = '#4F46E5';
    
    modal.show();
}

// ============================================================================
// GUARDAR CLÍNICA (SIN CAMBIOS)
// ============================================================================
function saveClinic() {
    // Obtener datos del formulario
    const clinicName = document.getElementById('clinic_name').value.trim();
    const clinicPhone = document.getElementById('clinic_phone').value.trim();
    const clinicEmail = document.getElementById('clinic_email').value.trim();
    const clinicAddress = document.getElementById('clinic_address').value.trim();
    const clinicPlan = document.getElementById('clinic_plan').value;
    const clinicThemeColor = document.getElementById('clinic_theme_color').value;
    
    const adminUsername = document.getElementById('admin_username').value.trim();
    const adminEmail = document.getElementById('admin_email').value.trim();
    const adminFullName = document.getElementById('admin_full_name').value.trim();
    const adminPhone = document.getElementById('admin_phone').value.trim();
    const adminPassword = document.getElementById('admin_password').value;
    
    // Validaciones
    if (!clinicName) {
        showToast('El nombre de la clínica es requerido', 'warning');
        return;
    }
    
    if (!adminUsername || !adminEmail || !adminPassword) {
        showToast('Completa todos los campos requeridos del administrador', 'warning');
        return;
    }
    
    if (adminPassword.length < 6) {
        showToast('La contraseña debe tener al menos 6 caracteres', 'warning');
        return;
    }
    
    // Validar formato de email
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(adminEmail)) {
        showToast('El email del administrador no es válido', 'warning');
        return;
    }
    
    // Preparar datos
    const formData = {
        // Clínica
        name: clinicName,
        phone: clinicPhone || null,
        email: clinicEmail || null,
        address: clinicAddress || null,
        plan: clinicPlan,
        theme_color: clinicThemeColor,
        
        // Administrador
        admin_username: adminUsername,
        admin_email: adminEmail,
        admin_full_name: adminFullName || adminUsername,
        admin_phone: adminPhone || null,
        admin_password: adminPassword
    };
    
    // Deshabilitar botón
    const saveBtn = document.querySelector('#createClinicModal .btn-success');
    const originalText = saveBtn.innerHTML;
    saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Creando...';
    saveBtn.disabled = true;
    
    // Enviar petición
    fetch('/super-admin/api/clinics', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
    })
    .then(response => response.json().then(data => ({ ok: response.ok, data })))
    .then(({ok, data}) => {
        if (!ok) {
            showToast(data.error || 'Error al crear clínica', 'danger');
            throw new Error(data.error);
        }
        
        // Éxito
        credentialsData = {
            clinic_name: data.clinic.name,
            admin_username: data.admin.username,
            admin_email: data.admin.email,
            admin_password: data.admin.password
        };
        
        // Cerrar modal de creación
        const createModal = bootstrap.Modal.getInstance(document.getElementById('createClinicModal'));
        createModal.hide();
        
        // Recargar datos
        loadClinics();
        loadGlobalStatistics();
        
        // Mostrar modal de credenciales
        showCredentialsModal();
        
        showToast('✅ Clínica creada exitosamente', 'success');
    })
    .catch(error => {
        console.error('Error saving clinic:', error);
    })
    .finally(() => {
        saveBtn.innerHTML = originalText;
        saveBtn.disabled = false;
    });
}

// ============================================================================
// MODAL: MOSTRAR CREDENCIALES (SIN CAMBIOS)
// ============================================================================
function showCredentialsModal() {
    if (!credentialsData) return;
    
    const modal = new bootstrap.Modal(document.getElementById('credentialsModal'));
    const display = document.getElementById('credentialsDisplay');
    
    display.innerHTML = `
        <div class="card">
            <div class="card-body">
                <h6 class="card-title mb-3">
                    <i class="fas fa-hospital me-2"></i>
                    Clínica: <strong>${credentialsData.clinic_name}</strong>
                </h6>
                <hr>
                <div class="mb-2">
                    <strong><i class="fas fa-user me-2"></i>Username:</strong>
                    <code class="ms-2">${credentialsData.admin_username}</code>
                </div>
                <div class="mb-2">
                    <strong><i class="fas fa-envelope me-2"></i>Email:</strong>
                    <code class="ms-2">${credentialsData.admin_email}</code>
                </div>
                <div class="mb-2">
                    <strong><i class="fas fa-lock me-2"></i>Password:</strong>
                    <code class="ms-2">${credentialsData.admin_password}</code>
                </div>
            </div>
        </div>
    `;
    
    modal.show();
}

// ============================================================================
// COPIAR CREDENCIALES (SIN CAMBIOS)
// ============================================================================
function copyCredentials() {
    if (!credentialsData) return;
    
    const text = `
Clínica: ${credentialsData.clinic_name}
Username: ${credentialsData.admin_username}
Email: ${credentialsData.admin_email}
Password: ${credentialsData.admin_password}
    `.trim();
    
    navigator.clipboard.writeText(text).then(() => {
        showToast('📋 Credenciales copiadas al portapapeles', 'success');
    }).catch(err => {
        console.error('Error al copiar:', err);
        showToast('Error al copiar credenciales', 'danger');
    });
}
// ============================================================================
// ✨ NUEVO: EDITAR CLÍNICA
// ============================================================================
function editClinic(id) {
    currentClinicId = id;
    
    // Mostrar loading en el botón mientras carga
    const allEditButtons = document.querySelectorAll('.btn-action-sm.btn-primary');
    allEditButtons.forEach(btn => {
        if (btn.onclick && btn.onclick.toString().includes(`editClinic(${id})`)) {
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
        }
    });
    
    fetch(`/super-admin/api/clinics/${id}`)
        .then(response => response.json())
        .then(clinic => {
            // Llenar campos del formulario
            document.getElementById('edit_clinic_id').value = clinic.id;
            document.getElementById('edit_clinic_name').value = clinic.name;
            document.getElementById('edit_clinic_phone').value = clinic.phone || '';
            document.getElementById('edit_clinic_email').value = clinic.email || '';
            document.getElementById('edit_clinic_address').value = clinic.address || '';
            document.getElementById('edit_clinic_logo_url').value = clinic.logo_url || '';
            document.getElementById('edit_clinic_plan').value = clinic.plan;
            document.getElementById('edit_clinic_theme_color').value = clinic.theme_color;
            
            // Actualizar preview del logo
            const logoPreview = document.getElementById('edit_logo_preview');
            if (clinic.logo_url) {
                logoPreview.src = clinic.logo_url;
                logoPreview.onerror = function() {
                    this.src = 'https://via.placeholder.com/150x150?text=URL+Invalida';
                };
            } else {
                logoPreview.src = 'https://via.placeholder.com/150x150?text=Sin+Logo';
            }
            
            // Actualizar preview del color
            document.getElementById('edit_color_preview').style.backgroundColor = clinic.theme_color;
            
            // ✨ Buscar el CLINIC_ADMIN de esta clínica
            const clinicAdmin = clinic.users ? clinic.users.find(u => u.role === 'CLINIC_ADMIN') : null;
            
            if (clinicAdmin) {
                // Mostrar información del admin
                document.getElementById('edit_admin_username').textContent = clinicAdmin.username;
                document.getElementById('edit_admin_email').textContent = clinicAdmin.email;
                document.getElementById('edit_admin_full_name').textContent = clinicAdmin.full_name || '-';
                document.getElementById('edit_admin_user_id').value = clinicAdmin.id;
                
                // Habilitar botón de resetear contraseña
                document.getElementById('btnResetAdminPassword').disabled = false;
                currentAdminUserId = clinicAdmin.id;
            } else {
                // No hay admin (caso raro, pero manejarlo)
                document.getElementById('edit_admin_username').textContent = 'No asignado';
                document.getElementById('edit_admin_email').textContent = '-';
                document.getElementById('edit_admin_full_name').textContent = '-';
                document.getElementById('edit_admin_user_id').value = '';
                
                // Deshabilitar botón de resetear contraseña
                document.getElementById('btnResetAdminPassword').disabled = true;
                currentAdminUserId = null;
            }
            
            // Abrir modal
            const modal = new bootstrap.Modal(document.getElementById('editClinicModal'));
            modal.show();
            
            // Restaurar botones de edición
            allEditButtons.forEach(btn => {
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-edit"></i>';
            });
        })
        .catch(error => {
            console.error('Error loading clinic:', error);
            showToast('Error al cargar datos de la clínica', 'danger');
            
            // Restaurar botones en caso de error
            allEditButtons.forEach(btn => {
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-edit"></i>';
            });
        });
}

// ============================================================================
// ✨ NUEVO: GUARDAR CAMBIOS DE CLÍNICA
// ============================================================================
function saveClinicChanges() {
    const clinicId = document.getElementById('edit_clinic_id').value;
    const name = document.getElementById('edit_clinic_name').value.trim();
    const phone = document.getElementById('edit_clinic_phone').value.trim();
    const email = document.getElementById('edit_clinic_email').value.trim();
    const address = document.getElementById('edit_clinic_address').value.trim();
    const logoUrl = document.getElementById('edit_clinic_logo_url').value.trim();
    const plan = document.getElementById('edit_clinic_plan').value;
    const themeColor = document.getElementById('edit_clinic_theme_color').value;
    
    // Validaciones
    if (!name) {
        showToast('El nombre de la clínica es requerido', 'warning');
        return;
    }
    
    if (email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(email)) {
            showToast('El email no es válido', 'warning');
            return;
        }
    }
    
    // Preparar datos
    const formData = {
        name: name,
        phone: phone || null,
        email: email || null,
        address: address || null,
        logo_url: logoUrl || null,
        plan: plan,
        theme_color: themeColor
    };
    
    // Deshabilitar botón
    const saveBtn = document.querySelector('#editClinicModal .btn-success');
    const originalText = saveBtn.innerHTML;
    saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Guardando...';
    saveBtn.disabled = true;
    
    // Enviar petición
    fetch(`/super-admin/api/clinics/${clinicId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
    })
    .then(response => response.json().then(data => ({ ok: response.ok, data })))
    .then(({ok, data}) => {
        if (!ok) {
            showToast(data.error || 'Error al guardar cambios', 'danger');
            throw new Error(data.error);
        }
        
        // Éxito
        showToast('✅ Clínica actualizada exitosamente', 'success');
        
        // Cerrar modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('editClinicModal'));
        modal.hide();
        
        // Recargar tabla de clínicas
        loadClinics();
        loadGlobalStatistics();
    })
    .catch(error => {
        console.error('Error saving clinic changes:', error);
    })
    .finally(() => {
        saveBtn.innerHTML = originalText;
        saveBtn.disabled = false;
    });
}

// ============================================================================
// ✨ NUEVO: RESETEAR CONTRASEÑA DEL ADMINISTRADOR
// ============================================================================
function resetClinicAdminPassword() {
    const adminUserId = document.getElementById('edit_admin_user_id').value;
    const adminUsername = document.getElementById('edit_admin_username').textContent;
    const adminEmail = document.getElementById('edit_admin_email').textContent;
    
    if (!adminUserId) {
        showToast('No se puede resetear: administrador no encontrado', 'danger');
        return;
    }
    
    // Confirmación
    const confirmMessage = `¿Estás seguro de resetear la contraseña de "${adminUsername}"?\n\nSe generará una contraseña temporal que deberás compartir con el administrador.`;
    
    if (!confirm(confirmMessage)) {
        return;
    }
    
    // Deshabilitar botón
    const resetBtn = document.getElementById('btnResetAdminPassword');
    const originalText = resetBtn.innerHTML;
    resetBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Reseteando...';
    resetBtn.disabled = true;
    
    // Enviar petición al backend
    fetch(`/super-admin/api/users/${adminUserId}/reset-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})  // El backend genera la contraseña automáticamente
    })
    .then(response => response.json().then(data => ({ ok: response.ok, data })))
    .then(({ok, data}) => {
        if (!ok) {
            showToast(data.error || 'Error al resetear contraseña', 'danger');
            throw new Error(data.error);
        }
        
        // Éxito - Guardar datos para mostrar en el modal
        passwordResetData = {
            username: data.username,
            email: data.email,
            new_password: data.new_password
        };
        
        // Cerrar modal de edición
        const editModal = bootstrap.Modal.getInstance(document.getElementById('editClinicModal'));
        editModal.hide();
        
        // Mostrar modal de contraseña reseteada
        showPasswordResetModal();
        
        showToast('✅ Contraseña reseteada exitosamente', 'success');
    })
    .catch(error => {
        console.error('Error resetting password:', error);
    })
    .finally(() => {
        resetBtn.innerHTML = originalText;
        resetBtn.disabled = false;
    });
}

// ============================================================================
// ✨ NUEVO: MOSTRAR MODAL DE CONTRASEÑA RESETEADA
// ============================================================================
function showPasswordResetModal() {
    if (!passwordResetData) return;
    
    const modal = new bootstrap.Modal(document.getElementById('passwordResetModal'));
    const display = document.getElementById('passwordResetDisplay');
    
    display.innerHTML = `
        <h6 class="mb-3">
            <i class="fas fa-user-shield me-2"></i>
            Administrador: <strong>${passwordResetData.username}</strong>
        </h6>
        <hr>
        <div class="mb-2">
            <strong><i class="fas fa-user me-2"></i>Username:</strong>
            <code class="ms-2">${passwordResetData.username}</code>
        </div>
        <div class="mb-2">
            <strong><i class="fas fa-envelope me-2"></i>Email:</strong>
            <code class="ms-2">${passwordResetData.email}</code>
        </div>
        <div class="mb-2">
            <strong><i class="fas fa-key me-2"></i>Nueva Contraseña:</strong>
            <code class="ms-2 text-danger fw-bold">${passwordResetData.new_password}</code>
        </div>
    `;
    
    modal.show();
}

// ============================================================================
// ✨ NUEVO: COPIAR CONTRASEÑA RESETEADA
// ============================================================================
function copyResetPassword() {
    if (!passwordResetData) return;
    
    const text = `
Administrador: ${passwordResetData.username}
Email: ${passwordResetData.email}
Nueva Contraseña: ${passwordResetData.new_password}

⚠️ IMPORTANTE: Esta es una contraseña temporal. El administrador debe cambiarla después del primer inicio de sesión.
    `.trim();
    
    navigator.clipboard.writeText(text).then(() => {
        showToast('📋 Contraseña copiada al portapapeles', 'success');
    }).catch(err => {
        console.error('Error al copiar:', err);
        showToast('Error al copiar la contraseña', 'danger');
    });
}

// ============================================================================
// VER DETALLES DE CLÍNICA (SIN CAMBIOS)
// ============================================================================
function viewClinic(id) {
    fetch(`/super-admin/api/clinics/${id}`)
        .then(response => response.json())
        .then(clinic => {
            const stats = clinic.statistics;
            
            const modalHtml = `
                <div class="modal fade" id="viewClinicModal" tabindex="-1">
                    <div class="modal-dialog modal-lg">
                        <div class="modal-content">
                            <div class="modal-header bg-info text-white">
                                <h5 class="modal-title">
                                    <i class="fas fa-hospital me-2"></i>${clinic.name}
                                </h5>
                                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                            </div>
                            <div class="modal-body">
                                <div class="row">
                                    <div class="col-md-6">
                                        <h6 class="mb-3">Información General</h6>
                                        <p><strong>ID:</strong> #${clinic.id}</p>
                                        <p><strong>Teléfono:</strong> ${clinic.phone || 'N/A'}</p>
                                        <p><strong>Email:</strong> ${clinic.email || 'N/A'}</p>
                                        <p><strong>Dirección:</strong> ${clinic.address || 'N/A'}</p>
                                        <p><strong>Plan:</strong> <span class="badge-plan ${clinic.plan}">${clinic.plan.toUpperCase()}</span></p>
                                        <p><strong>Estado:</strong> ${clinic.is_active ? '<span class="status-badge active">Activa</span>' : '<span class="status-badge inactive">Suspendida</span>'}</p>
                                        <p><strong>Creada:</strong> ${new Date(clinic.created_at).toLocaleDateString('es-PE')}</p>
                                    </div>
                                    <div class="col-md-6">
                                        <h6 class="mb-3">Estadísticas</h6>
                                        <p><strong>Usuarios:</strong> ${stats.users.total}</p>
                                        <p class="ms-3 text-muted">• Administradores: ${stats.users.admins}</p>
                                        <p class="ms-3 text-muted">• Profesionales: ${stats.users.professionals}</p>
                                        <p><strong>Pacientes:</strong> ${stats.patients}</p>
                                        <p><strong>Servicios:</strong> ${stats.services}</p>
                                        <p><strong>Citas:</strong> ${stats.appointments.total}</p>
                                        <p class="ms-3 text-muted">• Programadas: ${stats.appointments.programadas}</p>
                                        <p class="ms-3 text-muted">• Completadas: ${stats.appointments.completadas}</p>
                                        <p class="ms-3 text-muted">• Canceladas: ${stats.appointments.canceladas}</p>
                                    </div>
                                </div>
                                
                                ${clinic.users && clinic.users.length > 0 ? `
                                    <hr>
                                    <h6 class="mb-3">Usuarios de la Clínica</h6>
                                    <div class="table-responsive">
                                        <table class="table table-sm">
                                            <thead>
                                                <tr>
                                                    <th>Usuario</th>
                                                    <th>Email</th>
                                                    <th>Rol</th>
                                                    <th>Estado</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                ${clinic.users.map(user => `
                                                    <tr>
                                                        <td>${user.username}</td>
                                                        <td>${user.email}</td>
                                                        <td><span class="badge bg-primary">${user.role}</span></td>
                                                        <td>${user.is_active ? '<span class="badge bg-success">Activo</span>' : '<span class="badge bg-danger">Inactivo</span>'}</td>
                                                    </tr>
                                                `).join('')}
                                            </tbody>
                                        </table>
                                    </div>
                                ` : ''}
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cerrar</button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            
            // Eliminar modal anterior si existe
            const existingModal = document.getElementById('viewClinicModal');
            if (existingModal) {
                existingModal.remove();
            }
            
            // Agregar nuevo modal al body
            document.body.insertAdjacentHTML('beforeend', modalHtml);
            
            // Mostrar modal
            const modal = new bootstrap.Modal(document.getElementById('viewClinicModal'));
            modal.show();
            
            // Limpiar modal al cerrar
            document.getElementById('viewClinicModal').addEventListener('hidden.bs.modal', function() {
                this.remove();
            });
        })
        .catch(error => {
            console.error('Error loading clinic details:', error);
            showToast('Error al cargar detalles de la clínica', 'danger');
        });
}

// ============================================================================
// TOGGLE STATUS (ACTIVAR/SUSPENDER) - SIN CAMBIOS
// ============================================================================
function toggleClinicStatus(id) {
    // Obtener datos actuales de la clínica
    fetch(`/super-admin/api/clinics/${id}`)
        .then(response => response.json())
        .then(clinic => {
            const action = clinic.is_active ? 'suspender' : 'activar';
            const actionUpper = clinic.is_active ? 'Suspender' : 'Activar';
            
            const message = clinic.is_active 
                ? `¿Estás seguro de suspender la clínica "${clinic.name}"?\n\nLos usuarios no podrán iniciar sesión hasta que se reactive.`
                : `¿Activar la clínica "${clinic.name}"?\n\nLos usuarios podrán volver a iniciar sesión.`;
            
            if (!confirm(message)) {
                return;
            }
            
            // Enviar petición
            fetch(`/super-admin/api/clinics/${id}/toggle-status`, {
                method: 'POST'
            })
            .then(response => response.json())
            .then(data => {
                showToast(data.message || `Clínica ${action}da exitosamente`, 'success');
                loadClinics();
                loadGlobalStatistics();
            })
            .catch(error => {
                console.error('Error toggling clinic status:', error);
                showToast(`Error al ${action} la clínica`, 'danger');
            });
        })
        .catch(error => {
            console.error('Error loading clinic:', error);
            showToast('Error al obtener información de la clínica', 'danger');
        });
}

// ============================================================================
// ELIMINAR CLÍNICA - SIN CAMBIOS
// ============================================================================
function deleteClinic(id, name) {
    // Paso 1: Obtener estadísticas para mostrar al usuario
    fetch(`/super-admin/api/clinics/${id}`)
        .then(response => response.json())
        .then(clinic => {
            const stats = clinic.statistics;
            
            // Paso 2: Primera confirmación con estadísticas
            const confirmMessage = `
⚠️ ADVERTENCIA: Esta acción es IRREVERSIBLE

Se eliminará permanentemente la clínica "${name}" y TODOS sus datos:

- ${stats.users.total} usuario(s)
- ${stats.patients} paciente(s)
- ${stats.appointments.total} cita(s)
- ${stats.services} servicio(s)

¿Estás ABSOLUTAMENTE seguro de continuar?
            `.trim();
            
            if (!confirm(confirmMessage)) {
                return;
            }
            
            // Paso 3: Segunda confirmación - escribir "ELIMINAR"
            const confirmation = prompt(
                `Para confirmar, escribe exactamente: ELIMINAR\n\n(Todo en mayúsculas)`
            );
            
            if (confirmation !== 'ELIMINAR') {
                if (confirmation !== null) {
                    showToast('Eliminación cancelada. Texto incorrecto.', 'warning');
                }
                return;
            }
            
            // Paso 4: Proceder con eliminación
            fetch(`/super-admin/api/clinics/${id}`, {
                method: 'DELETE'
            })
            .then(response => response.json())
            .then(data => {
                showToast(
                    `✅ Clínica "${name}" eliminada permanentemente. ${data.deleted.appointments} citas eliminadas.`,
                    'success'
                );
                
                // Recargar datos
                loadClinics();
                loadGlobalStatistics();
            })
            .catch(error => {
                console.error('Error deleting clinic:', error);
                showToast('Error al eliminar la clínica', 'danger');
            });
        })
        .catch(error => {
            console.error('Error loading clinic stats:', error);
            showToast('Error al obtener información de la clínica', 'danger');
        });
}

// ============================================================================
// HELPER: TOAST - SIN CAMBIOS
// ============================================================================
function showToast(message, type = 'info') {
    const toastContainer = document.createElement('div');
    toastContainer.style.cssText = `
        position: fixed;
        top: 80px;
        right: 20px;
        z-index: 9999;
        animation: slideInRight 0.3s ease-out;
        max-width: 400px;
    `;
    
    const alertClass = type === 'success' ? 'alert-success' : 
                      type === 'danger' ? 'alert-danger' : 
                      type === 'warning' ? 'alert-warning' : 'alert-info';
    
    const icon = type === 'success' ? 'fa-check-circle' : 
                 type === 'danger' ? 'fa-exclamation-circle' : 
                 type === 'warning' ? 'fa-exclamation-triangle' : 'fa-info-circle';
    
    toastContainer.innerHTML = `
        <div class="alert ${alertClass} alert-dismissible fade show" role="alert">
            <i class="fas ${icon} me-2"></i>${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    document.body.appendChild(toastContainer);
    
    setTimeout(() => {
        toastContainer.style.animation = 'fadeOut 0.3s ease-out';
        setTimeout(() => toastContainer.remove(), 300);
    }, 5000);
}

// ============================================================================
// ANIMACIONES CSS - SIN CAMBIOS
// ============================================================================
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes fadeOut {
        from { opacity: 1; }
        to { opacity: 0; }
    }
`;
document.head.appendChild(style);

// ============================================================================
// EXPORTAR FUNCIONES GLOBALES
// ============================================================================
window.loadClinics = loadClinics;
window.openCreateClinicModal = openCreateClinicModal;
window.saveClinic = saveClinic;
window.copyCredentials = copyCredentials;
window.editClinic = editClinic;                   // ✨ NUEVA
window.saveClinicChanges = saveClinicChanges;     // ✨ NUEVA
window.resetClinicAdminPassword = resetClinicAdminPassword; // ✨ NUEVA
window.copyResetPassword = copyResetPassword;     // ✨ NUEVA
window.viewClinic = viewClinic;
window.toggleClinicStatus = toggleClinicStatus;
window.deleteClinic = deleteClinic;
