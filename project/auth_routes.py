from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from project import db
from project.models import User, Notification, UserRole, get_peru_time
from functools import wraps

auth_bp = Blueprint('auth', __name__)


# ============================================================================
# DECORADORES DE AUTORIZACIÓN
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


def clinic_admin_required(f):
    """Decorador: Solo permite acceso a CLINIC_ADMIN o superior"""
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


def professional_required(f):
    """Decorador: Solo permite acceso a PROFESSIONAL o superior"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Por favor inicia sesión para acceder.', 'warning')
            return redirect(url_for('auth.login'))
        
        if not current_user.can_manage_appointments():
            flash('Acceso denegado. Se requieren permisos de profesional.', 'danger')
            return redirect(url_for('auth.dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# RUTAS DE AUTENTICACIÓN
# ============================================================================
@auth_bp.route('/')
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Página de inicio de sesión.
    - GET: Muestra formulario de login
    - POST: Procesa credenciales y autentica usuario
    """
    # Si ya está autenticado, redirigir al dashboard correspondiente
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))
    
    if request.method == 'POST':
        # Obtener credenciales del formulario
        username_or_email = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)
        
        # Validación básica
        if not username_or_email or not password:
            flash('Por favor completa todos los campos.', 'warning')
            return render_template('login.html')
        
        # Buscar usuario por username o email
        user = User.query.filter(
            (User.username == username_or_email) | (User.email == username_or_email)
        ).first()
        
        # Verificar credenciales
        if user and user.check_password(password):
            # Verificar si la cuenta está activa
            if not user.is_active:
                flash('Tu cuenta ha sido desactivada. Contacta al administrador.', 'danger')
                return render_template('login.html')
            
            # Verificar si la clínica está activa (excepto SUPER_ADMIN)
            if user.clinic_id:
                if not user.clinic.is_active:
                    flash('La clínica ha sido suspendida. Contacta al Super Administrador.', 'danger')
                    return render_template('login.html')
            
            # Login exitoso
            login_user(user, remember=bool(remember))
            
            # Actualizar último login
            user.last_login = get_peru_time()
            db.session.commit()
            
            # Crear notificación de bienvenida
            welcome_notification = Notification(
                user_id=user.id,
                message=f'¡Bienvenido de nuevo, {user.full_name or user.username}!',
                type='success'
            )
            db.session.add(welcome_notification)
            db.session.commit()
            
            # Flash message según rol
            role_names = {
                UserRole.SUPER_ADMIN: 'Super Administrador',
                UserRole.CLINIC_ADMIN: 'Administrador de Clínica',
                UserRole.PROFESSIONAL: 'Profesional'
            }
            flash(f'¡Bienvenido, {role_names.get(user.role, user.username)}!', 'success')
            
            # Redirigir según la página solicitada o al dashboard
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            return redirect(url_for('auth.dashboard'))
        
        else:
            # Credenciales inválidas
            flash('Usuario o contraseña incorrectos. Por favor intenta de nuevo.', 'danger')
            return render_template('login.html')
    
    # GET: Mostrar formulario de login
    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """
    Cierra la sesión del usuario actual.
    """
    username = current_user.username
    logout_user()
    flash(f'Has cerrado sesión exitosamente, {username}.', 'info')
    return redirect(url_for('auth.login'))


# ============================================================================
# DASHBOARD PRINCIPAL (Enrutador por Rol)
# ============================================================================
@auth_bp.route('/dashboard')
@login_required
def dashboard():
    """
    Dashboard principal que redirige según el rol del usuario:
    - SUPER_ADMIN → Super Admin Dashboard
    - CLINIC_ADMIN → Clinic Admin Dashboard
    - PROFESSIONAL → Professional Dashboard (calendario)
    """
    # Verificar cuenta activa
    if not current_user.is_active:
        logout_user()
        flash('Tu cuenta ha sido desactivada.', 'danger')
        return redirect(url_for('auth.login'))
    
    # Verificar clínica activa (excepto SUPER_ADMIN)
    if current_user.clinic_id and not current_user.clinic.is_active:
        logout_user()
        flash('La clínica ha sido suspendida.', 'danger')
        return redirect(url_for('auth.login'))
    
    # Redirigir según rol
    if current_user.is_super_admin():
        return redirect(url_for('super_admin.dashboard'))
    
    elif current_user.is_clinic_admin():
        return redirect(url_for('clinic_admin.dashboard'))
    
    elif current_user.is_professional():
        return render_template('dashboard.html', user=current_user)
    
    else:
        # Rol no reconocido (no debería pasar)
        flash('Rol de usuario no reconocido. Contacta al administrador.', 'danger')
        logout_user()
        return redirect(url_for('auth.login'))


# ============================================================================
# CONFIGURACIÓN DE CUENTA
# ============================================================================
@auth_bp.route('/account', methods=['GET'])
@login_required
def account_settings():
    """
    Página de configuración de cuenta del usuario.
    Permite cambiar datos personales, contraseña y preferencias.
    """
    return render_template('account_settings.html', user=current_user)


@auth_bp.route('/account/update-profile', methods=['POST'])
@login_required
def update_profile():
    """
    API: Actualiza información del perfil del usuario.
    """
    data = request.get_json()
    
    # Campos editables
    if 'full_name' in data:
        current_user.full_name = data['full_name'].strip()
    
    if 'phone' in data:
        current_user.phone = data['phone'].strip()
    
    if 'email' in data:
        new_email = data['email'].strip()
        # Verificar que el email no esté en uso por otro usuario
        existing = User.query.filter(
            User.email == new_email,
            User.id != current_user.id
        ).first()
        
        if existing:
            return jsonify({'error': 'Este email ya está en uso por otro usuario.'}), 400
        
        current_user.email = new_email
    
    try:
        db.session.commit()
        return jsonify({
            'message': 'Perfil actualizado exitosamente.',
            'user': current_user.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al actualizar perfil: {str(e)}'}), 500


@auth_bp.route('/account/change-password', methods=['POST'])
@login_required
def change_password():
    """
    API: Cambia la contraseña del usuario.
    """
    data = request.get_json()
    
    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')
    confirm_password = data.get('confirm_password', '')
    
    # Validaciones
    if not current_password or not new_password or not confirm_password:
        return jsonify({'error': 'Todos los campos son requeridos.'}), 400
    
    # Verificar contraseña actual
    if not current_user.check_password(current_password):
        return jsonify({'error': 'La contraseña actual es incorrecta.'}), 400
    
    # Verificar que las contraseñas coincidan
    if new_password != confirm_password:
        return jsonify({'error': 'Las contraseñas nuevas no coinciden.'}), 400
    
    # Validar longitud mínima
    if len(new_password) < 6:
        return jsonify({'error': 'La contraseña debe tener al menos 6 caracteres.'}), 400
    
    # Cambiar contraseña
    try:
        current_user.set_password(new_password)
        db.session.commit()
        
        # Crear notificación
        notification = Notification(
            user_id=current_user.id,
            message='Tu contraseña ha sido cambiada exitosamente.',
            type='success'
        )
        db.session.add(notification)
        db.session.commit()
        
        return jsonify({'message': 'Contraseña cambiada exitosamente.'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al cambiar contraseña: {str(e)}'}), 500


@auth_bp.route('/account/toggle-dark-mode', methods=['POST'])
@login_required
def toggle_dark_mode():
    """
    API: Alterna el modo oscuro del usuario.
    """
    try:
        current_user.pref_dark_mode = not current_user.pref_dark_mode
        db.session.commit()
        
        return jsonify({
            'message': 'Preferencia actualizada.',
            'dark_mode': current_user.pref_dark_mode
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al actualizar preferencia: {str(e)}'}), 500


# ============================================================================
# API: INFORMACIÓN DEL USUARIO ACTUAL
# ============================================================================
@auth_bp.route('/api/me', methods=['GET'])
@login_required
def get_current_user():
    """
    API: Retorna información del usuario autenticado.
    Útil para el frontend.
    """
    user_data = current_user.to_dict(include_sensitive=True)
    
    # Agregar información de clínica si aplica
    if current_user.clinic_id:
        user_data['clinic'] = current_user.clinic.to_dict()
    
    return jsonify(user_data)


# ============================================================================
# HEALTH CHECK (para monitoreo)
# ============================================================================
@auth_bp.route('/health', methods=['GET'])
def health_check():
    """
    Endpoint de health check para monitoreo de la aplicación.
    """
    try:
        # Verificar conexión a base de datos
        db.session.execute('SELECT 1')
        
        return jsonify({
            'status': 'healthy',
            'service': 'AgendaNova',
            'timestamp': get_peru_time().isoformat()
        }), 200
    
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': get_peru_time().isoformat()
        }), 500


# ============================================================================
# PÁGINA DE ERROR 403 (Acceso Denegado)
# ============================================================================
@auth_bp.route('/forbidden')
def forbidden():
    """Página de acceso denegado"""
    return render_template('errors/403.html'), 403


# ============================================================================
# HELPER: Verificar si usuario tiene acceso a una clínica
# ============================================================================
def verify_clinic_access(clinic_id):
    """
    Verifica si el usuario actual tiene acceso a una clínica específica.
    
    Args:
        clinic_id (int): ID de la clínica a verificar
    
    Returns:
        bool: True si tiene acceso, False en caso contrario
    """
    if not current_user.is_authenticated:
        return False
    
    # SUPER_ADMIN tiene acceso a todas las clínicas
    if current_user.is_super_admin():
        return True
    
    # Otros roles solo a su clínica
    return current_user.clinic_id == clinic_id


# ============================================================================
# CONTEXT PROCESSOR: Variables globales para templates
# ============================================================================
@auth_bp.app_context_processor
def inject_global_vars():
    """
    Inyecta variables globales en todos los templates.
    """
    return {
        'UserRole': UserRole,
        'current_year': get_peru_time().year,
        'app_name': 'AgendaNova',
        'app_version': '2.0.0'
    }