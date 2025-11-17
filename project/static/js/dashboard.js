// ============================================================================
// DASHBOARD.JS - Lógica del Calendario y Gestión de Citas
// ============================================================================

let calendar;
let currentEventId = null;

// ============================================================================
// INICIALIZACIÓN
// ============================================================================
document.addEventListener('DOMContentLoaded', function() {
    initializeCalendar();
    loadStatistics();
    loadPatients();
    loadServices();
    loadAppointmentsList();
    loadCancelledAppointments();
});

// ============================================================================
// FULLCALENDAR CONFIGURATION
// ============================================================================
function initializeCalendar() {
    const calendarEl = document.getElementById('calendar-container');
    
    if (!calendarEl) {
        console.warn('Calendar container not found');
        return;
    }
    
    calendar = new FullCalendar.Calendar(calendarEl, {
        // Configuración básica
        initialView: 'dayGridMonth',
        locale: 'es',
        timeZone: 'America/Lima',
        
        // Header toolbar
        headerToolbar: {
            left: 'prev,next today',
            center: 'title',
            right: 'dayGridMonth,timeGridWeek,timeGridDay,listWeek'
        },
        
        // Textos en español
        buttonText: {
            today: 'Hoy',
            month: 'Mes',
            week: 'Semana',
            day: 'Día',
            list: 'Lista'
        },
        
        // Configuración de horario
        slotMinTime: '07:00:00',
        slotMaxTime: '21:00:00',
        slotDuration: '00:30:00',
        allDaySlot: false,
        
        // Opciones de interacción
        selectable: true,
        editable: true,
        eventResizableFromStart: true,
        eventDurationEditable: true,
        
        // Altura
        height: 'auto',
        
        // Cargar eventos desde API
        events: function(info, successCallback, failureCallback) {
            const startStr = info.startStr;
            const endStr = info.endStr;
            
            fetch(`/api/appointments?start=${startStr}&end=${endStr}`)
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
        
        // ========================================================================
        // EVENTO: Seleccionar rango de fechas (crear nueva cita)
        // ========================================================================
        select: function(info) {
            currentEventId = null;
            openAppointmentModal(info.startStr, info.endStr);
            calendar.unselect();
        },
        
        // ========================================================================
        // EVENTO: Click en cita existente (ver/editar)
        // ========================================================================
        eventClick: function(info) {
            currentEventId = info.event.id;
            showAppointmentDetails(info.event);
        },
        
        // ========================================================================
        // EVENTO: Arrastrar cita (drag & drop)
        // ========================================================================
        eventDrop: function(info) {
            updateEventDates(info.event, info.revert);
        },
        
        // ========================================================================
        // EVENTO: Redimensionar cita
        // ========================================================================
        eventResize: function(info) {
            updateEventDates(info.event, info.revert);
        },
        
        // ========================================================================
        // EVENTO: Renderizado de cada evento (tooltips)
        // ========================================================================
        eventDidMount: function(info) {
            const props = info.event.extendedProps;
            const start = new Date(info.event.start);
            const end = info.event.end || info.event.start;
            
            const tooltipContent = `
                <strong>${info.event.title}</strong><br>
                <i class="fas fa-stethoscope"></i> ${props.service || 'Sin servicio'}<br>
                <i class="fas fa-clock"></i> ${start.toLocaleTimeString('es-PE', {hour: '2-digit', minute: '2-digit'})} - ${end.toLocaleTimeString('es-PE', {hour: '2-digit', minute: '2-digit'})}<br>
                <i class="fas fa-info-circle"></i> ${props.status}
            `;
            
            info.el.title = tooltipContent.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
        },
        
        // ========================================================================
        // Configuración de eventos
        // ========================================================================
        eventContent: function(arg) {
            const time = arg.timeText;
            const title = arg.event.title;
            
            return {
                html: `
                    <div class="fc-event-main-frame">
                        <div class="fc-event-time">${time}</div>
                        <div class="fc-event-title-container">
                            <div class="fc-event-title">${title}</div>
                        </div>
                    </div>
                `
            };
        }
    });
    
    calendar.render();
}

// ============================================================================
// MODALES: ABRIR/CERRAR
// ============================================================================
function openNewAppointmentModal() {
    currentEventId = null;
    const now = new Date();
    const startStr = formatDateTimeLocal(now);
    const endDate = new Date(now.getTime() + 60 * 60 * 1000); // +1 hora
    const endStr = formatDateTimeLocal(endDate);
    openAppointmentModal(startStr, endStr);
}

function openAppointmentModal(startStr, endStr) {
    const modal = new bootstrap.Modal(document.getElementById('appointmentModal'));
    const modalTitle = document.getElementById('modalTitle');
    const form = document.getElementById('appointmentForm');
    
    // Resetear formulario
    form.reset();
    
    // Configurar título
    if (currentEventId) {
        modalTitle.innerHTML = '<i class="fas fa-calendar-edit me-2"></i>Editar Cita';
    } else {
        modalTitle.innerHTML = '<i class="fas fa-calendar-plus me-2"></i>Añadir Cita';
    }
    
    // Establecer fechas
    document.getElementById('start_datetime').value = formatDateTimeLocal(new Date(startStr));
    document.getElementById('end_datetime').value = formatDateTimeLocal(new Date(endStr));
    
    modal.show();
}

function showAppointmentDetails(event) {
    const modal = new bootstrap.Modal(document.getElementById('appointmentModal'));
    const modalTitle = document.getElementById('modalTitle');
    
    modalTitle.innerHTML = '<i class="fas fa-calendar-edit me-2"></i>Editar Cita';
    
    // Cargar datos del evento
    const props = event.extendedProps;
    
    document.getElementById('patient_id').value = props.patient_id || '';
    document.getElementById('service_id').value = event.extendedProps.service_id || '';
    document.getElementById('notes').value = props.notes || '';
    document.getElementById('start_datetime').value = formatDateTimeLocal(new Date(event.start));
    document.getElementById('end_datetime').value = formatDateTimeLocal(new Date(event.end || event.start));
    
    modal.show();
}

// ============================================================================
// GUARDAR CITA (CREATE/UPDATE)
// ============================================================================
function saveAppointment() {
    const patientId = document.getElementById('patient_id').value;
    const serviceId = document.getElementById('service_id').value;
    const startStr = document.getElementById('start_datetime').value;
    const endStr = document.getElementById('end_datetime').value;
    const notes = document.getElementById('notes').value;
    
    // Validaciones
    if (!patientId) {
        showToast('Por favor selecciona un paciente', 'warning');
        return;
    }
    
    if (!serviceId) {
        showToast('Por favor selecciona un servicio', 'warning');
        return;
    }
    
    if (!startStr || !endStr) {
        showToast('Por favor completa las fechas', 'warning');
        return;
    }
    
    const startDate = new Date(startStr);
    const endDate = new Date(endStr);
    
    if (endDate <= startDate) {
        showToast('La fecha de fin debe ser posterior a la fecha de inicio', 'warning');
        return;
    }
    
    // Preparar datos
    const formData = {
        patient_id: parseInt(patientId),
        service_id: parseInt(serviceId),
        start_datetime: startDate.toISOString(),
        end_datetime: endDate.toISOString(),
        notes: notes.trim()
    };
    
    // Determinar URL y método
    const url = currentEventId ? `/api/appointments/${currentEventId}` : '/api/appointments';
    const method = currentEventId ? 'PUT' : 'POST';
    
    // Deshabilitar botón
    const saveBtn = document.querySelector('#appointmentModal .btn-primary');
    const originalText = saveBtn.innerHTML;
    saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Guardando...';
    saveBtn.disabled = true;
    
    // Enviar petición
    fetch(url, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
    })
    .then(response => response.json().then(data => ({ 
        ok: response.ok, 
        status: response.status, 
        data 
    })))
    .then(({ok, status, data}) => {
        if (!ok) {
            // Manejo de conflictos (409)
            if (status === 409) {
                showToast(`⚠️ ${data.message || 'Horario ocupado'}`, 'danger');
                
                if (data.conflicting_appointment) {
                    const conflict = data.conflicting_appointment;
                    showToast(
                        `Conflicto con: ${conflict.patient} (${new Date(conflict.start).toLocaleString('es-PE')})`,
                        'warning'
                    );
                }
            } else {
                showToast(data.error || 'Error al guardar la cita', 'danger');
            }
            throw new Error(data.error || 'Error desconocido');
        }
        
        // Éxito
        const modal = bootstrap.Modal.getInstance(document.getElementById('appointmentModal'));
        modal.hide();
        
        // Recargar calendario y listas
        calendar.refetchEvents();
        loadStatistics();
        loadAppointmentsList();
        
        showToast(data.message || 'Cita guardada exitosamente', 'success');
    })
    .catch(error => {
        console.error('Error saving appointment:', error);
    })
    .finally(() => {
        saveBtn.innerHTML = originalText;
        saveBtn.disabled = false;
    });
}

// ============================================================================
// ACTUALIZAR FECHAS (DRAG & DROP / RESIZE)
// ============================================================================
function updateEventDates(event, revert) {
    const formData = {
        patient_id: event.extendedProps.patient_id,
        service_id: event.extendedProps.service_id,
        start_datetime: new Date(event.start).toISOString(),
        end_datetime: new Date(event.end || event.start).toISOString(),
        notes: event.extendedProps.notes || ''
    };
    
    fetch(`/api/appointments/${event.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
    })
    .then(response => response.json().then(data => ({ 
        ok: response.ok, 
        status: response.status, 
        data 
    })))
    .then(({ok, status, data}) => {
        if (!ok) {
            if (status === 409) {
                showToast(`⚠️ ${data.message || 'Horario ocupado'}`, 'danger');
            } else {
                showToast('Error al actualizar la cita', 'danger');
            }
            revert(); // Revertir cambio visual
        } else {
            showToast('Cita actualizada', 'success');
            loadStatistics();
            loadAppointmentsList();
        }
    })
    .catch(error => {
        console.error('Error updating appointment:', error);
        showToast('Error al actualizar la cita', 'danger');
        revert();
    });
}

// ============================================================================
// COMPLETAR CITA
// ============================================================================
function completeAppointment(id) {
    if (!confirm('¿Marcar esta cita como completada?')) {
        return;
    }
    
    fetch(`/api/appointments/${id}/complete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => response.json().then(data => ({ ok: response.ok, data })))
    .then(({ok, data}) => {
        if (!ok) {
            showToast(data.error || 'Error al completar la cita', 'danger');
        } else {
            calendar.refetchEvents();
            loadStatistics();
            loadAppointmentsList();
            showToast('✅ Cita marcada como completada', 'success');
        }
    })
    .catch(error => {
        console.error('Error completing appointment:', error);
        showToast('Error al completar la cita', 'danger');
    });
}

// ============================================================================
// CANCELAR CITA
// ============================================================================
function cancelAppointment(id, patientName) {
    const reason = prompt(
        `¿Por qué deseas cancelar la cita de ${patientName}?\n\n(Opcional, presiona OK para continuar)`
    );
    
    if (reason === null) {
        return; // Usuario canceló
    }
    
    fetch(`/api/appointments/${id}/cancel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            reason: reason || 'Sin motivo especificado' 
        })
    })
    .then(response => response.json().then(data => ({ ok: response.ok, data })))
    .then(({ok, data}) => {
        if (!ok) {
            showToast(data.error || 'Error al cancelar la cita', 'danger');
        } else {
            calendar.refetchEvents();
            loadStatistics();
            loadAppointmentsList();
            loadCancelledAppointments();
            showToast('❌ Cita cancelada exitosamente', 'success');
        }
    })
    .catch(error => {
        console.error('Error cancelling appointment:', error);
        showToast('Error al cancelar la cita', 'danger');
    });
}

// ============================================================================
// ENVIAR RECORDATORIO WHATSAPP
// ============================================================================
function sendWhatsAppReminder(id) {
    fetch(`/api/appointments/${id}/whatsapp-reminder`)
        .then(response => response.json())
        .then(data => {
            if (data.whatsapp_link) {
                // Abrir WhatsApp en nueva pestaña
                window.open(data.whatsapp_link, '_blank');
                showToast(`Recordatorio enviado a ${data.patient_name}`, 'success');
            } else {
                showToast(data.error || 'Error al generar recordatorio', 'danger');
            }
        })
        .catch(error => {
            console.error('Error sending WhatsApp reminder:', error);
            showToast('Error al enviar recordatorio', 'danger');
        });
}

// ============================================================================
// CARGAR LISTA DE CITAS
// ============================================================================
function loadAppointmentsList() {
    const listContainer = document.getElementById('appointments-list');
    if (!listContainer) return;
    
    listContainer.innerHTML = '<div class="text-center py-3"><div class="spinner-border text-primary"></div></div>';
    
    fetch('/api/appointments')
        .then(response => response.json())
        .then(events => {
            if (events.length === 0) {
                listContainer.innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-calendar-times"></i>
                        <h5>No hay citas programadas</h5>
                        <p class="text-muted">Haz clic en "Nueva Cita" para comenzar</p>
                    </div>
                `;
                return;
            }
            
            listContainer.innerHTML = '';
            
            // Ordenar por fecha (más cercanas primero)
            events.sort((a, b) => new Date(a.start) - new Date(b.start));
            
            events.forEach(event => {
                const apt = event.extendedProps;
                const startDate = new Date(event.start);
                const endDate = new Date(event.end || event.start);
                const isPast = apt.can_complete;
                const canCancel = apt.can_cancel;
                
                // Determinar clase según estado
                let statusClass = '';
                if (apt.status === 'Completada') {
                    statusClass = 'completada';
                } else if (apt.status === 'Cancelada') {
                    statusClass = 'cancelada';
                }
                
                const card = document.createElement('div');
                card.className = `appointment-card ${statusClass}`;
                card.innerHTML = `
                    <div class="appointment-card-header">
                        <div>
                            <h6 class="mb-1">${event.title}</h6>
                            <span class="badge bg-${apt.status === 'Completada' ? 'success' : 'primary'}">
                                ${apt.status}
                            </span>
                        </div>
                    </div>
                    <div class="appointment-card-body mt-2">
                        <div class="mb-1">
                            <i class="far fa-calendar"></i> 
                            ${startDate.toLocaleDateString('es-PE', {weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'})}
                        </div>
                        <div class="mb-1">
                            <i class="far fa-clock"></i> 
                            ${startDate.toLocaleTimeString('es-PE', {hour: '2-digit', minute: '2-digit'})} - 
                            ${endDate.toLocaleTimeString('es-PE', {hour: '2-digit', minute: '2-digit'})}
                        </div>
                        ${apt.service ? `
                            <div class="mb-1">
                                <i class="fas fa-stethoscope"></i> ${apt.service}
                            </div>
                        ` : ''}
                        ${apt.patient_phone ? `
                            <div class="mb-1">
                                <i class="fas fa-phone"></i> ${apt.patient_phone}
                            </div>
                        ` : ''}
                        ${apt.notes ? `
                            <div class="mb-1">
                                <i class="fas fa-sticky-note"></i> ${apt.notes}
                            </div>
                        ` : ''}
                    </div>
                    ${(isPast && apt.status === 'Programada') || canCancel || apt.patient_phone ? `
                        <div class="appointment-card-actions">
                            ${isPast && apt.status === 'Programada' ? `
                                <button class="btn btn-sm btn-success" onclick="completeAppointment(${event.id})" title="Marcar como completada">
                                    <i class="fas fa-check me-1"></i>Completar
                                </button>
                            ` : ''}
                            ${canCancel && apt.status === 'Programada' ? `
                                <button class="btn btn-sm btn-danger" onclick="cancelAppointment(${event.id}, '${event.title}')" title="Cancelar cita">
                                    <i class="fas fa-times me-1"></i>Cancelar
                                </button>
                            ` : ''}
                            ${apt.patient_phone && apt.status === 'Programada' ? `
                                <button class="btn btn-sm btn-success" onclick="sendWhatsAppReminder(${event.id})" title="Enviar recordatorio por WhatsApp">
                                    <i class="fab fa-whatsapp me-1"></i>Recordatorio
                                </button>
                            ` : ''}
                        </div>
                    ` : ''}
                `;
                listContainer.appendChild(card);
            });
        })
        .catch(error => {
            console.error('Error loading appointments list:', error);
            listContainer.innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    Error al cargar citas
                </div>
            `;
        });
}

// ============================================================================
// CARGAR CITAS CANCELADAS
// ============================================================================
function loadCancelledAppointments() {
    const container = document.getElementById('cancelled-list');
    if (!container) return;
    
    container.innerHTML = '<div class="text-center py-3"><div class="spinner-border text-warning"></div></div>';
    
    fetch('/api/appointments?include_cancelled=true&status=Cancelada')
        .then(response => response.json())
        .then(events => {
            // Filtrar solo canceladas
            const cancelled = events.filter(e => e.extendedProps.status === 'Cancelada');
            
            if (cancelled.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-check-circle"></i>
                        <h5>No hay citas canceladas</h5>
                        <p class="text-muted">Excelente gestión de tu agenda</p>
                    </div>
                `;
                return;
            }
            
            container.innerHTML = '';
            
            // Ordenar por fecha de cancelación (más recientes primero)
            cancelled.sort((a, b) => {
                const dateA = a.extendedProps.cancelled_at ? new Date(a.extendedProps.cancelled_at) : new Date(0);
                const dateB = b.extendedProps.cancelled_at ? new Date(b.extendedProps.cancelled_at) : new Date(0);
                return dateB - dateA;
            });
            
            cancelled.forEach(event => {
                const apt = event.extendedProps;
                const cancelledDate = apt.cancelled_at ? new Date(apt.cancelled_at) : null;
                const aptDate = new Date(event.start);
                
                const card = document.createElement('div');
                card.className = 'cancelled-card';
                card.innerHTML = `
                    <h6 class="mb-2"><del>${event.title}</del></h6>
                    <div class="text-muted small">
                        <div class="mb-1">
                            <i class="far fa-calendar"></i> 
                            <strong>Programada:</strong> ${aptDate.toLocaleDateString('es-PE')} 
                            ${aptDate.toLocaleTimeString('es-PE', {hour: '2-digit', minute: '2-digit'})}
                        </div>
                        ${cancelledDate ? `
                            <div class="mb-1 text-danger">
                                <i class="fas fa-ban"></i> 
                                <strong>Cancelada:</strong> ${cancelledDate.toLocaleDateString('es-PE')} 
                                ${cancelledDate.toLocaleTimeString('es-PE', {hour: '2-digit', minute: '2-digit'})}
                            </div>
                        ` : ''}
                        ${apt.cancellation_reason ? `
                            <div class="mb-1">
                                <i class="fas fa-info-circle"></i> 
                                <strong>Motivo:</strong> ${apt.cancellation_reason}
                            </div>
                        ` : ''}
                        ${apt.service ? `
                            <div class="mb-1">
                                <i class="fas fa-stethoscope"></i> ${apt.service}
                            </div>
                        ` : ''}
                    </div>
                `;
                container.appendChild(card);
            });
        })
        .catch(error => {
            console.error('Error loading cancelled appointments:', error);
            container.innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    Error al cargar historial
                </div>
            `;
        });
}

// ============================================================================
// CARGAR PACIENTES
// ============================================================================
function loadPatients() {
    const patientSelect = document.getElementById('patient_id');
    if (!patientSelect) return;
    
    fetch('/api/patients')
        .then(response => response.json())
        .then(patients => {
            patientSelect.innerHTML = '<option value="">-- Seleccionar paciente --</option>';
            
            patients.forEach(patient => {
                const option = document.createElement('option');
                option.value = patient.id;
                option.textContent = `${patient.name} (${patient.phone})`;
                patientSelect.appendChild(option);
            });
        })
        .catch(error => {
            console.error('Error loading patients:', error);
            showToast('Error al cargar pacientes', 'danger');
        });
}

// ============================================================================
// CARGAR SERVICIOS
// ============================================================================
function loadServices() {
    const serviceSelect = document.getElementById('service_id');
    if (!serviceSelect) return;
    
    fetch('/api/services')
        .then(response => response.json())
        .then(services => {
            serviceSelect.innerHTML = '<option value="">-- Seleccionar servicio --</option>';
            
            services.forEach(service => {
                const option = document.createElement('option');
                option.value = service.id;
                option.textContent = `${service.name} (${service.duration_minutes} min)`;
                option.dataset.duration = service.duration_minutes;
                serviceSelect.appendChild(option);
            });
        })
        .catch(error => {
            console.error('Error loading services:', error);
            showToast('Error al cargar servicios', 'danger');
        });
}

// ============================================================================
// CREAR PACIENTE RÁPIDO
// ============================================================================
function openNewPatientModal() {
    const modal = new bootstrap.Modal(document.getElementById('newPatientModal'));
    document.getElementById('newPatientForm').reset();
    modal.show();
}

function saveNewPatient() {
    const name = document.getElementById('patient_name').value.trim();
    const phone = document.getElementById('patient_phone').value.trim();
    const email = document.getElementById('patient_email').value.trim();
    const notes = document.getElementById('patient_notes').value.trim();
    
    if (!name || !phone) {
        showToast('Nombre y teléfono son requeridos', 'warning');
        return;
    }
    
    const saveBtn = document.querySelector('#newPatientModal .btn-primary');
    const originalText = saveBtn.innerHTML;
    saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Guardando...';
    saveBtn.disabled = true;
    
    fetch('/api/patients', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            name: name,
            phone: phone,
            email: email || null,
            notes: notes || null
        })
    })
    .then(response => response.json().then(data => ({ ok: response.ok, data })))
    .then(({ok, data}) => {
        if (!ok) {
            showToast(data.error || 'Error al crear paciente', 'danger');
            throw new Error(data.error);
        }
        
        // Cerrar modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('newPatientModal'));
        modal.hide();
        
        // Recargar lista de pacientes
        loadPatients();
        
        // Seleccionar automáticamente el nuevo paciente
        setTimeout(() => {
            document.getElementById('patient_id').value = data.patient.id;
        }, 300);
        
        showToast(`Paciente "${name}" creado exitosamente`, 'success');
    })
    .catch(error => {
        console.error('Error saving patient:', error);
    })
    .finally(() => {
        saveBtn.innerHTML = originalText;
        saveBtn.disabled = false;
    });
}

// ============================================================================
// CARGAR ESTADÍSTICAS
// ============================================================================
function loadStatistics() {
    fetch('/api/stats')
        .then(response => response.json())
        .then(data => {
            // Detectar rol y asignar estadísticas
            if (data.my_appointments !== undefined) {
                // PROFESSIONAL
                document.getElementById('stat1').textContent = data.my_appointments_programada || 0;
                document.getElementById('label1').textContent = 'Citas Pendientes';
                
                document.getElementById('stat2').textContent = data.my_appointments_completada || 0;
                document.getElementById('label2').textContent = 'Citas Completadas';
                
                document.getElementById('stat3').textContent = data.appointments_today || 0;
                document.getElementById('label3').textContent = 'Citas Hoy';
            }
            
            animateCounters();
        })
        .catch(error => {
            console.error('Error loading statistics:', error);
        });
}

// ============================================================================
// ANIMAR CONTADORES
// ============================================================================
function animateCounters() {
    document.querySelectorAll('.stat-value').forEach(el => {
        const target = parseInt(el.textContent) || 0;
        let current = 0;
        const increment = Math.max(1, target / 30);
        const duration = 1000; // 1 segundo
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
// HELPERS
// ============================================================================
function formatDateTimeLocal(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    return `${year}-${month}-${day}T${hours}:${minutes}`;
}

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

    const formattedMessage = message.replace(/\n/g, '<br>');

    toastContainer.innerHTML = `
        <div class="alert ${alertClass} alert-dismissible fade show" role="alert">
            <i class="fas ${icon} me-2"></i>${formattedMessage}
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
// ANIMACIONES CSS (HELPERS)
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
window.openNewAppointmentModal = openNewAppointmentModal;
window.openNewPatientModal = openNewPatientModal;
window.saveAppointment = saveAppointment;
window.saveNewPatient = saveNewPatient;
window.completeAppointment = completeAppointment;
window.cancelAppointment = cancelAppointment;
window.sendWhatsAppReminder = sendWhatsAppReminder;
window.loadAppointmentsList = loadAppointmentsList;
window.loadCancelledAppointments = loadCancelledAppointments;
window.formatDateTimeLocal = formatDateTimeLocal;