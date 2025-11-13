from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from functools import wraps
from project import db
from project.models import (
    User, Clinic, Appointment, Patient, Service, Notification,
    AppointmentStatus, UserRole, get_peru_time
)
from sqlalchemy import func, and_, or_
from datetime import datetime, timedelta

clinic_admin_bp = Blueprint('clinic_admin', __name__)


# ============================================================================
# DECORADOR: Solo CLINIC_ADMIN o SUPER_ADMIN
# ============================================================================
def clinic_admin_required(f):
    """Decorador: Solo permite acceso a CLINIC_ADMIN o SUPER_ADMIN"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Por favor inicia sesión para acceder.', 'warning')
            return redirect(url_for('auth.login'))
        
        if not (current_user.is_super_admin() or current_user.is_clinic_admin()):
            flash('Acceso denegado. Se requieren permisos de administrador.', 'danger')
            return redirect(url_for('auth.dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function


def get_clinic_id():
    """
    Obtiene el clinic_id del usuario autenticado.
    Para CLINIC_ADMIN: su clinic_id
    Para SUPER_ADMIN: debe especificar clinic_id en query params
    """
    if current_user.is_super_admin():
        # SUPER_ADMIN necesita especificar clinic_id
        clinic_id = request.args.get('clinic_id', type=int)
        if not clinic_id:
            return None
        return clinic_id
    return current_user.clinic_id


# ============================================================================
# DASHBOARD CLINIC ADMIN
# ============================================================================
@clinic_admin_bp.route('/dashboard')
@login_required
@clinic_admin_required
def dashboard():
    """
    Dashboard principal del Clinic Admin.
    Vista general de su clínica: profesionales, pacientes, citas, servicios.
    """
    clinic_id = get_clinic_id()
    
    if not clinic_id:
        flash('Error: No se pudo determinar la clínica.', 'danger')
        return redirect(url_for('auth.dashboard'))
    
    # Obtener clínica
    clinic = Clinic.query.get_or_404(clinic_id)
    
    # Verificar que la clínica esté activa
    if not clinic.is_active:
        flash('Esta clínica ha sido suspendida. Contacta al administrador del sistema.', 'danger')
        return redirect(url_for('auth.logout'))
    
    # Estadísticas de la clínica
    stats = {
        'professionals': User.query.filter_by(
            clinic_id=clinic_id,
            role=UserRole.PROFESSIONAL,
            is_active=True
        ).count(),
        'patients': Patient.query.filter_by(clinic_id=clinic_id).count(),
        'services': Service.query.filter_by(
            clinic_id=clinic_id,
            is_active=True
        ).count(),
        'appointments_programadas': Appointment.query.filter_by(
            clinic_id=clinic_id,
            status=AppointmentStatus.PROGRAMADA
        ).count(),
        'appointments_completadas': Appointment.query.filter_by(
            clinic_id=clinic_id,
            status=AppointmentStatus.COMPLETADA
        ).count(),
        'appointments_hoy': 0  # Calculado abajo
    }
    
    # Citas de hoy
    today_start = datetime.combine(datetime.now().date(), datetime.min.time())
    today_end = datetime.combine(datetime.now().date(), datetime.max.time())
    
    stats['appointments_hoy'] = Appointment.query.filter(
        Appointment.clinic_id == clinic_id,
        Appointment.start_datetime >= today_start,
        Appointment.start_datetime <= today_end,
        Appointment.status == AppointmentStatus.PROGRAMADA
    ).count()
    
    # Obtener profesionales con sus estadísticas
    professionals = db.session.query(
        User,
        func.count(Appointment.id).label('appointments_count')
    ).outerjoin(
        Appointment,
        and_(
            Appointment.professional_id == User.id,
            Appointment.status != AppointmentStatus.CANCELADA
        )
    ).filter(
        User.clinic_id == clinic_id,
        User.role == UserRole.PROFESSIONAL
    ).group_by(User.id).order_by(User.full_name).all()
    
    return render_template(
        'clinic_admin_dashboard.html',
        user=current_user,
        clinic=clinic,
        stats=stats,
        professionals=professionals
    )


# ============================================================================
# API: GESTIÓN DE PROFESIONALES
# ============================================================================
@clinic_admin_bp.route('/api/professionals', methods=['GET'])
@login_required
@clinic_admin_required
def get_professionals():
    """GET: Obtiene lista de profesionales de la clínica"""
    clinic_id = get_clinic_id()
    
    if not clinic_id:
        return jsonify({'error': 'clinic_id requerido'}), 400
    
    professionals = User.query.filter_by(
        clinic_id=clinic_id,
        role=UserRole.PROFESSIONAL
    ).order_by(User.full_name).all()
    
    # Agregar estadísticas a cada profesional
    professionals_data = []
    for prof in professionals:
        data = prof.to_dict(include_sensitive=True)
        
        # Citas totales
        data['appointments_total'] = Appointment.query.filter_by(
            professional_id=prof.id
        ).count()
        
        # Citas programadas
        data['appointments_programadas'] = Appointment.query.filter_by(
            professional_id=prof.id,
            status=AppointmentStatus.PROGRAMADA
        ).count()
        
        # Citas completadas
        data['appointments_completadas'] = Appointment.query.filter_by(
            professional_id=prof.id,
            status=AppointmentStatus.COMPLETADA
        ).count()
        
        professionals_data.append(data)
    
    return jsonify(professionals_data)


@clinic_admin_bp.route('/api/professionals/<int:id>', methods=['GET'])
@login_required
@clinic_admin_required
def get_professional(id):
    """GET: Obtiene detalles de un profesional específico"""
    professional = User.query.get_or_404(id)
    
    clinic_id = get_clinic_id()
    
    # Verificar que el profesional pertenece a la clínica
    if professional.clinic_id != clinic_id:
        return jsonify({'error': 'Profesional no encontrado en esta clínica'}), 404
    
    if professional.role != UserRole.PROFESSIONAL:
        return jsonify({'error': 'El usuario no es un profesional'}), 400
    
    data = professional.to_dict(include_sensitive=True)
    
    # Estadísticas detalladas
    data['statistics'] = {
        'appointments': {
            'total': Appointment.query.filter_by(professional_id=id).count(),
            'programadas': Appointment.query.filter_by(
                professional_id=id,
                status=AppointmentStatus.PROGRAMADA
            ).count(),
            'completadas': Appointment.query.filter_by(
                professional_id=id,
                status=AppointmentStatus.COMPLETADA
            ).count(),
            'canceladas': Appointment.query.filter_by(
                professional_id=id,
                status=AppointmentStatus.CANCELADA
            ).count(),
            'no_asistio': Appointment.query.filter_by(
                professional_id=id,
                status=AppointmentStatus.NO_ASISTIO
            ).count()
        },
        'patients_attended': db.session.query(
            func.count(func.distinct(Appointment.patient_id))
        ).filter(
            Appointment.professional_id == id,
            Appointment.status == AppointmentStatus.COMPLETADA
        ).scalar() or 0
    }
    
    # Últimas 10 citas
    recent_appointments = Appointment.query.filter_by(
        professional_id=id
    ).order_by(Appointment.start_datetime.desc()).limit(10).all()
    
    data['recent_appointments'] = [apt.to_dict() for apt in recent_appointments]
    
    return jsonify(data)


@clinic_admin_bp.route('/api/professionals', methods=['POST'])
@login_required
@clinic_admin_required
def create_professional():
    """POST: Crea un nuevo profesional en la clínica"""
    clinic_id = get_clinic_id()
    
    if not clinic_id:
        return jsonify({'error': 'clinic_id requerido'}), 400
    
    data = request.get_json()
    
    # Validaciones
    required_fields = ['username', 'email', 'password', 'full_name']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'Campo requerido: {field}'}), 400
    
    # Verificar que el username no exista
    existing_user = User.query.filter_by(username=data['username']).first()
    if existing_user:
        return jsonify({'error': f'El username "{data["username"]}" ya está en uso'}), 400
    
    # Verificar que el email no exista
    existing_email = User.query.filter_by(email=data['email']).first()
    if existing_email:
        return jsonify({'error': f'El email "{data["email"]}" ya está en uso'}), 400
    
    try:
        # Crear profesional
        professional = User(
            username=data['username'].strip(),
            email=data['email'].strip(),
            full_name=data['full_name'].strip(),
            phone=data.get('phone', '').strip() or None,
            role=UserRole.PROFESSIONAL,
            clinic_id=clinic_id,
            is_active=True
        )
        professional.set_password(data['password'])
        
        db.session.add(professional)
        db.session.commit()
        
        # Crear notificación de bienvenida
        notification = Notification(
            user_id=professional.id,
            message=f'¡Bienvenido a {Clinic.query.get(clinic_id).name}! Tu cuenta ha sido creada exitosamente.',
            type='success'
        )
        db.session.add(notification)
        db.session.commit()
        
        return jsonify({
            'message': 'Profesional creado exitosamente',
            'professional': professional.to_dict(),
            'credentials': {
                'username': professional.username,
                'password': data['password']  # Solo se retorna aquí
            }
        }), 201
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al crear profesional: {str(e)}'}), 500


@clinic_admin_bp.route('/api/professionals/<int:id>', methods=['PUT'])
@login_required
@clinic_admin_required
def update_professional(id):
    """PUT: Actualiza información de un profesional"""
    professional = User.query.get_or_404(id)
    
    clinic_id = get_clinic_id()
    
    # Verificar que pertenece a la clínica
    if professional.clinic_id != clinic_id:
        return jsonify({'error': 'No autorizado'}), 403
    
    if professional.role != UserRole.PROFESSIONAL:
        return jsonify({'error': 'El usuario no es un profesional'}), 400
    
    data = request.get_json()
    
    try:
        # Actualizar campos
        if 'full_name' in data:
            professional.full_name = data['full_name'].strip()
        
        if 'email' in data:
            new_email = data['email'].strip()
            # Verificar que el email no esté en uso por otro usuario
            existing = User.query.filter(
                User.email == new_email,
                User.id != id
            ).first()
            if existing:
                return jsonify({'error': 'Este email ya está en uso'}), 400
            professional.email = new_email
        
        if 'phone' in data:
            professional.phone = data['phone'].strip() or None
        
        db.session.commit()
        
        return jsonify({
            'message': 'Profesional actualizado exitosamente',
            'professional': professional.to_dict()
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al actualizar profesional: {str(e)}'}), 500


@clinic_admin_bp.route('/api/professionals/<int:id>/toggle-status', methods=['POST'])
@login_required
@clinic_admin_required
def toggle_professional_status(id):
    """POST: Activa/desactiva un profesional"""
    professional = User.query.get_or_404(id)
    
    clinic_id = get_clinic_id()
    
    # Verificar que pertenece a la clínica
    if professional.clinic_id != clinic_id:
        return jsonify({'error': 'No autorizado'}), 403
    
    if professional.role != UserRole.PROFESSIONAL:
        return jsonify({'error': 'El usuario no es un profesional'}), 400
    
    try:
        professional.is_active = not professional.is_active
        db.session.commit()
        
        status = 'activado' if professional.is_active else 'desactivado'
        
        # Crear notificación
        notification = Notification(
            user_id=professional.id,
            message=f'Tu cuenta ha sido {status} por el administrador.',
            type='warning' if not professional.is_active else 'success'
        )
        db.session.add(notification)
        db.session.commit()
        
        return jsonify({
            'message': f'Profesional {status} exitosamente',
            'is_active': professional.is_active
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al cambiar estado: {str(e)}'}), 500


@clinic_admin_bp.route('/api/professionals/<int:id>/reset-password', methods=['POST'])
@login_required
@clinic_admin_required
def reset_professional_password(id):
    """POST: Resetea la contraseña de un profesional"""
    professional = User.query.get_or_404(id)
    
    clinic_id = get_clinic_id()
    
    # Verificar que pertenece a la clínica
    if professional.clinic_id != clinic_id:
        return jsonify({'error': 'No autorizado'}), 403
    
    if professional.role != UserRole.PROFESSIONAL:
        return jsonify({'error': 'El usuario no es un profesional'}), 400
    
    data = request.get_json() or {}
    new_password = data.get('new_password')
    
    # Si no se proporciona, generar una temporal
    if not new_password:
        import secrets
        import string
        alphabet = string.ascii_letters + string.digits
        new_password = ''.join(secrets.choice(alphabet) for i in range(12))
    
    try:
        professional.set_password(new_password)
        db.session.commit()
        
        # Crear notificación
        notification = Notification(
            user_id=professional.id,
            message='Tu contraseña ha sido reseteada. Por favor cámbiala en tu próximo inicio de sesión.',
            type='warning'
        )
        db.session.add(notification)
        db.session.commit()
        
        return jsonify({
            'message': 'Contraseña reseteada exitosamente',
            'new_password': new_password,  # Solo se retorna aquí
            'username': professional.username,
            'email': professional.email
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al resetear contraseña: {str(e)}'}), 500


@clinic_admin_bp.route('/api/professionals/<int:id>', methods=['DELETE'])
@login_required
@clinic_admin_required
def delete_professional(id):
    """
    DELETE: Elimina permanentemente un profesional.
    ADVERTENCIA: También eliminará todas sus citas asociadas.
    """
    professional = User.query.get_or_404(id)
    
    clinic_id = get_clinic_id()
    
    # Verificar que pertenece a la clínica
    if professional.clinic_id != clinic_id:
        return jsonify({'error': 'No autorizado'}), 403
    
    if professional.role != UserRole.PROFESSIONAL:
        return jsonify({'error': 'El usuario no es un profesional'}), 400
    
    # Contar citas asociadas
    appointments_count = Appointment.query.filter_by(professional_id=id).count()
    
    try:
        username = professional.username
        
        # Eliminar (cascada se encarga de las citas)
        db.session.delete(professional)
        db.session.commit()
        
        return jsonify({
            'message': f'Profesional "{username}" eliminado permanentemente',
            'deleted_appointments': appointments_count
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al eliminar profesional: {str(e)}'}), 500


# ============================================================================
# API: GESTIÓN DE SERVICIOS
# ============================================================================
@clinic_admin_bp.route('/api/services', methods=['GET'])
@login_required
@clinic_admin_required
def get_services():
    """GET: Obtiene lista de servicios de la clínica"""
    clinic_id = get_clinic_id()
    
    if not clinic_id:
        return jsonify({'error': 'clinic_id requerido'}), 400
    
    # Filtrar por estado si se especifica
    is_active = request.args.get('is_active')
    
    query = Service.query.filter_by(clinic_id=clinic_id)
    
    if is_active is not None:
        query = query.filter_by(is_active=is_active.lower() == 'true')
    
    services = query.order_by(Service.name).all()
    
    return jsonify([service.to_dict() for service in services])


@clinic_admin_bp.route('/api/services', methods=['POST'])
@login_required
@clinic_admin_required
def create_service():
    """POST: Crea un nuevo servicio en la clínica"""
    clinic_id = get_clinic_id()
    
    if not clinic_id:
        return jsonify({'error': 'clinic_id requerido'}), 400
    
    data = request.get_json()
    
    # Validaciones
    if not data.get('name'):
        return jsonify({'error': 'El nombre del servicio es requerido'}), 400
    
    if not data.get('duration_minutes'):
        return jsonify({'error': 'La duración es requerida'}), 400
    
    try:
        service = Service(
            clinic_id=clinic_id,
            name=data['name'].strip(),
            description=data.get('description', '').strip() or None,
            duration_minutes=int(data['duration_minutes']),
            price=float(data['price']) if data.get('price') else None,
            is_active=True
        )
        
        db.session.add(service)
        db.session.commit()
        
        return jsonify({
            'message': 'Servicio creado exitosamente',
            'service': service.to_dict()
        }), 201
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al crear servicio: {str(e)}'}), 500


@clinic_admin_bp.route('/api/services/<int:id>', methods=['PUT'])
@login_required
@clinic_admin_required
def update_service(id):
    """PUT: Actualiza un servicio"""
    service = Service.query.get_or_404(id)
    
    clinic_id = get_clinic_id()
    
    # Verificar que pertenece a la clínica
    if service.clinic_id != clinic_id:
        return jsonify({'error': 'No autorizado'}), 403
    
    data = request.get_json()
    
    try:
        if 'name' in data:
            service.name = data['name'].strip()
        if 'description' in data:
            service.description = data['description'].strip() or None
        if 'duration_minutes' in data:
            service.duration_minutes = int(data['duration_minutes'])
        if 'price' in data:
            service.price = float(data['price']) if data['price'] else None
        if 'is_active' in data:
            service.is_active = bool(data['is_active'])
        
        db.session.commit()
        
        return jsonify({
            'message': 'Servicio actualizado exitosamente',
            'service': service.to_dict()
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al actualizar servicio: {str(e)}'}), 500


@clinic_admin_bp.route('/api/services/<int:id>/toggle-status', methods=['POST'])
@login_required
@clinic_admin_required
def toggle_service_status(id):
    """POST: Activa/desactiva un servicio"""
    service = Service.query.get_or_404(id)
    
    clinic_id = get_clinic_id()
    
    # Verificar que pertenece a la clínica
    if service.clinic_id != clinic_id:
        return jsonify({'error': 'No autorizado'}), 403
    
    try:
        service.is_active = not service.is_active
        db.session.commit()
        
        status = 'activado' if service.is_active else 'desactivado'
        
        return jsonify({
            'message': f'Servicio {status} exitosamente',
            'is_active': service.is_active
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al cambiar estado: {str(e)}'}), 500


# ============================================================================
# API: CONFIGURACIÓN DE CLÍNICA
# ============================================================================
@clinic_admin_bp.route('/api/clinic/settings', methods=['GET'])
@login_required
@clinic_admin_required
def get_clinic_settings():
    """GET: Obtiene configuración de la clínica"""
    clinic_id = get_clinic_id()
    
    if not clinic_id:
        return jsonify({'error': 'clinic_id requerido'}), 400
    
    clinic = Clinic.query.get_or_404(clinic_id)
    
    return jsonify(clinic.to_dict())


@clinic_admin_bp.route('/api/clinic/settings', methods=['PUT'])
@login_required
@clinic_admin_required
def update_clinic_settings():
    """PUT: Actualiza configuración de la clínica"""
    clinic_id = get_clinic_id()
    
    if not clinic_id:
        return jsonify({'error': 'clinic_id requerido'}), 400
    
    clinic = Clinic.query.get_or_404(clinic_id)
    data = request.get_json()
    
    try:
        # Campos que el CLINIC_ADMIN puede editar
        if 'name' in data:
            clinic.name = data['name'].strip()
        if 'phone' in data:
            clinic.phone = data['phone'].strip() or None
        if 'email' in data:
            clinic.email = data['email'].strip() or None
        if 'address' in data:
            clinic.address = data['address'].strip() or None
        if 'logo_url' in data:
            clinic.logo_url = data['logo_url'].strip() or None
        if 'theme_color' in data:
            clinic.theme_color = data['theme_color']
        
        # El CLINIC_ADMIN NO puede cambiar:
        # - is_active (solo SUPER_ADMIN)
        # - plan (solo SUPER_ADMIN)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Configuración actualizada exitosamente',
            'clinic': clinic.to_dict()
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al actualizar configuración: {str(e)}'}), 500


# ============================================================================
# API: REPORTES DE LA CLÍNICA
# ============================================================================
@clinic_admin_bp.route('/api/reports/summary', methods=['GET'])
@login_required
@clinic_admin_required
def get_clinic_report():
    """
    GET: Obtiene reporte resumido de la clínica.
    Query params:
        - start (str): Fecha inicio (YYYY-MM-DD)
        - end (str): Fecha fin (YYYY-MM-DD)
    """
    clinic_id = get_clinic_id()
    
    if not clinic_id:
        return jsonify({'error': 'clinic_id requerido'}), 400
    
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
    query = Appointment.query.filter(
        Appointment.clinic_id == clinic_id,
        Appointment.start_datetime >= start_date,
        Appointment.start_datetime <= end_date
    )
    
    # Contadores por estado
    total = query.count()
    programadas = query.filter_by(status=AppointmentStatus.PROGRAMADA).count()
    completadas = query.filter_by(status=AppointmentStatus.COMPLETADA).count()
    canceladas = query.filter_by(status=AppointmentStatus.CANCELADA).count()
    no_asistio = query.filter_by(status=AppointmentStatus.NO_ASISTIO).count()
    
    # Ingresos estimados (solo citas completadas con servicio)
    ingresos = db.session.query(func.sum(Service.price)).join(
        Appointment, Appointment.service_id == Service.id
    ).filter(
        Appointment.clinic_id == clinic_id,
        Appointment.status == AppointmentStatus.COMPLETADA,
        Appointment.start_datetime >= start_date,
        Appointment.start_datetime <= end_date
    ).scalar() or 0
    
    # Citas por profesional
    by_professional = db.session.query(
        User.full_name,
        User.username,
        func.count(Appointment.id).label('count')
    ).join(
        Appointment, Appointment.professional_id == User.id
    ).filter(
        Appointment.clinic_id == clinic_id,
        Appointment.start_datetime >= start_date,
        Appointment.start_datetime <= end_date
    ).group_by(User.id).all()
    
    # Citas por servicio
    by_service = db.session.query(
        Service.name,
        func.count(Appointment.id).label('count')
    ).join(
        Appointment, Appointment.service_id == Service.id
    ).filter(
        Appointment.clinic_id == clinic_id,
        Appointment.start_datetime >= start_date,
        Appointment.start_datetime <= end_date
    ).group_by(Service.id).all()
    
    return jsonify({
        'period': {
            'start': start_str,
            'end': end_str
        },
        'summary': {
            'total': total,
            'programadas': programadas,
            'completadas': completadas,
            'canceladas': canceladas,
            'no_asistio': no_asistio,
            'tasa_completadas': round((completadas / total * 100) if total > 0 else 0, 2),
            'tasa_canceladas': round((canceladas / total * 100) if total > 0 else 0, 2)
        },
        'ingresos_estimados': float(ingresos),
        'by_professional': [
            {
                'name': prof[0] or prof[1],
                'appointments': prof[2]
            }
            for prof in by_professional
        ],
        'by_service': [
            {
                'name': service[0],
                'appointments': service[1]
            }
            for service in by_service
        ]
    })


@clinic_admin_bp.route('/api/reports/professionals-performance', methods=['GET'])
@login_required
@clinic_admin_required
def get_professionals_performance():
    """
    GET: Obtiene reporte de desempeño de profesionales.
    Query params:
        - start (str): Fecha inicio (YYYY-MM-DD)
        - end (str): Fecha fin (YYYY-MM-DD)
    """
    clinic_id = get_clinic_id()
    
    if not clinic_id:
        return jsonify({'error': 'clinic_id requerido'}), 400
    
    start_str = request.args.get('start')
    end_str = request.args.get('end')
    
    if not start_str or not end_str:
        # Por defecto: últimos 30 días
        end_date = get_peru_time()
        start_date = end_date - timedelta(days=30)
    else:
        try:
            start_date = datetime.strptime(start_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_str, '%Y-%m-%d')
        except ValueError:
            return jsonify({'error': 'Formato de fecha inválido. Usa YYYY-MM-DD'}), 400
    
    # Obtener todos los profesionales de la clínica
    professionals = User.query.filter_by(
        clinic_id=clinic_id,
        role=UserRole.PROFESSIONAL
    ).all()
    
    performance_data = []
    
    for prof in professionals:
        # Citas en el período
        appointments = Appointment.query.filter(
            Appointment.professional_id == prof.id,
            Appointment.start_datetime >= start_date,
            Appointment.start_datetime <= end_date
        ).all()
        
        total = len(appointments)
        completadas = sum(1 for apt in appointments if apt.status == AppointmentStatus.COMPLETADA)
        canceladas = sum(1 for apt in appointments if apt.status == AppointmentStatus.CANCELADA)
        no_asistio = sum(1 for apt in appointments if apt.status == AppointmentStatus.NO_ASISTIO)
        
        # Pacientes únicos atendidos
        pacientes_atendidos = db.session.query(
            func.count(func.distinct(Appointment.patient_id))
        ).filter(
            Appointment.professional_id == prof.id,
            Appointment.status == AppointmentStatus.COMPLETADA,
            Appointment.start_datetime >= start_date,
            Appointment.start_datetime <= end_date
        ).scalar() or 0
        
        # Ingresos generados
        ingresos = db.session.query(func.sum(Service.price)).join(
            Appointment, Appointment.service_id == Service.id
        ).filter(
            Appointment.professional_id == prof.id,
            Appointment.status == AppointmentStatus.COMPLETADA,
            Appointment.start_datetime >= start_date,
            Appointment.start_datetime <= end_date
        ).scalar() or 0
        
        performance_data.append({
            'professional_id': prof.id,
            'name': prof.full_name or prof.username,
            'email': prof.email,
            'is_active': prof.is_active,
            'appointments': {
                'total': total,
                'completadas': completadas,
                'canceladas': canceladas,
                'no_asistio': no_asistio,
                'tasa_completadas': round((completadas / total * 100) if total > 0 else 0, 2),
                'tasa_canceladas': round((canceladas / total * 100) if total > 0 else 0, 2)
            },
            'pacientes_atendidos': pacientes_atendidos,
            'ingresos_generados': float(ingresos)
        })
    
    # Ordenar por citas completadas (descendente)
    performance_data.sort(key=lambda x: x['appointments']['completadas'], reverse=True)
    
    return jsonify({
        'period': {
            'start': start_date.strftime('%Y-%m-%d'),
            'end': end_date.strftime('%Y-%m-%d')
        },
        'professionals': performance_data
    })


# ============================================================================
# API: CALENDARIO GLOBAL DE LA CLÍNICA
# ============================================================================
@clinic_admin_bp.route('/api/calendar/all-appointments', methods=['GET'])
@login_required
@clinic_admin_required
def get_all_clinic_appointments():
    """
    GET: Obtiene todas las citas de la clínica para el calendario.
    Query params:
        - start (str): Fecha inicio (ISO 8601)
        - end (str): Fecha fin (ISO 8601)
        - professional_id (int): Filtrar por profesional (opcional)
    """
    clinic_id = get_clinic_id()
    
    if not clinic_id:
        return jsonify({'error': 'clinic_id requerido'}), 400
    
    # Base query
    query = Appointment.query.filter_by(clinic_id=clinic_id)
    
    # Filtrar por rango de fechas
    start_str = request.args.get('start')
    end_str = request.args.get('end')
    
    if start_str and end_str:
        try:
            from project.api_routes import parse_datetime
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
    
    # Filtrar por profesional (opcional)
    professional_id = request.args.get('professional_id', type=int)
    if professional_id:
        query = query.filter_by(professional_id=professional_id)
    
    # Excluir canceladas por defecto
    include_cancelled = request.args.get('include_cancelled', 'false').lower() == 'true'
    if not include_cancelled:
        query = query.filter(
            Appointment.status.in_([
                AppointmentStatus.PROGRAMADA,
                AppointmentStatus.COMPLETADA
            ])
        )
    
    appointments = query.order_by(Appointment.start_datetime).all()
    
    # Formato FullCalendar
    return jsonify([apt.to_fullcalendar_event() for apt in appointments])


# ============================================================================
# API: ESTADÍSTICAS DEL DASHBOARD
# ============================================================================
@clinic_admin_bp.route('/api/stats/dashboard', methods=['GET'])
@login_required
@clinic_admin_required
def get_dashboard_stats():
    """GET: Obtiene estadísticas para el dashboard del CLINIC_ADMIN"""
    clinic_id = get_clinic_id()
    
    if not clinic_id:
        return jsonify({'error': 'clinic_id requerido'}), 400
    
    # Estadísticas generales
    stats = {
        'professionals': {
            'total': User.query.filter_by(
                clinic_id=clinic_id,
                role=UserRole.PROFESSIONAL
            ).count(),
            'active': User.query.filter_by(
                clinic_id=clinic_id,
                role=UserRole.PROFESSIONAL,
                is_active=True
            ).count()
        },
        'patients': {
            'total': Patient.query.filter_by(clinic_id=clinic_id).count()
        },
        'services': {
            'total': Service.query.filter_by(clinic_id=clinic_id).count(),
            'active': Service.query.filter_by(
                clinic_id=clinic_id,
                is_active=True
            ).count()
        },
        'appointments': {
            'programadas': Appointment.query.filter_by(
                clinic_id=clinic_id,
                status=AppointmentStatus.PROGRAMADA
            ).count(),
            'completadas': Appointment.query.filter_by(
                clinic_id=clinic_id,
                status=AppointmentStatus.COMPLETADA
            ).count(),
            'canceladas': Appointment.query.filter_by(
                clinic_id=clinic_id,
                status=AppointmentStatus.CANCELADA
            ).count()
        }
    }
    
    # Citas de hoy
    today_start = datetime.combine(datetime.now().date(), datetime.min.time())
    today_end = datetime.combine(datetime.now().date(), datetime.max.time())
    
    stats['appointments']['hoy'] = Appointment.query.filter(
        Appointment.clinic_id == clinic_id,
        Appointment.start_datetime >= today_start,
        Appointment.start_datetime <= today_end,
        Appointment.status == AppointmentStatus.PROGRAMADA
    ).count()
    
    # Citas de esta semana
    from datetime import date
    today = date.today()
    start_week = today - timedelta(days=today.weekday())  # Lunes
    end_week = start_week + timedelta(days=6)  # Domingo
    
    week_start = datetime.combine(start_week, datetime.min.time())
    week_end = datetime.combine(end_week, datetime.max.time())
    
    stats['appointments']['semana'] = Appointment.query.filter(
        Appointment.clinic_id == clinic_id,
        Appointment.start_datetime >= week_start,
        Appointment.start_datetime <= week_end,
        Appointment.status.in_([AppointmentStatus.PROGRAMADA, AppointmentStatus.COMPLETADA])
    ).count()
    
    # Ingresos del mes
    month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    stats['ingresos_mes'] = float(db.session.query(
        func.sum(Service.price)
    ).join(
        Appointment, Appointment.service_id == Service.id
    ).filter(
        Appointment.clinic_id == clinic_id,
        Appointment.status == AppointmentStatus.COMPLETADA,
        Appointment.start_datetime >= month_start
    ).scalar() or 0)
    
    return jsonify(stats)


# ============================================================================
# API: ACTIVIDAD RECIENTE
# ============================================================================
@clinic_admin_bp.route('/api/activity/recent', methods=['GET'])
@login_required
@clinic_admin_required
def get_recent_activity():
    """
    GET: Obtiene actividad reciente de la clínica.
    Query params:
        - limit (int): Número de registros (default: 20)
    """
    clinic_id = get_clinic_id()
    
    if not clinic_id:
        return jsonify({'error': 'clinic_id requerido'}), 400
    
    limit = request.args.get('limit', 20, type=int)
    
    # Últimas citas creadas
    recent_appointments = Appointment.query.filter_by(
        clinic_id=clinic_id
    ).order_by(Appointment.created_at.desc()).limit(limit).all()
    
    activity = []
    
    for apt in recent_appointments:
        activity.append({
            'type': 'appointment_created',
            'timestamp': apt.created_at.isoformat(),
            'description': f'Nueva cita: {apt.patient.name if apt.patient else "Paciente"} con {apt.professional.full_name or apt.professional.username}',
            'data': {
                'appointment_id': apt.id,
                'patient_name': apt.patient.name if apt.patient else None,
                'professional_name': apt.professional.full_name or apt.professional.username,
                'status': apt.status.value,
                'start_datetime': apt.start_datetime.isoformat()
            }
        })
    
    # Ordenar por timestamp
    activity.sort(key=lambda x: x['timestamp'], reverse=True)
    
    return jsonify(activity[:limit])


# ============================================================================
# API: BÚSQUEDA RÁPIDA
# ============================================================================
@clinic_admin_bp.route('/api/search/quick', methods=['GET'])
@login_required
@clinic_admin_required
def quick_search():
    """
    GET: Búsqueda rápida en pacientes, profesionales y citas.
    Query params:
        - q (str): Término de búsqueda (mínimo 2 caracteres)
    """
    clinic_id = get_clinic_id()
    
    if not clinic_id:
        return jsonify({'error': 'clinic_id requerido'}), 400
    
    query_term = request.args.get('q', '').strip()
    
    if len(query_term) < 2:
        return jsonify({'error': 'El término de búsqueda debe tener al menos 2 caracteres'}), 400
    
    results = {
        'patients': [],
        'professionals': [],
        'appointments': []
    }
    
    # Buscar pacientes
    patients = Patient.query.filter(
        Patient.clinic_id == clinic_id,
        or_(
            Patient.name.ilike(f'%{query_term}%'),
            Patient.phone.ilike(f'%{query_term}%'),
            Patient.email.ilike(f'%{query_term}%')
        )
    ).limit(5).all()
    
    results['patients'] = [
        {
            'id': p.id,
            'name': p.name,
            'phone': p.phone,
            'email': p.email
        }
        for p in patients
    ]
    
    # Buscar profesionales
    professionals = User.query.filter(
        User.clinic_id == clinic_id,
        User.role == UserRole.PROFESSIONAL,
        or_(
            User.full_name.ilike(f'%{query_term}%'),
            User.username.ilike(f'%{query_term}%'),
            User.email.ilike(f'%{query_term}%')
        )
    ).limit(5).all()
    
    results['professionals'] = [
        {
            'id': p.id,
            'name': p.full_name or p.username,
            'email': p.email,
            'is_active': p.is_active
        }
        for p in professionals
    ]
    
    # Buscar citas recientes por nombre de paciente
    appointments = Appointment.query.join(Patient).filter(
        Appointment.clinic_id == clinic_id,
        Patient.name.ilike(f'%{query_term}%'),
        Appointment.status.in_([AppointmentStatus.PROGRAMADA, AppointmentStatus.COMPLETADA])
    ).order_by(Appointment.start_datetime.desc()).limit(5).all()
    
    results['appointments'] = [
        {
            'id': a.id,
            'patient_name': a.patient.name if a.patient else None,
            'professional_name': a.professional.full_name or a.professional.username,
            'start_datetime': a.start_datetime.isoformat(),
            'status': a.status.value
        }
        for a in appointments
    ]
    
    return jsonify({
        'query': query_term,
        'results': results,
        'total': len(results['patients']) + len(results['professionals']) + len(results['appointments'])
    })