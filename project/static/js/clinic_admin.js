// ============================================================================
// CLINIC_ADMIN.JS - Lógica del Panel de Administración de Clínica
// ============================================================================

let clinicCalendar;
let currentProfessionalId = null;
let currentServiceId = null;
let professionalCredentials = null;

// ============================================================================
// INICIALIZACIÓN
// ============================================================================
document.addEventListener('DOMContentLoaded', function() {
    loadDashboardStats();
    loadOverviewData();
});

// ============================================================================
// ESTADÍSTICAS DEL DASHBOARD
// ============================================================================
function loadDashboardStats() {
    fetch('/clinic-admin/api/stats/dashboard')
        .then(response => response.json())
        .then(data => {
            // Profesionales
            document.getElementById('statProfessionals').textContent = 
                data.professionals?.total || 0;
            
            // Pacientes
            document.getElementById('statPatients').textContent = 
                data.patients?.total || 0;
            
            // Citas Programadas
            document.getElementById('statAppointments').textContent = 
                data.appointments?.programadas || 0;
            
            // Servicios Activos
            document.getElementById('statServices').textContent = 
                data.services?.active || 0;
            
            // Animar contadores
            animateStatsCounters();
        })
        .catch(error => {
            console.error('Error loading dashboard stats:', error);
        });
}

// ============================================================================
// ANIMAR CONTADORES
// ============================================================================
function animateStatsCounters() {
    document.querySelectorAll('.stat-value-medium').forEach(el => {
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
// TAB RESUMEN: OVERVIEW DATA
// ============================================================================
function loadOverviewData() {
    // Actividad Reciente
    loadRecentActivity();
    
    // Top Profesionales
    loadTopProfessionals();
    
    // Citas de Hoy
    loadTodayAppointments();
}

function loadRecentActivity() {
    const container = document.getElementById('recentActivityContainer');
    
    fetch('/clinic-admin/api/activity/recent?limit=5')
        .then(response => response.json())
        .then(activities => {
            if (activities.length === 0) {
                container.innerHTML = `
                    <div class="text-center text-muted py-3">
                        <i class="fas fa-info-circle me-2"></i>
                        No hay actividad reciente
                    </div>
                `;
                return;
            }
            
            container.innerHTML = '';
            activities.forEach(activity => {
                const activityDate = new Date(activity.timestamp);
                const activityItem = document.createElement('div');
                activityItem.className = 'mb-3 pb-3 border-bottom';
                activityItem.innerHTML = `
                    <div class="d-flex justify-content-between align-items-start">
                        <div class="flex-grow-1">
                            <div class="mb-1">${activity.description}</div>
                            <small class="text-muted">
                                <i class="far fa-clock me-1"></i>
                                ${activityDate.toLocaleString('es-PE')}
                            </small>
                        </div>
                        <span class="badge bg-primary">
                            ${activity.type}
                        </span>
                    </div>
                `;
                container.appendChild(activityItem);
            });
        })
        .catch(error => {
            console.error('Error loading recent activity:', error);
            container.innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    Error al cargar actividad
                </div>
            `;
        });
}

function loadTopProfessionals() {
    const container = document.getElementById('topProfessionalsContainer');
    
    fetch('/clinic-admin/api/professionals')
        .then(response => response.json())
        .then(professionals => {
            if (professionals.length === 0) {
                container.innerHTML = `
                    <div class="text-center text-muted py-3">
                        <i class="fas fa-info-circle me-2"></i>
                        No hay profesionales registrados
                    </div>
                `;
                return;
            }
            
            // Ordenar por número de citas completadas
            professionals.sort((a, b) => 
                (b.appointments_completadas || 0) - (a.appointments_completadas || 0)
            );
            
            container.innerHTML = '';
            professionals.slice(0, 5).forEach((prof, index) => {
                const profItem = document.createElement('div');
                profItem.className = 'mb-3 pb-3 border-bottom';
                profItem.innerHTML = `
                    <div class="d-flex justify-content-between align-items-center">
                        <div class="d-flex align-items-center gap-2">
                            <div class="badge bg-primary" style="min-width: 30px;">
                                #${index + 1}
                            </div>
                            <div>
                                <div class="fw-bold">${prof.full_name || prof.username}</div>
                                <small class="text-muted">
                                    ${prof.appointments_completadas || 0} citas completadas
                                </small>
                            </div>
                        </div>
                        <span class="badge ${prof.is_active ? 'bg-success' : 'bg-danger'}">
                            ${prof.is_active ? 'Activo' : 'Inactivo'}
                        </span>
                    </div>
                `;
                container.appendChild(profItem);
            });
        })
        .catch(error => {
            console.error('Error loading top professionals:', error);
            container.innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    Error al cargar profesionales
                </div>
            `;
        });
}

function loadTodayAppointments() {
    const container = document.getElementById('todayAppointmentsContainer');
    
    const today = new Date();
    const startStr = today.toISOString().split('T')[0];
    const endDate = new Date(today);
    endDate.setHours(23, 59, 59);
    const endStr = endDate.toISOString();
    
    fetch(`/api/appointments?start=${startStr}&end=${endStr}`)
        .then(response => response.json())
        .then(events => {
            if (events.length === 0) {
                container.innerHTML = `
                    <div class="text-center text-muted py-3">
                        <i class="fas fa-calendar-times me-2"></i>
                        No hay citas programadas para hoy
                    </div>
                `;
                return;
            }
            
            // Ordenar por hora
            events.sort((a, b) => new Date(a.start) - new Date(b.start));
            
            container.innerHTML = '';
            events.forEach(event => {
                const startTime = new Date(event.start).toLocaleTimeString('es-PE', {
                    hour: '2-digit',
                    minute: '2-digit'
                });
                
                const props = event.extendedProps;
                
                const aptItem = document.createElement('div');
                aptItem.className = 'mb-2 p-2 border rounded';
                aptItem.innerHTML = `
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <strong>${startTime}</strong> - ${event.title}
                            <div class="small text-muted">
                                ${props.professional} | ${props.service || 'Sin servicio'}
                            </div>
                        </div>
                        <span class="badge" style="background-color: ${event.backgroundColor}">
                            ${props.status}
                        </span>
                    </div>
                `;
                container.appendChild(aptItem);
            });
        })
        .catch(error => {
            console.error('Error loading today appointments:', error);
            container.innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    Error al cargar citas
                </div>
            `;
        });
}

// ============================================================================
// TAB PROFESIONALES: GESTIÓN
// ============================================================================
function loadProfessionals() {
    const tbody = document.getElementById('professionalsTableBody');
    tbody.innerHTML = '<tr><td colspan="6" class="text-center py-4"><div class="spinner-border text-primary"></div></td></tr>';
    
    fetch('/clinic-admin/api/professionals')
        .then(response => response.json())
        .then(professionals => {
            if (professionals.length === 0) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="6">
                            <div class="empty-state">
                                <i class="fas fa-user-md"></i>
                                <h5>No hay profesionales registrados</h5>
                                <p class="text-muted">Haz clic en "Nuevo Profesional" para comenzar</p>
                            </div>
                        </td>
                    </tr>
                `;
                return;
            }
            
            tbody.innerHTML = '';
            
            professionals.forEach(prof => {
                const row = document.createElement('tr');
                
                // Iniciales del nombre
                const initials = prof.full_name 
                    ? prof.full_name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase()
                    : prof.username.substring(0, 2).toUpperCase();
                
                row.innerHTML = `
                    <td>
                        <div class="user-info-cell">
                            <div class="user-avatar">${initials}</div>
                            <div class="user-details">
                                <h6>${prof.full_name || prof.username}</h6>
                                <small>@${prof.username}</small>
                            </div>
                        </div>
                    </td>
                    <td>${prof.email}</td>
                    <td>${prof.phone || '-'}</td>
                    <td>
                        <span class="badge bg-info">
                            ${prof.appointments_total || 0}
                        </span>
                    </td>
                    <td>
                        <span class="status-badge ${prof.is_active ? 'active' : 'inactive'}">
                            ${prof.is_active ? 'Activo' : 'Inactivo'}
                        </span>
                    </td>
                    <td>
                        <div class="action-buttons">
                            <button class="btn btn-action-sm btn-info" 
                                    onclick="viewProfessionalDetails(${prof.id})" 
                                    title="Ver detalles">
                                <i class="fas fa-eye"></i>
                            </button>
                            <button class="btn btn-action-sm btn-primary" 
                                    onclick="editProfessional(${prof.id})" 
                                    title="Editar">
                                <i class="fas fa-edit"></i>
                            </button>
                            <button class="btn btn-action-sm ${prof.is_active ? 'btn-warning' : 'btn-success'}" 
                                    onclick="toggleProfessionalStatus(${prof.id})" 
                                    title="${prof.is_active ? 'Desactivar' : 'Activar'}">
                                <i class="fas ${prof.is_active ? 'fa-ban' : 'fa-check'}"></i>
                            </button>
                            <button class="btn btn-action-sm btn-secondary" 
                                    onclick="resetProfessionalPassword(${prof.id})" 
                                    title="Resetear contraseña">
                                <i class="fas fa-key"></i>
                            </button>
                            <button class="btn btn-action-sm btn-danger" 
                                    onclick="deleteProfessional(${prof.id}, '${prof.username}')" 
                                    title="Eliminar">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    </td>
                `;
                
                tbody.appendChild(row);
            });
        })
        .catch(error => {
            console.error('Error loading professionals:', error);
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="text-center text-danger py-4">
                        <i class="fas fa-exclamation-triangle me-2"></i>
                        Error al cargar profesionales
                    </td>
                </tr>
            `;
        });
}

function openCreateProfessionalModal() {
    currentProfessionalId = null;
    
    const modal = new bootstrap.Modal(document.getElementById('professionalModal'));
    const form = document.getElementById('professionalForm');
    
    // Resetear formulario
    form.reset();
    document.getElementById('professionalId').value = '';
    
    // Configurar título
    document.getElementById('professionalModalTitle').innerHTML = 
        '<i class="fas fa-user-plus me-2"></i>Nuevo Profesional';
    
    // Mostrar campo de contraseña
    document.getElementById('passwordFieldContainer').style.display = 'block';
    document.getElementById('professionalPassword').required = true;
    
    modal.show();
}

function editProfessional(id) {
    currentProfessionalId = id;
    
    // Obtener datos del profesional
    fetch(`/clinic-admin/api/professionals/${id}`)
        .then(response => response.json())
        .then(prof => {
            const modal = new bootstrap.Modal(document.getElementById('professionalModal'));
            
            // Llenar formulario
            document.getElementById('professionalId').value = prof.id;
            document.getElementById('professionalUsername').value = prof.username;
            document.getElementById('professionalUsername').disabled = true; // No editable
            document.getElementById('professionalEmail').value = prof.email;
            document.getElementById('professionalFullName').value = prof.full_name || '';
            document.getElementById('professionalPhone').value = prof.phone || '';
            
            // Ocultar campo de contraseña al editar
            document.getElementById('passwordFieldContainer').style.display = 'none';
            document.getElementById('professionalPassword').required = false;
            
            // Configurar título
            document.getElementById('professionalModalTitle').innerHTML = 
                '<i class="fas fa-user-edit me-2"></i>Editar Profesional';
            
            modal.show();
        })
        .catch(error => {
            console.error('Error loading professional:', error);
            showToast('Error al cargar datos del profesional', 'danger');
        });
}

function saveProfessional() {
    const professionalId = document.getElementById('professionalId').value;
    const username = document.getElementById('professionalUsername').value.trim();
    const email = document.getElementById('professionalEmail').value.trim();
    const fullName = document.getElementById('professionalFullName').value.trim();
    const phone = document.getElementById('professionalPhone').value.trim();
    const password = document.getElementById('professionalPassword').value;
    
    // Validaciones
    if (!username || !email || !fullName) {
        showToast('Completa todos los campos requeridos', 'warning');
        return;
    }
    
    if (!professionalId && !password) {
        showToast('La contraseña es requerida para nuevos profesionales', 'warning');
        return;
    }
    
    if (password && password.length < 6) {
        showToast('La contraseña debe tener al menos 6 caracteres', 'warning');
        return;
    }
    
    // Validar formato de email
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
        showToast('El email no es válido', 'warning');
        return;
    }
    
    // Preparar datos
    const formData = {
        username: username,
        email: email,
        full_name: fullName,
        phone: phone || null
    };
    
    // Si es creación, incluir contraseña
    if (!professionalId) {
        formData.password = password;
    }
    
    // Determinar URL y método
    const url = professionalId 
        ? `/clinic-admin/api/professionals/${professionalId}` 
        : '/clinic-admin/api/professionals';
    const method = professionalId ? 'PUT' : 'POST';
    
    // Deshabilitar botón
    const saveBtn = document.querySelector('#professionalModal .btn-primary');
    const originalText = saveBtn.innerHTML;
    saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Guardando...';
    saveBtn.disabled = true;
    
    // Enviar petición
    fetch(url, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
    })
    .then(response => response.json().then(data => ({ ok: response.ok, data })))
    .then(({ok, data}) => {
        if (!ok) {
            showToast(data.error || 'Error al guardar profesional', 'danger');
            throw new Error(data.error);
        }
        
        // Cerrar modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('professionalModal'));
        modal.hide();
        
        // Si es creación, mostrar credenciales
        if (!professionalId && data.credentials) {
            professionalCredentials = data.credentials;
            showProfessionalCredentials();
        }
        
        // Recargar lista
        loadProfessionals();
        loadDashboardStats();
        
        showToast(data.message || 'Profesional guardado exitosamente', 'success');
    })
    .catch(error => {
        console.error('Error saving professional:', error);
    })
    .finally(() => {
        saveBtn.innerHTML = originalText;
        saveBtn.disabled = false;
        
        // Re-habilitar username si estaba deshabilitado
        document.getElementById('professionalUsername').disabled = false;
    });
}

function showProfessionalCredentials() {
    if (!professionalCredentials) return;
    
    const modal = new bootstrap.Modal(document.getElementById('credentialsModal'));
    const display = document.getElementById('credentialsDisplay');
    
    display.innerHTML = `
        <h6 class="mb-3">
            <i class="fas fa-user-md me-2"></i>
            ${professionalCredentials.full_name}
        </h6>
        <hr>
        <div class="mb-2">
            <strong><i class="fas fa-user me-2"></i>Username:</strong>
            <code class="ms-2">${professionalCredentials.username}</code>
        </div>
        <div class="mb-2">
            <strong><i class="fas fa-envelope me-2"></i>Email:</strong>
            <code class="ms-2">${professionalCredentials.email}</code>
        </div>
        <div class="mb-2">
            <strong><i class="fas fa-lock me-2"></i>Password:</strong>
            <code class="ms-2">${professionalCredentials.password}</code>
        </div>
    `;
    
    modal.show();
}

function copyProfessionalCredentials() {
    if (!professionalCredentials) return;
    
    const text = `
Profesional: ${professionalCredentials.full_name}
Username: ${professionalCredentials.username}
Email: ${professionalCredentials.email}
Password: ${professionalCredentials.password}
    `.trim();
    
    navigator.clipboard.writeText(text).then(() => {
        showToast('📋 Credenciales copiadas al portapapeles', 'success');
    }).catch(err => {
        console.error('Error al copiar:', err);
        showToast('Error al copiar credenciales', 'danger');
    });
}

function viewProfessionalDetails(id) {
    fetch(`/clinic-admin/api/professionals/${id}`)
        .then(response => response.json())
        .then(prof => {
            const stats = prof.statistics;
            
            const modalHtml = `
                <div class="modal fade" id="viewProfessionalModal" tabindex="-1">
                    <div class="modal-dialog modal-lg">
                        <div class="modal-content">
                            <div class="modal-header bg-primary text-white">
                                <h5 class="modal-title">
                                    <i class="fas fa-user-md me-2"></i>${prof.full_name || prof.username}
                                </h5>
                                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                            </div>
                            <div class="modal-body">
                                <div class="row">
                                    <div class="col-md-6">
                                        <h6 class="mb-3">Información Personal</h6>
                                        <p><strong>Username:</strong> ${prof.username}</p>
                                        <p><strong>Email:</strong> ${prof.email}</p>
                                        <p><strong>Teléfono:</strong> ${prof.phone || 'N/A'}</p>
                                        <p><strong>Estado:</strong> 
                                            <span class="status-badge ${prof.is_active ? 'active' : 'inactive'}">
                                                ${prof.is_active ? 'Activo' : 'Inactivo'}
                                            </span>
                                        </p>
                                        <p><strong>Registrado:</strong> ${new Date(prof.created_at).toLocaleDateString('es-PE')}</p>
                                        ${prof.last_login ? `<p><strong>Último Login:</strong> ${new Date(prof.last_login).toLocaleString('es-PE')}</p>` : ''}
                                    </div>
                                    <div class="col-md-6">
                                        <h6 class="mb-3">Estadísticas</h6>
                                        <p><strong>Citas Totales:</strong> ${stats.appointments.total}</p>
                                        <p><strong>Completadas:</strong> 
                                            <span class="badge bg-success">${stats.appointments.completadas}</span>
                                        </p>
                                        <p><strong>Programadas:</strong> 
                                            <span class="badge bg-primary">${stats.appointments.programadas}</span>
                                        </p>
                                        <p><strong>Canceladas:</strong> 
                                            <span class="badge bg-danger">${stats.appointments.canceladas}</span>
                                        </p>
                                        <p><strong>No Asistió:</strong> 
                                            <span class="badge bg-warning">${stats.appointments.no_asistio}</span>
                                        </p>
                                        <p><strong>Pacientes Atendidos:</strong> ${stats.patients_attended}</p>
                                    </div>
                                </div>
                                
                                ${prof.recent_appointments && prof.recent_appointments.length > 0 ? `
                                    <hr>
                                    <h6 class="mb-3">Últimas Citas</h6>
                                    <div class="table-responsive">
                                        <table class="table table-sm">
                                            <thead>
                                                <tr>
                                                    <th>Fecha</th>
                                                    <th>Paciente</th>
                                                    <th>Servicio</th>
                                                    <th>Estado</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                ${prof.recent_appointments.map(apt => `
                                                    <tr>
                                                        <td>${new Date(apt.start_datetime).toLocaleDateString('es-PE')}</td>
                                                        <td>${apt.patient_name}</td>
                                                        <td>${apt.service_name || 'N/A'}</td>
                                                        <td><span class="badge bg-secondary">${apt.status}</span></td>
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
            const existingModal = document.getElementById('viewProfessionalModal');
            if (existingModal) {
                existingModal.remove();
            }
            
            // Agregar nuevo modal
            document.body.insertAdjacentHTML('beforeend', modalHtml);
            
            // Mostrar modal
            const modal = new bootstrap.Modal(document.getElementById('viewProfessionalModal'));
            modal.show();
            
            // Limpiar al cerrar
            document.getElementById('viewProfessionalModal').addEventListener('hidden.bs.modal', function() {
                this.remove();
            });
        })
        .catch(error => {
            console.error('Error loading professional details:', error);
            showToast('Error al cargar detalles del profesional', 'danger');
        });
}

function toggleProfessionalStatus(id) {
    if (!confirm('¿Cambiar el estado de este profesional?')) {
        return;
    }
    
    fetch(`/clinic-admin/api/professionals/${id}/toggle-status`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        showToast(data.message || 'Estado actualizado', 'success');
        loadProfessionals();
        loadDashboardStats();
    })
    .catch(error => {
        console.error('Error toggling status:', error);
        showToast('Error al cambiar estado', 'danger');
    });
}

function resetProfessionalPassword(id) {
    const newPassword = prompt('Ingresa la nueva contraseña (mínimo 6 caracteres):\n\nDeja vacío para generar una automática');
    
    if (newPassword === null) {
        return; // Usuario canceló
    }
    
    if (newPassword && newPassword.length < 6) {
        showToast('La contraseña debe tener al menos 6 caracteres', 'warning');
        return;
    }
    
    fetch(`/clinic-admin/api/professionals/${id}/reset-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            new_password: newPassword || null 
        })
    })
    .then(response => response.json())
    .then(data => {
        // Mostrar contraseña generada
        alert(`Contraseña reseteada exitosamente:\n\nUsername: ${data.username}\nEmail: ${data.email}\nNueva Contraseña: ${data.new_password}\n\n⚠️ Guarda esta contraseña y compártela con el profesional.`);
        
        showToast('✅ Contraseña reseteada exitosamente', 'success');
    })
    .catch(error => {
        console.error('Error resetting password:', error);
        showToast('Error al resetear contraseña', 'danger');
    });
}

function deleteProfessional(id, username) {
    // Primera confirmación
    if (!confirm(`¿Eliminar permanentemente al profesional "${username}"?\n\nEsta acción también eliminará todas sus citas asociadas.`)) {
        return;
    }
    
    // Segunda confirmación
    const confirmation = prompt(`Para confirmar, escribe exactamente: ${username}`);
    
    if (confirmation !== username) {
        if (confirmation !== null) {
            showToast('Eliminación cancelada. Nombre incorrecto.', 'warning');
        }
        return;
    }
    
    fetch(`/clinic-admin/api/professionals/${id}`, {
        method: 'DELETE'
    })
    .then(response => response.json())
    .then(data => {
        showToast(`✅ ${data.message}`, 'success');
        loadProfessionals();
        loadDashboardStats();
    })
    .catch(error => {
        console.error('Error deleting professional:', error);
        showToast('Error al eliminar profesional', 'danger');
    });
}

// ============================================================================
// TAB SERVICIOS: GESTIÓN
// ============================================================================
function loadServices() {
    const tbody = document.getElementById('servicesTableBody');
    tbody.innerHTML = '<tr><td colspan="6" class="text-center py-4"><div class="spinner-border text-primary"></div></td></tr>';
    
    fetch('/clinic-admin/api/services')
        .then(response => response.json())
        .then(services => {
            if (services.length === 0) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="6">
                            <div class="empty-state">
                                <i class="fas fa-stethoscope"></i>
                                <h5>No hay servicios registrados</h5>
                                <p class="text-muted">Haz clic en "Nuevo Servicio" para comenzar</p>
                            </div>
                        </td>
                    </tr>
                `;
                return;
            }
            
            tbody.innerHTML = '';
            
            services.forEach(service => {
                const row = document.createElement('tr');
                
                row.innerHTML = `
                    <td>
                        <strong>${service.name}</strong>
                    </td>
                    <td>${service.description || '-'}</td>
                    <td>
                        <span class="badge bg-info">
                            ${service.duration_minutes} min
                        </span>
                    </td>
                    <td>
                        ${service.price ? `S/ ${parseFloat(service.price).toFixed(2)}` : '-'}
                    </td>
                    <td>
                        <span class="status-badge ${service.is_active ? 'active' : 'inactive'}">
                            ${service.is_active ? 'Activo' : 'Inactivo'}
                        </span>
                    </td>
                    <td>
                        <div class="action-buttons">
                            <button class="btn btn-action-sm btn-primary" 
                                    onclick="editService(${service.id})" 
                                    title="Editar">
                                <i class="fas fa-edit"></i>
                            </button>
                            <button class="btn btn-action-sm ${service.is_active ? 'btn-warning' : 'btn-success'}" 
                                    onclick="toggleServiceStatus(${service.id})" 
                                    title="${service.is_active ? 'Desactivar' : 'Activar'}">
                                <i class="fas ${service.is_active ? 'fa-ban' : 'fa-check'}"></i>
                            </button>
                        </div>
                    </td>
                `;
                
                tbody.appendChild(row);
            });
        })
        .catch(error => {
            console.error('Error loading services:', error);
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="text-center text-danger py-4">
                        <i class="fas fa-exclamation-triangle me-2"></i>
                        Error al cargar servicios
                    </td>
                </tr>
            `;
        });
}

function openCreateServiceModal() {
    currentServiceId = null;
    
    const modal = new bootstrap.Modal(document.getElementById('serviceModal'));
    const form = document.getElementById('serviceForm');
    
    // Resetear formulario
    form.reset();
    document.getElementById('serviceId').value = '';
    
    // Configurar título
    document.getElementById('serviceModalTitle').innerHTML = 
        '<i class="fas fa-plus me-2"></i>Nuevo Servicio';
    
    modal.show();
}

function editService(id) {
    currentServiceId = id;
    
    // Buscar servicio en la lista cargada
    fetch('/clinic-admin/api/services')
        .then(response => response.json())
        .then(services => {
            const service = services.find(s => s.id === id);
            if (!service) {
                showToast('Servicio no encontrado', 'danger');
                return;
            }
            
            const modal = new bootstrap.Modal(document.getElementById('serviceModal'));
            
            // Llenar formulario
            document.getElementById('serviceId').value = service.id;
            document.getElementById('serviceName').value = service.name;
            document.getElementById('serviceDescription').value = service.description || '';
            document.getElementById('serviceDuration').value = service.duration_minutes;
            document.getElementById('servicePrice').value = service.price ? parseFloat(service.price).toFixed(2) : '';
            
            // Configurar título
            document.getElementById('serviceModalTitle').innerHTML = 
                '<i class="fas fa-edit me-2"></i>Editar Servicio';
            
            modal.show();
        })
        .catch(error => {
            console.error('Error loading service:', error);
            showToast('Error al cargar servicio', 'danger');
        });
}

function saveService() {
    const serviceId = document.getElementById('serviceId').value;
    const name = document.getElementById('serviceName').value.trim();
    const description = document.getElementById('serviceDescription').value.trim();
    const duration = parseInt(document.getElementById('serviceDuration').value);
    const price = document.getElementById('servicePrice').value.trim();
    
    // Validaciones
    if (!name) {
        showToast('El nombre del servicio es requerido', 'warning');
        return;
    }
    
    if (!duration || duration < 5) {
        showToast('La duración debe ser al menos 5 minutos', 'warning');
        return;
    }
    
    // Preparar datos
    const formData = {
        name: name,
        description: description || null,
        duration_minutes: duration,
        price: price ? parseFloat(price) : null
    };
    
    // Determinar URL y método
    const url = serviceId 
        ? `/clinic-admin/api/services/${serviceId}` 
        : '/clinic-admin/api/services';
    const method = serviceId ? 'PUT' : 'POST';
    
    // Deshabilitar botón
    const saveBtn = document.querySelector('#serviceModal .btn-primary');
    const originalText = saveBtn.innerHTML;
    saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Guardando...';
    saveBtn.disabled = true;
    
    // Enviar petición
    fetch(url, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
    })
    .then(response => response.json().then(data => ({ ok: response.ok, data })))
    .then(({ok, data}) => {
        if (!ok) {
            showToast(data.error || 'Error al guardar servicio', 'danger');
            throw new Error(data.error);
        }
        
        // Cerrar modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('serviceModal'));
        modal.hide();
        
        // Recargar lista
        loadServices();
        loadDashboardStats();
        
        showToast(data.message || 'Servicio guardado exitosamente', 'success');
    })
    .catch(error => {
        console.error('Error saving service:', error);
    })
    .finally(() => {
        saveBtn.innerHTML = originalText;
        saveBtn.disabled = false;
    });
}

function toggleServiceStatus(id) {
    if (!confirm('¿Cambiar el estado de este servicio?')) {
        return;
    }
    
    fetch(`/clinic-admin/api/services/${id}/toggle-status`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        showToast(data.message || 'Estado actualizado', 'success');
        loadServices();
        loadDashboardStats();
    })
    .catch(error => {
        console.error('Error toggling status:', error);
        showToast('Error al cambiar estado', 'danger');
    });
}

// ============================================================================
// TAB CALENDARIO: VISTA GLOBAL
// ============================================================================
function initializeClinicCalendar() {
    if (clinicCalendar) {
        return; // Ya está inicializado
    }
    
    const calendarEl = document.getElementById('clinicCalendarContainer');
    
    if (!calendarEl) {
        console.warn('Calendar container not found');
        return;
    }
    
    clinicCalendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'dayGridMonth',
        locale: 'es',
        timeZone: 'America/Lima',
        
        headerToolbar: {
            left: 'prev,next today',
            center: 'title',
            right: 'dayGridMonth,timeGridWeek,timeGridDay,listWeek'
        },
        
        buttonText: {
            today: 'Hoy',
            month: 'Mes',
            week: 'Semana',
            day: 'Día',
            list: 'Lista'
        },
        
        slotMinTime: '07:00:00',
        slotMaxTime: '21:00:00',
        slotDuration: '00:30:00',
        allDaySlot: false,
        
        height: 'auto',
        
        // Cargar todas las citas de la clínica
        events: function(info, successCallback, failureCallback) {
            const startStr = info.startStr;
            const endStr = info.endStr;
            
            // Incluir filtro de profesional si existe
            const professionalFilter = document.getElementById('filterProfessional').value;
            let url = `/clinic-admin/api/calendar/all-appointments?start=${startStr}&end=${endStr}`;
            
            if (professionalFilter) {
                url += `&professional_id=${professionalFilter}`;
            }
            
            fetch(url)
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Error al cargar citas');
                    }
                    return response.json();
                })
                .then(data => {
                    successCallback(data);
                })
                .catch(error => {
                    console.error('Error fetching appointments:', error);
                    showToast('Error al cargar las citas', 'danger');
                    failureCallback(error);
                });
        },
        
        eventClick: function(info) {
            showAppointmentInfo(info.event);
        },
        
        eventDidMount: function(info) {
            const props = info.event.extendedProps;
            const start = new Date(info.event.start);
            const end = info.event.end || info.event.start;
            
            const tooltipContent = `
                <strong>${info.event.title}</strong><br>
                <i class="fas fa-user-md"></i> ${props.professional || 'N/A'}<br>
                <i class="fas fa-stethoscope"></i> ${props.service || 'Sin servicio'}<br>
                <i class="fas fa-clock"></i> ${start.toLocaleTimeString('es-PE', {hour: '2-digit', minute: '2-digit'})} - ${end.toLocaleTimeString('es-PE', {hour: '2-digit', minute: '2-digit'})}<br>
                <i class="fas fa-info-circle"></i> ${props.status}
            `;
            
            info.el.title = tooltipContent.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
        }
    });
    
    clinicCalendar.render();
}

function loadProfessionalsForFilter() {
    const select = document.getElementById('filterProfessional');
    
    fetch('/clinic-admin/api/professionals')
        .then(response => response.json())
        .then(professionals => {
            select.innerHTML = '<option value="">Todos los profesionales</option>';
            
            professionals.forEach(prof => {
                const option = document.createElement('option');
                option.value = prof.id;
                option.textContent = prof.full_name || prof.username;
                select.appendChild(option);
            });
        })
        .catch(error => {
            console.error('Error loading professionals for filter:', error);
        });
}

function filterCalendarByProfessional() {
    if (clinicCalendar) {
        clinicCalendar.refetchEvents();
    }
}

function clearCalendarFilter() {
    document.getElementById('filterProfessional').value = '';
    if (clinicCalendar) {
        clinicCalendar.refetchEvents();
    }
}

function showAppointmentInfo(event) {
    const props = event.extendedProps;
    const start = new Date(event.start);
    const end = event.end || event.start;
    
    const infoHtml = `
        <div class="modal fade" id="appointmentInfoModal" tabindex="-1">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header" style="background-color: ${event.backgroundColor}; color: white;">
                        <h5 class="modal-title">
                            <i class="fas fa-calendar-alt me-2"></i>Detalles de la Cita
                        </h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="mb-3">
                            <strong><i class="fas fa-user-injured me-2"></i>Paciente:</strong>
                            <div>${props.patient_name || 'N/A'}</div>
                            ${props.patient_phone ? `<small class="text-muted">${props.patient_phone}</small>` : ''}
                        </div>
                        <div class="mb-3">
                            <strong><i class="fas fa-user-md me-2"></i>Profesional:</strong>
                            <div>${props.professional || 'N/A'}</div>
                        </div>
                        <div class="mb-3">
                            <strong><i class="fas fa-stethoscope me-2"></i>Servicio:</strong>
                            <div>${props.service || 'Sin servicio'}</div>
                        </div>
                        <div class="mb-3">
                            <strong><i class="fas fa-clock me-2"></i>Fecha y Hora:</strong>
                            <div>${start.toLocaleDateString('es-PE', {weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'})}</div>
                            <div>${start.toLocaleTimeString('es-PE', {hour: '2-digit', minute: '2-digit'})} - ${end.toLocaleTimeString('es-PE', {hour: '2-digit', minute: '2-digit'})}</div>
                        </div>
                        <div class="mb-3">
                            <strong><i class="fas fa-info-circle me-2"></i>Estado:</strong>
                            <span class="badge" style="background-color: ${event.backgroundColor}">
                                ${props.status}
                            </span>
                        </div>
                        ${props.notes ? `
                            <div class="mb-3">
                                <strong><i class="fas fa-sticky-note me-2"></i>Notas:</strong>
                                <div class="p-2 bg-light rounded">${props.notes}</div>
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
    const existingModal = document.getElementById('appointmentInfoModal');
    if (existingModal) {
        existingModal.remove();
    }
    
    // Agregar nuevo modal
    document.body.insertAdjacentHTML('beforeend', infoHtml);
    
    // Mostrar modal
    const modal = new bootstrap.Modal(document.getElementById('appointmentInfoModal'));
    modal.show();
    
    // Limpiar al cerrar
    document.getElementById('appointmentInfoModal').addEventListener('hidden.bs.modal', function() {
        this.remove();
    });
}

// ============================================================================
// TAB REPORTES: GENERACIÓN
// ============================================================================
function generateAppointmentReport() {
    const startDate = document.getElementById('reportStartDate').value;
    const endDate = document.getElementById('reportEndDate').value;
    
    if (!startDate || !endDate) {
        showToast('Selecciona un rango de fechas', 'warning');
        return;
    }
    
    const resultContainer = document.getElementById('appointmentReportResult');
    resultContainer.style.display = 'block';
    
    // Mostrar loading
    document.getElementById('reportTotal').textContent = '...';
    document.getElementById('reportCompletadas').textContent = '...';
    document.getElementById('reportCanceladas').textContent = '...';
    document.getElementById('reportIngresos').textContent = '...';
    
    fetch(`/clinic-admin/api/reports/summary?start=${startDate}&end=${endDate}`)
        .then(response => response.json())
        .then(data => {
            // Llenar resumen
            document.getElementById('reportTotal').textContent = data.summary.total || 0;
            document.getElementById('reportCompletadas').textContent = data.summary.completadas || 0;
            document.getElementById('reportCanceladas').textContent = data.summary.canceladas || 0;
            document.getElementById('reportIngresos').textContent = 
                `S/ ${parseFloat(data.ingresos_estimados || 0).toFixed(2)}`;
            
            // Llenar tabla por profesional
            const tbody = document.getElementById('reportByProfessional');
            tbody.innerHTML = '';
            
            if (data.by_professional && data.by_professional.length > 0) {
                data.by_professional.forEach(item => {
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td>${item.name}</td>
                        <td><span class="badge bg-primary">${item.appointments}</span></td>
                    `;
                    tbody.appendChild(row);
                });
            } else {
                tbody.innerHTML = '<tr><td colspan="2" class="text-center text-muted">Sin datos</td></tr>';
            }
            
            showToast('✅ Reporte generado exitosamente', 'success');
        })
        .catch(error => {
            console.error('Error generating report:', error);
            showToast('Error al generar reporte', 'danger');
            resultContainer.style.display = 'none';
        });
}

function exportAppointmentsCSV() {
    const startDate = document.getElementById('reportStartDate').value;
    const endDate = document.getElementById('reportEndDate').value;
    
    if (!startDate || !endDate) {
        showToast('Selecciona un rango de fechas', 'warning');
        return;
    }
    
    // Abrir en nueva pestaña
    const url = `/api/export/appointments?start=${startDate}&end=${endDate}`;
    window.open(url, '_blank');
    
    showToast('📄 Descargando CSV...', 'success');
}

function generatePerformanceReport() {
    const resultContainer = document.getElementById('performanceReportResult');
    resultContainer.style.display = 'block';
    
    const tbody = document.getElementById('performanceTableBody');
    tbody.innerHTML = '<tr><td colspan="7" class="text-center"><div class="spinner-border text-primary"></div></td></tr>';
    
    // Usar último mes por defecto
    const endDate = new Date();
    const startDate = new Date(endDate);
    startDate.setMonth(startDate.getMonth() - 1);
    
    const startStr = startDate.toISOString().split('T')[0];
    const endStr = endDate.toISOString().split('T')[0];
    
    fetch(`/clinic-admin/api/reports/professionals-performance?start=${startStr}&end=${endStr}`)
        .then(response => response.json())
        .then(data => {
            tbody.innerHTML = '';
            
            if (data.professionals && data.professionals.length > 0) {
                data.professionals.forEach(prof => {
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td>
                            <strong>${prof.name}</strong>
                            ${!prof.is_active ? '<span class="badge bg-danger ms-2">Inactivo</span>' : ''}
                        </td>
                        <td><span class="badge bg-secondary">${prof.appointments.total}</span></td>
                        <td><span class="badge bg-success">${prof.appointments.completadas}</span></td>
                        <td><span class="badge bg-danger">${prof.appointments.canceladas}</span></td>
                        <td>
                            <div class="progress" style="height: 20px;">
                                <div class="progress-bar bg-success" 
                                     role="progressbar" 
                                     style="width: ${prof.appointments.tasa_completadas}%"
                                     aria-valuenow="${prof.appointments.tasa_completadas}" 
                                     aria-valuemin="0" 
                                     aria-valuemax="100">
                                    ${prof.appointments.tasa_completadas}%
                                </div>
                            </div>
                        </td>
                        <td><span class="badge bg-info">${prof.pacientes_atendidos}</span></td>
                        <td><strong>S/ ${parseFloat(prof.ingresos_generados || 0).toFixed(2)}</strong></td>
                    `;
                    tbody.appendChild(row);
                });
            } else {
                tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">Sin datos en este período</td></tr>';
            }
            
            showToast('✅ Reporte de desempeño generado', 'success');
        })
        .catch(error => {
            console.error('Error generating performance report:', error);
            tbody.innerHTML = '<tr><td colspan="7" class="text-center text-danger">Error al generar reporte</td></tr>';
            showToast('Error al generar reporte de desempeño', 'danger');
        });
}

// ============================================================================
// TAB CONFIGURACIÓN: GUARDAR
// ============================================================================
function saveClinicConfig() {
    const name = document.getElementById('configClinicName').value.trim();
    const phone = document.getElementById('configClinicPhone').value.trim();
    const email = document.getElementById('configClinicEmail').value.trim();
    const address = document.getElementById('configClinicAddress').value.trim();
    const logoUrl = document.getElementById('configLogoUrl').value.trim();
    const themeColor = document.getElementById('configThemeColor').value;
    
    // Validaciones
    if (!name) {
        showToast('El nombre de la clínica es requerido', 'warning');
        return;
    }
    
    // Preparar datos
    const formData = {
        name: name,
        phone: phone || null,
        email: email || null,
        address: address || null,
        logo_url: logoUrl || null,
        theme_color: themeColor
    };
    
    // Deshabilitar botón
    const saveBtn = document.querySelector('#config-pane .btn-primary');
    const originalText = saveBtn.innerHTML;
    saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Guardando...';
    saveBtn.disabled = true;
    
    // Enviar petición
    fetch('/clinic-admin/api/clinic/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
    })
    .then(response => response.json().then(data => ({ ok: response.ok, data })))
    .then(({ok, data}) => {
        if (!ok) {
            showToast(data.error || 'Error al guardar configuración', 'danger');
            throw new Error(data.error);
        }
        
        showToast('✅ Configuración guardada exitosamente. Recarga la página para ver los cambios.', 'success');
        
        // Opcional: recargar después de 2 segundos
        setTimeout(() => {
            location.reload();
        }, 2000);
    })
    .catch(error => {
        console.error('Error saving config:', error);
    })
    .finally(() => {
        saveBtn.innerHTML = originalText;
        saveBtn.disabled = false;
    });
}

// ============================================================================
// HELPER: TOAST NOTIFICATIONS
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
    
    const duration = message.length > 100 ? 6000 : 4000;
    
    setTimeout(() => {
        toastContainer.style.animation = 'fadeOut 0.3s ease-out';
        setTimeout(() => toastContainer.remove(), 300);
    }, duration);
}

// ============================================================================
// ANIMACIONES CSS
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
window.loadDashboardStats = loadDashboardStats;
window.loadOverviewData = loadOverviewData;
window.loadProfessionals = loadProfessionals;
window.openCreateProfessionalModal = openCreateProfessionalModal;
window.editProfessional = editProfessional;
window.saveProfessional = saveProfessional;
window.copyProfessionalCredentials = copyProfessionalCredentials;
window.viewProfessionalDetails = viewProfessionalDetails;
window.toggleProfessionalStatus = toggleProfessionalStatus;
window.resetProfessionalPassword = resetProfessionalPassword;
window.deleteProfessional = deleteProfessional;
window.loadServices = loadServices;
window.openCreateServiceModal = openCreateServiceModal;
window.editService = editService;
window.saveService = saveService;
window.toggleServiceStatus = toggleServiceStatus;
window.initializeClinicCalendar = initializeClinicCalendar;
window.loadProfessionalsForFilter = loadProfessionalsForFilter;
window.filterCalendarByProfessional = filterCalendarByProfessional;
window.clearCalendarFilter = clearCalendarFilter;
window.generateAppointmentReport = generateAppointmentReport;
window.exportAppointmentsCSV = exportAppointmentsCSV;
window.generatePerformanceReport = generatePerformanceReport;
window.saveClinicConfig = saveClinicConfig;