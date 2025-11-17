from dotenv import load_dotenv
load_dotenv() # <-- ¡ESTA ES LA SOLUCIÓN! Carga el .env PRIMERO.

import os
import sys
from project import create_app, db
from project.models import User, UserRole

app = create_app() # <-- AHORA esta línea verá las variables del .env

if __name__ == '__main__':
    # Verificar si se pasa un comando especial
    if len(sys.argv) > 1 and sys.argv[1] == 'create-super-admin':
        with app.app_context():
            print("=" * 60)
            print("🔨 CREAR SUPER ADMINISTRADOR")
            print("=" * 60)
            
            # Verificar si ya existe un Super Admin
            existing_super_admin = User.query.filter_by(role=UserRole.SUPER_ADMIN).first()
            
            if existing_super_admin:
                print(f"⚠️  Ya existe un Super Admin: {existing_super_admin.username}")
                print(f"   Email: {existing_super_admin.email}")
                print("\n¿Deseas crear otro Super Admin? (s/n): ", end='')
                
                respuesta = input().lower()
                if respuesta != 's':
                    print("❌ Operación cancelada.")
                    sys.exit(0)
            
            print("\nIngresa los datos del nuevo Super Admin:")
            print("-" * 60)
            
            # Solicitar datos
            username = input("Username: ").strip()
            if not username:
                print("❌ Error: El username es requerido")
                sys.exit(1)
            
            # Verificar que el username no exista
            if User.query.filter_by(username=username).first():
                print(f"❌ Error: El username '{username}' ya está en uso")
                sys.exit(1)
            
            email = input("Email: ").strip()
            if not email:
                print("❌ Error: El email es requerido")
                sys.exit(1)
            
            # Verificar que el email no exista
            if User.query.filter_by(email=email).first():
                print(f"❌ Error: El email '{email}' ya está en uso")
                sys.exit(1)
            
            full_name = input("Nombre completo (opcional): ").strip()
            
            import getpass
            password = getpass.getpass("Contraseña (mínimo 6 caracteres): ")
            
            if len(password) < 6:
                print("❌ Error: La contraseña debe tener al menos 6 caracteres")
                sys.exit(1)
            
            password_confirm = getpass.getpass("Confirmar contraseña: ")
            
            if password != password_confirm:
                print("❌ Error: Las contraseñas no coinciden")
                sys.exit(1)
            
            try:
                # Crear Super Admin
                super_admin = User(
                    username=username,
                    email=email,
                    full_name=full_name or username,
                    role=UserRole.SUPER_ADMIN,
                    is_active=True,
                    clinic_id=None
                )
                super_admin.set_password(password)
                
                db.session.add(super_admin)
                db.session.commit()
                
                print("\n" + "=" * 60)
                print("✅ SUPER ADMIN CREADO EXITOSAMENTE")
                print("=" * 60)
                print(f"Username: {super_admin.username}")
                print(f"Email: {super_admin.email}")
                print(f"Nombre: {super_admin.full_name}")
                print("=" * 60)
                print("\n⚠️  IMPORTANTE: Guarda estas credenciales de forma segura.")
                print("\nYa puedes iniciar sesión en el sistema.\n")
                
            except Exception as e:
                db.session.rollback()
                print(f"\n❌ Error al crear Super Admin: {str(e)}")
                sys.exit(1)
        
        sys.exit(0)
    
    # Modo normal: Ejecutar servidor de desarrollo
    port = int(os.environ.get('PORT', 5000))
    # Esta línea ahora leerá 'development' de tu .env
    debug = os.environ.get('FLASK_ENV', 'production') == 'development'
    
    print("\n" + "=" * 60)
    print("🚀 AgendaNova - Sistema de Gestión de Citas")
    print("=" * 60)
    print(f"Entorno: {'DESARROLLO' if debug else 'PRODUCCIÓN'}")
    print(f"Puerto: {port}")
    print(f"URL: http://{'127.0.0.1' if debug else '0.0.0.0'}:{port}") # Corregido a 127.0.0.1 para dev
    print("=" * 60 + "\n")
    
    app.run(host='0.0.0.0', port=port, debug=debug)