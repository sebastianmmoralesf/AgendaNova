import os

class Config:
    """
    Configuración de la aplicación Flask.
    Limpia de dependencias de terceros (Google OAuth eliminado).
    """
    
    # ========================================================================
    # SECRET KEY
    # ========================================================================
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-CHANGE-IN-PRODUCTION-2025'
    
    # ========================================================================
    # DATABASE
    # ========================================================================
    # Prioridad:
    # 1. DATABASE_URL (para producción en Render con PostgreSQL)
    # 2. Fallback a SQLite local en /tmp para Render Free Tier
    # 3. Desarrollo local: instance/database.db
    
    if os.environ.get('DATABASE_URL'):
        # Render u otro hosting con PostgreSQL
        SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
        
        # Fix para Heroku/Render (postgres:// -> postgresql://)
        if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
            SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace(
                "postgres://", "postgresql://", 1
            )
    else:
        # Desarrollo local o Render con SQLite
        # En Render Free Tier, usar /tmp para persistencia efímera
        if os.environ.get('RENDER'):
            # Render detectado (variable de entorno automática)
            DATABASE_PATH = '/tmp/agendanova.db'
        else:
            # Desarrollo local
            basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
            DATABASE_PATH = os.path.join(basedir, 'instance', 'database.db')
        
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{DATABASE_PATH}'
    
    # Configuraciones adicionales de SQLAlchemy
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False  # Cambiar a True para debug SQL
    
    # ========================================================================
    # FLASK ENVIRONMENT
    # ========================================================================
    FLASK_ENV = os.environ.get('FLASK_ENV', 'production')
    DEBUG = FLASK_ENV == 'development'
    
    # ========================================================================
    # SESSION & SECURITY
    # ========================================================================
    SESSION_COOKIE_SECURE = FLASK_ENV == 'production'  # Solo HTTPS en producción
    SESSION_COOKIE_HTTPONLY = True  # Prevenir XSS
    SESSION_COOKIE_SAMESITE = 'Lax'  # Protección CSRF
    PERMANENT_SESSION_LIFETIME = 86400  # 24 horas en segundos
    
    # ========================================================================
    # CORS (si necesitas API externa)
    # ========================================================================
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*').split(',')
    
    # ========================================================================
    # PAGINATION (para futuras listas paginadas)
    # ========================================================================
    ITEMS_PER_PAGE = 20
    
    # ========================================================================
    # FILE UPLOAD (para futuros logos de clínicas)
    # ========================================================================
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB máximo
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    
    # ========================================================================
    # TIMEZONE
    # ========================================================================
    TIMEZONE = 'America/Lima'  # Perú (UTC-5)
    
    # ========================================================================
    # WHATSAPP DEEP LINK CONFIG
    # ========================================================================
    WHATSAPP_COUNTRY_CODE = '51'  # Perú
    
    # ========================================================================
    # SUPER ADMIN CREDENTIALS (seed inicial)
    # ========================================================================
    # Estas credenciales se usan SOLO para crear el primer SUPER_ADMIN
    # Si ya existe un SUPER_ADMIN en la BD, estos valores se ignoran
    SUPER_ADMIN_USERNAME = os.environ.get('SUPER_ADMIN_USERNAME', 'superadmin')
    SUPER_ADMIN_EMAIL = os.environ.get('SUPER_ADMIN_EMAIL', 'superadmin@agendanova.com')
    SUPER_ADMIN_PASSWORD = os.environ.get('SUPER_ADMIN_PASSWORD', 'Super@2025!')
    
    # ========================================================================
    # DEMO DATA (para desarrollo)
    # ========================================================================
    CREATE_DEMO_DATA = os.environ.get('CREATE_DEMO_DATA', 'false').lower() == 'true'
    
    # ========================================================================
    # LOGGING
    # ========================================================================
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    
    # ========================================================================
    # RATE LIMITING (para futuras implementaciones)
    # ========================================================================
    RATELIMIT_ENABLED = os.environ.get('RATELIMIT_ENABLED', 'false').lower() == 'true'
    RATELIMIT_DEFAULT = "200 per day;50 per hour"
    
    @staticmethod
    def init_app(app):
        """
        Inicializaciones adicionales de la app.
        Se puede usar para crear carpetas, configurar logging, etc.
        """
        # Crear carpeta de uploads si no existe
        if not os.path.exists(Config.UPLOAD_FOLDER):
            os.makedirs(Config.UPLOAD_FOLDER)
            print(f"✅ Carpeta de uploads creada: {Config.UPLOAD_FOLDER}")
        
        # Logging básico
        if Config.DEBUG:
            import logging
            logging.basicConfig(level=logging.DEBUG)
            app.logger.setLevel(logging.DEBUG)
            app.logger.info("🔧 Modo DEBUG activado")
        else:
            import logging
            logging.basicConfig(level=logging.INFO)
            app.logger.setLevel(logging.INFO)
            app.logger.info("🚀 Modo PRODUCCIÓN activado")


class DevelopmentConfig(Config):
    """Configuración específica para desarrollo local"""
    DEBUG = True
    SQLALCHEMY_ECHO = True  # Ver queries SQL en consola
    TESTING = False


class ProductionConfig(Config):
    """Configuración específica para producción"""
    DEBUG = False
    TESTING = False
    SQLALCHEMY_ECHO = False
    
    # Validaciones adicionales para producción
    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        
        # Validar SECRET_KEY en producción
        if app.config['SECRET_KEY'] == 'dev-secret-key-CHANGE-IN-PRODUCTION-2025':
            app.logger.warning(
                "⚠️  ADVERTENCIA: Usando SECRET_KEY por defecto en producción. "
                "Define la variable de entorno SECRET_KEY."
            )
        
        # Validar que no se use SQLite en producción a gran escala
        if app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite'):
            app.logger.warning(
                "⚠️  ADVERTENCIA: Usando SQLite en producción. "
                "Para mejor rendimiento, considera PostgreSQL."
            )


class TestingConfig(Config):
    """Configuración para tests (futuro)"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'  # Base de datos en memoria
    WTF_CSRF_ENABLED = False
    DEBUG = True


# ============================================================================
# CONFIGURACIÓN POR ENTORNO
# ============================================================================
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config():
    """
    Obtiene la configuración según la variable de entorno FLASK_ENV.
    """
    env = os.environ.get('FLASK_ENV', 'production')
    return config.get(env, config['default'])
