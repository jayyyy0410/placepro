from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from config import Config
from models import db, User, Student, Company, PlacementDrive, Application
from functools import wraps
import os
from resume_parser import parse_resume
from utils import (
    compute_match_score, compute_skills_gap, compute_resume_quality,
    compute_profile_completeness, get_recommendations,
    compute_student_progress, drives_approaching_deadline, days_until,
    score_label, score_color, quality_label
)

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Admin access only.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def company_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'company':
            flash('Company access only.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def student_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'student':
            flash('Student access only.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# Admin seed
def seed_admin():
    if not User.query.filter_by(role='admin').first():
        admin = User(
            username='admin',
            email='admin@portal.com',
            password=generate_password_hash('admin123'),
            role='admin'
        )
        db.session.add(admin)
        db.session.commit()
        print('Admin seeded: admin@portal.com / admin123')

with app.app_context():
    db.create_all()
    seed_admin()

    # ── Safe column migrations for SQLite ────────────────────────────────────
    # db.create_all() does NOT alter existing tables; we must use ALTER TABLE.
    # Each statement is wrapped in try/except so re-running is harmless.
    _new_cols = [
        ("student", "graduation_year", "INTEGER"),
        ("student", "about",           "TEXT"),
        ("student", "linkedin",        "VARCHAR(200)"),
        ("student", "github",          "VARCHAR(200)"),
        ("student", "portfolio_url",   "VARCHAR(200)"),
    ]
    with db.engine.connect() as _conn:
        for _table, _col, _type in _new_cols:
            try:
                _conn.execute(db.text(f"ALTER TABLE {_table} ADD COLUMN {_col} {_type}"))
                _conn.commit()
                print(f"[migrate] Added column: {_table}.{_col}")
            except Exception:
                pass   # column already exists — safe to ignore


@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form.get('email')
        password = request.form.get('password')
        user     = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.password, password):
            flash('Invalid email or password.', 'danger')
            return redirect(url_for('login'))

        if not user.is_active:
            flash('Your account has been deactivated or blacklisted.', 'danger')
            return redirect(url_for('login'))

        login_user(user)
        if user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif user.role == 'company':
            return redirect(url_for('company_dashboard'))
        else:
            return redirect(url_for('student_dashboard'))

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/register/student', methods=['GET', 'POST'])
def register_student():
    if request.method == 'POST':
        email    = request.form.get('email')
        username = request.form.get('username')

     
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            if not existing_user.is_active:
                flash('This email has been blacklisted and cannot register again.', 'danger')
            else:
                flash('Email already registered.', 'danger')
            return redirect(url_for('register_student'))

       
        if User.query.filter_by(username=username).first():
            flash('Username already taken.', 'danger')
            return redirect(url_for('register_student'))

        user = User(username=username, email=email,
                    password=generate_password_hash(request.form.get('password')),
                    role='student')
        db.session.add(user)
        db.session.flush()

        resume_filename = None
        if 'resume' in request.files:
            file = request.files['resume']
            if file.filename != '':
                resume_filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], resume_filename))

        student = Student(
            user_id=user.id,
            full_name=request.form.get('full_name'),
            phone=request.form.get('phone'),
            department=request.form.get('department'),
            cgpa=float(request.form.get('cgpa') or 0),
            skills=request.form.get('skills'),
            resume_filename=resume_filename
        )
        db.session.add(student)
        db.session.commit()
        flash('Registered successfully! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register_student.html')

@app.route('/register/company', methods=['GET', 'POST'])
def register_company():
    if request.method == 'POST':
        email    = request.form.get('email')
        username = request.form.get('username')

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            if not existing_user.is_active:
                flash('This email has been blacklisted and cannot register again.', 'danger')
            else:
                flash('Email already registered.', 'danger')
            return redirect(url_for('register_company'))

        
        if User.query.filter_by(username=username).first():
            flash('Username already taken.', 'danger')
            return redirect(url_for('register_company'))

        user = User(username=username, email=email,
                    password=generate_password_hash(request.form.get('password')),
                    role='company')
        db.session.add(user)
        db.session.flush()

        company = Company(
            user_id=user.id,
            company_name=request.form.get('company_name'),
            industry=request.form.get('industry'),
            hr_contact=request.form.get('hr_contact'),
            website=request.form.get('website')
        )
        db.session.add(company)
        db.session.commit()
        flash('Registration submitted! Awaiting admin approval.', 'info')
        return redirect(url_for('login'))
    return render_template('register_company.html')

@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    pending_companies = Company.query.filter_by(approval_status='Pending').count()
    pending_drives    = PlacementDrive.query.filter_by(status='Pending').count()
    return render_template('admin/dashboard.html',
        students=Student.query.count(),
        companies=Company.query.count(),
        drives=PlacementDrive.query.count(),
        applications=Application.query.count(),
        pending_companies=pending_companies,
        pending_drives=pending_drives)

@app.route('/admin/companies')
@login_required
@admin_required
def admin_companies():
    search = request.args.get('search', '')
    if search:
        companies = Company.query.filter(
            (Company.company_name.ilike(f'%{search}%')) |
            (Company.industry.ilike(f'%{search}%'))
        ).all()
    else:
        companies = Company.query.all()
    return render_template('admin/companies.html', companies=companies, search=search)

@app.route('/admin/approve_company/<int:id>')
@login_required
@admin_required
def approve_company(id):
    c = Company.query.get_or_404(id)
    c.approval_status = 'Approved'
    db.session.commit()
    flash('Company approved.', 'success')
    return redirect(url_for('admin_companies'))

@app.route('/admin/reject_company/<int:id>')
@login_required
@admin_required
def reject_company(id):
    c = Company.query.get_or_404(id)
    c.approval_status = 'Rejected'
    db.session.commit()
    flash('Company rejected.', 'warning')
    return redirect(url_for('admin_companies'))

@app.route('/admin/blacklist_company/<int:id>')
@login_required
@admin_required
def blacklist_company(id):
    c = Company.query.get_or_404(id)
    c.is_blacklisted  = True
    c.user.is_active  = False
    db.session.commit()
    flash('Company blacklisted.', 'danger')
    return redirect(url_for('admin_companies'))

@app.route('/admin/unblacklist_company/<int:id>')
@login_required
@admin_required
def unblacklist_company(id):
    c = Company.query.get_or_404(id)
    c.is_blacklisted  = False
    c.user.is_active  = True
    db.session.commit()
    flash('Company unblacklisted.', 'success')
    return redirect(url_for('admin_companies'))

@app.route('/admin/company/<int:id>/profile')
@login_required
@admin_required
def admin_view_company(id):
    company = Company.query.get_or_404(id)
    return render_template('admin/company_profile.html', company=company)

@app.route('/admin/students')
@login_required
@admin_required
def admin_students():
    search = request.args.get('search', '')
    if search:
        students = Student.query.join(User).filter(
            (User.username.ilike(f'%{search}%')) |
            (Student.full_name.ilike(f'%{search}%')) |
            (User.email.ilike(f'%{search}%'))
        ).all()
    else:
        students = Student.query.all()
    return render_template('admin/students.html', students=students, search=search)

@app.route('/admin/blacklist_student/<int:id>')
@login_required
@admin_required
def blacklist_student(id):
    s = Student.query.get_or_404(id)
    s.is_blacklisted  = True
    s.user.is_active  = False
    db.session.commit()
    flash('Student blacklisted.', 'danger')
    return redirect(url_for('admin_students'))

@app.route('/admin/unblacklist_student/<int:id>')
@login_required
@admin_required
def unblacklist_student(id):
    s = Student.query.get_or_404(id)
    s.is_blacklisted  = False
    s.user.is_active  = True
    db.session.commit()
    flash('Student unblacklisted.', 'success')
    return redirect(url_for('admin_students'))

@app.route('/admin/student/<int:id>/profile')
@login_required
@admin_required
def admin_view_student(id):
    student = Student.query.get_or_404(id)
    return render_template('admin/student_profile.html', student=student)

@app.route('/admin/drives')
@login_required
@admin_required
def admin_drives():
    return render_template('admin/drives.html', drives=PlacementDrive.query.all())

@app.route('/admin/approve_drive/<int:id>')
@login_required
@admin_required
def approve_drive(id):
    d = PlacementDrive.query.get_or_404(id)
    d.status = 'Approved'
    db.session.commit()
    flash('Drive approved.', 'success')
    return redirect(url_for('admin_drives'))

@app.route('/admin/reject_drive/<int:id>')
@login_required
@admin_required
def reject_drive(id):
    d = PlacementDrive.query.get_or_404(id)
    d.status = 'Rejected'
    db.session.commit()
    flash('Drive rejected.', 'warning')
    return redirect(url_for('admin_drives'))

@app.route('/admin/applications')
@login_required
@admin_required
def admin_applications():
    return render_template('admin/all_applications.html',
        applications=Application.query.all())

@app.route('/company/dashboard')
@login_required
@company_required
def company_dashboard():
    company = Company.query.filter_by(user_id=current_user.id).first()
    drives  = PlacementDrive.query.filter_by(company_id=company.id).all()
    return render_template('company/dashboard.html', company=company, drives=drives)

@app.route('/company/drive/create', methods=['GET', 'POST'])
@login_required
@company_required
def create_drive():
    company = Company.query.filter_by(user_id=current_user.id).first()
    if company.approval_status != 'Approved':
        flash('You must be approved by admin to create drives.', 'warning')
        return redirect(url_for('company_dashboard'))
    if request.method == 'POST':
        from datetime import datetime as dt
        ds    = request.form.get('deadline')
        drive = PlacementDrive(
            company_id=company.id,
            job_title=request.form.get('job_title'),
            job_description=request.form.get('job_description'),
            eligibility_criteria=request.form.get('eligibility_criteria'),
            required_skills=request.form.get('required_skills'),
            experience_required=request.form.get('experience_required'),
            salary_range=request.form.get('salary_range'),
            deadline=dt.strptime(ds, '%Y-%m-%d') if ds else None
        )
        db.session.add(drive)
        db.session.commit()
        flash('Drive submitted for admin approval.', 'success')
        return redirect(url_for('company_dashboard'))
    return render_template('company/drive_form.html')

@app.route('/company/drive/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@company_required
def edit_drive(id):
    drive = PlacementDrive.query.get_or_404(id)
    if drive.status != 'Pending':
        flash('You can only edit drives that are still pending approval.', 'warning')
        return redirect(url_for('company_dashboard'))
    if request.method == 'POST':
        from datetime import datetime as dt
        ds = request.form.get('deadline')
        drive.job_title            = request.form.get('job_title')
        drive.job_description      = request.form.get('job_description')
        drive.eligibility_criteria = request.form.get('eligibility_criteria')
        drive.required_skills      = request.form.get('required_skills')
        drive.experience_required  = request.form.get('experience_required')
        drive.salary_range         = request.form.get('salary_range')
        drive.deadline             = dt.strptime(ds, '%Y-%m-%d') if ds else None
        db.session.commit()
        flash('Drive updated successfully.', 'success')
        return redirect(url_for('company_dashboard'))
    return render_template('company/edit_drive.html', drive=drive)

@app.route('/company/drive/close/<int:id>')
@login_required
@company_required
def close_drive(id):
    drive        = PlacementDrive.query.get_or_404(id)
    drive.status = 'Closed'
    db.session.commit()
    flash('Drive closed.', 'info')
    return redirect(url_for('company_dashboard'))

@app.route('/company/drive/delete/<int:id>')
@login_required
@company_required
def delete_drive(id):
    drive = PlacementDrive.query.get_or_404(id)
    db.session.delete(drive)
    db.session.commit()
    flash('Drive deleted.', 'success')
    return redirect(url_for('company_dashboard'))

@app.route('/company/drive/<int:id>')
@login_required
@company_required
def drive_detail_company(id):
    drive = PlacementDrive.query.get_or_404(id)
    return render_template('company/drive_detail.html', drive=drive)

@app.route('/company/drive/<int:id>/applicants')
@login_required
@company_required
def view_applicants(id):
    drive = PlacementDrive.query.get_or_404(id)
    apps  = Application.query.filter_by(drive_id=id).all()
    return render_template('company/applicants.html', drive=drive, applications=apps)

@app.route('/company/student/<int:student_id>/profile')
@login_required
@company_required
def view_student_profile(student_id):
    student = Student.query.get_or_404(student_id)
    return render_template('company/student_profile.html', student=student)

@app.route('/company/application/<int:id>/status', methods=['POST'])
@login_required
@company_required
def update_status(id):
    application        = Application.query.get_or_404(id)
    application.status = request.form.get('status')
    db.session.commit()
    flash('Status updated.', 'success')
    return redirect(request.referrer or url_for('company_dashboard'))

@app.route('/student/dashboard')
@login_required
@student_required
def student_dashboard():
    student = Student.query.filter_by(user_id=current_user.id).first()
    search       = request.args.get('search', '')
    only_eligible = request.args.get('eligible') == '1'

    all_approved = PlacementDrive.query.filter_by(status='Approved').all()

    if search:
        sl = search.lower()
        drives = [
            d for d in all_approved
            if sl in (d.job_title or '').lower()
            or sl in (d.required_skills or '').lower()
            or sl in (d.company.company_name or '').lower()
        ]
    else:
        drives = all_approved

    # CGPA eligibility filter
    if only_eligible and student.cgpa:
        import re as _re
        def _eligible(drive):
            m = _re.search(r'(\d+\.?\d*)', drive.eligibility_criteria or '')
            return student.cgpa >= float(m.group(1)) if m else True
        drives = [d for d in drives if _eligible(d)]

    my_apps     = Application.query.filter_by(student_id=student.id).all()
    applied_ids = [a.drive_id for a in my_apps]

    # Compute match scores for every drive
    match_scores = {d.id: compute_match_score(student, d)[0] for d in drives}

    # Sort drives by match score descending
    drives.sort(key=lambda d: -match_scores[d.id])

    # Deadline alerts (next 5 days, unapplied)
    unapplied_drives = [d for d in all_approved if d.id not in applied_ids]
    deadline_alerts  = drives_approaching_deadline(unapplied_drives, days=5)

    # Top-3 recommendations
    recommendations = get_recommendations(student, all_approved, applied_ids, top_n=3)

    completeness = compute_profile_completeness(student)

    return render_template('student/dashboard.html',
        student=student, drives=drives,
        my_apps=my_apps, applied_ids=applied_ids, search=search,
        match_scores=match_scores, score_label=score_label, score_color=score_color,
        recommendations=recommendations, deadline_alerts=deadline_alerts,
        completeness=completeness, only_eligible=only_eligible,
        days_until=days_until)

@app.route('/student/apply/<int:drive_id>')
@login_required
@student_required
def apply_drive(drive_id):
    student  = Student.query.filter_by(user_id=current_user.id).first()
    existing = Application.query.filter_by(
        student_id=student.id, drive_id=drive_id).first()
    if existing:
        flash('You have already applied for this drive.', 'warning')
        return redirect(url_for('student_dashboard'))
    db.session.add(Application(student_id=student.id, drive_id=drive_id))
    db.session.commit()
    flash('Application submitted successfully!', 'success')
    return redirect(url_for('student_dashboard'))

@app.route('/student/withdraw/<int:application_id>')
@login_required
@student_required
def withdraw_application(application_id):
    application = Application.query.get_or_404(application_id)
    student     = Student.query.filter_by(user_id=current_user.id).first()
    if application.student_id != student.id:
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('student_dashboard'))
    if application.status != 'Applied':
        flash('You can only withdraw applications that are still pending.', 'warning')
        return redirect(url_for('student_history'))
    db.session.delete(application)
    db.session.commit()
    flash('Application withdrawn successfully.', 'success')
    return redirect(url_for('student_history'))

@app.route('/student/drive/<int:drive_id>')
@login_required
@student_required
def drive_detail_student(drive_id):
    drive   = PlacementDrive.query.get_or_404(drive_id)
    student = Student.query.filter_by(user_id=current_user.id).first()
    matching, missing = compute_skills_gap(student, drive)
    score, breakdown  = compute_match_score(student, drive)
    already_applied   = Application.query.filter_by(
        student_id=student.id, drive_id=drive_id).first() is not None
    return render_template('student/drive_detail.html',
        drive=drive, matching=matching, missing=missing,
        score=score, breakdown=breakdown,
        score_label=score_label(score), score_color=score_color(score),
        already_applied=already_applied)

@app.route('/student/profile', methods=['GET', 'POST'])
@login_required
@student_required
def student_profile():
    student = Student.query.filter_by(user_id=current_user.id).first()
    if request.method == 'POST':
        student.full_name       = request.form.get('full_name')
        student.phone           = request.form.get('phone')
        student.department      = request.form.get('department')
        student.cgpa            = float(request.form.get('cgpa') or 0) or None
        student.skills          = request.form.get('skills')
        student.about           = request.form.get('about')
        student.linkedin        = request.form.get('linkedin')
        student.github          = request.form.get('github')
        student.portfolio_url   = request.form.get('portfolio_url')
        gy = request.form.get('graduation_year')
        student.graduation_year = int(gy) if gy and gy.isdigit() else None
        if 'resume' in request.files:
            file = request.files['resume']
            if file.filename != '':
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                student.resume_filename = filename
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('student_profile'))
    quality_score, quality_tips = compute_resume_quality(student)
    qlabel, qcolor = quality_label(quality_score)
    completeness    = compute_profile_completeness(student)
    is_placed       = any(a.status in ('Selected', 'Placed') for a in student.applications)
    return render_template('student/profile.html',
        student=student,
        quality_score=quality_score, quality_tips=quality_tips,
        qlabel=qlabel, qcolor=qcolor,
        completeness=completeness, is_placed=is_placed)

@app.route('/student/history')
@login_required
@student_required
def student_history():
    student  = Student.query.filter_by(user_id=current_user.id).first()
    apps     = Application.query.filter_by(student_id=student.id).all()
    progress = compute_student_progress(apps)
    return render_template('student/history.html', applications=apps, progress=progress)


@app.route('/student/progress')
@login_required
@student_required
def student_progress():
    student  = Student.query.filter_by(user_id=current_user.id).first()
    apps     = Application.query.filter_by(student_id=student.id).all()
    progress = compute_student_progress(apps)
    quality_score, quality_tips = compute_resume_quality(student)
    qlabel, qcolor = quality_label(quality_score)
    completeness   = compute_profile_completeness(student)
    score_breakdown = None
    # best scored application for breakdown example
    all_drives = PlacementDrive.query.filter_by(status='Approved').all()
    applied_ids = [a.drive_id for a in apps]
    recs = get_recommendations(student, all_drives, applied_ids, top_n=5)
    return render_template('student/progress.html',
        student=student, progress=progress, apps=apps,
        quality_score=quality_score, quality_tips=quality_tips,
        qlabel=qlabel, qcolor=qcolor,
        completeness=completeness, recommendations=recs,
        score_label=score_label, score_color=score_color)


@app.route('/student/calendar')
@login_required
@student_required
def student_calendar():
    student     = Student.query.filter_by(user_id=current_user.id).first()
    my_apps     = Application.query.filter_by(student_id=student.id).all()
    applied_ids = {a.drive_id for a in my_apps}
    all_drives  = PlacementDrive.query.filter_by(status='Approved').all()
    # drives with deadlines, sorted soonest first
    drives_with_dl = sorted(
        [d for d in all_drives if d.deadline],
        key=lambda d: d.deadline
    )
    return render_template('student/calendar.html',
        drives=drives_with_dl, applied_ids=applied_ids,
        days_until=days_until, student=student)


@app.route('/admin/leaderboard')
@login_required
@admin_required
def admin_leaderboard():
    students = Student.query.all()
    # Rank by: placed first, then CGPA desc, then skill count desc
    def rank_key(s):
        is_placed = any(a.status in ('Selected', 'Placed') for a in s.applications)
        cgpa      = s.cgpa or 0
        skills    = len([x for x in (s.skills or '').split(',') if x.strip()])
        return (not is_placed, -cgpa, -skills)
    students_ranked = sorted(students, key=rank_key)
    return render_template('admin/leaderboard.html', students=students_ranked,
        compute_profile_completeness=compute_profile_completeness)


@app.route('/admin/charts')
@login_required
@admin_required
def admin_charts():
    # Application status distribution
    statuses = ['Applied', 'Shortlisted', 'Interview', 'Selected', 'Rejected', 'Placed']
    status_counts = [Application.query.filter_by(status=s).count() for s in statuses]

    # Drives per company
    companies = Company.query.filter_by(approval_status='Approved').all()
    company_names = [c.company_name for c in companies]
    drive_counts = [len(c.drives) for c in companies]

    return render_template('admin/charts.html',
        statuses=statuses,
        status_counts=status_counts,
        company_names=company_names,
        drive_counts=drive_counts,
        total_students=Student.query.count(),
        total_companies=Company.query.count(),
        total_drives=PlacementDrive.query.count(),
        total_applications=Application.query.count()
    )

# ── Resume Parser API ────────────────────────────────────────────────────────
@app.route('/student/parse-resume', methods=['POST'])
@login_required
@student_required
def parse_resume_api():
    """
    Accepts a PDF file upload or uses the student's existing resume.
    Returns JSON with extracted fields.
    """
    student = Student.query.filter_by(user_id=current_user.id).first()

    # 1. Use freshly uploaded file if provided
    if 'resume' in request.files and request.files['resume'].filename != '':
        file = request.files['resume']
        filename = secure_filename(file.filename)
        if not filename.lower().endswith('.pdf'):
            return jsonify({'error': 'Only PDF files are supported.'}), 400
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(save_path)
        # Also persist the filename on the student record
        student.resume_filename = filename
        db.session.commit()

    # 2. Fall back to existing resume on disk
    elif student.resume_filename:
        filename = student.resume_filename
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if not os.path.exists(save_path):
            return jsonify({'error': 'Resume file not found on server.'}), 404
    else:
        return jsonify({'error': 'No resume uploaded yet. Please upload a PDF first.'}), 400

    result = parse_resume(save_path)
    # Pre-join skills list as comma string for easy form filling
    result['skills_str'] = ', '.join(result.get('skills', []))
    return jsonify(result)


# ── Placement Heatmap ────────────────────────────────────────────────────────
@app.route('/admin/heatmap')
@login_required
@admin_required
def admin_heatmap():
    # Pull every application joined with student dept and company name
    rows = (
        db.session.query(
            Student.department,
            Company.company_name,
            Application.status
        )
        .join(Application, Application.student_id == Student.id)
        .join(PlacementDrive, PlacementDrive.id == Application.drive_id)
        .join(Company, Company.id == PlacementDrive.company_id)
        .filter(Student.department.isnot(None))
        .all()
    )

    # Unique sorted axes (skip blank departments)
    departments = sorted({r.department for r in rows if r.department and r.department.strip()})
    companies   = sorted({r.company_name for r in rows})

    # Build two matrices: all applications + placements-only
    apps_matrix   = {d: {c: 0 for c in companies} for d in departments}
    placed_matrix = {d: {c: 0 for c in companies} for d in departments}

    for r in rows:
        if not r.department or not r.department.strip():
            continue
        apps_matrix[r.department][r.company_name] += 1
        if r.status in ('Selected', 'Placed'):
            placed_matrix[r.department][r.company_name] += 1

    # Row totals (for sidebar bar chart feel)
    dept_totals = {d: sum(apps_matrix[d].values())    for d in departments}
    dept_placed = {d: sum(placed_matrix[d].values())  for d in departments}

    # Overall max values for intensity scaling
    max_apps   = max((apps_matrix[d][c]   for d in departments for c in companies), default=1) or 1
    max_placed = max((placed_matrix[d][c] for d in departments for c in companies), default=1) or 1

    # Column totals (computed here — Jinja2 has no 'extract' filter)
    col_totals_apps   = {c: sum(apps_matrix[d][c]   for d in departments) for c in companies}
    col_totals_placed = {c: sum(placed_matrix[d][c] for d in departments) for c in companies}

    return render_template('admin/heatmap.html',
        departments=departments, companies=companies,
        apps_matrix=apps_matrix, placed_matrix=placed_matrix,
        dept_totals=dept_totals, dept_placed=dept_placed,
        max_apps=max_apps, max_placed=max_placed,
        col_totals_apps=col_totals_apps, col_totals_placed=col_totals_placed,
        total_applications=len(rows),
        total_placements=sum(1 for r in rows if r.status in ('Selected', 'Placed')))


if __name__ == '__main__':
    app.run(debug=True)
