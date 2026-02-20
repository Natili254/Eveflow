from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    """User model for both vendors and admins"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='vendor')  # 'vendor' or 'admin'
    phone = db.Column(db.String(20))
    company_name = db.Column(db.String(150))
    business_type = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    applications = db.relationship('VendorApplication', backref='vendor', lazy=True, cascade='all, delete-orphan', foreign_keys='VendorApplication.vendor_id')
    payments = db.relationship('Payment', backref='vendor', lazy=True, cascade='all, delete-orphan', foreign_keys='Payment.vendor_id')
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        """Convert user to dictionary"""
        return {
            'id': self.id,
            'email': self.email,
            'full_name': self.full_name,
            'role': self.role,
            'phone': self.phone,
            'company_name': self.company_name,
            'business_type': self.business_type,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'is_active': self.is_active
        }

class Event(db.Model):
    """Event model"""
    __tablename__ = 'events'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    event_date = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(200))
    venue = db.Column(db.String(200))
    expected_attendees = db.Column(db.Integer)
    vendor_fee = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='upcoming')  # 'upcoming', 'ongoing', 'completed', 'cancelled'
    created_by_admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_by_admin = db.relationship('User', foreign_keys=[created_by_admin_id], lazy='joined')
    default_currency = db.Column(db.String(10), default='USD')
    currency_options = db.Column(db.String(120), default='USD')  # comma-separated list, e.g. USD,KES
    mpesa_number = db.Column(db.String(40))
    paypal_account = db.Column(db.String(120))
    zelle_account = db.Column(db.String(120))
    card_instructions = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    applications = db.relationship('VendorApplication', backref='event', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        """Convert event to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'event_date': self.event_date.isoformat() if self.event_date else None,
            'location': self.location,
            'venue': self.venue,
            'expected_attendees': self.expected_attendees,
            'vendor_fee': self.vendor_fee,
            'status': self.status,
            'created_by_admin_id': self.created_by_admin_id,
            'admin_email': self.created_by_admin.email if self.created_by_admin else None,
            'default_currency': self.default_currency,
            'currency_options': self.currency_options,
            'mpesa_number': self.mpesa_number,
            'paypal_account': self.paypal_account,
            'zelle_account': self.zelle_account,
            'card_instructions': self.card_instructions,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class VendorApplication(db.Model):
    """Vendor application for events"""
    __tablename__ = 'vendor_applications'
    
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    
    # Application details
    product_service = db.Column(db.String(200), nullable=False)
    booth_requirements = db.Column(db.Text)
    additional_notes = db.Column(db.Text)
    
    # Status tracking
    status = db.Column(db.String(20), default='pending')  # 'pending', 'approved', 'rejected', 'withdrawn'
    admin_notes = db.Column(db.Text)
    reviewed_at = db.Column(db.DateTime)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Timestamps
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    payments = db.relationship('Payment', backref='application', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        """Convert application to dictionary"""
        return {
            'id': self.id,
            'vendor_id': self.vendor_id,
            'vendor_name': self.vendor.full_name if self.vendor else None,
            'vendor_company': self.vendor.company_name if self.vendor else None,
            'event_id': self.event_id,
            'event_name': self.event.name if self.event else None,
            'event_date': self.event.event_date.isoformat() if self.event and self.event.event_date else None,
            'product_service': self.product_service,
            'booth_requirements': self.booth_requirements,
            'additional_notes': self.additional_notes,
            'status': self.status,
            'admin_notes': self.admin_notes,
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
            'applied_at': self.applied_at.isoformat() if self.applied_at else None,
            'vendor_fee': self.event.vendor_fee if self.event else 0,
            'default_currency': self.event.default_currency if self.event else 'USD',
            'currency_options': self.event.currency_options if self.event else 'USD',
            'mpesa_number': self.event.mpesa_number if self.event else None,
            'paypal_account': self.event.paypal_account if self.event else None,
            'zelle_account': self.event.zelle_account if self.event else None,
            'card_instructions': self.event.card_instructions if self.event else None
        }

class Payment(db.Model):
    """Payment tracking for vendor applications"""
    __tablename__ = 'payments'
    
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('vendor_applications.id'), nullable=False)
    vendor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Payment details
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50))  # 'credit_card', 'bank_transfer', 'cash', etc.
    transaction_id = db.Column(db.String(100), unique=True)
    status = db.Column(db.String(20), default='pending')  # 'pending', 'completed', 'failed', 'refunded'
    currency = db.Column(db.String(10), default='USD')
    pay_to = db.Column(db.String(255))
    
    # Timestamps
    payment_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Notes
    notes = db.Column(db.Text)
    
    def to_dict(self):
        """Convert payment to dictionary"""
        return {
            'id': self.id,
            'application_id': self.application_id,
            'vendor_id': self.vendor_id,
            'vendor_name': self.vendor.full_name if self.vendor else None,
            'amount': self.amount,
            'payment_method': self.payment_method,
            'transaction_id': self.transaction_id,
            'status': self.status,
            'currency': self.currency,
            'pay_to': self.pay_to,
            'payment_date': self.payment_date.isoformat() if self.payment_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'notes': self.notes
        }
 
