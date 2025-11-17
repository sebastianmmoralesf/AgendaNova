from project import db, bcrypt
from flask_login import UserMixin
from datetime import datetime, timezone, timedelta
from enum import Enum

# ============================================================================
# CONFIGURACIÓN: Zona horaria de Perú (UTC-5)
# ============================================================================
PERU_TZ = timezone(timedelta(hours=-5))

def get_peru_time():
    """Obtiene la hora actual en zona horaria de Perú (UTC-5)"""
    return datetime.now(PERU_TZ)


# ============================================================================
# ENUMS: Roles y Estados
# ============================================================================
class UserRole(str, Enum):
    """Roles de usuario en el sistema"""
    SUPER_ADMIN = 'SUPER_ADMIN'
    CLINIC_ADMIN = 'CLINIC_ADMIN'
    PROFESSIONAL = 'PROFESSIONAL'


class AppointmentStatus(str, Enum):
    """Estados de cita"""
    PROGRAMADA = 'Programada'
    COMPLETADA = 'Completada'
    CANCELADA = 'Cancelada'
    NO_ASISTIO = 'No Asistió'


# ============================================================================
# MODELO 1: CLINIC (Entidad Multi-Tenant Principal)
# ============================================================================
class Clinic(db.Model):
    """
    Representa una clínica/consultorio dentro del sistema SaaS.
    Es la entidad principal de aislamiento multi-tenant.
    """
    __tablename__ = 'clinic'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    
    # Información de contacto
    phone = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    address = db.Column(db.String(200), nullable=True)
    
    # Personalización
    logo_url = db.Column(db.String(500), nullable=True)  # URL del logo
    theme_color = db.Column(db.String(7), default='#4F46E5')  # Hex color
    
    # Estado y plan
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    plan = db.Column(db.String(20), default='free')  # free, basic, premium
    
    # Auditoría
    created_at = db.Column(db.DateTime, default=get_peru_time, nullable=False)
    updated_at = db.Column(db.DateTime, default=get_peru_time, onupdate=get_peru_time)
    
    # Relaciones (cascade para eliminar todo al borrar clínica)
    users = db.relationship('User', backref='clinic', lazy=True, cascade='all, delete-orphan')
    patients = db.relationship('Patient', backref='clinic', lazy=True, cascade='all, delete-orphan')
    services = db.relationship('Service', backref='clinic', lazy=True, cascade='all, delete-orphan')
    appointments = db.relationship('Appointment', backref='clinic', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Clinic {self.name}>'
    
    def to_dict(self):
        """Serializa el modelo a diccionario"""
        return {
            'id': self.id,
            'name': self.name,
            'phone': self.phone,
            'email': self.email,
            'address': self.address,
            'logo_url': self.logo_url,
            'theme_color': self.theme_color,
            'is_active': self.is_active,
            'plan': self.plan,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'users_count': len(self.users),
            'patients_count': len(self.patients),
            'appointments_count': len(self.appointments)
        }


# ============================================================================
# MODELO 2: USER (Roles Multi-Tenant)
# ============================================================================
class User(UserMixin, db.Model):
    """
    Usuario del sistema con roles jerárquicos:
    - SUPER_ADMIN: Gestiona todas las clínicas (clinic_id = NULL)
    - CLINIC_ADMIN: Administra una clínica específica
    - PROFESSIONAL: Profesional de salud dentro de una clínica
    """
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Datos de autenticación
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    
    # Rol y estado
    role = db.Column(db.Enum(UserRole), nullable=False, default=UserRole.PROFESSIONAL)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    # Multi-tenant: NULL solo para SUPER_ADMIN
    clinic_id = db.Column(db.Integer, db.ForeignKey('clinic.id', ondelete='CASCADE'), nullable=True)
    
    # Datos personales
    full_name = db.Column(db.String(150), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    
    # Preferencias
    pref_dark_mode = db.Column(db.Boolean, default=False, nullable=False)
    
    # Auditoría
    created_at = db.Column(db.DateTime, default=get_peru_time, nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)
    
    # Relaciones
    appointments_as_professional = db.relationship(
        'Appointment',
        foreign_keys='Appointment.professional_id',
        backref='professional',
        lazy=True,
        cascade='all, delete-orphan'
    )
    
    notifications = db.relationship(
        'Notification',
        backref='user',
        lazy=True,
        cascade='all, delete-orphan'
    )
    
    def __repr__(self):
        return f'<User {self.username} - {self.role.value}>'
    
    # ========================================================================
    # Métodos de contraseña
    # ========================================================================
    def set_password(self, password):
        """Hashea y guarda la contraseña"""
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    
    def check_password(self, password):
        """Verifica la contraseña"""
        if not self.password_hash:
            return False
        return bcrypt.check_password_hash(self.password_hash, password)
    
    # ========================================================================
    # Métodos de roles
    # ========================================================================
    def is_super_admin(self):
        """Verifica si es SUPER_ADMIN"""
        return self.role == UserRole.SUPER_ADMIN
    
    def is_clinic_admin(self):
        """Verifica si es CLINIC_ADMIN"""
        return self.role == UserRole.CLINIC_ADMIN
    
    def is_professional(self):
        """Verifica si es PROFESSIONAL"""
        return self.role == UserRole.PROFESSIONAL
    
    def can_manage_clinic(self, clinic_id):
        """Verifica si puede gestionar una clínica específica"""
        if self.is_super_admin():
            return True
        if self.is_clinic_admin() and self.clinic_id == clinic_id:
            return True
        return False
    
    def can_manage_appointments(self):
        """Verifica si puede gestionar citas"""
        return self.role in [UserRole.CLINIC_ADMIN, UserRole.PROFESSIONAL]
    
    # ========================================================================
    # Serialización
    # ========================================================================
    def to_dict(self, include_sensitive=False):
        """Serializa el usuario a diccionario"""
        data = {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role.value,
            'full_name': self.full_name,
            'phone': self.phone,
            'is_active': self.is_active,
            'clinic_id': self.clinic_id,
            'pref_dark_mode': self.pref_dark_mode,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }
        
        if include_sensitive:
            data['appointments_count'] = len(self.appointments_as_professional)
        
        return data


# ============================================================================
# MODELO 3: PATIENT (Pacientes por Clínica)
# ============================================================================
class Patient(db.Model):
    """
    Paciente vinculado a una clínica específica.
    Los pacientes NO son usuarios del sistema, son registros dentro de cada clínica.
    """
    __tablename__ = 'patient'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Multi-tenant
    clinic_id = db.Column(db.Integer, db.ForeignKey('clinic.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Datos personales
    name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    
    # Información adicional
    date_of_birth = db.Column(db.Date, nullable=True)
    address = db.Column(db.String(200), nullable=True)
    notes = db.Column(db.Text, nullable=True)  # Notas generales (no historia clínica)
    
    # Auditoría
    created_at = db.Column(db.DateTime, default=get_peru_time, nullable=False)
    updated_at = db.Column(db.DateTime, default=get_peru_time, onupdate=get_peru_time)
    
    # Relaciones
    appointments = db.relationship('Appointment', backref='patient', lazy=True)
    
    def __repr__(self):
        return f'<Patient {self.name}>'
    
    def to_dict(self):
        """Serializa el paciente a diccionario"""
        return {
            'id': self.id,
            'clinic_id': self.clinic_id,
            'name': self.name,
            'phone': self.phone,
            'email': self.email,
            'date_of_birth': self.date_of_birth.isoformat() if self.date_of_birth else None,
            'address': self.address,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'appointments_count': len(self.appointments)
        }
    
    def get_whatsapp_link(self, message=None):
        """Genera deep link de WhatsApp para recordatorios"""
        if not self.phone:
            return None
        
        # Limpiar número (quitar espacios, guiones, etc.)
        phone_clean = ''.join(filter(str.isdigit, self.phone))
        
        # Agregar código de país si no existe (Perú: +51)
        if not phone_clean.startswith('51'):
            phone_clean = '51' + phone_clean
        
        # Mensaje por defecto
        if not message:
            message = f"Hola {self.name}, te recordamos tu cita programada."
        
        # Codificar mensaje para URL
        from urllib.parse import quote
        message_encoded = quote(message)
        
        return f"https://wa.me/{phone_clean}?text={message_encoded}"


# ============================================================================
# MODELO 4: SERVICE (Servicios/Tratamientos por Clínica)
# ============================================================================
class Service(db.Model):
    """
    Servicio o tratamiento ofrecido por una clínica.
    Ejemplos: Consulta general, Limpieza dental, Terapia física, etc.
    """
    __tablename__ = 'service'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Multi-tenant
    clinic_id = db.Column(db.Integer, db.ForeignKey('clinic.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Datos del servicio
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    duration_minutes = db.Column(db.Integer, nullable=False, default=30)  # Duración en minutos
    price = db.Column(db.Numeric(10, 2), nullable=True)  # Precio (opcional)
    
    # Estado
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    # Auditoría
    created_at = db.Column(db.DateTime, default=get_peru_time, nullable=False)
    updated_at = db.Column(db.DateTime, default=get_peru_time, onupdate=get_peru_time)
    
    # Relaciones
    appointments = db.relationship('Appointment', backref='service', lazy=True)
    
    def __repr__(self):
        return f'<Service {self.name}>'
    
    def to_dict(self):
        """Serializa el servicio a diccionario"""
        return {
            'id': self.id,
            'clinic_id': self.clinic_id,
            'name': self.name,
            'description': self.description,
            'duration_minutes': self.duration_minutes,
            'price': float(self.price) if self.price else None,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


# ============================================================================
# MODELO 5: APPOINTMENT (Citas Multi-Tenant)
# ============================================================================
class Appointment(db.Model):
    """
    Cita médica/profesional.
    Aislada por clínica y asociada a un profesional y paciente específicos.
    """
    __tablename__ = 'appointment'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Multi-tenant
    clinic_id = db.Column(db.Integer, db.ForeignKey('clinic.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Relaciones principales
    professional_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id', ondelete='CASCADE'), nullable=False, index=True)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id', ondelete='SET NULL'), nullable=True)
    
    # Fechas y horarios
    start_datetime = db.Column(db.DateTime, nullable=False, index=True)
    end_datetime = db.Column(db.DateTime, nullable=False, index=True)
    
    # Estado
    status = db.Column(db.Enum(AppointmentStatus), nullable=False, default=AppointmentStatus.PROGRAMADA)
    
    # Notas clínicas (historia de evolución)
    notes = db.Column(db.Text, nullable=True)
    
    # Cancelación
    cancelled_at = db.Column(db.DateTime, nullable=True)
    cancellation_reason = db.Column(db.String(200), nullable=True)
    
    # Auditoría
    created_at = db.Column(db.DateTime, default=get_peru_time, nullable=False)
    updated_at = db.Column(db.DateTime, default=get_peru_time, onupdate=get_peru_time)
    
    def __repr__(self):
        return f'<Appointment {self.id} - {self.status.value}>'
    
    # ========================================================================
    # Métodos de validación
    # ========================================================================
    def can_be_completed(self):
        """Verifica si la cita puede marcarse como completada"""
        if self.status != AppointmentStatus.PROGRAMADA:
            return False
        
        now_peru = get_peru_time()
        end_aware = self.end_datetime.replace(tzinfo=PERU_TZ) if self.end_datetime.tzinfo is None else self.end_datetime
        return end_aware <= now_peru
    
    def can_be_cancelled(self):
        """Verifica si la cita puede cancelarse"""
        return self.status == AppointmentStatus.PROGRAMADA
    
    def can_be_edited(self):
        """Verifica si la cita puede editarse"""
        return self.status in [AppointmentStatus.PROGRAMADA, AppointmentStatus.NO_ASISTIO]
    
    # ========================================================================
    # Métodos de estado
    # ========================================================================
    def complete(self):
        """Marca la cita como completada"""
        if not self.can_be_completed():
            raise ValueError('No se puede completar esta cita. Debe estar programada y haber pasado la fecha.')
        
        self.status = AppointmentStatus.COMPLETADA
        self.updated_at = get_peru_time()
    
    def cancel(self, reason=None):
        """Cancela la cita"""
        if not self.can_be_cancelled():
            raise ValueError('No se puede cancelar esta cita.')
        
        self.status = AppointmentStatus.CANCELADA
        self.cancelled_at = get_peru_time()
        self.cancellation_reason = reason or 'Sin motivo especificado'
        self.updated_at = get_peru_time()
    
    def mark_no_show(self, reason=None):
        """Marca la cita como 'No Asistió'"""
        if self.status != AppointmentStatus.PROGRAMADA:
            raise ValueError('Solo se pueden marcar citas programadas como "No Asistió".')
        
        self.status = AppointmentStatus.NO_ASISTIO
        self.cancellation_reason = reason or 'El paciente no asistió'
        self.updated_at = get_peru_time()
    
    # ========================================================================
    # Validación de solapamiento
    # ========================================================================
    @staticmethod
    def check_overlap(clinic_id, professional_id, start_dt, end_dt, exclude_appointment_id=None):
        """
        Verifica si existe solapamiento de horarios.
        Ignora citas canceladas y "No Asistió".
        
        Returns:
            Appointment | None: La cita que se solapa, o None si no hay conflicto
        """
        query = Appointment.query.filter(
            Appointment.clinic_id == clinic_id,
            Appointment.professional_id == professional_id,
            Appointment.status.in_([AppointmentStatus.PROGRAMADA, AppointmentStatus.COMPLETADA]),
            Appointment.start_datetime < end_dt,
            Appointment.end_datetime > start_dt
        )
        
        if exclude_appointment_id:
            query = query.filter(Appointment.id != exclude_appointment_id)
        
        return query.first()
    
    # ========================================================================
    # Serialización
    # ========================================================================
    def to_dict(self):
        """Serializa la cita a diccionario"""
        # Hacer aware los datetimes
        start_aware = self.start_datetime.replace(tzinfo=PERU_TZ) if self.start_datetime.tzinfo is None else self.start_datetime
        end_aware = self.end_datetime.replace(tzinfo=PERU_TZ) if self.end_datetime.tzinfo is None else self.end_datetime
        
        return {
            'id': self.id,
            'clinic_id': self.clinic_id,
            'professional_id': self.professional_id,
            'professional_name': self.professional.full_name or self.professional.username if self.professional else None,
            'patient_id': self.patient_id,
            'patient_name': self.patient.name if self.patient else None,
            'patient_phone': self.patient.phone if self.patient else None,
            'service_id': self.service_id,
            'service_name': self.service.name if self.service else None,
            'start_datetime': start_aware.isoformat(),
            'end_datetime': end_aware.isoformat(),
            'status': self.status.value,
            'notes': self.notes,
            'cancelled_at': self.cancelled_at.isoformat() if self.cancelled_at else None,
            'cancellation_reason': self.cancellation_reason,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'can_complete': self.can_be_completed(),
            'can_cancel': self.can_be_cancelled(),
            'can_edit': self.can_be_edited()
        }
    
    def to_fullcalendar_event(self):
        """Serializa para FullCalendar"""
        # Color según estado
        color_map = {
            AppointmentStatus.PROGRAMADA: '#0d6efd',  # Azul
            AppointmentStatus.COMPLETADA: '#198754',  # Verde
            AppointmentStatus.CANCELADA: '#dc3545',   # Rojo
            AppointmentStatus.NO_ASISTIO: '#ffc107'   # Amarillo
        }
        
        start_aware = self.start_datetime.replace(tzinfo=PERU_TZ) if self.start_datetime.tzinfo is None else self.start_datetime
        end_aware = self.end_datetime.replace(tzinfo=PERU_TZ) if self.end_datetime.tzinfo is None else self.end_datetime
        
        return {
            'id': self.id,
            'title': self.patient.name if self.patient else 'Paciente desconocido',
            'start': start_aware.isoformat(),
            'end': end_aware.isoformat(),
            'backgroundColor': color_map.get(self.status, '#6c757d'),
            'borderColor': color_map.get(self.status, '#6c757d'),
            'extendedProps': {
                'patient_id': self.patient_id,
                'patient_name': self.patient.name if self.patient else None,
                'patient_phone': self.patient.phone if self.patient else None,
                'service': self.service.name if self.service else None,
                'professional': self.professional.full_name or self.professional.username if self.professional else None,
                'status': self.status.value,
                'notes': self.notes or '',
                'can_complete': self.can_be_completed(),
                'can_cancel': self.can_be_cancelled()
            }
        }


# ============================================================================
# MODELO 6: NOTIFICATION (Sistema de notificaciones)
# ============================================================================
class Notification(db.Model):
    """
    Notificaciones del sistema para usuarios.
    Usado para avisos de citas, cambios, etc.
    """
    __tablename__ = 'notification'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Usuario destinatario
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Contenido
    message = db.Column(db.String(200), nullable=False)
    type = db.Column(db.String(20), default='info', nullable=False)  # info, success, warning, danger
    
    # Estado
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    
    # Auditoría
    created_at = db.Column(db.DateTime, default=get_peru_time, nullable=False)
    
    def __repr__(self):
        return f'<Notification {self.id} - {self.type}>'
    
    def to_dict(self):
        """Serializa la notificación a diccionario"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'message': self.message,
            'type': self.type,
            'is_read': self.is_read,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M')
        }