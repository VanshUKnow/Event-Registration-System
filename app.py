from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)

# ============ DATABASE CONFIGURATION ============
# Update these with your MySQL credentials
MYSQL_USER = 'root'           # Your MySQL username
MYSQL_PASSWORD = 'root1234'   # Your MySQL password
MYSQL_HOST = 'localhost'      # MySQL server host
MYSQL_PORT = 3306            # MySQL server port
MYSQL_DB = 'event_registration'  # Database name

# SQLAlchemy configuration
app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ECHO'] = True  # Log all SQL queries (remove in production)

db = SQLAlchemy(app)

# ============ DATABASE MODELS ============

class Event(db.Model):
    """Event model for storing event information"""
    __tablename__ = 'events'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    date = db.Column(db.String(50), nullable=False)
    time = db.Column(db.String(50), nullable=False)
    location = db.Column(db.String(255), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # Relationship with registrations
    registrations = db.relationship('Registration', backref='event', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        """Convert event to dictionary"""
        registered_count = len(self.registrations)
        return {
            'id': self.id,
            'name': self.name,
            'date': self.date,
            'time': self.time,
            'location': self.location,
            'capacity': self.capacity,
            'description': self.description,
            'registered': registered_count,
            'available': self.capacity - registered_count,
            'is_full': registered_count >= self.capacity
        }


class Registration(db.Model):
    """Registration model for storing user registrations"""
    __tablename__ = 'registrations'
    
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    organization = db.Column(db.String(255), nullable=True)
    registered_at = db.Column(db.DateTime, default=datetime.now)
    
    # Unique constraint: one email per event
    __table_args__ = (db.UniqueConstraint('event_id', 'email', name='uq_event_email'),)
    
    def to_dict(self):
        """Convert registration to dictionary"""
        return {
            'id': self.id,
            'event_id': self.event_id,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'organization': self.organization,
            'registered_at': self.registered_at.strftime('%Y-%m-%d %H:%M:%S')
        }


# ============ ROUTES ============

@app.route('/')
def index():
    """Display all events"""
    try:
        events = Event.query.all()
        events_data = [event.to_dict() for event in events]
        return render_template('index.html', events=events_data)
    except Exception as e:
        print(f"Error in index route: {str(e)}")
        return render_template('index.html', events=[], error="Database connection error")


@app.route('/register/<int:event_id>', methods=['GET', 'POST'])
def register(event_id):
    """Registration form for an event"""
    try:
        event = Event.query.get_or_404(event_id)
        event_data = event.to_dict()
        
        if request.method == 'POST':
            # Get form data
            name = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip()
            phone = request.form.get('phone', '').strip()
            organization = request.form.get('organization', '').strip()
            
            # Validation
            errors = []
            if not name:
                errors.append('Name is required')
            if not email or '@' not in email:
                errors.append('Valid email is required')
            if not phone or len(phone) < 10:
                errors.append('Valid phone number is required')
            
            # Check capacity
            if event_data['is_full']:
                errors.append('This event is full. No more registrations available.')
            
            # Check if already registered
            existing = Registration.query.filter_by(event_id=event_id, email=email).first()
            if existing:
                errors.append('This email is already registered for this event')
            
            if errors:
                return render_template('registration.html', 
                                     event=event_data, 
                                     error=', '.join(errors),
                                     form_data=request.form)
            
            # Create and save registration
            try:
                registration = Registration(
                    event_id=event_id,
                    name=name,
                    email=email,
                    phone=phone,
                    organization=organization
                )
                db.session.add(registration)
                db.session.commit()
                
                return redirect(url_for('view_registration', registration_id=registration.id))
            except Exception as e:
                db.session.rollback()
                error_msg = f'Error saving registration: {str(e)}'
                return render_template('registration.html', 
                                     event=event_data, 
                                     error=error_msg,
                                     form_data=request.form)
        
        return render_template('registration.html', event=event_data, error=None)
        
    except Exception as e:
        print(f"Error in register route: {str(e)}")
        return redirect(url_for('index'))


@app.route('/view/<int:registration_id>')
def view_registration(registration_id):
    """View a specific registration confirmation"""
    try:
        registration = Registration.query.get_or_404(registration_id)
        event = Event.query.get(registration.event_id)
        
        return render_template('view.html', 
                             registration=registration.to_dict(), 
                             event=event.to_dict())
    except Exception as e:
        print(f"Error in view_registration route: {str(e)}")
        return redirect(url_for('index'))


@app.route('/edit/<int:registration_id>', methods=['GET', 'POST'])
def edit_registration(registration_id):
    """Edit a registration"""
    try:
        registration = Registration.query.get_or_404(registration_id)
        event = Event.query.get(registration.event_id)
        event_data = event.to_dict()
        reg_data = registration.to_dict()
        
        if request.method == 'POST':
            # Get form data
            name = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip()
            phone = request.form.get('phone', '').strip()
            organization = request.form.get('organization', '').strip()
            
            # Validation
            errors = []
            if not name:
                errors.append('Name is required')
            if not email or '@' not in email:
                errors.append('Valid email is required')
            if not phone or len(phone) < 10:
                errors.append('Valid phone number is required')
            
            # Check if email is already used by someone else for this event
            duplicate = Registration.query.filter(
                Registration.email == email,
                Registration.event_id == registration.event_id,
                Registration.id != registration_id
            ).first()
            
            if duplicate:
                errors.append('This email is already registered for this event')
            
            if errors:
                return render_template('edit.html', 
                                     registration=reg_data,
                                     event=event_data,
                                     error=', '.join(errors),
                                     form_data=request.form)
            
            # Update registration
            try:
                registration.name = name
                registration.email = email
                registration.phone = phone
                registration.organization = organization
                db.session.commit()
                
                return redirect(url_for('view_registration', registration_id=registration_id))
            except Exception as e:
                db.session.rollback()
                error_msg = f'Error updating registration: {str(e)}'
                return render_template('edit.html', 
                                     registration=reg_data,
                                     event=event_data,
                                     error=error_msg,
                                     form_data=request.form)
        
        return render_template('edit.html', 
                             registration=reg_data, 
                             event=event_data, 
                             error=None)
        
    except Exception as e:
        print(f"Error in edit_registration route: {str(e)}")
        return redirect(url_for('index'))


# ============ DATABASE INITIALIZATION ============

def init_db():
    """Initialize database with sample events"""
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Check if events already exist
        if Event.query.first() is None:
            # Sample events
            sample_events = [
                Event(
                    name='Python Workshop',
                    date='2026-02-20',
                    time='10:00 AM',
                    location='Tech Hub, Kalmeshwar',
                    capacity=50,
                    description='Learn advanced Python programming concepts'
                ),
                Event(
                    name='Web Development Bootcamp',
                    date='2026-02-28',
                    time='2:00 PM',
                    location='Innovation Center',
                    capacity=30,
                    description='Full-stack web development with Flask and React'
                ),
                Event(
                    name='AI/ML Masterclass',
                    date='2026-03-15',
                    time='11:00 AM',
                    location='Tech Hub, Kalmeshwar',
                    capacity=40,
                    description='Deep dive into machine learning and AI applications'
                )
            ]
            
            db.session.add_all(sample_events)
            db.session.commit()
            print("✅ Database initialized with sample events")
        else:
            print("✅ Database already has events")


if __name__ == '__main__':
    # Initialize database
    init_db()
    
    # Run the application
    app.run(debug=True)