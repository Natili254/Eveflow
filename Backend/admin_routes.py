from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, User, Event, VendorApplication, Payment
from datetime import datetime, timedelta
from sqlalchemy import func, and_, extract

admin_bp = Blueprint('admin', __name__)


def _current_user_id():
    try:
        return int(get_jwt_identity())
    except (TypeError, ValueError):
        return None


def check_admin():
    """Check if current user is admin"""
    current_user_id = _current_user_id()
    if current_user_id is None:
        return False
    user = User.query.get(current_user_id)
    return user and user.role == 'admin'


def get_current_admin_id():
    current_user_id = _current_user_id()
    if current_user_id is None:
        return None
    user = User.query.get(current_user_id)
    if not user or user.role != 'admin':
        return None
    return user.id


def normalize_currency_options(raw_options, default_currency='USD'):
    if not raw_options:
        return default_currency.upper()
    if isinstance(raw_options, list):
        values = raw_options
    else:
        values = str(raw_options).split(',')
    cleaned = []
    for value in values:
        code = str(value).strip().upper()
        if code in ('EURO', 'EUROS'):
            code = 'EUR'
        if code and code not in cleaned:
            cleaned.append(code)
    return ','.join(cleaned or [default_currency.upper()])

# ============= VENDOR MANAGEMENT =============
@admin_bp.route('/vendors', methods=['GET'])
@jwt_required()
def get_all_vendors():
    """Get all vendors"""
    try:
        if not check_admin():
            return jsonify({'error': 'Access denied'}), 403
        
        vendors = User.query.filter_by(role='vendor').order_by(User.created_at.desc()).all()
        return jsonify([vendor.to_dict() for vendor in vendors]), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/vendors/<int:vendor_id>', methods=['GET'])
@jwt_required()
def get_vendor_details(vendor_id):
    """Get detailed vendor information"""
    try:
        if not check_admin():
            return jsonify({'error': 'Access denied'}), 403
        
        vendor = User.query.get(vendor_id)
        if not vendor or vendor.role != 'vendor':
            return jsonify({'error': 'Vendor not found'}), 404
        
        # Get vendor's applications
        applications = VendorApplication.query.filter_by(vendor_id=vendor_id).all()
        
        # Get vendor's payments
        payments = Payment.query.filter_by(vendor_id=vendor_id).all()
        
        return jsonify({
            'vendor': vendor.to_dict(),
            'applications': [app.to_dict() for app in applications],
            'payments': [payment.to_dict() for payment in payments]
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/vendors/<int:vendor_id>/toggle-status', methods=['PUT'])
@jwt_required()
def toggle_vendor_status(vendor_id):
    """Activate or deactivate vendor account"""
    try:
        if not check_admin():
            return jsonify({'error': 'Access denied'}), 403
        
        vendor = User.query.get(vendor_id)
        if not vendor or vendor.role != 'vendor':
            return jsonify({'error': 'Vendor not found'}), 404
        
        vendor.is_active = not vendor.is_active
        vendor.updated_at = datetime.utcnow()
        db.session.commit()
        
        status = 'activated' if vendor.is_active else 'deactivated'
        return jsonify({
            'message': f'Vendor {status} successfully',
            'vendor': vendor.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# ============= APPLICATION MANAGEMENT =============
@admin_bp.route('/applications', methods=['GET'])
@jwt_required()
def get_all_applications():
    """Get all vendor applications with optional filtering"""
    try:
        if not check_admin():
            return jsonify({'error': 'Access denied'}), 403
        
        current_admin_id = get_current_admin_id()
        if current_admin_id is None:
            return jsonify({'error': 'Access denied'}), 403

        # Get query parameters
        status = request.args.get('status')
        event_id = request.args.get('event_id', type=int)
        
        query = VendorApplication.query.join(Event).filter(
            Event.created_by_admin_id == current_admin_id
        )
        
        if status:
            query = query.filter_by(status=status)
        if event_id:
            query = query.filter_by(event_id=event_id)
        
        applications = query.order_by(VendorApplication.applied_at.desc()).all()
        
        return jsonify([app.to_dict() for app in applications]), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/applications/<int:application_id>/review', methods=['PUT'])
@jwt_required()
def review_application(application_id):
    """Approve or reject an application"""
    try:
        if not check_admin():
            return jsonify({'error': 'Access denied'}), 403
        
        current_user_id = _current_user_id()
        if current_user_id is None:
            return jsonify({'error': 'Invalid token'}), 401
        
        application = VendorApplication.query.get(application_id)
        if not application:
            return jsonify({'error': 'Application not found'}), 404
        if not application.event or application.event.created_by_admin_id != current_user_id:
            return jsonify({'error': 'Access denied for this event'}), 403
        
        data = request.get_json()
        
        # Validate status
        if 'status' not in data or data['status'] not in ['approved', 'rejected']:
            return jsonify({'error': 'Invalid status. Must be approved or rejected'}), 400
        
        # Update application
        application.status = data['status']
        application.admin_notes = data.get('admin_notes')
        application.reviewed_at = datetime.utcnow()
        application.reviewed_by = current_user_id
        application.updated_at = datetime.utcnow()
        
        # If approved, create a payment record
        if data['status'] == 'approved' and application.event:
            existing_payment = Payment.query.filter_by(application_id=application.id).first()
            if not existing_payment:
                payment = Payment(
                    application_id=application.id,
                    vendor_id=application.vendor_id,
                    amount=application.event.vendor_fee,
                    status='pending'
                )
                db.session.add(payment)
        
        db.session.commit()
        
        return jsonify({
            'message': f'Application {data["status"]} successfully',
            'application': application.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# ============= EVENT MANAGEMENT =============
@admin_bp.route('/events', methods=['GET'])
@jwt_required()
def get_all_events():
    """Get all events"""
    try:
        if not check_admin():
            return jsonify({'error': 'Access denied'}), 403
        
        current_admin_id = get_current_admin_id()
        if current_admin_id is None:
            return jsonify({'error': 'Access denied'}), 403

        events = Event.query.filter_by(
            created_by_admin_id=current_admin_id
        ).order_by(Event.event_date.desc()).all()
        
        # Add application counts
        events_data = []
        for event in events:
            event_dict = event.to_dict()
            event_dict['application_count'] = VendorApplication.query.filter_by(event_id=event.id).count()
            event_dict['approved_vendors'] = VendorApplication.query.filter_by(
                event_id=event.id,
                status='approved'
            ).count()
            events_data.append(event_dict)
        
        return jsonify(events_data), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/events', methods=['POST'])
@jwt_required()
def create_event():
    """Create a new event"""
    try:
        if not check_admin():
            return jsonify({'error': 'Access denied'}), 403
        
        current_admin_id = get_current_admin_id()
        if current_admin_id is None:
            return jsonify({'error': 'Access denied'}), 403

        data = request.get_json()
        
        # Validate required fields
        required_fields = ['name', 'event_date']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Parse event date
        try:
            event_date = datetime.fromisoformat(data['event_date'].replace('Z', '+00:00'))
        except ValueError:
            return jsonify({'error': 'Invalid event_date format. Use ISO format'}), 400
        
        # Create event
        event = Event(
            name=data['name'],
            description=data.get('description'),
            event_date=event_date,
            location=data.get('location'),
            venue=data.get('venue'),
            expected_attendees=data.get('expected_attendees'),
            vendor_fee=data.get('vendor_fee', 0.0),
            status=data.get('status', 'upcoming'),
            created_by_admin_id=current_admin_id,
            default_currency=str(data.get('default_currency', 'USD')).upper(),
            currency_options=normalize_currency_options(
                data.get('currency_options'),
                data.get('default_currency', 'USD')
            ),
            mpesa_number=data.get('mpesa_number'),
            paypal_account=data.get('paypal_account'),
            zelle_account=data.get('zelle_account'),
            card_instructions=data.get('card_instructions')
        )

        allowed_currencies = [c.strip() for c in event.currency_options.split(',') if c.strip()]
        if event.default_currency not in allowed_currencies:
            return jsonify({'error': 'default_currency must be included in currency_options'}), 400
        
        db.session.add(event)
        db.session.commit()
        
        return jsonify({
            'message': 'Event created successfully',
            'event': event.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/events/<int:event_id>', methods=['PUT'])
@jwt_required()
def update_event(event_id):
    """Update an event"""
    try:
        if not check_admin():
            return jsonify({'error': 'Access denied'}), 403
        
        event = Event.query.get(event_id)
        if not event:
            return jsonify({'error': 'Event not found'}), 404
        current_admin_id = get_current_admin_id()
        if current_admin_id is None or event.created_by_admin_id != current_admin_id:
            return jsonify({'error': 'Access denied for this event'}), 403
        
        data = request.get_json()
        
        # Update allowed fields
        if 'name' in data:
            event.name = data['name']
        if 'description' in data:
            event.description = data['description']
        if 'event_date' in data:
            try:
                event.event_date = datetime.fromisoformat(data['event_date'].replace('Z', '+00:00'))
            except ValueError:
                return jsonify({'error': 'Invalid event_date format'}), 400
        if 'location' in data:
            event.location = data['location']
        if 'venue' in data:
            event.venue = data['venue']
        if 'expected_attendees' in data:
            event.expected_attendees = data['expected_attendees']
        if 'vendor_fee' in data:
            event.vendor_fee = data['vendor_fee']
        if 'status' in data:
            event.status = data['status']
        if 'default_currency' in data:
            event.default_currency = str(data['default_currency']).upper()
        if 'currency_options' in data:
            event.currency_options = normalize_currency_options(
                data['currency_options'],
                data.get('default_currency', event.default_currency)
            )
        if 'mpesa_number' in data:
            event.mpesa_number = data['mpesa_number']
        if 'paypal_account' in data:
            event.paypal_account = data['paypal_account']
        if 'zelle_account' in data:
            event.zelle_account = data['zelle_account']
        if 'card_instructions' in data:
            event.card_instructions = data['card_instructions']

        allowed_currencies = [c.strip() for c in (event.currency_options or '').split(',') if c.strip()]
        if not allowed_currencies:
            return jsonify({'error': 'currency_options cannot be empty'}), 400
        if (event.default_currency or '').upper() not in allowed_currencies:
            return jsonify({'error': 'default_currency must be included in currency_options'}), 400
        
        event.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Event updated successfully',
            'event': event.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/events/<int:event_id>', methods=['DELETE'])
@jwt_required()
def delete_event(event_id):
    """Delete an event"""
    try:
        if not check_admin():
            return jsonify({'error': 'Access denied'}), 403
        
        event = Event.query.get(event_id)
        if not event:
            return jsonify({'error': 'Event not found'}), 404
        current_admin_id = get_current_admin_id()
        if current_admin_id is None or event.created_by_admin_id != current_admin_id:
            return jsonify({'error': 'Access denied for this event'}), 403
        
        # Check if there are any applications
        app_count = VendorApplication.query.filter_by(event_id=event_id).count()
        if app_count > 0:
            return jsonify({
                'error': f'Cannot delete event with {app_count} applications. Cancel event instead.'
            }), 400
        
        db.session.delete(event)
        db.session.commit()
        
        return jsonify({'message': 'Event deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# ============= PAYMENT MANAGEMENT =============
@admin_bp.route('/payments', methods=['GET'])
@jwt_required()
def get_all_payments():
    """Get all payments"""
    try:
        if not check_admin():
            return jsonify({'error': 'Access denied'}), 403
        
        current_admin_id = get_current_admin_id()
        if current_admin_id is None:
            return jsonify({'error': 'Access denied'}), 403

        payments = Payment.query.join(VendorApplication).join(Event).filter(
            Event.created_by_admin_id == current_admin_id
        ).order_by(Payment.created_at.desc()).all()
        return jsonify([payment.to_dict() for payment in payments]), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/payments/<int:payment_id>/update-status', methods=['PUT'])
@jwt_required()
def update_payment_status(payment_id):
    """Update payment status"""
    try:
        if not check_admin():
            return jsonify({'error': 'Access denied'}), 403
        
        payment = Payment.query.get(payment_id)
        if not payment:
            return jsonify({'error': 'Payment not found'}), 404
        current_admin_id = get_current_admin_id()
        if current_admin_id is None:
            return jsonify({'error': 'Access denied'}), 403
        if not payment.application or not payment.application.event or payment.application.event.created_by_admin_id != current_admin_id:
            return jsonify({'error': 'Access denied for this event'}), 403
        
        data = request.get_json()
        
        if 'status' not in data:
            return jsonify({'error': 'Status is required'}), 400
        
        if data['status'] not in ['pending', 'completed', 'failed', 'refunded']:
            return jsonify({'error': 'Invalid status'}), 400
        
        payment.status = data['status']
        if data['status'] == 'completed' and not payment.payment_date:
            payment.payment_date = datetime.utcnow()
        
        if 'payment_method' in data:
            payment.payment_method = data['payment_method']
        if 'transaction_id' in data:
            payment.transaction_id = data['transaction_id']
        if 'notes' in data:
            payment.notes = data['notes']
        
        payment.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Payment status updated successfully',
            'payment': payment.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# ============= ANALYTICS & DASHBOARD =============
@admin_bp.route('/dashboard/stats', methods=['GET'])
@jwt_required()
def get_admin_dashboard_stats():
    """Get comprehensive dashboard statistics"""
    try:
        if not check_admin():
            return jsonify({'error': 'Access denied'}), 403
        
        current_admin_id = get_current_admin_id()
        if current_admin_id is None:
            return jsonify({'error': 'Access denied'}), 403

        owned_events_query = Event.query.filter_by(created_by_admin_id=current_admin_id)
        owned_event_ids = [e.id for e in owned_events_query.all()]

        owned_app_query = VendorApplication.query.filter(VendorApplication.event_id.in_(owned_event_ids)) if owned_event_ids else VendorApplication.query.filter(False)
        owned_apps = owned_app_query.all()
        owned_vendor_ids = {a.vendor_id for a in owned_apps}

        # Vendor stats
        total_vendors = User.query.filter(User.role == 'vendor', User.id.in_(owned_vendor_ids)).count() if owned_vendor_ids else 0
        active_vendors = User.query.filter(User.role == 'vendor', User.is_active == True, User.id.in_(owned_vendor_ids)).count() if owned_vendor_ids else 0
        
        # Application stats
        total_applications = owned_app_query.count()
        pending_applications = owned_app_query.filter_by(status='pending').count()
        approved_applications = owned_app_query.filter_by(status='approved').count()
        rejected_applications = owned_app_query.filter_by(status='rejected').count()
        
        # Event stats
        total_events = owned_events_query.count()
        upcoming_events = owned_events_query.filter(
            Event.status == 'upcoming',
            Event.event_date > datetime.utcnow()
        ).count()
        ongoing_events = owned_events_query.filter_by(status='ongoing').count()
        
        # Payment stats
        all_payments = Payment.query.join(VendorApplication).join(Event).filter(
            Event.created_by_admin_id == current_admin_id
        ).all()
        total_revenue = sum(p.amount for p in all_payments if p.status == 'completed')
        pending_revenue = sum(p.amount for p in all_payments if p.status == 'pending')
        
        # Recent activity (last 7 days)
        week_ago = datetime.utcnow() - timedelta(days=7)
        new_vendors_week = User.query.filter(
            User.role == 'vendor',
            User.created_at >= week_ago,
            User.id.in_(owned_vendor_ids)
        ).count() if owned_vendor_ids else 0
        new_applications_week = owned_app_query.filter(
            VendorApplication.applied_at >= week_ago
        ).count()
        
        return jsonify({
            'vendors': {
                'total': total_vendors,
                'active': active_vendors,
                'inactive': total_vendors - active_vendors,
                'new_this_week': new_vendors_week
            },
            'applications': {
                'total': total_applications,
                'pending': pending_applications,
                'approved': approved_applications,
                'rejected': rejected_applications,
                'new_this_week': new_applications_week
            },
            'events': {
                'total': total_events,
                'upcoming': upcoming_events,
                'ongoing': ongoing_events
            },
            'revenue': {
                'total': total_revenue,
                'pending': pending_revenue
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/analytics/applications-by-status', methods=['GET'])
@jwt_required()
def get_applications_by_status():
    """Get application count by status for charts"""
    try:
        if not check_admin():
            return jsonify({'error': 'Access denied'}), 403
        
        current_admin_id = get_current_admin_id()
        if current_admin_id is None:
            return jsonify({'error': 'Access denied'}), 403

        results = db.session.query(
            VendorApplication.status,
            func.count(VendorApplication.id)
        ).join(Event, VendorApplication.event_id == Event.id).filter(
            Event.created_by_admin_id == current_admin_id
        ).group_by(VendorApplication.status).all()
        
        data = [{'status': status, 'count': count} for status, count in results]
        return jsonify(data), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/analytics/applications-over-time', methods=['GET'])
@jwt_required()
def get_applications_over_time():
    """Get applications over time (last 6 months)"""
    try:
        if not check_admin():
            return jsonify({'error': 'Access denied'}), 403
        
        current_admin_id = get_current_admin_id()
        if current_admin_id is None:
            return jsonify({'error': 'Access denied'}), 403

        six_months_ago = datetime.utcnow() - timedelta(days=180)
        
        results = db.session.query(
            func.date_trunc('month', VendorApplication.applied_at).label('month'),
            func.count(VendorApplication.id)
        ).join(Event, VendorApplication.event_id == Event.id).filter(
            Event.created_by_admin_id == current_admin_id,
            VendorApplication.applied_at >= six_months_ago
        ).group_by('month').order_by('month').all()
        
        data = [{'month': month.strftime('%Y-%m'), 'count': count} for month, count in results]
        return jsonify(data), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/analytics/revenue-by-month', methods=['GET'])
@jwt_required()
def get_revenue_by_month():
    """Get revenue by month"""
    try:
        if not check_admin():
            return jsonify({'error': 'Access denied'}), 403
        
        current_admin_id = get_current_admin_id()
        if current_admin_id is None:
            return jsonify({'error': 'Access denied'}), 403

        six_months_ago = datetime.utcnow() - timedelta(days=180)
        
        results = db.session.query(
            func.date_trunc('month', Payment.payment_date).label('month'),
            func.sum(Payment.amount)
        ).join(VendorApplication, Payment.application_id == VendorApplication.id).join(
            Event, VendorApplication.event_id == Event.id
        ).filter(
            Event.created_by_admin_id == current_admin_id,
            Payment.status == 'completed',
            Payment.payment_date >= six_months_ago
        ).group_by('month').order_by('month').all()
        
        data = [{'month': month.strftime('%Y-%m') if month else 'Unknown', 'revenue': float(revenue or 0)} 
                for month, revenue in results]
        return jsonify(data), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
