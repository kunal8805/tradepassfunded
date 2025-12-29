from flask import Flask, render_template, request, jsonify, session, redirect
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import hashlib
import uuid
import os

# ============ INIT APP ============
app = Flask(__name__)
app.secret_key = 'tradepass-secret-key-2024-change-this-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tradepass.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ============ DATABASE MODELS ============
class Visitor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    visitor_id = db.Column(db.String(20))
    ip_hash = db.Column(db.String(64))
    user_agent = db.Column(db.Text)
    referrer = db.Column(db.Text)
    source = db.Column(db.String(50))
    first_visit = db.Column(db.DateTime, default=datetime.utcnow)
    last_visit = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    clicks = db.relationship('Click', backref='visitor', lazy=True)

class Click(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    visitor_id = db.Column(db.String(20), db.ForeignKey('visitor.visitor_id'))
    ip_hash = db.Column(db.String(64))
    plan = db.Column(db.String(20))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    click_id = db.Column(db.String(36))

# ============ ADMIN CREDENTIALS ============
ADMIN_EMAIL = "tragene@gmail.com"
ADMIN_PASSWORD = "Kunal_8805"

# ============ HELPER FUNCTIONS ============
def hash_ip(ip):
    """Hash IP address for privacy"""
    return hashlib.sha256(ip.encode()).hexdigest()[:16]

def get_visitor_id():
    """Generate unique visitor ID"""
    count = Visitor.query.count()
    return f"V{1000 + count + 1}"

def detect_source(referrer):
    """Detect traffic source from referrer"""
    if not referrer or referrer == '':
        return 'direct'
    
    ref = referrer.lower()
    if 'instagram' in ref:
        return 'instagram'
    elif 'youtube.com' in ref or 'youtu.be' in ref:
        return 'youtube'
    elif 'facebook.com' in ref or 'fb.com' in ref:
        return 'facebook'
    elif 'whatsapp' in ref:
        return 'whatsapp'
    elif 'tiktok' in ref:
        return 'tiktok'
    elif 'telegram' in ref or 't.me' in ref:
        return 'telegram'
    else:
        return 'other'

def time_ago(dt):
    """Convert datetime to human readable time ago"""
    now = datetime.utcnow()
    diff = now - dt
    
    if diff.days > 0:
        return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    else:
        return "just now"

# ============ ADMIN AUTH CHECK ============
def check_admin():
    """Check if admin is logged in"""
    return session.get('admin_logged_in') == True

# ============ PUBLIC ROUTES ============
@app.route('/')
def home():
    """Home page - tracks all visitors"""
    ip = request.remote_addr or '127.0.0.1'
    ip_hash = hash_ip(ip)
    
    # Check if visitor already exists
    visitor = Visitor.query.filter_by(ip_hash=ip_hash).first()
    
    if visitor:
        # Update last visit time
        visitor.last_visit = datetime.utcnow()
        db.session.commit()
        visitor_id = visitor.visitor_id
    else:
        # Create new visitor
        visitor_id = get_visitor_id()
        new_visitor = Visitor(
            visitor_id=visitor_id,
            ip_hash=ip_hash,
            user_agent=request.user_agent.string,
            referrer=request.referrer,
            source=detect_source(request.referrer),
            first_visit=datetime.utcnow(),
            last_visit=datetime.utcnow()
        )
        db.session.add(new_visitor)
        db.session.commit()
    
    print(f"👤 Visitor tracked: {visitor_id} from {detect_source(request.referrer)}")
    return render_template('public/home.html')

@app.route('/track', methods=['POST'])
def track_click():
    """Track buy button clicks"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data received'}), 400
        
        plan = data.get('plan', 'unknown')
        ip = request.remote_addr or '127.0.0.1'
        ip_hash = hash_ip(ip)
        
        # Find visitor
        visitor = Visitor.query.filter_by(ip_hash=ip_hash).first()
        
        if visitor:
            # Create click record
            click = Click(
                visitor_id=visitor.visitor_id,
                ip_hash=ip_hash,
                plan=plan,
                click_id=str(uuid.uuid4())[:8]
            )
            db.session.add(click)
            db.session.commit()
            
            print(f"🖱️ Buy click: {visitor.visitor_id} -> {plan}")
            
            return jsonify({
                'success': True,
                'visitor_id': visitor.visitor_id,
                'plan': plan,
                'message': 'Click tracked successfully'
            })
        else:
            # Create visitor first, then track click
            visitor_id = get_visitor_id()
            new_visitor = Visitor(
                visitor_id=visitor_id,
                ip_hash=ip_hash,
                user_agent=request.user_agent.string,
                referrer=request.referrer,
                source=detect_source(request.referrer)
            )
            db.session.add(new_visitor)
            
            click = Click(
                visitor_id=visitor_id,
                ip_hash=ip_hash,
                plan=plan,
                click_id=str(uuid.uuid4())[:8]
            )
            db.session.add(click)
            db.session.commit()
            
            print(f"👤➕🖱️ New visitor with click: {visitor_id} -> {plan}")
            
            return jsonify({
                'success': True,
                'visitor_id': visitor_id,
                'plan': plan,
                'message': 'New visitor and click tracked'
            })
            
    except Exception as e:
        print(f"❌ Tracking error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/coming-soon')
def coming_soon():
    """Coming soon page"""
    return "<h1>Coming Soon or technical issue</h1>"

# ============ ADMIN ROUTES ============
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page - CLEAN NO BRANDING"""
    if check_admin():
        return redirect('/admin/dashboard')
    
    error = None
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            session['admin_email'] = email
            return redirect('/admin/dashboard')
        else:
            error = "Invalid email or password"
    
    # Clean login page - NO branding
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Login</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: #0f172a;
                height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }
            
            .login-box {
                background: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 12px;
                padding: 40px;
                width: 100%;
                max-width: 380px;
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
            }
            
            .login-header {
                text-align: center;
                margin-bottom: 30px;
            }
            
            .login-icon {
                width: 50px;
                height: 50px;
                background: rgba(74, 222, 128, 0.1);
                border: 1px solid rgba(74, 222, 128, 0.3);
                border-radius: 12px;
                display: flex;
                align-items: center;
                justify-content: center;
                margin: 0 auto 15px;
                color: #4ade80;
                font-size: 20px;
            }
            
            .login-header h2 {
                color: white;
                font-size: 20px;
                font-weight: 500;
            }
            
            .form-group {
                margin-bottom: 20px;
            }
            
            .form-label {
                color: #94a3b8;
                font-size: 14px;
                margin-bottom: 6px;
                display: block;
            }
            
            .form-input {
                width: 100%;
                padding: 12px 14px;
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                color: white;
                font-size: 15px;
                transition: all 0.2s;
            }
            
            .form-input:focus {
                outline: none;
                border-color: #4ade80;
                background: rgba(255, 255, 255, 0.08);
            }
            
            .form-input::placeholder {
                color: #64748b;
            }
            
            .error-msg {
                background: rgba(239, 68, 68, 0.1);
                border: 1px solid rgba(239, 68, 68, 0.2);
                color: #fca5a5;
                padding: 10px;
                border-radius: 8px;
                margin-bottom: 15px;
                font-size: 14px;
                text-align: center;
                display: ''' + ('block' if error else 'none') + ''';
            }
            
            .login-btn {
                width: 100%;
                padding: 12px;
                background: #4ade80;
                border: none;
                border-radius: 8px;
                color: white;
                font-size: 15px;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.2s;
                margin-top: 5px;
            }
            
            .login-btn:hover {
                background: #22c55e;
                transform: translateY(-1px);
            }
            
            .back-link {
                text-align: center;
                margin-top: 20px;
            }
            
            .back-link a {
                color: #94a3b8;
                text-decoration: none;
                font-size: 14px;
                transition: color 0.2s;
            }
            
            .back-link a:hover {
                color: #4ade80;
            }
            
            @media (max-width: 480px) {
                .login-box {
                    padding: 30px 25px;
                }
                
                .login-icon {
                    width: 45px;
                    height: 45px;
                    font-size: 18px;
                }
            }
        </style>
    </head>
    <body>
        <div class="login-box">
            <div class="login-header">
                <div class="login-icon">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"></path>
                        <polyline points="10 17 15 12 10 7"></polyline>
                        <line x1="15" y1="12" x2="3" y2="12"></line>
                    </svg>
                </div>
                <h2>Login to Dashboard</h2>
            </div>
            
            <div class="error-msg" id="errorMsg">
                ''' + (error if error else '') + '''
            </div>
            
            <form method="POST" action="/admin/login">
                <div class="form-group">
                    <label class="form-label">Email</label>
                    <input type="email" name="email" class="form-input" placeholder="Enter email" required>
                </div>
                
                <div class="form-group">
                    <label class="form-label">Password</label>
                    <input type="password" name="password" class="form-input" placeholder="Enter password" required>
                </div>
                
                <button type="submit" class="login-btn">
                    Sign In
                </button>
            </form>
            
            <div class="back-link">
                <a href="/">← Back to Home</a>
            </div>
        </div>
        
        <script>
            // Auto-hide error after 4 seconds
            setTimeout(() => {
                const error = document.getElementById('errorMsg');
                if (error) error.style.display = 'none';
            }, 4000);
            
            // Auto-focus on email field
            document.querySelector('input[name="email"]').focus();
        </script>
    </body>
    </html>
    '''

@app.route('/admin/logout')
def admin_logout():
    """Admin logout"""
    session.clear()
    return redirect('/admin/login')

@app.route('/admin/dashboard')
def admin_dashboard():
    """Admin dashboard - REAL data only"""
    if not check_admin():
        return redirect('/admin/login')
    
    # Get REAL stats
    total_visitors = Visitor.query.count()
    total_clicks = Click.query.count()
    
    # Today's date
    today = datetime.utcnow().date()
    
    # Today's visitors
    today_visitors = Visitor.query.filter(
        db.func.date(Visitor.first_visit) == today
    ).count()
    
    # Today's clicks
    today_clicks = Click.query.filter(
        db.func.date(Click.timestamp) == today
    ).count()
    
    # Conversion rate
    conversion_rate = round((total_clicks / total_visitors * 100), 1) if total_visitors > 0 else 0
    
    # Top plan
    from sqlalchemy import func
    top_plan_data = db.session.query(
        Click.plan, func.count(Click.id)
    ).group_by(Click.plan).order_by(func.count(Click.id).desc()).first()
    
    top_plan = "No clicks yet"
    if top_plan_data and top_plan_data[0]:
        plan_name = top_plan_data[0].replace('plan_', '₹')
        top_plan = f"{plan_name} ({top_plan_data[1]} clicks)"
    
    # Recent visitors (REAL data)
    recent_visitors_data = Visitor.query.order_by(Visitor.last_visit.desc()).limit(5).all()
    recent_visitors = []
    
    for v in recent_visitors_data:
        click_count = Click.query.filter_by(visitor_id=v.visitor_id).count()
        recent_visitors.append({
            'visitor_id': v.visitor_id,
            'time': v.last_visit.strftime('%H:%M'),
            'time_ago': time_ago(v.last_visit),
            'source': v.source,
            'clicks': click_count
        })
    
    # Recent clicks (REAL data)
    recent_clicks_data = Click.query.order_by(Click.timestamp.desc()).limit(5).all()
    recent_clicks = []
    
    for c in recent_clicks_data:
        recent_clicks.append({
            'plan': c.plan,
            'visitor_id': c.visitor_id,
            'time_ago': time_ago(c.timestamp),
            'ip_hash': c.ip_hash[:8] + '...'
        })
    
    # Plan breakdown (REAL data)
    plan_stats = []
    plans = ['plan_99', 'plan_149', 'plan_199']
    
    for plan in plans:
        count = Click.query.filter_by(plan=plan).count()
        percentage = round((count / total_clicks * 100), 1) if total_clicks > 0 else 0
        
        # Revenue calculation
        if plan == 'plan_99':
            revenue = count * 99
        elif plan == 'plan_149':
            revenue = count * 149
        else:
            revenue = count * 199
            
        plan_stats.append({
            'plan': plan.replace('plan_', '₹'),
            'count': count,
            'percentage': percentage,
            'revenue': f"₹{revenue:,}"
        })
    
    # Render dashboard
    return render_template('admin/dashboard.html',
                          logged_in=True,
                          admin_email=session.get('admin_email', 'Admin'),
                          current_time=datetime.utcnow().strftime('%H:%M'),
                          stats={
                              'total_visitors': total_visitors,
                              'total_clicks': total_clicks,
                              'today_visitors': today_visitors,
                              'today_clicks': today_clicks,
                              'conversion_rate': conversion_rate,
                              'top_plan': top_plan
                          },
                          recent_visitors=recent_visitors,
                          recent_clicks=recent_clicks,
                          plan_stats=plan_stats)

@app.route('/admin/visitors')
def admin_visitors():
    """All visitors page"""
    if not check_admin():
        return redirect('/admin/login')
    
    # Get ALL visitors
    all_visitors = Visitor.query.order_by(Visitor.last_visit.desc()).all()
    
    visitors_data = []
    for v in all_visitors:
        click_count = Click.query.filter_by(visitor_id=v.visitor_id).count()
        visitors_data.append({
            'id': v.visitor_id,
            'ip': v.ip_hash[:8] + '...',
            'source': v.source,
            'first_visit': v.first_visit.strftime('%Y-%m-%d %H:%M'),
            'last_visit': time_ago(v.last_visit),
            'clicks': click_count,
            'is_returning': click_count > 0
        })
    
    return render_template('admin/visitors.html',
                          logged_in=True,
                          admin_email=session.get('admin_email', 'Admin'),
                          visitors=visitors_data)

@app.route('/admin/clicks')
def admin_clicks():
    """All clicks page"""
    if not check_admin():
        return redirect('/admin/login')
    
    # Get ALL clicks
    all_clicks = Click.query.order_by(Click.timestamp.desc()).all()
    
    clicks_data = []
    for c in all_clicks:
        clicks_data.append({
            'id': c.click_id,
            'visitor_id': c.visitor_id,
            'plan': c.plan.replace('plan_', '₹'),
            'time': c.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'time_ago': time_ago(c.timestamp),
            'ip': c.ip_hash[:8] + '...'
        })
    
    return render_template('admin/clicks.html',
                          logged_in=True,
                          admin_email=session.get('admin_email', 'Admin'),
                          clicks=clicks_data)

# ============ INITIALIZE DATABASE ============
def init_db():
    """Create database tables"""
    with app.app_context():
        db.create_all()
        print("✅ Database initialized successfully")
        print(f"📊 Current visitors: {Visitor.query.count()}")
        print(f"🖱️ Current clicks: {Click.query.count()}")

# ============ MAIN ============
if __name__ == '__main__':
    # Delete old database if exists to avoid errors
    if os.path.exists('tradepass.db'):
        try:
            os.remove('tradepass.db')
            print("🗑️  Old database removed")
        except:
            pass
    
    init_db()
    
    print("\n" + "="*60)
    print("🚀 TRADEPASS ANALYTICS SERVER")
    print("="*60)
    print("🌐 Homepage:      http://localhost:5000")
    print("🔐 Admin Login:   http://localhost:5000/admin/login")
    print("   (Also: http://localhost:5000/login)")
    print("📊 Dashboard:     http://localhost:5000/admin/dashboard")
    print("👥 Visitors:      http://localhost:5000/admin/visitors")
    print("🖱️ Clicks:        http://localhost:5000/admin/clicks")
    print("="*60)
    print("🔑 ADMIN CREDENTIALS:")
    print(f"   Email:    {ADMIN_EMAIL}")
    print(f"   Password: {ADMIN_PASSWORD}")
    print("="*60)
    print("📈 FEATURES:")
    print("• Clean login page - NO credentials shown")
    print("• Real IP tracking with hashing")
    print("• Every click tracked")
    print("• Professional admin panel")
    print("="*60 + "\n")
    
    app.run(debug=True, port=5000)