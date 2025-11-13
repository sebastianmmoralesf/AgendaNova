from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from functools import wraps
from project import db
from project.models import User, Clinic, Appointment, Patient, Service, UserRole, get_peru_time
from sqlalchemy import func

super_admin_bp = Blueprint('super_admin', __name__)


# ============================================================================
# DECORADOR: Solo SUPER_ADMIN
# ============================================================================
def super_admin_required(f):
    """Decorador: Solo permite acceso a SUPER_ADMIN"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Por favor inicia sesión para acceder.', 'warning')
            return redirect(url_for('auth.login'))
        
        if not current_user.is_super_admin():
            flash('Acceso denegado. Se requieren permisos de Super Administrador.', 'danger')
            return redirect(url_for('auth.dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# DASHBOARD SUPER ADMIN
# ============================================================================
@super_admin_bp.route('/dashboard')
@login_required
@super_admin_required
def dashboard():
    """
    Dashboard principal del Super Administrador.
    Vista general de todas las clínicas del sistema.
    """
    # Estadísticas globales
    stats = {
        'total_clinics': Clinic.query.count(),
        'active_clinics': Clinic.query.filter_by(is_active=True).count(),
        'total_users': User.query.filter(User.role != UserRole.SUPER_ADMIN).count(),
        'total_appointments': Appointment.query.count(),
        'total_patients': Patient.query.count()
    }
    
    # Obtener todas las clínicas con información agregada
    clinics = db.session.query(
        Clinic,
        func.count(User.id.distinct()).label('users_count'),
        func.count(Patient.id.distinct()).label('patients_count'),
        func.count(Appointment.id.distinct()).label('appointments_count')
    ).outerjoin(
        User, User.clinic_id == Clinic.id
    ).outerjoin(
        Patient, Patient.clinic_id == Clinic.id
    ).outerjoin(
        Appointment, Appointment.clinic_id == Clinic.id
    ).group_by(Clinic.id).order_by(Clinic.created_at.desc()).all()
    
    return render_template(
        'super_admin_dashboard.html',
        user=current_user,
        stats=stats,
        clinics=clinics
    )


# ============================================================================
# API: GESTIÓN DE CLÍNICAS
# ============================================================================
@super_admin_bp.route('/api/clinics', methods=['GET'])
@login_required
@super_admin_required
def get_clinics():
    """GET: Obtiene lista de todas las clínicas"""
    clinics = Clinic.query.order_by(Clinic.created_at.desc()).all()
    
    clinics_data = []
    for clinic in clinics:
        data = clinic.to_dict()
        
        # Agregar estadísticas adicionales
        data['users_count'] = User.query.filter_by(clinic_id=clinic.id).count()
        data['patients_count'] = Patient.query.filter_by(clinic_id=clinic.id).count()
        data['appointments_count'] = Appointment.query.filter_by(clinic_id=clinic.id).count()
        
        # Obtener CLINIC_ADMIN
        clinic_admin = User.query.filter_by(
            clinic_id=clinic.id,
            role=UserRole.CLINIC_ADMIN
        ).first()
        
        if clinic_admin:
            data['admin'] = {
                'id': clinic_admin.id,
                'username': clinic_admin.username,
                'email': clinic_admin.email,
                'full_name': clinic_admin.full_name
            }
        else:
            data['admin'] = None
        
        clinics_data.append(data)
    
    return jsonify(clinics_data)


@super_admin_bp.route('/api/clinics/<int:id>', methods=['GET'])
@login_required
@super_admin_required
def get_clinic(id):
    """GET: Obtiene detalles de una clínica específica"""
    clinic = Clinic.query.get_or_404(id)
    
    data = clinic.to_dict()
    
    # Estadísticas detalladas
    data['statistics'] = {
        'users': {
            'total': User.query.filter_by(clinic_id=id).count(),
            'admins': User.query.filter_by(clinic_id=id, role=UserRole.CLINIC_ADMIN).count(),
            'professionals': User.query.filter_by(clinic_id=id, role=UserRole.PROFESSIONAL).count(),
            'active': User.query.filter_by(clinic_id=id, is_active=True).count()
        },
        'patients': Patient.query.filter_by(clinic_id=id).count(),
        'services': Service.query.filter_by(clinic_id=id, is_active=True).count(),
        'appointments': {
            'total': Appointment.query.filter_by(clinic_id=id).count(),
            'programadas': Appointment.query.filter_by(clinic_id=id, status='Programada').count(),
            'completadas': Appointment.query.filter_by(clinic_id=id, status='Completada').count(),
            'canceladas': Appointment.query.filter_by(clinic_id=id, status='Cancelada').count()
        }
    }
    
    # Lista de usuarios
    users = User.query.filter_by(clinic_id=id).all()
    data['users'] = [u.to_dict() for u in users]
    
    return jsonify(data)


@super_admin_bp.route('/api/clinics', methods=['POST'])
@login_required
@super_admin_required
def create_clinic():
    """
    POST: Crea una nueva clínica en el sistema.
    Automáticamente crea una cuenta CLINIC_ADMIN asociada.
    """
    data = request.get_json()
    
    # Validaciones
    if not data.get('name'):
        return jsonify({'error': 'El nombre de la clínica es requerido'}), 400
    
    if not data.get('admin_username') or not data.get('admin_email') or not data.get('admin_password'):
        return jsonify({'error': 'Credenciales del administrador son requeridas'}), 400
    
    # Verificar que el username no exista
    existing_user = User.query.filter_by(username=data['admin_username']).first()
    if existing_user:
        return jsonify({'error': f'El username "{data["admin_username"]}" ya está en uso'}), 400
    
    # Verificar que el email no exista
    existing_email = User.query.filter_by(email=data['admin_email']).first()
    if existing_email:
        return jsonify({'error': f'El email "{data["admin_email"]}" ya está en uso'}), 400
    
    try:
        # Crear clínica
        clinic = Clinic(
            name=data['name'].strip(),
            phone=data.get('phone', '').strip() or None,
            email=data.get('email', '').strip() or None,
            address=data.get('address', '').strip() or None,
            logo_url=data.get('logo_url', '').strip() or None,
            theme_color=data.get('theme_color', '#4F46E5'),
            plan=data.get('plan', 'free'),
            is_active=True
        )
        
        db.session.add(clinic)
        db.session.flush()  # Obtener clinic.id sin hacer commit
        
        # Crear CLINIC_ADMIN
        clinic_admin = User(
            username=data['admin_username'].strip(),
            email=data['admin_email'].strip(),
            full_name=data.get('admin_full_name', '').strip() or data['admin_username'],
            phone=data.get('admin_phone', '').strip() or None,
            role=UserRole.CLINIC_ADMIN,
            clinic_id=clinic.id,
            is_active=True
        )
        clinic_admin.set_password(data['admin_password'])
        
        db.session.add(clinic_admin)
        db.session.commit()
        
        return jsonify({
            'message': 'Clínica creada exitosamente',
            'clinic': clinic.to_dict(),
            'admin': {
                'id': clinic_admin.id,
                'username': clinic_admin.username,
                'email': clinic_admin.email,
                'password': data['admin_password']  # Solo se retorna en creación
            }
        }), 201
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al crear clínica: {str(e)}'}), 500


@super_admin_bp.route('/api/clinics/<int:id>', methods=['PUT'])
@login_required
@super_admin_required
def update_clinic(id):
    """PUT: Actualiza información de una clínica"""
    clinic = Clinic.query.get_or_404(id)
    data = request.get_json()
    
    try:
        # Actualizar campos
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
        if 'plan' in data:
            clinic.plan = data['plan']
        
        db.session.commit()
        
        return jsonify({
            'message': 'Clínica actualizada exitosamente',
            'clinic': clinic.to_dict()
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al actualizar clínica: {str(e)}'}), 500


@super_admin_bp.route('/api/clinics/<int:id>/toggle-status', methods=['POST'])
@login_required
@super_admin_required
def toggle_clinic_status(id):
    """POST: Activa/desactiva una clínica"""
    clinic = Clinic.query.get_or_404(id)
    
    try:
        clinic.is_active = not clinic.is_active
        db.session.commit()
        
        status = 'activada' if clinic.is_active else 'desactivada'
        
        # Si se desactiva, cerrar sesiones de usuarios de esa clínica
        if not clinic.is_active:
            # Los usuarios ya no podrán hacer login (se valida en auth_routes.py)
            pass
        
        return jsonify({
            'message': f'Clínica {status} exitosamente',
            'is_active': clinic.is_active
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al cambiar estado: {str(e)}'}), 500


@super_admin_bp.route('/api/clinics/<int:id>', methods=['DELETE'])
@login_required
@super_admin_required
def delete_clinic(id):
    """
    DELETE: Elimina permanentemente una clínica y todos sus datos asociados.
    ADVERTENCIA: Esta operación es irreversible y elimina:
    - Todos los usuarios de la clínica
    - Todos los pacientes
    - Todos los servicios
    - Todas las citas
    """
    clinic = Clinic.query.get_or_404(id)
    
    # Obtener estadísticas antes de eliminar (para confirmar)
    users_count = User.query.filter_by(clinic_id=id).count()
    patients_count = Patient.query.filter_by(clinic_id=id).count()
    appointments_count = Appointment.query.filter_by(clinic_id=id).count()
    
    try:
        clinic_name = clinic.name
        
        # La cascada se encarga de eliminar todo
        db.session.delete(clinic)
        db.session.commit()
        
        return jsonify({
            'message': f'Clínica "{clinic_name}" eliminada permanentemente',
            'deleted': {
                'users': users_count,
                'patients': patients_count,
                'appointments': appointments_count
            }
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al eliminar clínica: {str(e)}'}), 500


# ============================================================================
# API: GESTIÓN DE USUARIOS (Vista Global)
# ============================================================================
@super_admin_bp.route('/api/users', methods=['GET'])
@login_required
@super_admin_required
def get_all_users():
    """
    GET: Obtiene lista de todos los usuarios del sistema.
    Query params:
        - clinic_id (int): Filtrar por clínica
        - role (str): Filtrar por rol
        - is_active (bool): Filtrar por estado
    """
    query = User.query.filter(User.role != UserRole.SUPER_ADMIN)
    
    # Filtros opcionales
    clinic_id = request.args.get('clinic_id', type=int)
    if clinic_id:
        query = query.filter_by(clinic_id=clinic_id)
    
    role = request.args.get('role')
    if role:
        try:
            query = query.filter_by(role=UserRole(role))
        except ValueError:
            return jsonify({'error': f'Rol inválido: {role}'}), 400
    
    is_active = request.args.get('is_active')
    if is_active is not None:
        query = query.filter_by(is_active=is_active.lower() == 'true')
    
    users = query.order_by(User.created_at.desc()).all()
    
    return jsonify([u.to_dict(include_sensitive=True) for u in users])


@super_admin_bp.route('/api/users/<int:id>/toggle-status', methods=['POST'])
@login_required
@super_admin_required
def toggle_user_status(id):
    """POST: Activa/desactiva un usuario"""
    user = User.query.get_or_404(id)
    
    # No se puede desactivar a sí mismo
    if user.id == current_user.id:
        return jsonify({'error': 'No puedes desactivar tu propia cuenta'}), 400
    
    # No se puede desactivar a otro SUPER_ADMIN
    if user.is_super_admin():
        return jsonify({'error': 'No puedes desactivar a otro Super Administrador'}), 400
    
    try:
        user.is_active = not user.is_active
        db.session.commit()
        
        status = 'activado' if user.is_active else 'desactivado'
        
        return jsonify({
            'message': f'Usuario {status} exitosamente',
            'is_active': user.is_active
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al cambiar estado: {str(e)}'}), 500


@super_admin_bp.route('/api/users/<int:id>/reset-password', methods=['POST'])
@login_required
@super_admin_required
def reset_user_password(id):
    """
    POST: Resetea la contraseña de un usuario.
    Genera una contraseña temporal que debe ser cambiada en el primer login.
    """
    user = User.query.get_or_404(id)
    
    if user.is_super_admin():
        return jsonify({'error': 'No puedes resetear la contraseña de un Super Administrador'}), 400
    
    data = request.get_json() or {}
    new_password = data.get('new_password')
    
    # Si no se proporciona, generar una temporal
    if not new_password:
        import secrets
        import string
        alphabet = string.ascii_letters + string.digits
        new_password = ''.join(secrets.choice(alphabet) for i in range(12))
    
    try:
        user.set_password(new_password)
        db.session.commit()
        
        return jsonify({
            'message': 'Contraseña reseteada exitosamente',
            'new_password': new_password,  # Solo se retorna aquí
            'username': user.username,
            'email': user.email
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al resetear contraseña: {str(e)}'}), 500


# ============================================================================
# API: ESTADÍSTICAS GLOBALES
# ============================================================================
@super_admin_bp.route('/api/stats/global', methods=['GET'])
@login_required
@super_admin_required
def get_global_stats():
    """GET: Obtiene estadísticas globales del sistema"""
    from datetime import datetime, timedelta
    
    # Rango de fechas (últimos 30 días)
    end_date = get_peru_time()
    start_date = end_date - timedelta(days=30)
    
    stats = {
        'clinics': {
            'total': Clinic.query.count(),
            'active': Clinic.query.filter_by(is_active=True).count(),
            'inactive': Clinic.query.filter_by(is_active=False).count(),
            'by_plan': {
                'free': Clinic.query.filter_by(plan='free').count(),
                'basic': Clinic.query.filter_by(plan='basic').count(),
                'premium': Clinic.query.filter_by(plan='premium').count()
            }
        },
        'users': {
            'total': User.query.filter(User.role != UserRole.SUPER_ADMIN).count(),
            'active': User.query.filter(
                User.role != UserRole.SUPER_ADMIN,
                User.is_active == True
            ).count(),
            'by_role': {
                'clinic_admin': User.query.filter_by(role=UserRole.CLINIC_ADMIN).count(),
                'professional': User.query.filter_by(role=UserRole.PROFESSIONAL).count()
            }
        },
        'patients': {
            'total': Patient.query.count()
        },
        'appointments': {
            'total': Appointment.query.count(),
            'last_30_days': Appointment.query.filter(
                Appointment.created_at >= start_date
            ).count(),
            'by_status': {
                'programadas': Appointment.query.filter_by(status='Programada').count(),
                'completadas': Appointment.query.filter_by(status='Completada').count(),
                'canceladas': Appointment.query.filter_by(status='Cancelada').count(),
                'no_asistio': Appointment.query.filter_by(status='No Asistió').count()
            }
        }
    }
    
    # Top 5 clínicas por actividad (número de citas)
    top_clinics = db.session.query(
        Clinic.name,
        Clinic.id,
        func.count(Appointment.id).label('appointments_count')
    ).join(
        Appointment, Appointment.clinic_id == Clinic.id
    ).group_by(
        Clinic.id
    ).order_by(
        func.count(Appointment.id).desc()
    ).limit(5).all()
    
    stats['top_clinics'] = [
        {
            'name': clinic[0],
            'id': clinic[1],
            'appointments': clinic[2]
        }
        for clinic in top_clinics
    ]
    
    return jsonify(stats)


@super_admin_bp.route('/api/stats/activity', methods=['GET'])
@login_required
@super_admin_required
def get_activity_stats():
    """
    GET: Obtiene estadísticas de actividad por período.
    Query params:
        - period (str): 'week', 'month', 'year' (default: 'month')
    """
    from datetime import datetime, timedelta
    
    period = request.args.get('period', 'month')
    
    end_date = get_peru_time()
    
    if period == 'week':
        start_date = end_date - timedelta(days=7)
        group_format = '%Y-%m-%d'  # Agrupar por día
    elif period == 'month':
        start_date = end_date - timedelta(days=30)
        group_format = '%Y-%m-%d'  # Agrupar por día
    elif period == 'year':
        start_date = end_date - timedelta(days=365)
        group_format = '%Y-%m'  # Agrupar por mes
    else:
        return jsonify({'error': 'Período inválido. Usa: week, month, year'}), 400
    
    # Citas creadas por período
    appointments_by_date = db.session.query(
        func.strftime(group_format, Appointment.created_at).label('date'),
        func.count(Appointment.id).label('count')
    ).filter(
        Appointment.created_at >= start_date
    ).group_by('date').order_by('date').all()
    
    # Nuevos usuarios por período
    users_by_date = db.session.query(
        func.strftime(group_format, User.created_at).label('date'),
        func.count(User.id).label('count')
    ).filter(
        User.created_at >= start_date,
        User.role != UserRole.SUPER_ADMIN
    ).group_by('date').order_by('date').all()
    
    # Nuevas clínicas por período
    clinics_by_date = db.session.query(
        func.strftime(group_format, Clinic.created_at).label('date'),
        func.count(Clinic.id).label('count')
    ).filter(
        Clinic.created_at >= start_date
    ).group_by('date').order_by('date').all()
    
    return jsonify({
        'period': period,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'appointments': [
            {'date': row[0], 'count': row[1]}
            for row in appointments_by_date
        ],
        'users': [
            {'date': row[0], 'count': row[1]}
            for row in users_by_date
        ],
        'clinics': [
            {'date': row[0], 'count': row[1]}
            for row in clinics_by_date
        ]
    })


# ============================================================================
# LOGS Y AUDITORÍA (Futuro)
# ============================================================================
@super_admin_bp.route('/api/logs', methods=['GET'])
@login_required
@super_admin_required
def get_system_logs():
    """
    GET: Obtiene logs del sistema (placeholder para futura implementación).
    """
    # TODO: Implementar sistema de logs/auditoría
    return jsonify({
        'message': 'Sistema de logs en desarrollo',
        'logs': []
    })