from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, User, Event, VendorApplication, Payment
from datetime import datetime
from sqlalchemy import func, and_
from uuid import uuid4

vendor_bp = Blueprint('vendor', __name__)


def _current_user_id():
    try:
        return int(get_jwt_identity())
    except (TypeError, ValueError):
        return None


@vendor_bp.route('/events', methods=['GET'])
@jwt_required()
def get_available_events():
    """Get all available events for vendors to apply"""
    try:
        current_user_id = _current_user_id()
        if current_user_id is None:
            return jsonify({'error': 'Invalid token'}), 401
        user = User.query.get(current_user_id)
        
        if user.role != 'vendor':
            return jsonify({'error': 'Access denied'}), 403
        
        # Get upcoming and ongoing events
        events = Event.query.filter(
            Event.status.in_(['upcoming', 'ongoing'])
        ).order_by(Event.event_date.asc()).all()
        
        # Get user's applications
        user_applications = VendorApplication.query.filter_by(vendor_id=current_user_id).all()
        applied_event_ids = {app.event_id for app in user_applications}
        
        events_data = []
        for event in events:
            event_dict = event.to_dict()
            event_dict['has_applied'] = event.id in applied_event_ids
            events_data.append(event_dict)
        
        return jsonify(events_data), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@vendor_bp.route('/applications', methods=['GET'])
@jwt_required()
def get_vendor_applications():
    """Get all applications for current vendor"""
    try:
        current_user_id = _current_user_id()
        if current_user_id is None:
            return jsonify({'error': 'Invalid token'}), 401
        user = User.query.get(current_user_id)
        
        if user.role != 'vendor':
            return jsonify({'error': 'Access denied'}), 403
        
        applications = VendorApplication.query.filter_by(
            vendor_id=current_user_id
        ).order_by(VendorApplication.applied_at.desc()).all()
        
        return jsonify([app.to_dict() for app in applications]), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@vendor_bp.route('/applications', methods=['POST'])
@jwt_required()
def submit_application():
    """Submit a new vendor application"""
    try:
        current_user_id = _current_user_id()
        if current_user_id is None:
            return jsonify({'error': 'Invalid token'}), 401
        user = User.query.get(current_user_id)
        
        if user.role != 'vendor':
            return jsonify({'error': 'Access denied'}), 403
        
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['event_id', 'product_service']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Check if event exists
        event = Event.query.get(data['event_id'])
        if not event:
            return jsonify({'error': 'Event not found'}), 404
        
        # Check if already applied
        existing = VendorApplication.query.filter_by(
            vendor_id=current_user_id,
            event_id=data['event_id']
        ).first()
        
        if existing:
            return jsonify({'error': 'You have already applied to this event'}), 409
        
        # Create application
        application = VendorApplication(
            vendor_id=current_user_id,
            event_id=data['event_id'],
            product_service=data['product_service'],
            booth_requirements=data.get('booth_requirements'),
            additional_notes=data.get('additional_notes')
        )
        
        db.session.add(application)
        db.session.commit()
        
        return jsonify({
            'message': 'Application submitted successfully',
            'application': application.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@vendor_bp.route('/applications/<int:application_id>', methods=['PUT'])
@jwt_required()
def update_application(application_id):
    """Update a pending application"""
    try:
        current_user_id = _current_user_id()
        if current_user_id is None:
            return jsonify({'error': 'Invalid token'}), 401
        
        application = VendorApplication.query.get(application_id)
        if not application:
            return jsonify({'error': 'Application not found'}), 404
        
        # Check ownership
        if application.vendor_id != current_user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Can only update pending applications
        if application.status != 'pending':
            return jsonify({'error': f'Cannot update {application.status} application'}), 400
        
        data = request.get_json()
        
        # Update allowed fields
        if 'product_service' in data:
            application.product_service = data['product_service']
        if 'booth_requirements' in data:
            application.booth_requirements = data['booth_requirements']
        if 'additional_notes' in data:
            application.additional_notes = data['additional_notes']
        
        application.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Application updated successfully',
            'application': application.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@vendor_bp.route('/applications/<int:application_id>', methods=['DELETE'])
@jwt_required()
def withdraw_application(application_id):
    """Withdraw/delete an application"""
    try:
        current_user_id = _current_user_id()
        if current_user_id is None:
            return jsonify({'error': 'Invalid token'}), 401
        
        application = VendorApplication.query.get(application_id)
        if not application:
            return jsonify({'error': 'Application not found'}), 404
        
        # Check ownership
        if application.vendor_id != current_user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Can only withdraw pending applications
        if application.status != 'pending':
            return jsonify({'error': f'Cannot withdraw {application.status} application'}), 400
        
        application.status = 'withdrawn'
        application.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'message': 'Application withdrawn successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@vendor_bp.route('/dashboard/stats', methods=['GET'])
@jwt_required()
def get_dashboard_stats():
    """Get dashboard statistics for vendor"""
    try:
        current_user_id = _current_user_id()
        if current_user_id is None:
            return jsonify({'error': 'Invalid token'}), 401
        user = User.query.get(current_user_id)
        
        if user.role != 'vendor':
            return jsonify({'error': 'Access denied'}), 403
        
        # Total applications
        total_applications = VendorApplication.query.filter_by(
            vendor_id=current_user_id
        ).count()
        
        # Pending applications
        pending = VendorApplication.query.filter_by(
            vendor_id=current_user_id,
            status='pending'
        ).count()
        
        # Approved applications
        approved = VendorApplication.query.filter_by(
            vendor_id=current_user_id,
            status='approved'
        ).count()
        
        # Rejected applications
        rejected = VendorApplication.query.filter_by(
            vendor_id=current_user_id,
            status='rejected'
        ).count()
        
        # Total payments and pending payments
        payments = Payment.query.filter_by(vendor_id=current_user_id).all()
        total_paid = sum(p.amount for p in payments if p.status == 'completed')
        pending_payments = sum(p.amount for p in payments if p.status == 'pending')
        
        # Upcoming events (approved applications)
        upcoming_events = VendorApplication.query.join(Event).filter(
            VendorApplication.vendor_id == current_user_id,
            VendorApplication.status == 'approved',
            Event.event_date > datetime.utcnow()
        ).count()
        
        return jsonify({
            'total_applications': total_applications,
            'pending': pending,
            'approved': approved,
            'rejected': rejected,
            'total_paid': total_paid,
            'pending_payments': pending_payments,
            'upcoming_events': upcoming_events
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@vendor_bp.route('/payments', methods=['GET'])
@jwt_required()
def get_vendor_payments():
    """Get all payments for current vendor"""
    try:
        current_user_id = _current_user_id()
        if current_user_id is None:
            return jsonify({'error': 'Invalid token'}), 401
        user = User.query.get(current_user_id)
        
        if user.role != 'vendor':
            return jsonify({'error': 'Access denied'}), 403
        
        payments = Payment.query.filter_by(
            vendor_id=current_user_id
        ).order_by(Payment.created_at.desc()).all()
        
        return jsonify([payment.to_dict() for payment in payments]), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@vendor_bp.route('/payments/<int:payment_id>/pay', methods=['PUT'])
@jwt_required()
def pay_for_approved_application(payment_id):
    """Pay vendor fee for an approved application"""
    try:
        current_user_id = _current_user_id()
        if current_user_id is None:
            return jsonify({'error': 'Invalid token'}), 401

        user = User.query.get(current_user_id)
        if not user or user.role != 'vendor':
            return jsonify({'error': 'Access denied'}), 403

        payment = Payment.query.get(payment_id)
        if not payment:
            return jsonify({'error': 'Payment not found'}), 404

        if payment.vendor_id != current_user_id:
            return jsonify({'error': 'Access denied'}), 403

        application = VendorApplication.query.get(payment.application_id)
        if not application or application.status != 'approved':
            return jsonify({'error': 'Payment only allowed for approved applications'}), 400

        if payment.status == 'completed':
            return jsonify({'error': 'Payment already completed'}), 409

        data = request.get_json() or {}
        method = (data.get('payment_method') or '').strip().lower()
        allowed_methods = {'zelle', 'paypal', 'mpesa', 'card'}
        currency = str(data.get('currency') or (application.event.default_currency if application.event else 'USD')).upper()

        if method not in allowed_methods:
            return jsonify({
                'error': 'Invalid payment method. Use one of: zelle, paypal, mpesa, card'
            }), 400

        event = application.event
        if not event:
            return jsonify({'error': 'Related event not found'}), 404

        allowed_currencies = [c.strip().upper() for c in (event.currency_options or 'USD').split(',') if c.strip()]
        if currency not in allowed_currencies:
            return jsonify({'error': f'Currency not allowed. Choose one of: {", ".join(allowed_currencies)}'}), 400

        pay_to = None
        if method == 'mpesa':
            pay_to = event.mpesa_number
            if not pay_to:
                return jsonify({'error': 'Mpesa number is not configured for this event'}), 400
        elif method == 'paypal':
            pay_to = event.paypal_account
            if not pay_to:
                return jsonify({'error': 'PayPal account is not configured for this event'}), 400
        elif method == 'zelle':
            pay_to = event.zelle_account
            if not pay_to:
                return jsonify({'error': 'Zelle account is not configured for this event'}), 400
        elif method == 'card':
            pay_to = event.card_instructions or 'Card payment accepted by admin'

        payment.payment_method = method
        payment.transaction_id = data.get('transaction_id') or f"TXN-{uuid4().hex[:12].upper()}"
        payment.notes = data.get('notes')
        payment.currency = currency
        payment.pay_to = pay_to
        payment.status = 'completed'
        payment.payment_date = datetime.utcnow()
        payment.updated_at = datetime.utcnow()
        db.session.commit()

        return jsonify({
            'message': 'Payment completed successfully',
            'payment': payment.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
