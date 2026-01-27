from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from project import db
from project.models import (
    Appointment, Patient, Service, User, Notification, Clinic,
    AppointmentStatus, UserRole, get_peru_time, PERU_TZ
)
from datetime import datetime
from sqlalchemy import and_, or_

api_bp = Blueprint('api', __name__)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
def parse_datetime(date_string):
    """
    Parsea una fecha ISO 8601 y la convierte a datetime naive en zona horaria de Perú.
    
    Args:
        date_string (str): Fecha en formato ISO 8601
    
    Returns:
        datetime: Datetime naive en zona horaria de Perú
    
    Raises:
        ValueError: Si el formato es inválido
    """
    try:
        # Parsear el string ISO (soporta con/sin timezone)
        dt = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        
        # Si tiene timezone, convertir a Perú
        if dt.tzinfo is not None:
            dt_peru = dt.astimezone(PERU_TZ)
        else:
            # Es hora naive, asumimos que ya es hora de Perú
            dt_peru = dt.replace(tzinfo=PERU_TZ)
        
        # Retornar como naive (sin timezone) para SQLite
        return dt_peru.replace(tzinfo=None)
        
    except (ValueError, AttributeError) as e:
        raise ValueError(f'Formato de fecha inválido: {date_string}. Usa ISO 8601 (ej: 2025-01-15T09:00:00)')


def get_user_clinic_id():
    """
    Obtiene el clinic_id del usuario autenticado.
    SUPER_ADMIN retorna None (acceso a todas las clínicas).
    
    Returns:
        int | None: ID de clínica o None para SUPER_ADMIN
    """
    if current_user.is_super_admin():
        return None  # Acceso global
    return current_user.clinic_id


def verify_clinic_access(clinic_id):
    """
    Verifica si el usuario tiene acceso a una clínica específica.
    
    Args:
        clinic_id (int): ID de la clínica
    
    Returns:
        bool: True si tiene acceso, False en caso contrario
    """
    if current_user.is_super_admin():
        return True
    return current_user.clinic_id == clinic_id


# ============================================================================
# API: PACIENTES (PATIENTS)
# ============================================================================
@api_bp.route('/patients', methods=['GET'])
@login_required
def get_patients():
    """
    GET: Obtiene lista de pacientes filtrada por clínica.
    Query params:
        - search (str): Búsqueda por nombre o teléfono
        - limit (int): Límite de resultados (default: 50)
    """
    clinic_id = get_user_clinic_id()
    
    # Base query con filtro de clínica
    if clinic_id:
        query = Patient.query.filter_by(clinic_id=clinic_id)
    else:
        # SUPER_ADMIN: necesita especificar clinic_id
        clinic_id_param = request.args.get('clinic_id', type=int)
        if not clinic_id_param:
            return jsonify({'error': 'clinic_id requerido para SUPER_ADMIN'}), 400
        query = Patient.query.filter_by(clinic_id=clinic_id_param)
    
    # Búsqueda opcional
    search = request.args.get('search', '').strip()
    if search:
        query = query.filter(
            or_(
                Patient.name.ilike(f'%{search}%'),
                Patient.phone.ilike(f'%{search}%'),
                Patient.email.ilike(f'%{search}%')
            )
        )
    
    # Límite
    limit = request.args.get('limit', 50, type=int)
    patients = query.order_by(Patient.name).limit(limit).all()
    
    return jsonify([patient.to_dict() for patient in patients])


@api_bp.route('/patients/<int:id>', methods=['GET'])
@login_required
def get_patient(id):
    """GET: Obtiene un paciente específico"""
    patient = Patient.query.get_or_404(id)
    
    # Verificar acceso a la clínica
    if not verify_clinic_access(patient.clinic_id):
        return jsonify({'error': 'No autorizado para ver este paciente'}), 403
    
    return jsonify(patient.to_dict())


@api_bp.route('/patients', methods=['POST'])
@login_required
def create_patient():
    """
    POST: Crea un nuevo paciente
    
    TAREA 1 FIX: Validación de campos opcionales antes de .strip()
    """
    # Solo PROFESSIONAL o superior puede crear pacientes
    if not current_user.can_manage_appointments():
        return jsonify({'error': 'No autorizado para crear pacientes'}), 403
    
    data = request.get_json()
    
    # Validaciones
    if not data.get('name') or not data.get('phone'):
        return jsonify({'error': 'Nombre y teléfono son requeridos'}), 400
    
    clinic_id = get_user_clinic_id()
    if not clinic_id:
        return jsonify({'error': 'SUPER_ADMIN debe especificar clinic_id'}), 400
    
    # Verificar duplicado por teléfono en la misma clínica
    existing = Patient.query.filter_by(
        phone=data['phone'],
        clinic_id=clinic_id
    ).first()
    
    if existing:
        return jsonify({
            'error': 'Ya existe un paciente con este teléfono en esta clínica',
            'existing_patient': existing.to_dict()
        }), 400
    
    # Crear paciente
    try:
        # ✅ TAREA 1 FIX: Validar antes de .strip()
        email_value = data.get('email')
        address_value = data.get('address')
        notes_value = data.get('notes')
        
        patient = Patient(
            clinic_id=clinic_id,
            name=data['name'].strip(),
            phone=data['phone'].strip(),
            email=email_value.strip() if email_value else None,  # ✅ FIX
            date_of_birth=datetime.fromisoformat(data['date_of_birth']).date() if data.get('date_of_birth') else None,
            address=address_value.strip() if address_value else None,  # ✅ FIX
            notes=notes_value.strip() if notes_value else None  # ✅ FIX
        )
        
        db.session.add(patient)
        db.session.commit()
        
        return jsonify({
            'message': 'Paciente creado exitosamente',
            'patient': patient.to_dict()
        }), 201
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al crear paciente: {str(e)}'}), 500


@api_bp.route('/patients/<int:id>', methods=['PUT'])
@login_required
def update_patient(id):
    """PUT: Actualiza un paciente existente"""
    patient = Patient.query.get_or_404(id)
    
    # Verificar acceso
    if not verify_clinic_access(patient.clinic_id):
        return jsonify({'error': 'No autorizado'}), 403
    
    if not current_user.can_manage_appointments():
        return jsonify({'error': 'No autorizado'}), 403
    
    data = request.get_json()
    
    try:
        # Actualizar campos con validación similar
        if 'name' in data:
            patient.name = data['name'].strip()
        if 'phone' in data:
            patient.phone = data['phone'].strip()
        if 'email' in data:
            email_value = data['email']
            patient.email = email_value.strip() if email_value else None
        if 'date_of_birth' in data:
            patient.date_of_birth = datetime.fromisoformat(data['date_of_birth']).date() if data['date_of_birth'] else None
        if 'address' in data:
            address_value = data['address']
            patient.address = address_value.strip() if address_value else None
        if 'notes' in data:
            notes_value = data['notes']
            patient.notes = notes_value.strip() if notes_value else None
        
        db.session.commit()
        
        return jsonify({
            'message': 'Paciente actualizado exitosamente',
            'patient': patient.to_dict()
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al actualizar paciente: {str(e)}'}), 500


# ============================================================================
# API: SERVICIOS (SERVICES)
# ============================================================================
@api_bp.route('/services', methods=['GET'])
@login_required
def get_services():
    """GET: Obtiene lista de servicios activos de la clínica"""
    clinic_id = get_user_clinic_id()
    
    if clinic_id:
        services = Service.query.filter_by(
            clinic_id=clinic_id,
            is_active=True
        ).order_by(Service.name).all()
    else:
        # SUPER_ADMIN necesita especificar clinic_id
        clinic_id_param = request.args.get('clinic_id', type=int)
        if not clinic_id_param:
            return jsonify({'error': 'clinic_id requerido para SUPER_ADMIN'}), 400
        services = Service.query.filter_by(
            clinic_id=clinic_id_param,
            is_active=True
        ).order_by(Service.name).all()
    
    return jsonify([service.to_dict() for service in services])


# ============================================================================
# API: PROFESIONALES (PROFESSIONALS)
# ============================================================================
@api_bp.route('/professionals', methods=['GET'])
@login_required
def get_professionals():
    """GET: Obtiene lista de profesionales activos de la clínica"""
    clinic_id = get_user_clinic_id()
    
    if clinic_id:
        professionals = User.query.filter_by(
            clinic_id=clinic_id,
            role=UserRole.PROFESSIONAL,
            is_active=True
        ).order_by(User.full_name).all()
    else:
        # SUPER_ADMIN necesita especificar clinic_id
        clinic_id_param = request.args.get('clinic_id', type=int)
        if not clinic_id_param:
            return jsonify({'error': 'clinic_id requerido para SUPER_ADMIN'}), 400
        professionals = User.query.filter_by(
            clinic_id=clinic_id_param,
            role=UserRole.PROFESSIONAL,
            is_active=True
        ).order_by(User.full_name).all()
    
    return jsonify([
        {
            'id': prof.id,
            'username': prof.username,
            'full_name': prof.full_name or prof.username,
            'email': prof.email,
            'phone': prof.phone
        }
        for prof in professionals
    ])


# ============================================================================
# TAREA 2: NUEVO ENDPOINT - BÚSQUEDA AUTOCOMPLETE DE PACIENTES
# ============================================================================
@api_bp.route('/search/patients', methods=['GET'])
@login_required
def search_patients():
    """
    GET: Búsqueda autocomplete de pacientes por nombre o teléfono.
    PRIORIDAD: Primero teléfono, luego nombre.
    
    Query params:
        - q (str): Término de búsqueda (mínimo 1 carácter)
    
    Returns:
        JSON: Lista de hasta 10 pacientes con {id, name, phone}
    """
    query_term = request.args.get('q', '').strip()
    
    # Validación: al menos 1 carácter
    if not query_term or len(query_term) < 1:
        return jsonify([])
    
    clinic_id = get_user_clinic_id()
    
    # Base query
    if clinic_id:
        base_query = Patient.query.filter_by(clinic_id=clinic_id)
    else:
        # SUPER_ADMIN necesita especificar clinic_id
        clinic_id_param = request.args.get('clinic_id', type=int)
        if not clinic_id_param:
            return jsonify({'error': 'clinic_id requerido para SUPER_ADMIN'}), 400
        base_query = Patient.query.filter_by(clinic_id=clinic_id_param)
    
    # ✅ BÚSQUEDA CON PRIORIDAD: Teléfono PRIMERO, luego Nombre
    
    # 1️⃣ Buscar por TELÉFONO (prioridad alta)
    phone_matches = base_query.filter(
        Patient.phone.ilike(f'{query_term}%')
    ).order_by(Patient.name).limit(10).all()
    
    # 2️⃣ Buscar por NOMBRE (solo si no hay suficientes resultados por teléfono)
    name_matches = []
    if len(phone_matches) < 10:
        remaining_slots = 10 - len(phone_matches)
        
        # Excluir IDs que ya están en phone_matches
        exclude_ids = [p.id for p in phone_matches]
        
        name_query = base_query.filter(
            Patient.name.ilike(f'{query_term}%')
        )
        
        if exclude_ids:
            name_query = name_query.filter(~Patient.id.in_(exclude_ids))
        
        name_matches = name_query.order_by(Patient.name).limit(remaining_slots).all()
    
    # 3️⃣ Combinar resultados: TELÉFONO primero, luego NOMBRE
    patients = phone_matches + name_matches
    
    # Retornar formato simplificado para autocomplete
    return jsonify([
        {
            'id': patient.id,
            'name': patient.name,
            'phone': patient.phone
        }
        for patient in patients
    ])

# ============================================================================
# API: CITAS (APPOINTMENTS) - CRUD COMPLETO
# ============================================================================
@api_bp.route('/appointments', methods=['GET'])
@login_required
def get_appointments():
    """
    GET: Obtiene citas filtradas por clínica y rol del usuario.
    Query params:
        - start (str): Fecha inicio (ISO 8601)
        - end (str): Fecha fin (ISO 8601)
        - professional_id (int): Filtrar por profesional
        - status (str): Filtrar por estado
    """
    clinic_id = get_user_clinic_id()
    
    # Base query según rol
    if current_user.is_super_admin():
        # SUPER_ADMIN necesita especificar clinic_id
        clinic_id_param = request.args.get('clinic_id', type=int)
        if not clinic_id_param:
            return jsonify({'error': 'clinic_id requerido para SUPER_ADMIN'}), 400
        query = Appointment.query.filter_by(clinic_id=clinic_id_param)
    
    elif current_user.is_clinic_admin():
        # CLINIC_ADMIN ve todas las citas de su clínica
        query = Appointment.query.filter_by(clinic_id=clinic_id)
    
    elif current_user.is_professional():
        # PROFESSIONAL solo ve sus propias citas
        query = Appointment.query.filter_by(
            clinic_id=clinic_id,
            professional_id=current_user.id
        )
    
    else:
        return jsonify({'error': 'Rol no autorizado'}), 403
    
    # Filtros adicionales
    # Rango de fechas
    start_str = request.args.get('start')
    end_str = request.args.get('end')
    
    if start_str and end_str:
        try:
            start_dt = parse_datetime(start_str)
            end_dt = parse_datetime(end_str)
            query = query.filter(
                and_(
                    Appointment.start_datetime >= start_dt,
                    Appointment.end_datetime <= end_dt
                )
            )
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
    
    # Filtro por profesional (solo para CLINIC_ADMIN)
    professional_id = request.args.get('professional_id', type=int)
    if professional_id and current_user.is_clinic_admin():
        query = query.filter_by(professional_id=professional_id)
    
    # Filtro por estado
    status = request.args.get('status')
    if status:
        try:
            query = query.filter_by(status=AppointmentStatus(status))
        except ValueError:
            return jsonify({'error': f'Estado inválido: {status}'}), 400
    
    # Excluir canceladas por defecto (a menos que se pida explícitamente)
    include_cancelled = request.args.get('include_cancelled', 'false').lower() == 'true'
    if not include_cancelled:
        query = query.filter(
            Appointment.status.in_([
                AppointmentStatus.PROGRAMADA,
                AppointmentStatus.COMPLETADA
            ])
        )
    
    # Ordenar por fecha
    appointments = query.order_by(Appointment.start_datetime).all()
    
    # Formato para FullCalendar
    return jsonify([apt.to_fullcalendar_event() for apt in appointments])


@api_bp.route('/appointments/<int:id>', methods=['GET'])
@login_required
def get_appointment(id):
    """GET: Obtiene una cita específica"""
    appointment = Appointment.query.get_or_404(id)
    
    # Verificar acceso
    if not verify_clinic_access(appointment.clinic_id):
        return jsonify({'error': 'No autorizado'}), 403
    
    # PROFESSIONAL solo puede ver sus propias citas
    if current_user.is_professional() and appointment.professional_id != current_user.id:
        return jsonify({'error': 'No autorizado para ver esta cita'}), 403
    
    return jsonify(appointment.to_dict())


@api_bp.route('/appointments', methods=['POST'])
@login_required
def create_appointment():
    """
    POST: Crea una nueva cita con validación anti-solapamiento.
    """
    if not current_user.can_manage_appointments():
        return jsonify({'error': 'No autorizado para crear citas'}), 403
    
    data = request.get_json()
    
    # Validaciones de campos requeridos
    required_fields = ['patient_id', 'service_id', 'start_datetime', 'end_datetime']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Campo requerido: {field}'}), 400
    
    # Parsear fechas
    try:
        start_dt = parse_datetime(data['start_datetime'])
        end_dt = parse_datetime(data['end_datetime'])
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    
    # Validar que end > start
    if end_dt <= start_dt:
        return jsonify({'error': 'La fecha de fin debe ser posterior a la fecha de inicio'}), 400
    
    # Obtener clinic_id
    clinic_id = get_user_clinic_id()
    if not clinic_id:
        return jsonify({'error': 'SUPER_ADMIN debe especificar clinic_id'}), 400
    
    # Determinar professional_id
    if current_user.is_clinic_admin():
        # CLINIC_ADMIN puede asignar a cualquier profesional de su clínica
        professional_id = data.get('professional_id')
        if not professional_id:
            return jsonify({'error': 'professional_id requerido para CLINIC_ADMIN'}), 400
        
        # Verificar que el profesional pertenece a la clínica
        professional = User.query.get(professional_id)
        if not professional or professional.clinic_id != clinic_id:
            return jsonify({'error': 'Profesional no encontrado en esta clínica'}), 404
    else:
        # PROFESSIONAL crea citas para sí mismo
        professional_id = current_user.id
    
    # Verificar que el paciente pertenece a la clínica
    patient = Patient.query.get(data['patient_id'])
    if not patient or patient.clinic_id != clinic_id:
        return jsonify({'error': 'Paciente no encontrado en esta clínica'}), 404
    
    # Verificar que el servicio pertenece a la clínica
    service = Service.query.get(data['service_id'])
    if not service or service.clinic_id != clinic_id:
        return jsonify({'error': 'Servicio no encontrado en esta clínica'}), 404
    
    # ========================================================================
    # VALIDACIÓN CRÍTICA: ANTI-SOLAPAMIENTO
    # ========================================================================
    overlapping = Appointment.check_overlap(
        clinic_id=clinic_id,
        professional_id=professional_id,
        start_dt=start_dt,
        end_dt=end_dt
    )
    
    if overlapping:
        return jsonify({
            'error': 'Conflict',
            'message': 'El horario se solapa con otra cita existente',
            'conflicting_appointment': {
                'id': overlapping.id,
                'patient': overlapping.patient.name,
                'start': overlapping.start_datetime.replace(tzinfo=PERU_TZ).isoformat(),
                'end': overlapping.end_datetime.replace(tzinfo=PERU_TZ).isoformat()
            }
        }), 409  # HTTP 409 Conflict
    
    # ========================================================================
    # CREAR CITA
    # ========================================================================
    try:
        notes_value = data.get('notes', '')
        
        appointment = Appointment(
            clinic_id=clinic_id,
            professional_id=professional_id,
            patient_id=data['patient_id'],
            service_id=data['service_id'],
            start_datetime=start_dt,
            end_datetime=end_dt,
            status=AppointmentStatus.PROGRAMADA,
            notes=notes_value.strip() if notes_value else None
        )
        
        db.session.add(appointment)
        db.session.commit()
        
        return jsonify({
            'message': 'Cita creada exitosamente',
            'appointment': appointment.to_dict()
        }), 201
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al crear cita: {str(e)}'}), 500


@api_bp.route('/appointments/<int:id>', methods=['PUT'])
@login_required
def update_appointment(id):
    """
    PUT: Actualiza una cita existente (fechas, paciente, servicio, notas).
    NO cambia el estado (usar endpoints dedicados).
    """
    appointment = Appointment.query.get_or_404(id)
    
    # Verificar acceso
    if not verify_clinic_access(appointment.clinic_id):
        return jsonify({'error': 'No autorizado'}), 403
    
    # PROFESSIONAL solo puede editar sus propias citas
    if current_user.is_professional() and appointment.professional_id != current_user.id:
        return jsonify({'error': 'No autorizado'}), 403
    
    # Solo se pueden editar citas programadas o no asistió
    if not appointment.can_be_edited():
        return jsonify({'error': 'No se puede editar una cita completada o cancelada'}), 400
    
    data = request.get_json()
    
    # Parsear nuevas fechas si se proporcionan
    start_dt = appointment.start_datetime
    end_dt = appointment.end_datetime
    
    if 'start_datetime' in data:
        try:
            start_dt = parse_datetime(data['start_datetime'])
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
    
    if 'end_datetime' in data:
        try:
            end_dt = parse_datetime(data['end_datetime'])
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
    
    # Validar que end > start
    if end_dt <= start_dt:
        return jsonify({'error': 'La fecha de fin debe ser posterior a la fecha de inicio'}), 400
    
    # ========================================================================
    # VALIDACIÓN CRÍTICA: ANTI-SOLAPAMIENTO (excluyendo esta cita)
    # ========================================================================
    if 'start_datetime' in data or 'end_datetime' in data:
        overlapping = Appointment.check_overlap(
            clinic_id=appointment.clinic_id,
            professional_id=appointment.professional_id,
            start_dt=start_dt,
            end_dt=end_dt,
            exclude_appointment_id=id
        )
        
        if overlapping:
            return jsonify({
                'error': 'Conflict',
                'message': 'El nuevo horario se solapa con otra cita existente',
                'conflicting_appointment': {
                    'id': overlapping.id,
                    'patient': overlapping.patient.name,
                    'start': overlapping.start_datetime.replace(tzinfo=PERU_TZ).isoformat(),
                    'end': overlapping.end_datetime.replace(tzinfo=PERU_TZ).isoformat()
                }
            }), 409
    
    # ========================================================================
    # ACTUALIZAR CITA
    # ========================================================================
    try:
        appointment.start_datetime = start_dt
        appointment.end_datetime = end_dt
        
        # Actualizar otros campos si se proporcionan
        if 'patient_id' in data:
            patient = Patient.query.get(data['patient_id'])
            if not patient or patient.clinic_id != appointment.clinic_id:
                return jsonify({'error': 'Paciente no encontrado en esta clínica'}), 404
            appointment.patient_id = data['patient_id']
        
        if 'service_id' in data:
            service = Service.query.get(data['service_id'])
            if not service or service.clinic_id != appointment.clinic_id:
                return jsonify({'error': 'Servicio no encontrado en esta clínica'}), 404
            appointment.service_id = data['service_id']
        
        if 'notes' in data:
            notes_value = data['notes']
            appointment.notes = notes_value.strip() if notes_value else None
        
        db.session.commit()
        
        return jsonify({
            'message': 'Cita actualizada exitosamente',
            'appointment': appointment.to_dict()
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al actualizar cita: {str(e)}'}), 500


@api_bp.route('/appointments/<int:id>/complete', methods=['POST'])
@login_required
def complete_appointment(id):
    """POST: Marca una cita como completada"""
    appointment = Appointment.query.get_or_404(id)
    
    # Verificar acceso
    if not verify_clinic_access(appointment.clinic_id):
        return jsonify({'error': 'No autorizado'}), 403
    
    if current_user.is_professional() and appointment.professional_id != current_user.id:
        return jsonify({'error': 'No autorizado'}), 403
    
    try:
        appointment.complete()
        db.session.commit()
        
        return jsonify({
            'message': 'Cita marcada como completada',
            'appointment': appointment.to_dict()
        })
    
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al completar cita: {str(e)}'}), 500


@api_bp.route('/appointments/<int:id>/cancel', methods=['POST'])
@login_required
def cancel_appointment(id):
    """POST: Cancela una cita con motivo opcional"""
    appointment = Appointment.query.get_or_404(id)
    
    # Verificar acceso
    if not verify_clinic_access(appointment.clinic_id):
        return jsonify({'error': 'No autorizado'}), 403
    
    if current_user.is_professional() and appointment.professional_id != current_user.id:
        return jsonify({'error': 'No autorizado'}), 403
    
    data = request.get_json() or {}
    reason = data.get('reason', 'Cancelado por el profesional')
    
    try:
        appointment.cancel(reason)
        db.session.commit()
        
        return jsonify({
            'message': 'Cita cancelada exitosamente',
            'appointment': appointment.to_dict()
        })
    
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al cancelar cita: {str(e)}'}), 500


@api_bp.route('/appointments/<int:id>/mark-no-show', methods=['POST'])
@login_required
def mark_no_show(id):
    """POST: Marca una cita como 'No Asistió'"""
    appointment = Appointment.query.get_or_404(id)
    
    # Verificar acceso
    if not verify_clinic_access(appointment.clinic_id):
        return jsonify({'error': 'No autorizado'}), 403
    
    if current_user.is_professional() and appointment.professional_id != current_user.id:
        return jsonify({'error': 'No autorizado'}), 403
    
    data = request.get_json() or {}
    reason = data.get('reason', 'El paciente no asistió a la cita')
    
    try:
        appointment.mark_no_show(reason)
        db.session.commit()
        
        return jsonify({
            'message': 'Cita marcada como "No Asistió"',
            'appointment': appointment.to_dict()
        })
    
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al marcar cita: {str(e)}'}), 500


@api_bp.route('/appointments/<int:id>', methods=['DELETE'])
@login_required
def delete_appointment(id):
    """
    DELETE: Elimina permanentemente una cita.
    Solo CLINIC_ADMIN o SUPER_ADMIN pueden eliminar.
    """
    appointment = Appointment.query.get_or_404(id)
    
    # Solo admin puede eliminar permanentemente
    if not (current_user.is_super_admin() or current_user.is_clinic_admin()):
        return jsonify({'error': 'Solo administradores pueden eliminar citas permanentemente'}), 403
    
    # Verificar acceso a la clínica
    if not verify_clinic_access(appointment.clinic_id):
        return jsonify({'error': 'No autorizado'}), 403
    
    try:
        db.session.delete(appointment)
        db.session.commit()
        
        return jsonify({'message': 'Cita eliminada permanentemente'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al eliminar cita: {str(e)}'}), 500


# ============================================================================
# API: NOTIFICACIONES
# ============================================================================
@api_bp.route('/notifications', methods=['GET'])
@login_required
def get_notifications():
    """GET: Obtiene notificaciones no leídas del usuario"""
    notifications = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).order_by(Notification.created_at.desc()).limit(10).all()
    
    return jsonify([notif.to_dict() for notif in notifications])


@api_bp.route('/notifications/<int:id>/read', methods=['POST'])
@login_required
def mark_notification_read(id):
    """POST: Marca una notificación como leída"""
    notification = Notification.query.get_or_404(id)
    
    # Verificar que pertenece al usuario
    if notification.user_id != current_user.id:
        return jsonify({'error': 'No autorizado'}), 403
    
    notification.is_read = True
    db.session.commit()
    
    return jsonify({'message': 'Notificación marcada como leída'})


# ============================================================================
# API: ESTADÍSTICAS
# ============================================================================
@api_bp.route('/stats', methods=['GET'])
@login_required
def get_stats():
    """GET: Obtiene estadísticas según el rol del usuario"""
    clinic_id = get_user_clinic_id()
    stats = {}
    
    if current_user.is_super_admin():
        # Estadísticas globales
        stats['total_clinics'] = Clinic.query.filter_by(is_active=True).count()
        stats['total_users'] = User.query.count()
        stats['total_appointments'] = Appointment.query.count()
    
    elif current_user.is_clinic_admin():
        # Estadísticas de la clínica
        stats['professionals_count'] = User.query.filter_by(
            clinic_id=clinic_id,
            role=UserRole.PROFESSIONAL,
            is_active=True
        ).count()
        stats['patients_count'] = Patient.query.filter_by(clinic_id=clinic_id).count()
        stats['appointments_programada'] = Appointment.query.filter_by(
            clinic_id=clinic_id,
            status=AppointmentStatus.PROGRAMADA
        ).count()
        stats['appointments_completada'] = Appointment.query.filter_by(
            clinic_id=clinic_id,
            status=AppointmentStatus.COMPLETADA
        ).count()
        stats['appointments_cancelada'] = Appointment.query.filter_by(
            clinic_id=clinic_id,
            status=AppointmentStatus.CANCELADA
        ).count()
    
    elif current_user.is_professional():
        # Estadísticas del profesional
        stats['my_appointments_programada'] = Appointment.query.filter_by(
            professional_id=current_user.id,
            status=AppointmentStatus.PROGRAMADA
        ).count()
        stats['my_appointments_completada'] = Appointment.query.filter_by(
            professional_id=current_user.id,
            status=AppointmentStatus.COMPLETADA
        ).count()
        stats['my_appointments_cancelada'] = Appointment.query.filter_by(
            professional_id=current_user.id,
            status=AppointmentStatus.CANCELADA
        ).count()
        
        # Citas de hoy
        from datetime import date
        today_start = datetime.combine(date.today(), datetime.min.time())
        today_end = datetime.combine(date.today(), datetime.max.time())
        
        stats['appointments_today'] = Appointment.query.filter(
            Appointment.professional_id == current_user.id,
            Appointment.start_datetime >= today_start,
            Appointment.start_datetime <= today_end,
            Appointment.status == AppointmentStatus.PROGRAMADA
        ).count()
    
    return jsonify(stats)



# ============================================================================
# API: DISPONIBILIDAD DE HORARIOS
# ============================================================================
@api_bp.route('/availability', methods=['GET'])
@login_required
def check_availability():
    """
    GET: Verifica disponibilidad de un profesional en un rango de fechas.
    Query params:
        - professional_id (int): ID del profesional
        - date (str): Fecha a consultar (YYYY-MM-DD)
        - duration (int): Duración en minutos (default: 30)
    """
    professional_id = request.args.get('professional_id', type=int)
    date_str = request.args.get('date')
    duration = request.args.get('duration', 30, type=int)
    
    if not professional_id or not date_str:
        return jsonify({'error': 'professional_id y date son requeridos'}), 400
    
    # Verificar que el profesional pertenece a la clínica (excepto SUPER_ADMIN)
    professional = User.query.get_or_404(professional_id)
    if not verify_clinic_access(professional.clinic_id):
        return jsonify({'error': 'No autorizado'}), 403
    
    # Parsear fecha
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Formato de fecha inválido. Usa YYYY-MM-DD'}), 400
    
    # Obtener todas las citas del profesional en esa fecha
    day_start = datetime.combine(target_date, datetime.min.time())
    day_end = datetime.combine(target_date, datetime.max.time())
    
    appointments = Appointment.query.filter(
        Appointment.professional_id == professional_id,
        Appointment.clinic_id == professional.clinic_id,
        Appointment.start_datetime >= day_start,
        Appointment.start_datetime <= day_end,
        Appointment.status.in_([AppointmentStatus.PROGRAMADA, AppointmentStatus.COMPLETADA])
    ).order_by(Appointment.start_datetime).all()
    
    # Construir slots disponibles (horario: 8:00 - 20:00, cada 30 min)
    from datetime import time, timedelta
    
    work_start = datetime.combine(target_date, time(8, 0))
    work_end = datetime.combine(target_date, time(20, 0))
    slot_duration = timedelta(minutes=duration)
    
    available_slots = []
    current_slot = work_start
    
    while current_slot + slot_duration <= work_end:
        slot_end = current_slot + slot_duration
        
        # Verificar si el slot está ocupado
        is_occupied = any(
            apt.start_datetime < slot_end and apt.end_datetime > current_slot
            for apt in appointments
        )
        
        if not is_occupied:
            available_slots.append({
                'start': current_slot.replace(tzinfo=PERU_TZ).isoformat(),
                'end': slot_end.replace(tzinfo=PERU_TZ).isoformat()
            })
        
        current_slot += slot_duration
    
    return jsonify({
        'professional_id': professional_id,
        'date': date_str,
        'duration_minutes': duration,
        'available_slots': available_slots,
        'total_available': len(available_slots)
    })


# ============================================================================
# API: RECORDATORIOS DE WHATSAPP (DEEP LINK)
# ============================================================================
@api_bp.route('/appointments/<int:id>/whatsapp-reminder', methods=['GET'])
@login_required
def get_whatsapp_reminder(id):
    """
    GET: Genera deep link de WhatsApp para enviar recordatorio.
    """
    appointment = Appointment.query.get_or_404(id)
    
    # Verificar acceso
    if not verify_clinic_access(appointment.clinic_id):
        return jsonify({'error': 'No autorizado'}), 403
    
    if current_user.is_professional() and appointment.professional_id != current_user.id:
        return jsonify({'error': 'No autorizado'}), 403
    
    # Obtener paciente
    patient = appointment.patient
    if not patient or not patient.phone:
        return jsonify({'error': 'El paciente no tiene número de teléfono registrado'}), 400
    
    # Formatear fecha/hora de la cita
    start_dt = appointment.start_datetime.replace(tzinfo=PERU_TZ)
    fecha_str = start_dt.strftime('%d/%m/%Y')
    hora_str = start_dt.strftime('%H:%M')
    
    # Construir mensaje personalizado
    service_name = appointment.service.name if appointment.service else 'consulta'
    clinic_name = appointment.clinic.name if appointment.clinic else 'nuestra clínica'
    
    message = (
        f"Hola {patient.name}, "
        f"te recordamos tu cita de {service_name} "
        f"el {fecha_str} a las {hora_str} hrs "
        f"en {clinic_name}. "
        f"¡Te esperamos!"
    )
    
    # Generar deep link
    whatsapp_link = patient.get_whatsapp_link(message)
    
    if not whatsapp_link:
        return jsonify({'error': 'No se pudo generar el enlace de WhatsApp'}), 500
    
    return jsonify({
        'whatsapp_link': whatsapp_link,
        'patient_name': patient.name,
        'patient_phone': patient.phone,
        'message': message
    })


# ============================================================================
# API: EXPORTACIÓN DE DATOS (CSV)
# ============================================================================
@api_bp.route('/export/appointments', methods=['GET'])
@login_required
def export_appointments_csv():
    """
    GET: Exporta citas a formato CSV.
    Query params:
        - start (str): Fecha inicio (YYYY-MM-DD)
        - end (str): Fecha fin (YYYY-MM-DD)
        - status (str): Filtrar por estado
    """
    from flask import Response
    import csv
    from io import StringIO
    
    clinic_id = get_user_clinic_id()
    
    # Base query según rol
    if current_user.is_super_admin():
        clinic_id_param = request.args.get('clinic_id', type=int)
        if not clinic_id_param:
            return jsonify({'error': 'clinic_id requerido para SUPER_ADMIN'}), 400
        query = Appointment.query.filter_by(clinic_id=clinic_id_param)
    elif current_user.is_clinic_admin():
        query = Appointment.query.filter_by(clinic_id=clinic_id)
    elif current_user.is_professional():
        query = Appointment.query.filter_by(
            clinic_id=clinic_id,
            professional_id=current_user.id
        )
    else:
        return jsonify({'error': 'No autorizado'}), 403
    
    # Filtros
    start_str = request.args.get('start')
    end_str = request.args.get('end')
    
    if start_str and end_str:
        try:
            start_date = datetime.strptime(start_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_str, '%Y-%m-%d')
            query = query.filter(
                and_(
                    Appointment.start_datetime >= start_date,
                    Appointment.start_datetime <= end_date
                )
            )
        except ValueError:
            return jsonify({'error': 'Formato de fecha inválido. Usa YYYY-MM-DD'}), 400
    
    status = request.args.get('status')
    if status:
        try:
            query = query.filter_by(status=AppointmentStatus(status))
        except ValueError:
            return jsonify({'error': f'Estado inválido: {status}'}), 400
    
    appointments = query.order_by(Appointment.start_datetime).all()
    
    # Crear CSV
    output = StringIO()
    writer = csv.writer(output)
    
    # Headers
    writer.writerow([
        'ID',
        'Fecha',
        'Hora Inicio',
        'Hora Fin',
        'Paciente',
        'Teléfono',
        'Servicio',
        'Profesional',
        'Estado',
        'Notas'
    ])
    
    # Datos
    for apt in appointments:
        start_dt = apt.start_datetime.replace(tzinfo=PERU_TZ)
        end_dt = apt.end_datetime.replace(tzinfo=PERU_TZ)
        
        writer.writerow([
            apt.id,
            start_dt.strftime('%Y-%m-%d'),
            start_dt.strftime('%H:%M'),
            end_dt.strftime('%H:%M'),
            apt.patient.name if apt.patient else 'N/A',
            apt.patient.phone if apt.patient else 'N/A',
            apt.service.name if apt.service else 'N/A',
            apt.professional.full_name or apt.professional.username if apt.professional else 'N/A',
            apt.status.value,
            apt.notes or ''
        ])

    # Preparar respuesta
    output.seek(0)
    filename = f"citas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename={filename}'
        }
    )


# ============================================================================
# API: REPORTES (para CLINIC_ADMIN)
# ============================================================================
@api_bp.route('/reports/summary', methods=['GET'])
@login_required
def get_report_summary():
    """
    GET: Obtiene resumen de reportes para un rango de fechas.
    Query params:
        - start (str): Fecha inicio (YYYY-MM-DD)
        - end (str): Fecha fin (YYYY-MM-DD)
    """
    if not (current_user.is_clinic_admin() or current_user.is_super_admin()):
        return jsonify({'error': 'Solo administradores pueden ver reportes'}), 403
    
    clinic_id = get_user_clinic_id()
    
    start_str = request.args.get('start')
    end_str = request.args.get('end')
    
    if not start_str or not end_str:
        return jsonify({'error': 'start y end son requeridos'}), 400
    
    try:
        start_date = datetime.strptime(start_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_str, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': 'Formato de fecha inválido. Usa YYYY-MM-DD'}), 400
    
    # Base query
    if current_user.is_super_admin():
        clinic_id_param = request.args.get('clinic_id', type=int)
        if not clinic_id_param:
            return jsonify({'error': 'clinic_id requerido para SUPER_ADMIN'}), 400
        query = Appointment.query.filter_by(clinic_id=clinic_id_param)
    else:
        query = Appointment.query.filter_by(clinic_id=clinic_id)
    
    # Filtrar por rango de fechas
    query = query.filter(
        and_(
            Appointment.start_datetime >= start_date,
            Appointment.start_datetime <= end_date
        )
    )
    
    # Contadores por estado
    total_appointments = query.count()
    programadas = query.filter_by(status=AppointmentStatus.PROGRAMADA).count()
    completadas = query.filter_by(status=AppointmentStatus.COMPLETADA).count()
    canceladas = query.filter_by(status=AppointmentStatus.CANCELADA).count()
    no_asistio = query.filter_by(status=AppointmentStatus.NO_ASISTIO).count()
    
    # Ingresos estimados (solo citas completadas con servicio)
    from sqlalchemy import func
    ingresos = db.session.query(func.sum(Service.price)).join(
        Appointment, Appointment.service_id == Service.id
    ).filter(
        Appointment.clinic_id == (clinic_id or clinic_id_param),
        Appointment.status == AppointmentStatus.COMPLETADA,
        Appointment.start_datetime >= start_date,
        Appointment.start_datetime <= end_date
    ).scalar() or 0
    
    # Citas por profesional
    appointments_by_professional = db.session.query(
        User.full_name,
        User.username,
        func.count(Appointment.id).label('count')
    ).join(
        Appointment, Appointment.professional_id == User.id
    ).filter(
        Appointment.clinic_id == (clinic_id or clinic_id_param),
        Appointment.start_datetime >= start_date,
        Appointment.start_datetime <= end_date
    ).group_by(User.id).all()
    
    return jsonify({
        'period': {
            'start': start_str,
            'end': end_str
        },
        'summary': {
            'total': total_appointments,
            'programadas': programadas,
            'completadas': completadas,
            'canceladas': canceladas,
            'no_asistio': no_asistio
        },
        'ingresos_estimados': float(ingresos),
        'by_professional': [
            {
                'name': prof[0] or prof[1],
                'appointments': prof[2]
            }
            for prof in appointments_by_professional
        ]
    })


# ============================================================================
# ERROR HANDLERS ESPECÍFICOS DEL API
# ============================================================================
@api_bp.errorhandler(404)
def api_not_found(error):
    """Handler para recursos no encontrados en el API"""
    return jsonify({'error': 'Recurso no encontrado'}), 404


@api_bp.errorhandler(500)
def api_internal_error(error):
    """Handler para errores internos del servidor en el API"""
    db.session.rollback()
    return jsonify({'error': 'Error interno del servidor'}), 500    
