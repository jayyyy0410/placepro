from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
 
db = SQLAlchemy()
from flask_login import UserMixin
 
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Student(db.Model):
    id              = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    full_name       = db.Column(db.String(100))
    phone           = db.Column(db.String(20))
    department      = db.Column(db.String(100))
    cgpa            = db.Column(db.Float)
    skills          = db.Column(db.Text)   # comma-separated skills
    resume_filename = db.Column(db.String(200))
    is_blacklisted  = db.Column(db.Boolean, default=False)
    # ── Profile Enhancements ──
    graduation_year = db.Column(db.Integer)
    about           = db.Column(db.Text)
    linkedin        = db.Column(db.String(200))
    github          = db.Column(db.String(200))
    portfolio_url   = db.Column(db.String(200))
    user            = db.relationship('User', backref='student_profile')


class Company(db.Model):
    id              = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    company_name    = db.Column(db.String(100), nullable=False)
    industry        = db.Column(db.String(100))
    hr_contact      = db.Column(db.String(100))
    website         = db.Column(db.String(200))
    approval_status = db.Column(db.String(20), default='Pending')
    is_blacklisted  = db.Column(db.Boolean, default=False)
    user            = db.relationship('User', backref='company_profile')

class PlacementDrive(db.Model):
    id                   = db.Column(db.Integer, primary_key=True)
    company_id           = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    job_title            = db.Column(db.String(100), nullable=False)
    job_description      = db.Column(db.Text)
    eligibility_criteria = db.Column(db.Text)
    required_skills      = db.Column(db.String(200))
    experience_required  = db.Column(db.String(100))
    salary_range         = db.Column(db.String(100))
    deadline             = db.Column(db.DateTime)
    status               = db.Column(db.String(20), default='Pending')
    created_at           = db.Column(db.DateTime, default=datetime.utcnow)
    company              = db.relationship('Company', backref='drives')

class Application(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    drive_id   = db.Column(db.Integer, db.ForeignKey('placement_drive.id'), nullable=False)
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)
    status     = db.Column(db.String(20), default='Applied')
    student    = db.relationship('Student', backref='applications')
    drive      = db.relationship('PlacementDrive', backref='applications')

