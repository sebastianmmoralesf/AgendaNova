import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_cors import CORS

# ============================================================================
# INICIALIZACIÓN DE EXTENSIONES
# ============================================================================
db = SQLAlchemy()
bcrypt = Bcrypt()
login_manager = LoginManager()


def create_app(config_name=None):
    """
    Application Factory Pattern.
    Crea y configura la aplicación Flask.
    
    Args:
        config_name (str): Nombre del entorno ('development', 'production', 'testing')
    
    Returns:
        Flask: Aplicación configurada
    """
    app = Flask(__name__)
    
    # ========================================================================
    # CONFIGURACIÓN
    # ========================================================================
    if config_name is None:
        from project.config import get_config
        app.config.from_object(get_config())
        get_config().init_app(app)
    else:
        from project.config import config
        app.config.from_object(config[config_name])
        config[config_name].init_app(app)
    
    # ========================================================================
    # CREAR CARPETA INSTANCE (para SQLite local)
    # ========================================================================
    if app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite'):
        instance_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 
            'instance'
        )
        if not os.path.exists(instance_path):
            os.makedirs(instance_path)
            app.logger.info(f"✅ Carpeta instance creada: {instance_path}")
    
    # ========================================================================
    # INICIALIZAR EXTENSIONES
    # ========================================================================
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    CORS(app, origins=app.config.get('CORS_ORIGINS', '*'))
    
    # ========================================================================
    # CONFIGURAR FLASK-LOGIN
    # ========================================================================
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor inicia sesión para acceder a esta página.'
    login_manager.login_message_category = 'warning'
    
    from project.models import User
    
    @login_manager.user_loader
    def load_user(user_id):
        """Carga un usuario por su ID para Flask-Login"""
        return User.query.get(int(user_id))
    
    # ========================================================================
    # REGISTRAR BLUEPRINTS
    # ========================================================================
    from project.auth_routes import auth_bp
    from project.api_routes import api_bp
    from project.super_admin_routes import super_admin_bp
    from project.clinic_admin_routes import clinic_admin_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(super_admin_bp, url_prefix='/super-admin')
    app.register_blueprint(clinic_admin_bp, url_prefix='/clinic-admin')
    
    # ========================================================================
    # INICIALIZAR BASE DE DATOS Y SEED
    # ========================================================================
    with app.app_context():
        # Crear todas las tablas
        db.create_all()
        app.logger.info("✅ Base de datos inicializada")
        
        # Seed de datos iniciales
        seed_initial_data(app)
    
    # ========================================================================
    # CUSTOM ERROR HANDLERS (Opcional)
    # ========================================================================
    @app.errorhandler(404)
    def not_found(error):
        from flask import render_template
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(403)
    def forbidden(error):
        from flask import render_template
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()  # Rollback en caso de error
        from flask import render_template
        return render_template('errors/500.html'), 500
    
    # ========================================================================
    # LOGGING PERSONALIZADO
    # ========================================================================
    if not app.debug:
        import logging
        from logging.handlers import RotatingFileHandler
        
        if not os.path.exists('logs'):
            os.mkdir('logs')
        
        file_handler = RotatingFileHandler(
            'logs/agendanova.log',
            maxBytes=10240000,  # 10MB
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('🚀 AgendaNova iniciado')
    
    return app


# ============================================================================
# SEED DE DATOS INICIALES
# ============================================================================
def seed_initial_data(app):
    """
    Crea datos iniciales en la base de datos:
    1. SUPER_ADMIN (si no existe)
    2. Clínica Demo (si CREATE_DEMO_DATA=true)
    3. Usuarios de prueba (si CREATE_DEMO_DATA=true)
    """
    from project.models import User, Clinic, Patient, Service, Appointment, UserRole
    from datetime import datetime, timedelta
    
    # ========================================================================
    # 1. CREAR SUPER_ADMIN (SIEMPRE)
    # ========================================================================
    super_admin = User.query.filter_by(role=UserRole.SUPER_ADMIN).first()
    
    if not super_admin:
        app.logger.info("🔨 Creando SUPER_ADMIN inicial...")
        
        super_admin = User(
            username=app.config['SUPER_ADMIN_USERNAME'],
            email=app.config['SUPER_ADMIN_EMAIL'],
            role=UserRole.SUPER_ADMIN,
            full_name='Super Administrador',
            is_active=True,
            clinic_id=None  # SUPER_ADMIN no pertenece a ninguna clínica
        )
        super_admin.set_password(app.config['SUPER_ADMIN_PASSWORD'])
        
        db.session.add(super_admin)
        db.session.commit()
        
        app.logger.info(f"✅ SUPER_ADMIN creado exitosamente")
        app.logger.info(f"   Username: {super_admin.username}")
        app.logger.info(f"   Email: {super_admin.email}")
        app.logger.info(f"   Password: {app.config['SUPER_ADMIN_PASSWORD']}")
        app.logger.info(f"   ⚠️  CAMBIA ESTA CONTRASEÑA EN PRODUCCIÓN")
    else:
        app.logger.info(f"✓ SUPER_ADMIN ya existe: {super_admin.username}")
    
    # ========================================================================
    # 2. CREAR DATOS DEMO (SOLO SI CREATE_DEMO_DATA=true)
    # ========================================================================
    if not app.config.get('CREATE_DEMO_DATA', False):
        app.logger.info("ℹ️  CREATE_DEMO_DATA=false, saltando datos de prueba")
        return
    
    app.logger.info("🔨 Creando datos de demostración...")
    
    # ========================================================================
    # 2.1. CREAR CLÍNICA DEMO
    # ========================================================================
    clinic_demo = Clinic.query.filter_by(name='Clínica Demo').first()
    
    if not clinic_demo:
        clinic_demo = Clinic(
            name='Clínica Demo',
            phone='+51 999 888 777',
            email='contacto@clinicademo.com',
            address='Av. Principal 123, Lima, Perú',
            theme_color='#4F46E5',
            is_active=True,
            plan='free'
        )
        db.session.add(clinic_demo)
        db.session.commit()
        app.logger.info(f"✅ Clínica Demo creada (ID: {clinic_demo.id})")
    else:
        app.logger.info(f"✓ Clínica Demo ya existe (ID: {clinic_demo.id})")
    
    # ========================================================================
    # 2.2. CREAR CLINIC_ADMIN PARA CLÍNICA DEMO
    # ========================================================================
    clinic_admin = User.query.filter_by(
        username='admin_clinica_demo'
    ).first()
    
    if not clinic_admin:
        clinic_admin = User(
            username='admin_clinica_demo',
            email='admin@clinicademo.com',
            role=UserRole.CLINIC_ADMIN,
            full_name='Administrador Demo',
            phone='+51 999 888 777',
            clinic_id=clinic_demo.id,
            is_active=True
        )
        clinic_admin.set_password('Admin@2025!')
        db.session.add(clinic_admin)
        db.session.commit()
        
        app.logger.info(f"✅ CLINIC_ADMIN creado: {clinic_admin.username}")
        app.logger.info(f"   Password: Admin@2025!")
    else:
        app.logger.info(f"✓ CLINIC_ADMIN ya existe: {clinic_admin.username}")
    
    # ========================================================================
    # 2.3. CREAR PROFESIONALES PARA CLÍNICA DEMO
    # ========================================================================
    professionals_data = [
        {
            'username': 'dr_lopez',
            'email': 'dr.lopez@clinicademo.com',
            'full_name': 'Dr. Carlos López',
            'phone': '+51 987 654 321',
            'password': 'Doctor@2025!'
        },
        {
            'username': 'dra_martinez',
            'email': 'dra.martinez@clinicademo.com',
            'full_name': 'Dra. Ana Martínez',
            'phone': '+51 987 654 322',
            'password': 'Doctor@2025!'
        }
    ]
    
    professionals = []
    for prof_data in professionals_data:
        prof = User.query.filter_by(username=prof_data['username']).first()
        
        if not prof:
            prof = User(
                username=prof_data['username'],
                email=prof_data['email'],
                role=UserRole.PROFESSIONAL,
                full_name=prof_data['full_name'],
                phone=prof_data['phone'],
                clinic_id=clinic_demo.id,
                is_active=True
            )
            prof.set_password(prof_data['password'])
            db.session.add(prof)
            professionals.append(prof)
            app.logger.info(f"✅ Profesional creado: {prof.username}")
        else:
            professionals.append(prof)
            app.logger.info(f"✓ Profesional ya existe: {prof.username}")
    
    db.session.commit()
    
    # ========================================================================
    # 2.4. CREAR SERVICIOS PARA CLÍNICA DEMO
    # ========================================================================
    services_data = [
        {
            'name': 'Consulta General',
            'description': 'Consulta médica general',
            'duration_minutes': 30,
            'price': 80.00
        },
        {
            'name': 'Control de Rutina',
            'description': 'Control médico de rutina',
            'duration_minutes': 20,
            'price': 50.00
        },
        {
            'name': 'Terapia Física',
            'description': 'Sesión de terapia física',
            'duration_minutes': 45,
            'price': 100.00
        },
        {
            'name': 'Consulta de Especialidad',
            'description': 'Consulta con especialista',
            'duration_minutes': 60,
            'price': 150.00
        }
    ]
    
    services = []
    for service_data in services_data:
        service = Service.query.filter_by(
            name=service_data['name'],
            clinic_id=clinic_demo.id
        ).first()
        
        if not service:
            service = Service(
                name=service_data['name'],
                description=service_data['description'],
                duration_minutes=service_data['duration_minutes'],
                price=service_data['price'],
                clinic_id=clinic_demo.id,
                is_active=True
            )
            db.session.add(service)
            services.append(service)
        else:
            services.append(service)
    
    db.session.commit()
    app.logger.info(f"✅ {len(services)} servicios creados/verificados")
    
    # ========================================================================
    # 2.5. CREAR PACIENTES PARA CLÍNICA DEMO
    # ========================================================================
    patients_data = [
        {
            'name': 'Juan Pérez García',
            'phone': '+51 987 111 222',
            'email': 'juan.perez@email.com',
            'notes': 'Paciente regular desde 2023'
        },
        {
            'name': 'María González López',
            'phone': '+51 987 222 333',
            'email': 'maria.gonzalez@email.com',
            'notes': 'Alergias: Penicilina'
        },
        {
            'name': 'Pedro Rodríguez Sánchez',
            'phone': '+51 987 333 444',
            'email': 'pedro.rodriguez@email.com',
            'notes': 'Hipertensión controlada'
        },
        {
            'name': 'Ana Torres Ramírez',
            'phone': '+51 987 444 555',
            'email': 'ana.torres@email.com',
            'notes': 'Primera visita'
        },
        {
            'name': 'Luis Fernández Castro',
            'phone': '+51 987 555 666',
            'email': 'luis.fernandez@email.com',
            'notes': 'Tratamiento de rehabilitación'
        }
    ]
    
    patients = []
    for patient_data in patients_data:
        patient = Patient.query.filter_by(
            phone=patient_data['phone'],
            clinic_id=clinic_demo.id
        ).first()
        
        if not patient:
            patient = Patient(
                name=patient_data['name'],
                phone=patient_data['phone'],
                email=patient_data['email'],
                notes=patient_data['notes'],
                clinic_id=clinic_demo.id
            )
            db.session.add(patient)
            patients.append(patient)
        else:
            patients.append(patient)
    
    db.session.commit()
    app.logger.info(f"✅ {len(patients)} pacientes creados/verificados")
    
    # ========================================================================
    # 2.6. CREAR CITAS DE EJEMPLO
    # ========================================================================
    if professionals and patients and services:
        # Verificar si ya hay citas
        existing_appointments = Appointment.query.filter_by(
            clinic_id=clinic_demo.id
        ).count()
        
        if existing_appointments == 0:
            from project.models import AppointmentStatus, get_peru_time
            
            now = get_peru_time()
            appointments_data = [
                # Citas futuras (Programadas)
                {
                    'professional': professionals[0],
                    'patient': patients[0],
                    'service': services[0],
                    'start': now + timedelta(days=1, hours=9),
                    'end': now + timedelta(days=1, hours=9, minutes=30),
                    'status': AppointmentStatus.PROGRAMADA,
                    'notes': 'Control de rutina'
                },
                {
                    'professional': professionals[0],
                    'patient': patients[1],
                    'service': services[1],
                    'start': now + timedelta(days=1, hours=10),
                    'end': now + timedelta(days=1, hours=10, minutes=20),
                    'status': AppointmentStatus.PROGRAMADA,
                    'notes': 'Primera consulta'
                },
                {
                    'professional': professionals[1],
                    'patient': patients[2],
                    'service': services[2],
                    'start': now + timedelta(days=2, hours=14),
                    'end': now + timedelta(days=2, hours=14, minutes=45),
                    'status': AppointmentStatus.PROGRAMADA,
                    'notes': 'Sesión de terapia'
                },
                # Citas pasadas (Completadas)
                {
                    'professional': professionals[0],
                    'patient': patients[3],
                    'service': services[0],
                    'start': now - timedelta(days=2, hours=11),
                    'end': now - timedelta(days=2, hours=11, minutes=30),
                    'status': AppointmentStatus.COMPLETADA,
                    'notes': 'Paciente atendido satisfactoriamente'
                },
                {
                    'professional': professionals[1],
                    'patient': patients[4],
                    'service': services[3],
                    'start': now - timedelta(days=1, hours=15),
                    'end': now - timedelta(days=1, hours=16),
                    'status': AppointmentStatus.COMPLETADA,
                    'notes': 'Consulta de especialidad - Todo OK'
                }
            ]
            
            for apt_data in appointments_data:
                appointment = Appointment(
                    clinic_id=clinic_demo.id,
                    professional_id=apt_data['professional'].id,
                    patient_id=apt_data['patient'].id,
                    service_id=apt_data['service'].id,
                    start_datetime=apt_data['start'].replace(tzinfo=None),
                    end_datetime=apt_data['end'].replace(tzinfo=None),
                    status=apt_data['status'],
                    notes=apt_data['notes']
                )
                db.session.add(appointment)
            
            db.session.commit()
            app.logger.info(f"✅ {len(appointments_data)} citas de ejemplo creadas")
        else:
            app.logger.info(f"✓ Ya existen {existing_appointments} citas en la clínica demo")
    
    # ========================================================================
    # RESUMEN FINAL
    # ========================================================================
    app.logger.info("=" * 60)
    app.logger.info("✅ SEED COMPLETADO - Datos de Demostración Creados")
    app.logger.info("=" * 60)
    app.logger.info(f"🏥 Clínica: {clinic_demo.name}")
    app.logger.info(f"👤 Usuarios creados:")
    app.logger.info(f"   • SUPER_ADMIN: {super_admin.username}")
    app.logger.info(f"   • CLINIC_ADMIN: {clinic_admin.username}")
    for prof in professionals:
        app.logger.info(f"   • PROFESSIONAL: {prof.username}")
    app.logger.info(f"👥 Pacientes: {len(patients)}")
    app.logger.info(f"🛠️  Servicios: {len(services)}")
    app.logger.info(f"📅 Citas: {Appointment.query.filter_by(clinic_id=clinic_demo.id).count()}")
    app.logger.info("=" * 60)