from flask import Flask, jsonify, send_file
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from config import config
from models import db, User, Event, VendorApplication, Payment
from auth_routes import auth_bp
from vendor_routes import vendor_bp
from admin_routes import admin_bp
from datetime import datetime
from sqlalchemy import inspect, text
import os


def migrate_sqlite_schema(app):
    """Add missing columns in existing SQLite databases."""
    database_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    if not str(database_uri).startswith('sqlite'):
        return

    with app.app_context():
        inspector = inspect(db.engine)
        table_names = inspector.get_table_names()
        if 'events' not in table_names:
            return

        existing_columns = {column['name'] for column in inspector.get_columns('events')}
        alter_statements = []

        if 'created_by_admin_id' not in existing_columns:
            alter_statements.append("ALTER TABLE events ADD COLUMN created_by_admin_id INTEGER")
        if 'default_currency' not in existing_columns:
            alter_statements.append("ALTER TABLE events ADD COLUMN default_currency VARCHAR(10) DEFAULT 'USD'")
        if 'currency_options' not in existing_columns:
            alter_statements.append("ALTER TABLE events ADD COLUMN currency_options VARCHAR(120) DEFAULT 'USD'")
        if 'mpesa_number' not in existing_columns:
            alter_statements.append("ALTER TABLE events ADD COLUMN mpesa_number VARCHAR(40)")
        if 'paypal_account' not in existing_columns:
            alter_statements.append("ALTER TABLE events ADD COLUMN paypal_account VARCHAR(120)")
        if 'zelle_account' not in existing_columns:
            alter_statements.append("ALTER TABLE events ADD COLUMN zelle_account VARCHAR(120)")
        if 'card_instructions' not in existing_columns:
            alter_statements.append("ALTER TABLE events ADD COLUMN card_instructions VARCHAR(255)")

        if not alter_statements:
            return

        for statement in alter_statements:
            db.session.execute(text(statement))

        admin_id = db.session.execute(
            text("SELECT id FROM users WHERE role = 'admin' ORDER BY id LIMIT 1")
        ).scalar()
        if admin_id is not None and 'created_by_admin_id' not in existing_columns:
            db.session.execute(
                text(
                    "UPDATE events "
                    "SET created_by_admin_id = :admin_id "
                    "WHERE created_by_admin_id IS NULL"
                ),
                {'admin_id': admin_id}
            )

        # Payments table migrations for older SQLite schemas.
        if 'payments' in table_names:
            payment_columns = {column['name'] for column in inspector.get_columns('payments')}
            if 'currency' not in payment_columns:
                db.session.execute(text("ALTER TABLE payments ADD COLUMN currency VARCHAR(10) DEFAULT 'USD'"))
                db.session.execute(text("UPDATE payments SET currency = 'USD' WHERE currency IS NULL OR currency = ''"))
            if 'pay_to' not in payment_columns:
                db.session.execute(text("ALTER TABLE payments ADD COLUMN pay_to VARCHAR(255)"))

        db.session.commit()

def create_app(config_name='development'):
    """Application factory pattern"""
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    db.init_app(app)
    jwt = JWTManager(app)
    
    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(vendor_bp, url_prefix='/api/vendor')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    
    # Health check endpoint
    @app.route('/', methods=['GET'])
    def landing_page():
        frontend_index = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'Frontend',
            'index.html'
        )
        if os.path.exists(frontend_index):
            return send_file(frontend_index)
        return jsonify({'error': 'Landing page not found'}), 404

    @app.route('/api/health', methods=['GET'])
    def health_check():
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat()
        }), 200

    @app.route('/api/events', methods=['GET'])
    def public_events():
        """Public list of available events"""
        try:
            events = Event.query.filter(
                Event.status.in_(['upcoming', 'ongoing'])
            ).order_by(Event.event_date.asc()).all()
            return jsonify([event.to_dict() for event in events]), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Resource not found'}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500
    
    # JWT error handlers
    @jwt.unauthorized_loader
    def unauthorized_callback(callback):
        return jsonify({'error': 'Missing authorization token'}), 401
    
    @jwt.invalid_token_loader
    def invalid_token_callback(callback):
        return jsonify({'error': 'Invalid token'}), 401
    
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({'error': 'Token has expired'}), 401
    
    return app

def init_db(app):
    """Initialize database with sample data"""
    with app.app_context():
        # Create all tables
        db.create_all()
        migrate_sqlite_schema(app)
        
        # Check if data already exists
        if User.query.first() is not None:
            print("Database already initialized")
            return
        
        print("Initializing database with sample data...")
        
        # Create admin user
        admin = User(
            email='admin@eventflow.com',
            full_name='System Administrator',
            role='admin',
            phone='+1234567890'
        )
        admin.set_password('admin123')
        db.session.add(admin)
        
        # Create sample vendors
        vendors = [
            {
                'email': 'vendor1@example.com',
                'full_name': 'John Smith',
                'company_name': 'Gourmet Foods Co.',
                'business_type': 'Food & Beverage',
                'phone': '+1234567891',
                'password': 'vendor123'
            },
            {
                'email': 'vendor2@example.com',
                'full_name': 'Sarah Johnson',
                'company_name': 'Artisan Crafts',
                'business_type': 'Handmade Crafts',
                'phone': '+1234567892',
                'password': 'vendor123'
            },
            {
                'email': 'vendor3@example.com',
                'full_name': 'Michael Chen',
                'company_name': 'Tech Gadgets Plus',
                'business_type': 'Electronics',
                'phone': '+1234567893',
                'password': 'vendor123'
            }
        ]
        
        vendor_objects = []
        for v_data in vendors:
            password = v_data.pop('password')
            vendor = User(**v_data, role='vendor')
            vendor.set_password(password)
            vendor_objects.append(vendor)
            db.session.add(vendor)
        
        db.session.commit()
        
        # Create sample events
        events = [
            {
                'name': 'Spring Food Festival 2026',
                'description': 'Annual spring food festival featuring local and international cuisine',
                'event_date': datetime(2026, 4, 15, 10, 0),
                'location': 'Central Park, New York',
                'venue': 'Great Lawn',
                'expected_attendees': 5000,
                'vendor_fee': 500.0,
                'status': 'upcoming'
            },
            {
                'name': 'Tech Expo 2026',
                'description': 'Latest technology innovations and gadgets showcase',
                'event_date': datetime(2026, 5, 20, 9, 0),
                'location': 'Convention Center, San Francisco',
                'venue': 'Hall A',
                'expected_attendees': 10000,
                'vendor_fee': 1000.0,
                'status': 'upcoming'
            },
            {
                'name': 'Summer Craft Fair',
                'description': 'Handmade crafts and artisan products',
                'event_date': datetime(2026, 6, 10, 11, 0),
                'location': 'Downtown Square, Portland',
                'venue': 'Main Plaza',
                'expected_attendees': 3000,
                'vendor_fee': 300.0,
                'status': 'upcoming'
            },
            {
                'name': 'Winter Music Festival 2025',
                'description': 'Music and entertainment festival',
                'event_date': datetime(2025, 12, 15, 18, 0),
                'location': 'Beach Park, Miami',
                'venue': 'Main Stage Area',
                'expected_attendees': 8000,
                'vendor_fee': 750.0,
                'status': 'completed'
            }
        ]
        
        event_objects = []
        for e_data in events:
            e_data['created_by_admin_id'] = admin.id
            event = Event(**e_data)
            event_objects.append(event)
            db.session.add(event)
        
        db.session.commit()
        
        # Create sample applications
        applications = [
            {
                'vendor_id': vendor_objects[0].id,
                'event_id': event_objects[0].id,
                'product_service': 'Gourmet burgers and craft beverages',
                'booth_requirements': 'Need 10x10 booth with electricity and water access',
                'status': 'approved',
                'reviewed_at': datetime.utcnow(),
                'reviewed_by': admin.id,
                'admin_notes': 'Excellent vendor with great reviews'
            },
            {
                'vendor_id': vendor_objects[1].id,
                'event_id': event_objects[2].id,
                'product_service': 'Handmade jewelry and pottery',
                'booth_requirements': 'Standard 8x8 booth',
                'status': 'pending'
            },
            {
                'vendor_id': vendor_objects[2].id,
                'event_id': event_objects[1].id,
                'product_service': 'Latest smartphones and accessories',
                'booth_requirements': 'Large booth with display cases and electricity',
                'status': 'approved',
                'reviewed_at': datetime.utcnow(),
                'reviewed_by': admin.id
            },
            {
                'vendor_id': vendor_objects[0].id,
                'event_id': event_objects[3].id,
                'product_service': 'Food and beverages',
                'booth_requirements': 'Standard booth',
                'status': 'approved',
                'reviewed_at': datetime(2025, 11, 1, 10, 0),
                'reviewed_by': admin.id
            }
        ]
        
        application_objects = []
        for a_data in applications:
            application = VendorApplication(**a_data)
            application_objects.append(application)
            db.session.add(application)
        
        db.session.commit()
        
        # Create sample payments
        payments = [
            {
                'application_id': application_objects[0].id,
                'vendor_id': vendor_objects[0].id,
                'amount': 500.0,
                'payment_method': 'credit_card',
                'transaction_id': 'TXN001234567',
                'status': 'completed',
                'payment_date': datetime(2026, 2, 1, 14, 30)
            },
            {
                'application_id': application_objects[2].id,
                'vendor_id': vendor_objects[2].id,
                'amount': 1000.0,
                'payment_method': 'bank_transfer',
                'status': 'pending'
            },
            {
                'application_id': application_objects[3].id,
                'vendor_id': vendor_objects[0].id,
                'amount': 750.0,
                'payment_method': 'credit_card',
                'transaction_id': 'TXN001234568',
                'status': 'completed',
                'payment_date': datetime(2025, 11, 15, 10, 0)
            }
        ]
        
        for p_data in payments:
            payment = Payment(**p_data)
            db.session.add(payment)
        
        db.session.commit()
        
        print("Database initialized successfully!")
        print("\nLogin credentials:")
        print("Admin: admin@eventflow.com / admin123")
        print("Vendor 1: vendor1@example.com / vendor123")
        print("Vendor 2: vendor2@example.com / vendor123")
        print("Vendor 3: vendor3@example.com / vendor123")

if __name__ == '__main__':
    config_name = os.environ.get('APP_CONFIG', 'development')
    app = create_app(config_name)
    
    # Initialize database
    init_db(app)
    
    # Run the application
    print("\nStarting EventFlow API server...")
    print(f"Using config: {config_name}")
    print("API available at: http://localhost:5000/api")
    app.run(debug=True, host='0.0.0.0', port=5000)
