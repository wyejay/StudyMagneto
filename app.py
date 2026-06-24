from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'studyhub_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///studyhub.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32 MB

db = SQLAlchemy(app)

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ==================== MODELS ====================
class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    color = db.Column(db.String(7), default='#3b82f6')

class TimetableSlot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    day = db.Column(db.String(20), nullable=False)
    start_time = db.Column(db.String(5), nullable=False)
    end_time = db.Column(db.String(5), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    location = db.Column(db.String(100))
    notes = db.Column(db.Text)
    subject = db.relationship('Subject')

class StudyPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'))
    priority = db.Column(db.String(20), default='medium')
    due_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='not_started')
    progress = db.Column(db.Integer, default=0)
    subject = db.relationship('Subject')

class StudyMaterial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)
    original_name = db.Column(db.String(200), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'))
    description = db.Column(db.Text)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    subject = db.relationship('Subject')

class ProgressLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, default=date.today)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    hours = db.Column(db.Float, nullable=False)
    topics = db.Column(db.Text)
    rating = db.Column(db.Integer, default=3)
    subject = db.relationship('Subject')

# Create tables
with app.app_context():
    db.create_all()

# Helper
def get_days():
    return ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

# ==================== ROUTES ====================

@app.route('/')
def index():
    today = datetime.now().strftime('%A')
    today_slots = TimetableSlot.query.filter_by(day=today).order_by(TimetableSlot.start_time).all()
    
    upcoming_plans = StudyPlan.query.filter(
        StudyPlan.due_date >= date.today(), 
        StudyPlan.status != 'completed'
    ).order_by(StudyPlan.due_date).limit(5).all()
    
    total_hours = db.session.query(db.func.sum(ProgressLog.hours)).scalar() or 0
    subjects = Subject.query.all()
    
    return render_template('index.html', 
                         today_slots=today_slots, 
                         upcoming_plans=upcoming_plans, 
                         total_hours=total_hours,
                         subjects=subjects,
                         today=today)

@app.route('/subjects', methods=['GET', 'POST'])
def subjects():
    if request.method == 'POST':
        name = request.form.get('name')
        color = request.form.get('color', '#3b82f6')
        if name:
            if not Subject.query.filter_by(name=name).first():
                new_subject = Subject(name=name, color=color)
                db.session.add(new_subject)
                db.session.commit()
                flash('Subject added successfully!', 'success')
            else:
                flash('Subject already exists!', 'error')
        return redirect(url_for('subjects'))
    
    subjects = Subject.query.all()
    return render_template('subjects.html', subjects=subjects)

@app.route('/timetable', methods=['GET', 'POST'])
def timetable():
    if request.method == 'POST':
        day = request.form.get('day')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')
        subject_id = request.form.get('subject_id')
        location = request.form.get('location')
        notes = request.form.get('notes')
        
        if all([day, start_time, end_time, subject_id]):
            slot = TimetableSlot(
                day=day,
                start_time=start_time,
                end_time=end_time,
                subject_id=int(subject_id),
                location=location,
                notes=notes
            )
            db.session.add(slot)
            db.session.commit()
            flash('Timetable slot added!', 'success')
        return redirect(url_for('timetable'))
    
    slots = TimetableSlot.query.order_by(TimetableSlot.day, TimetableSlot.start_time).all()
    subjects = Subject.query.all()
    days = get_days()
    return render_template('timetable.html', slots=slots, subjects=subjects, days=days)

@app.route('/plans', methods=['GET', 'POST'])
def plans():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        subject_id = request.form.get('subject_id')
        priority = request.form.get('priority')
        due_date_str = request.form.get('due_date')
        
        if title and due_date_str:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
            plan = StudyPlan(
                title=title,
                description=description,
                subject_id=int(subject_id) if subject_id else None,
                priority=priority or 'medium',
                due_date=due_date
            )
            db.session.add(plan)
            db.session.commit()
            flash('Study plan created!', 'success')
        return redirect(url_for('plans'))
    
    plans = StudyPlan.query.order_by(StudyPlan.due_date).all()
    subjects = Subject.query.all()
    return render_template('plans.html', plans=plans, subjects=subjects)

@app.route('/update_plan/<int:plan_id>', methods=['POST'])
def update_plan(plan_id):
    plan = StudyPlan.query.get_or_404(plan_id)
    status = request.form.get('status')
    progress = request.form.get('progress')
    
    if status:
        plan.status = status
    if progress:
        plan.progress = int(progress)
    
    db.session.commit()
    return redirect(url_for('plans'))

@app.route('/materials', methods=['GET', 'POST'])
def materials():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part', 'error')
            return redirect(url_for('materials'))
        
        file = request.files['file']
        subject_id = request.form.get('subject_id')
        description = request.form.get('description')
        
        if file and file.filename:
            original_name = file.filename
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            material = StudyMaterial(
                filename=filename,
                original_name=original_name,
                subject_id=int(subject_id) if subject_id else None,
                description=description
            )
            db.session.add(material)
            db.session.commit()
            flash('Material uploaded successfully!', 'success')
        return redirect(url_for('materials'))
    
    materials = StudyMaterial.query.order_by(StudyMaterial.upload_date.desc()).all()
    subjects = Subject.query.all()
    return render_template('materials.html', materials=materials, subjects=subjects)

@app.route('/download/<int:material_id>')
def download(material_id):
    material = StudyMaterial.query.get_or_404(material_id)
    return send_from_directory(app.config['UPLOAD_FOLDER'], material.filename, 
                             as_attachment=True, download_name=material.original_name)

@app.route('/progress', methods=['GET', 'POST'])
def progress():
    if request.method == 'POST':
        subject_id = request.form.get('subject_id')
        hours = float(request.form.get('hours', 0))
        topics = request.form.get('topics')
        rating = int(request.form.get('rating', 3))
        
        if subject_id and hours > 0:
            log = ProgressLog(
                subject_id=int(subject_id),
                hours=hours,
                topics=topics,
                rating=rating
            )
            db.session.add(log)
            db.session.commit()
            flash('Progress logged!', 'success')
        return redirect(url_for('progress'))
    
    logs = ProgressLog.query.order_by(ProgressLog.date.desc()).limit(50).all()
    subject_hours = db.session.query(
        Subject.name, db.func.sum(ProgressLog.hours)
    ).join(ProgressLog).group_by(Subject.name).all()
    
    subjects = Subject.query.all()
    return render_template('progress.html', logs=logs, subject_hours=subject_hours, subjects=subjects)

@app.route('/delete/<string:model>/<int:id>')
def delete_item(model, id):
    if model == 'slot':
        item = TimetableSlot.query.get_or_404(id)
    elif model == 'plan':
        item = StudyPlan.query.get_or_404(id)
    elif model == 'material':
        item = StudyMaterial.query.get_or_404(id)
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], item.filename))
        except:
            pass
    elif model == 'log':
        item = ProgressLog.query.get_or_404(id)
    else:
        flash('Invalid model', 'error')
        return redirect(url_for('index'))
    
    db.session.delete(item)
    db.session.commit()
    flash(f'{model.capitalize()} deleted!', 'success')
    return redirect(request.referrer or url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
