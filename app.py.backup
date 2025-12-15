from flask import Flask, render_template, request, redirect, session, jsonify, url_for, flash, Response, send_from_directory
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from datetime import datetime, timedelta
from functools import wraps
import bcrypt
import traceback
import csv
import io
import os
import subprocess
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import secrets
from dotenv import load_dotenv
import uuid
from werkzeug.utils import secure_filename

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default_secret_key_change_in_production')

# Database configuration from environment variables
DB_NAME = os.getenv('DB_NAME', 'BCM_Ticket_tracker')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD')
if not DB_PASSWORD:
    raise ValueError("DB_PASSWORD environment variable is required")
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')

SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USERNAME = os.getenv('SMTP_USERNAME')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
EMAIL_FROM = os.getenv('EMAIL_FROM', SMTP_USERNAME)
EMAIL_ENABLED = os.getenv('EMAIL_ENABLED', 'false').lower() == 'true'

if not SMTP_USERNAME or not SMTP_PASSWORD:
    print("WARNING: Email credentials not configured")
    EMAIL_ENABLED = False

TARGET_CONN_STR = (
    f"dbname='{DB_NAME}' user='{DB_USER}' password='{DB_PASSWORD}' host='{DB_HOST}' port='{DB_PORT}'"
)

app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Allowed extensions
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'txt', 'zip', 'rar', 'csv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- DB Initialization ---
def initialize_database():
    dbname = DB_NAME

    try:
        conn = psycopg2.connect(dbname='postgres', user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()

        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
        exists = cur.fetchone()
        if not exists:
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))
            print(f"Database '{dbname}' created.")
        else:
            print(f"Database '{dbname}' already exists.")

        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error checking/creating database: {e}")
        traceback.print_exc()
        return

    try:
        conn = get_db_connection()
        if not conn:
            print("Cannot connect to database after creation.")
            return
        cur = conn.cursor()

        print("Creating organizations table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS organizations (
                org_id SERIAL PRIMARY KEY,
                org_name TEXT NOT NULL,
                org_slug TEXT UNIQUE NOT NULL,
                org_email TEXT,
                org_phone TEXT,
                
                -- Subscription info
                subscription_tier TEXT DEFAULT 'free' CHECK (subscription_tier IN ('free', 'starter', 'professional', 'enterprise')),
                subscription_status TEXT DEFAULT 'active' CHECK (subscription_status IN ('active', 'trial', 'expired', 'cancelled')),
                max_users INT DEFAULT 10,
                max_tickets_per_month INT DEFAULT 100,
                
                -- Billing info
                stripe_customer_id TEXT,
                stripe_subscription_id TEXT,
                payfast_subscription_id TEXT,
                
                -- Branding (white-label)
                logo_url TEXT,
                primary_color TEXT DEFAULT '#4e73df',
                secondary_color TEXT DEFAULT '#858796',
                
                -- Status
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                trial_ends_at TIMESTAMP,
                
                -- Contact
                owner_user_id INT,
                
                -- Metadata
                settings JSONB DEFAULT '{}'::jsonb
            )
        """)
        print("✓ Organizations table created/verified")

        print("Creating org_departments table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS org_departments (
                dept_id SERIAL PRIMARY KEY,
                org_id INT NOT NULL REFERENCES organizations(org_id) ON DELETE CASCADE,
                dept_name TEXT NOT NULL,
                dept_slug TEXT NOT NULL,
                description TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(org_id, dept_slug)
            )
        """)
        print("✓ Org departments table created/verified")

  
        print("Checking for default organization...")
        cur.execute("SELECT org_id FROM organizations WHERE org_slug = 'default-org'")
        default_org = cur.fetchone()
        
        if not default_org:
            cur.execute("""
                INSERT INTO organizations (
                    org_name, 
                    org_slug, 
                    org_email,
                    subscription_tier,
                    subscription_status,
                    max_users,
                    is_active
                ) VALUES (
                    'Default Organization',
                    'default-org',
                    'admin@ttah.local',
                    'enterprise',
                    'active',
                    999999,
                    TRUE
                )
                RETURNING org_id
            """)
            default_org_id = cur.fetchone()[0]
            print(f"✓ Default organization created (ID: {default_org_id})")
            
            # Create default departments
            default_departments = [
                ('IT Support', 'it-support', 'IT and technical support'),
                ('Customer Service', 'customer-service', 'Customer service department')
            ]
            
            for dept_name, dept_slug, description in default_departments:
                cur.execute("""
                    INSERT INTO org_departments (org_id, dept_name, dept_slug, description)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (org_id, dept_slug) DO NOTHING
                """, (default_org_id, dept_name, dept_slug, description))
            
            print(f"✓ Created {len(default_departments)} default departments")
        else:
            default_org_id = default_org[0]
            print(f"✓ Default organization exists (ID: {default_org_id})")

        print("Creating users table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id SERIAL PRIMARY KEY,
                org_id INT REFERENCES organizations(org_id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                surname TEXT NOT NULL,
                email TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                region TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'assignee', 'admin')),
                created_at TIMESTAMP(0) WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                UNIQUE(org_id, email)
            )
        """)
        
        # Add org_id if it doesn't exist (for existing databases)
        cur.execute("""
            DO $$ 
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'users' AND column_name = 'org_id'
                ) THEN
                    ALTER TABLE users ADD COLUMN org_id INT REFERENCES organizations(org_id) ON DELETE CASCADE;
                    UPDATE users SET org_id = (SELECT org_id FROM organizations WHERE org_slug = 'default-org') WHERE org_id IS NULL;
                END IF;
            END $$;
        """)
        print("✓ Users table created/verified")

        print("Creating tickets table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                ticket_id SERIAL PRIMARY KEY,
                org_id INT REFERENCES organizations(org_id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                attachment_path TEXT,    
                account_number INT,
                meter_number TEXT,
                status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in-progress', 'transferred', 'closed')),
                created_by INT NOT NULL,
                assigned_to INT NOT NULL,
                created_at TIMESTAMP(0) WITHOUT TIME ZONE DEFAULT NOW(),
                resolved_at TIMESTAMP(0) WITHOUT TIME ZONE,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ticket_type TEXT DEFAULT 'meter' CHECK (ticket_type IN ('meter', 'general')),
                category TEXT,
                location TEXT,
                contact_info TEXT,
                FOREIGN KEY (created_by) REFERENCES users (user_id),
                FOREIGN KEY (assigned_to) REFERENCES users (user_id)
            )
        """)
        
        # Add org_id if it doesn't exist (for existing databases)
        cur.execute("""
            DO $$ 
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'tickets' AND column_name = 'org_id'
                ) THEN
                    ALTER TABLE tickets ADD COLUMN org_id INT REFERENCES organizations(org_id) ON DELETE CASCADE;
                    UPDATE tickets SET org_id = (SELECT org_id FROM organizations WHERE org_slug = 'default-org') WHERE org_id IS NULL;
                END IF;
            END $$;
        """)
        print("✓ Tickets table created/verified")

        print("Creating announcements table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS announcements (
                announcement_id SERIAL PRIMARY KEY,
                org_id INT REFERENCES organizations(org_id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                target_audience TEXT NOT NULL DEFAULT 'all' CHECK (target_audience IN ('all', 'user', 'assignee', 'admin', 'users', 'assignees', 'admins')),
                suppress_tickets BOOLEAN NOT NULL DEFAULT TRUE,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_by INT NOT NULL,
                created_at TIMESTAMP(0) WITHOUT TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES users (user_id)
            )
        """)
        
        # Add org_id if it doesn't exist
        cur.execute("""
            DO $$ 
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'announcements' AND column_name = 'org_id'
                ) THEN
                    ALTER TABLE announcements ADD COLUMN org_id INT REFERENCES organizations(org_id) ON DELETE CASCADE;
                    UPDATE announcements SET org_id = (SELECT org_id FROM organizations WHERE org_slug = 'default-org') WHERE org_id IS NULL;
                END IF;
            END $$;
        """)
        print("✓ Announcements table created/verified")


        print("Creating announcement_reads table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS announcement_reads (
                user_id INT NOT NULL,
                announcement_id INT NOT NULL,
                read_at TIMESTAMP(0) WITHOUT TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, announcement_id),
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (announcement_id) REFERENCES announcements (announcement_id)
            )
        """)
        print("✓ Announcement reads table created/verified")

     
        print("Creating system_config table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS system_config (
                config_id SERIAL PRIMARY KEY,
                config_key TEXT UNIQUE NOT NULL,
                config_value TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP(0) WITHOUT TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Insert default system configuration
        cur.execute("""
            INSERT INTO system_config (config_key, config_value, description) 
            VALUES 
                ('default_ticket_status', 'open', 'Default status for new tickets'),
                ('auto_close_days', '30', 'Days after which inactive tickets are auto-closed'),
                ('max_file_size', '10', 'Maximum file upload size in MB'),
                ('session_timeout', '120', 'Session timeout in minutes')
            ON CONFLICT (config_key) DO NOTHING
        """)
        print("✓ System config table created/verified")


        print("Creating ticket_history table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ticket_history (
                ticket_history_id SERIAL PRIMARY KEY,
                ticket_id INT NOT NULL,
                action TEXT,
                name TEXT,
                role TEXT,
                performed_by INT NOT NULL,
                performed_at TIMESTAMP(0) WITHOUT TIME ZONE DEFAULT NOW(),
                notes TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ticket_id) REFERENCES tickets (ticket_id),
                FOREIGN KEY (performed_by) REFERENCES users (user_id)
            )
        """)
        print("✓ Ticket history table created/verified")

        print("Creating password_reset_tokens table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                token_id SERIAL PRIMARY KEY,
                user_id INT NOT NULL,
                token TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP(0) WITHOUT TIME ZONE DEFAULT NOW(),
                expires_at TIMESTAMP(0) WITHOUT TIME ZONE NOT NULL,
                used BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
            )
        """)
        print("✓ Password reset tokens table created/verified")


        print("Creating indexes...")
        indexes = [
            # User indexes
            "CREATE INDEX IF NOT EXISTS idx_users_org_id ON users(org_id)",
            "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",
            "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)",
            
            # Ticket indexes
            "CREATE INDEX IF NOT EXISTS idx_tickets_org_id ON tickets(org_id)",
            "CREATE INDEX IF NOT EXISTS idx_tickets_created_by ON tickets (created_by)",
            "CREATE INDEX IF NOT EXISTS idx_tickets_assigned_to ON tickets (assigned_to)",
            "CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status)",
            "CREATE INDEX IF NOT EXISTS idx_tickets_updated_at ON tickets(updated_at)",
            
            # Ticket history indexes
            "CREATE INDEX IF NOT EXISTS idx_ticket_history_ticket_id ON ticket_history (ticket_id)",
            "CREATE INDEX IF NOT EXISTS idx_ticket_history_updated_at ON ticket_history(updated_at)",
            
            # Announcement indexes
            "CREATE INDEX IF NOT EXISTS idx_announcements_org_id ON announcements(org_id)",
            "CREATE INDEX IF NOT EXISTS idx_announcements_is_active ON announcements (is_active)",
            "CREATE INDEX IF NOT EXISTS idx_announcements_target_audience ON announcements (target_audience)",
            
            # Announcement reads indexes
            "CREATE INDEX IF NOT EXISTS idx_announcement_reads_user_id ON announcement_reads (user_id)",
            "CREATE INDEX IF NOT EXISTS idx_announcement_reads_announcement_id ON announcement_reads (announcement_id)",
            "CREATE INDEX IF NOT EXISTS idx_announcement_reads_updated_at ON announcement_reads(updated_at)",
            
            # Password reset indexes
            "CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_token ON password_reset_tokens (token)",
            "CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user_id ON password_reset_tokens (user_id)",
            "CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_expires_at ON password_reset_tokens (expires_at)",
            
            # Organization indexes
            "CREATE INDEX IF NOT EXISTS idx_organizations_slug ON organizations(org_slug)",
            "CREATE INDEX IF NOT EXISTS idx_organizations_stripe_customer ON organizations(stripe_customer_id)",
            "CREATE INDEX IF NOT EXISTS idx_org_departments_org_id ON org_departments(org_id)",
        ]
        
        for index_sql in indexes:
            cur.execute(index_sql)
        
        print("✓ All indexes created/verified")


        print("Creating triggers...")
        
        # Create trigger function
        cur.execute("""
            CREATE OR REPLACE FUNCTION update_updated_at_column()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = CURRENT_TIMESTAMP;
                RETURN NEW;
            END;
            $$ language 'plpgsql'
        """)

        # Create triggers for each table
        cur.execute("""
            DO $$
            BEGIN
                -- Tickets trigger
                IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_tickets_updated_at') THEN
                    CREATE TRIGGER update_tickets_updated_at 
                        BEFORE UPDATE ON tickets 
                        FOR EACH ROW 
                        EXECUTE FUNCTION update_updated_at_column();
                END IF;
                
                -- Ticket history trigger
                IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_ticket_history_updated_at') THEN
                    CREATE TRIGGER update_ticket_history_updated_at 
                        BEFORE UPDATE ON ticket_history 
                        FOR EACH ROW 
                        EXECUTE FUNCTION update_updated_at_column();
                END IF;
                
                -- Announcements trigger
                IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_announcements_updated_at') THEN
                    CREATE TRIGGER update_announcements_updated_at 
                        BEFORE UPDATE ON announcements 
                        FOR EACH ROW 
                        EXECUTE FUNCTION update_updated_at_column();
                END IF;
                
                -- Announcement reads trigger
                IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_announcement_reads_updated_at') THEN
                    CREATE TRIGGER update_announcement_reads_updated_at 
                        BEFORE UPDATE ON announcement_reads 
                        FOR EACH ROW 
                        EXECUTE FUNCTION update_updated_at_column();
                END IF;
                
                -- Organizations trigger
                IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_organizations_updated_at') THEN
                    CREATE TRIGGER update_organizations_updated_at 
                        BEFORE UPDATE ON organizations 
                        FOR EACH ROW 
                        EXECUTE FUNCTION update_updated_at_column();
                END IF;
            END
            $$
        """)

        conn.commit()
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"Error creating tables: {e}")
        traceback.print_exc()

# --- DB Connection Helper ---
def get_db_connection():
    try:
        conn = psycopg2.connect(TARGET_CONN_STR)
        # print("DB connection successful.")
        return conn
    except Exception as e:
        print("Database connection failed:", e)
        traceback.print_exc()
        return None
    
# --- Organization Helper Functions ---
def get_user_organization(user_id):
    """Get the organization for a given user"""
    try:
        conn = get_db_connection()
        if not conn:
            return None
        
        cur = conn.cursor()
        cur.execute("""
            SELECT o.org_id, o.org_name, o.org_slug, o.subscription_tier, 
                   o.subscription_status, o.max_users, o.primary_color, o.logo_url
            FROM organizations o
            JOIN users u ON o.org_id = u.org_id
            WHERE u.user_id = %s
        """, (user_id,))
        
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        if result:
            return {
                'org_id': result[0],
                'org_name': result[1],
                'org_slug': result[2],
                'subscription_tier': result[3],
                'subscription_status': result[4],
                'max_users': result[5],
                'primary_color': result[6],
                'logo_url': result[7]
            }
        return None
        
    except Exception as e:
        print(f"Error getting user organization: {e}")
        return None

def check_organization_limits(org_id):
    """Check if organization has reached its limits"""
    try:
        conn = get_db_connection()
        if not conn:
            return {'can_add_users': False, 'can_create_tickets': False}
        
        cur = conn.cursor()
        
        # Get organization limits
        cur.execute("""
            SELECT max_users, max_tickets_per_month, subscription_status
            FROM organizations
            WHERE org_id = %s
        """, (org_id,))
        
        result = cur.fetchone()
        if not result:
            return {'can_add_users': False, 'can_create_tickets': False}
        
        max_users, max_tickets_per_month, sub_status = result
        
        # Check if subscription is active
        if sub_status not in ['active', 'trial']:
            return {'can_add_users': False, 'can_create_tickets': False}
        
        # Count current users
        cur.execute("""
            SELECT COUNT(*) FROM users WHERE org_id = %s
        """, (org_id,))
        current_users = cur.fetchone()[0]
        
        # Count tickets this month
        cur.execute("""
            SELECT COUNT(*) 
            FROM tickets 
            WHERE org_id = %s 
            AND created_at >= DATE_TRUNC('month', CURRENT_DATE)
        """, (org_id,))
        current_tickets = cur.fetchone()[0]
        
        cur.close()
        conn.close()
        
        return {
            'can_add_users': current_users < max_users,
            'can_create_tickets': current_tickets < max_tickets_per_month,
            'current_users': current_users,
            'max_users': max_users,
            'current_tickets': current_tickets,
            'max_tickets_per_month': max_tickets_per_month
        }
        
    except Exception as e:
        print(f"Error checking organization limits: {e}")
        return {'can_add_users': False, 'can_create_tickets': False}

def get_organization_departments(org_id):
    """Get all departments for an organization"""
    try:
        conn = get_db_connection()
        if not conn:
            return []
        
        cur = conn.cursor()
        cur.execute("""
            SELECT dept_id, dept_name, dept_slug, description
            FROM org_departments
            WHERE org_id = %s AND is_active = TRUE
            ORDER BY dept_name
        """, (org_id,))
        
        departments = []
        for row in cur.fetchall():
            departments.append({
                'dept_id': row[0],
                'dept_name': row[1],
                'dept_slug': row[2],
                'description': row[3]
            })
        
        cur.close()
        conn.close()
        return departments
        
    except Exception as e:
        print(f"Error getting organization departments: {e}")
        return []

# --- Session Configuration ---
def configure_session_timeout():
    """Configure Flask session timeout from database settings"""
    try:
        conn = get_db_connection()
        if not conn:
            print("Warning: Could not connect to database to configure session timeout")
            return
            
        cur = conn.cursor()
        cur.execute("SELECT config_value FROM system_config WHERE config_key = 'session_timeout'")
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        if result:
            timeout_minutes = int(result[0])
            # Convert minutes to timedelta for Flask
            app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=timeout_minutes)
            print(f"Session timeout configured: {timeout_minutes} minutes")
        else:
            # Default to 120 minutes if not configured
            app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=120)
            print("Session timeout set to default: 120 minutes")
            
    except Exception as e:
        print(f"Error configuring session timeout: {e}")
        # Fallback to default
        app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=120)
        print("Session timeout set to default: 120 minutes (fallback)")

# --- Status Validation Helper Functions ---
def validate_status(status):
    """Validate ticket status against allowed values"""
    valid_statuses = ['open', 'in-progress', 'transferred', 'closed']
    return status.lower() in valid_statuses

def validate_role(role):
    """Validate user role against allowed values"""
    valid_roles = ['user', 'assignee', 'admin']
    return role.lower() in valid_roles

def validate_target_audience(audience):
    """Validate announcement target audience"""
    valid_audiences = ['all', 'users', 'assignees', 'admins', 'user', 'assignee', 'admin']
    return audience.lower() in valid_audiences

def require_org_context(f):
    """Decorator to ensure user has valid organization context"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to continue.', 'error')
            return redirect(url_for('login'))
        
        if 'org_id' not in session:
            # Organization context missing - refresh from database
            org_info = get_user_organization(session['user_id'])
            if org_info:
                session['org_id'] = org_info['org_id']
                session['org_name'] = org_info['org_name']
                session['org_slug'] = org_info['org_slug']
                session['subscription_tier'] = org_info['subscription_tier']
            else:
                flash('Organization not found. Please contact support.', 'error')
                return redirect(url_for('logout'))
        
        return f(*args, **kwargs)
    return decorated_function

# --- Routes ---

def send_email(to_email, subject, body, html_body=None):
    """Send email with optional HTML body"""
    if not EMAIL_ENABLED:
        print(f"Email disabled. Would send to {to_email}: {subject}")
        return True
    
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        print("Email credentials not configured")
        return False
    
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['From'] = EMAIL_FROM
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Add text body
        msg.attach(MIMEText(body, 'plain'))
        
        # Add HTML body if provided
        if html_body:
            msg.attach(MIMEText(html_body, 'html'))
        
        # Send email
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.sendmail(EMAIL_FROM, to_email, msg.as_string())
        server.quit()
        
        print(f"Email sent successfully to {to_email}")
        return True
        
    except Exception as e:
        print(f"Failed to send email to {to_email}: {str(e)}")
        return False

def send_ticket_notification(ticket_id, action, recipient_email, recipient_name, ticket_data):
    """Send ticket notification email"""
    subject = f'Ticket {action.title()}: #{ticket_id} - {ticket_data.get("title", "N/A")}'
    
    body = f"""Dear {recipient_name},

This is a notification regarding ticket #{ticket_id}.

Ticket Details:
- Title: {ticket_data.get('title', 'N/A')}
- Description: {ticket_data.get('description', 'N/A')}
- Status: {ticket_data.get('status', 'N/A')}
- Account Number: {ticket_data.get('account_number', 'N/A')}
- Meter Number: {ticket_data.get('meter_number', 'N/A')}

Action: {action.title()}

Please log into the system to view more details.

Best regards,
TTAH Support Team
"""
    
    return send_email(recipient_email, subject, body)

# Replace your existing notify_ticket_action function with this improved version:

def notify_ticket_action(ticket_id, action):
    """Send email notifications for ticket actions - IMPROVED VERSION"""
    try:
        conn = get_db_connection()
        if not conn:
            return
            
        cur = conn.cursor()
        
        # Get comprehensive ticket and user details
        cur.execute("""
            SELECT t.title, t.description, t.status, t.account_number, t.meter_number,
                   t.created_by, t.assigned_to,
                   creator.email as creator_email, creator.name as creator_name, creator.surname as creator_surname,
                   assignee.email as assignee_email, assignee.name as assignee_name, assignee.surname as assignee_surname
            FROM tickets t
            LEFT JOIN users creator ON t.created_by = creator.user_id
            LEFT JOIN users assignee ON t.assigned_to = assignee.user_id
            WHERE t.ticket_id = %s
        """, (ticket_id,))
        
        result = cur.fetchone()
        if not result:
            print(f"Ticket {ticket_id} not found for email notification")
            return
        
        # Prepare ticket data
        ticket_data = {
            'title': result[0],
            'description': result[1],
            'status': result[2],
            'account_number': result[3],
            'meter_number': result[4]
        }
        
        # Get user details
        creator_id = result[5]
        assignee_id = result[6]
        creator_email = result[7]
        creator_name = f"{result[8]} {result[9]}" if result[8] and result[9] else "Unknown"
        assignee_email = result[10]
        assignee_name = f"{result[11]} {result[12]}" if result[11] and result[12] else "Unknown"
        
        # Determine who gets notified based on action
        recipients = []
        
        if action == 'created':
            # NEW TICKET: Notify assignee
            if assignee_email:
                recipients.append((assignee_email, assignee_name, f"You have been assigned a new ticket"))
        
        elif action == 'transferred':
            # TRANSFERRED: Notify new assignee AND original creator
            if assignee_email:
                recipients.append((assignee_email, assignee_name, f"A ticket has been transferred to you"))
            if creator_email and creator_email != assignee_email:
                recipients.append((creator_email, creator_name, f"Your ticket has been transferred"))
        
        elif action == 'closed':
            # CLOSED: Notify creator AND assignee (if different people)
            if creator_email:
                recipients.append((creator_email, creator_name, f"Your ticket has been closed"))
            if assignee_email and assignee_email != creator_email:
                recipients.append((assignee_email, assignee_name, f"A ticket you were assigned has been closed"))
        
        elif action in ['updated', 'status_changed', 'in-progress']:
            # STATUS UPDATES: Notify both creator and assignee
            if creator_email:
                recipients.append((creator_email, creator_name, f"Your ticket status has been updated"))
            if assignee_email and assignee_email != creator_email:
                recipients.append((assignee_email, assignee_name, f"A ticket you are assigned to has been updated"))
        
        # Send emails to all recipients
        for email, name, message_context in recipients:
            if email:
                success = send_ticket_notification_improved(ticket_id, action, email, name, ticket_data, message_context)
                print(f"Email notification sent to {email}: {success}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"Error sending ticket notifications: {str(e)}")

def send_ticket_notification_improved(ticket_id, action, recipient_email, recipient_name, ticket_data, message_context):
    """Improved ticket notification email"""
    
    # Better subject lines
    action_subjects = {
        'created': f'New Ticket Assigned: #{ticket_id} - {ticket_data.get("title", "N/A")}',
        'transferred': f'Ticket Transferred: #{ticket_id} - {ticket_data.get("title", "N/A")}',
        'closed': f'Ticket Closed: #{ticket_id} - {ticket_data.get("title", "N/A")}',
        'updated': f'Ticket Updated: #{ticket_id} - {ticket_data.get("title", "N/A")}',
        'status_changed': f'Ticket Status Changed: #{ticket_id} - {ticket_data.get("title", "N/A")}',
        'in-progress': f'Ticket In Progress: #{ticket_id} - {ticket_data.get("title", "N/A")}'
    }
    
    subject = action_subjects.get(action, f'Ticket Notification: #{ticket_id}')
    
    # Create email body
    body = f"""Dear {recipient_name},

{message_context}.

Ticket Details:
----------------------------------------------------------
• Ticket ID: #{ticket_id}
• Title: {ticket_data.get('title', 'N/A')}
• Status: {ticket_data.get('status', 'N/A')}
• Account Number: {ticket_data.get('account_number', 'N/A')}
• Meter Number: {ticket_data.get('meter_number', 'N/A')}
----------------------------------------------------------

Description:
{ticket_data.get('description', 'N/A')}

Please log into TTAH to view full details and take any necessary action.

Best regards,
TTAH Support Team
"""
    
    return send_email(recipient_email, subject, body)

# Add this function after your other email functions:

def send_password_reset_email(email, name, reset_token):
    """Send password reset email"""
    try:
        subject = "Password Reset Request - TTAH"
        
        # Create reset URL (adjust domain as needed)
        reset_url = url_for('reset_password', token=reset_token, _external=True)
        
        # Create text body
        body = f"""Dear {name},

You have requested to reset your password for your TTAH account.

Please click the following link to reset your password:
{reset_url}

This link will expire in 1 hour for security reasons.

If you did not request this password reset, please ignore this email.

Best regards,
TTAH Support Team
"""

        # Create HTML body
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #4e73df; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; background-color: #f8f9fc; }}
        .reset-button {{ 
            display: inline-block; 
            background-color: #28a745; 
            color: white; 
            padding: 12px 24px; 
            text-decoration: none; 
            border-radius: 5px; 
            margin: 20px 0; 
        }}
        .footer {{ text-align: center; padding: 20px; color: #666; }}
        .warning {{ background-color: #fff3cd; border: 1px solid #ffeaa7; padding: 10px; border-radius: 5px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>Password Reset Request</h2>
        </div>
        <div class="content">
            <p>Dear {name},</p>
            
            <p>You have requested to reset your password for your TTAH account.</p>
            
            <p>Please click the button below to reset your password:</p>
            
            <a href="{reset_url}" class="reset-button">Reset Password</a>
            
            <div class="warning">
                <p><strong>Important:</strong> This link will expire in 1 hour for security reasons.</p>
            </div>
            
            <p>If you cannot click the button above, copy and paste this link into your browser:</p>
            <p>{reset_url}</p>
            
            <p>If you did not request this password reset, please ignore this email.</p>
        </div>
        <div class="footer">
            <p>Best regards,<br>TTAH Support Team</p>
        </div>
    </div>
</body>
</html>
"""
        
        return send_email(email, subject, body, html_body)
        
    except Exception as e:
        print(f"Error sending password reset email: {str(e)}")
        return False


@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        surname = request.form.get('surname', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        region = request.form.get('region', '').strip()
        role = request.form.get('role', '').strip()

        if not all([name, surname, email, password, region, role]):
            flash("All fields are required.", "error")
            return redirect(url_for('register'))

        # Validate role
        if not validate_role(role):
            flash("Invalid role. Must be one of: user, assignee, admin", "error")
            return redirect(url_for('register'))

        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        try:
            conn = get_db_connection()
            if not conn:
                flash("Database connection error.", "error")
                return redirect(url_for('register'))

            cur = conn.cursor()
            
            # Get default organization ID
            cur.execute("SELECT org_id FROM organizations WHERE org_slug = 'default-org'")
            default_org = cur.fetchone()
            
            if not default_org:
                flash("System error: Default organization not found.", "error")
                return redirect(url_for('register'))
            
            default_org_id = default_org[0]
            
            # Check organization user limits
            limits = check_organization_limits(default_org_id)
            if not limits.get('can_add_users', False):
                flash("Organization has reached maximum user limit.", "error")
                return redirect(url_for('register'))
            
            # Insert user with org_id
            cur.execute("""
                INSERT INTO users (org_id, name, surname, email, password_hash, region, role)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (default_org_id, name, surname, email, hashed_pw.decode('utf-8'), region, role))
            
            conn.commit()
            cur.close()
            conn.close()
            
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
            
        except psycopg2.IntegrityError:
            flash('Registration failed. Email may already exist.', 'error')
            print("DB error during registration: Email already exists")
            return redirect(url_for('register'))
        except Exception as e:
            flash('Registration failed. Please try again.', 'error')
            print("DB error during registration:", e)
            traceback.print_exc()
            return redirect(url_for('register'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not email or not password:
            flash("Email and password are required.", "error")
            return redirect(url_for('login'))

        conn = get_db_connection()
        if not conn:
            flash("Database connection failed.", "error")
            return redirect(url_for('login'))

        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT u.user_id, u.name, u.role, u.region, u.password_hash, u.org_id,
                       o.org_name, o.org_slug, o.subscription_tier, o.subscription_status
                FROM users u
                JOIN organizations o ON u.org_id = o.org_id
                WHERE u.email = %s
            """, (email,))
            user = cur.fetchone()
            cur.close()
            conn.close()
            
        except Exception as e:
            flash("Error during login.", "error")
            print("Login DB error:", e)
            traceback.print_exc()
            return redirect(url_for('login'))

        if user and bcrypt.checkpw(password.encode('utf-8'), user[4].encode('utf-8')):
            # Check if organization subscription is active
            if user[9] not in ['active', 'trial']:
                flash("Your organization's subscription has expired. Please contact support.", "error")
                return redirect(url_for('login'))
            
            session.clear() 
            session['user_id'] = user[0]
            session['name'] = user[1]
            session['role'] = user[2]
            session['region'] = user[3]
            session['org_id'] = user[5]  # Store org_id in session
            session['org_name'] = user[6]
            session['org_slug'] = user[7]
            session['subscription_tier'] = user[8]
            
            # Make session permanent to respect timeout configuration
            session.permanent = True

            if user[2] == 'user':
                return redirect(url_for('user_dashboard'))
            elif user[2] == 'assignee':
                return redirect(url_for('assignee_dashboard'))
            elif user[2] in ['admin']:
                return redirect(url_for('admin_dashboard'))
            else:
                flash("Unknown role. Contact support.", "error")
                return redirect(url_for('login'))
        else:
            flash("Invalid email or password.", "error")
        return redirect(url_for('login'))

    return render_template('login.html')



# Replace your existing forgot_password route with this:

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        
        if not email:
            flash("Email is required.", "error")
            return redirect(url_for('forgot_password'))
        
        try:
            conn = get_db_connection()
            if not conn:
                flash("Database connection failed. Please try again later.", "error")
                return redirect(url_for('forgot_password'))
            
            cur = conn.cursor()
            cur.execute("SELECT user_id, name, surname FROM users WHERE email = %s", (email,))
            user = cur.fetchone()
            
            if user:
                user_id, name, surname = user
                
                # Generate reset token
                reset_token = secrets.token_urlsafe(32)
                expires_at = datetime.now() + timedelta(hours=1)  # Token expires in 1 hour
                
                # Store token in database
                cur.execute("""
                    INSERT INTO password_reset_tokens (user_id, token, expires_at)
                    VALUES (%s, %s, %s)
                """, (user_id, reset_token, expires_at))
                
                conn.commit()
                
                # Send reset email
                full_name = f"{name} {surname}"
                email_sent = send_password_reset_email(email, full_name, reset_token)
                
                if email_sent:
                    flash("Password reset link has been sent to your email.", "success")
                else:
                    flash("Failed to send reset email. Please try again later.", "error")
            else:
                # Always show the same message regardless of whether email exists
                # This prevents email enumeration attacks
                flash("If this email is registered, a password reset link has been sent.", "info")
            
            cur.close()
            conn.close()
            
        except Exception as e:
            print("Forgot password error:", e)
            traceback.print_exc()
            flash("An error occurred. Please try again later.", "error")
        
        return redirect(url_for('forgot_password'))
    
    return render_template('forgot_password.html')

# Add this new route after your forgot_password route:

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if request.method == 'GET':
        # Validate token
        try:
            conn = get_db_connection()
            if not conn:
                flash("Database connection failed.", "error")
                return redirect(url_for('login'))
            
            cur = conn.cursor()
            cur.execute("""
                SELECT prt.user_id, u.name, u.surname
                FROM password_reset_tokens prt
                JOIN users u ON prt.user_id = u.user_id
                WHERE prt.token = %s AND prt.expires_at > NOW() AND prt.used = FALSE
            """, (token,))
            
            result = cur.fetchone()
            cur.close()
            conn.close()
            
            if not result:
                flash("Invalid or expired reset token.", "error")
                return redirect(url_for('forgot_password'))
            
            user_id, name, surname = result
            return render_template('reset_password.html', token=token, name=f"{name} {surname}")
            
        except Exception as e:
            print("Reset password GET error:", e)
            traceback.print_exc()
            flash("An error occurred. Please try again.", "error")
            return redirect(url_for('forgot_password'))
    
    elif request.method == 'POST':
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not password or not confirm_password:
            flash("Both password fields are required.", "error")
            return redirect(url_for('reset_password', token=token))
        
        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for('reset_password', token=token))
        
        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "error")
            return redirect(url_for('reset_password', token=token))
        
        try:
            conn = get_db_connection()
            if not conn:
                flash("Database connection failed.", "error")
                return redirect(url_for('login'))
            
            cur = conn.cursor()
            
            # Validate token again
            cur.execute("""
                SELECT user_id FROM password_reset_tokens
                WHERE token = %s AND expires_at > NOW() AND used = FALSE
            """, (token,))
            
            result = cur.fetchone()
            if not result:
                flash("Invalid or expired reset token.", "error")
                cur.close()
                conn.close()
                return redirect(url_for('forgot_password'))
            
            user_id = result[0]
            
            # Hash new password
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            
            # Update user password
            cur.execute("""
                UPDATE users SET password_hash = %s WHERE user_id = %s
            """, (hashed_password.decode('utf-8'), user_id))
            
            # Mark token as used
            cur.execute("""
                UPDATE password_reset_tokens SET used = TRUE WHERE token = %s
            """, (token,))
            
            conn.commit()
            cur.close()
            conn.close()
            
            flash("Password has been reset successfully. Please log in with your new password.", "success")
            return redirect(url_for('login'))
            
        except Exception as e:
            print("Reset password POST error:", e)
            traceback.print_exc()
            flash("An error occurred while resetting password. Please try again.", "error")
            return redirect(url_for('reset_password', token=token))

@app.route('/user_dashboard')
@require_org_context
def user_dashboard():
    
    if 'user_id' not in session or session.get('role') not in ['user', 'assignee']:
        flash('Access denied.', 'error')
        return redirect(url_for('login'))
    
    name = session.get('name')
    region = session.get('region')
    org_id = session.get('org_id')
    org_name = session.get('org_name', 'Your Organization')
    
    departments = get_organization_departments(org_id)

    user_id = session.get('user_id')

    try:
        conn = get_db_connection()
        if not conn:
            flash("Database connection failed.", "error")
            return redirect(url_for('login'))

        cur = conn.cursor()

        # Get user's region and name
        cur.execute("SELECT region, name FROM users WHERE user_id = %s", (user_id,))
        user_info = cur.fetchone()
        region = user_info[0] if user_info else None
        name = user_info[1] if user_info else None

        # Get all assignees and admins in user's region except self
        cur.execute("""
            SELECT user_id, name, surname
            FROM users
            WHERE role = 'assignee' AND region = %s AND user_id != %s
        """, (region, user_id))
        assignees = cur.fetchall()

        # Get user's submitted tickets with status 'open'
        cur.execute("""
            SELECT t.ticket_id, t.title, t.created_at, u.region,
                t.meter_number, t.account_number, t.description,
                a.name AS assigned_name, a.surname AS assigned_surname
            FROM tickets t
            JOIN users u ON t.created_by = u.user_id
            LEFT JOIN users a ON t.assigned_to = a.user_id
            WHERE t.created_by = %s AND LOWER(t.status) = 'open'
            ORDER BY t.created_at DESC
        """, (user_id,))
        submitted_tickets = cur.fetchall()

        cur.close()
        conn.close()

    except Exception as e:
        flash("Error loading dashboard data.", "error")
        print("Dashboard load error:", e)
        traceback.print_exc()
        assignees = []
        submitted_tickets = []
        name = None
        region = None

    return render_template('user_dashboard.html', 
                         name=name, 
                         region=region,
                         org_name=org_name)

# Replace your existing mark_closed function with this updated version:

@app.route('/mark_closed/<int:ticket_id>', methods=['POST'])
def mark_closed(ticket_id):
    if 'user_id' not in session or session.get('role') != 'assignee':
        return jsonify({"success": False, "message": "Unauthorized action."}), 403

    user_id = session['user_id']

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"success": False, "message": "Database connection failed."}), 500

        cur = conn.cursor()

        # Check if the ticket is assigned to this user
        cur.execute("SELECT status FROM tickets WHERE ticket_id = %s AND assigned_to = %s", (ticket_id, user_id))
        ticket = cur.fetchone()
        if not ticket:
            return jsonify({"success": False, "message": "Ticket not found or not assigned to you."}), 404

        # Update ticket status to 'closed' and set resolved_at timestamp
        cur.execute("""
            UPDATE tickets
            SET status = 'closed',
                resolved_at = NOW()
            WHERE ticket_id = %s
        """, (ticket_id,))

        # Add entry to ticket history
        cur.execute("""
            INSERT INTO ticket_history (ticket_id, action, name, role, performed_by, notes)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            ticket_id,
            'Marked closed',
            session['name'],
            session['role'],
            user_id,
            'Ticket marked as closed by assignee.'
        ))

        conn.commit()
        cur.close()
        conn.close()

        # NEW: Send email notification
        notify_ticket_action(ticket_id, 'closed')

        return jsonify({"success": True, "message": "Ticket marked as closed."}), 200

    except Exception as e:
        print("Mark closed error:", e)
        traceback.print_exc()
        return jsonify({"success": False, "message": "An error occurred while updating the ticket."}), 500

# Add this route to your app.py:

@app.route('/api/tickets/<int:ticket_id>/transfer_history', methods=['GET'])
def get_transfer_history(ticket_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500

        cur = conn.cursor()
        
        # Get transfer history for this ticket
        cur.execute("""
            SELECT 
                th.performed_at,
                th.notes,
                u.name as performed_by,
                u.role as performed_by_role
            FROM ticket_history th
            JOIN users u ON th.performed_by = u.user_id
            WHERE th.ticket_id = %s AND th.action = 'Transferred'
            ORDER BY th.performed_at DESC
        """, (ticket_id,))
        
        history = []
        for row in cur.fetchall():
            history.append({
                'performed_at': row[0].strftime('%Y-%m-%d %H:%M:%S') if row[0] else None,
                'notes': row[1],
                'performed_by': row[2],
                'performed_by_role': row[3]
            })

        cur.close()
        conn.close()
        
        return jsonify({'transfer_history': history})

    except Exception as e:
        print("Error fetching transfer history:", e)
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/assignee_dashboard')
@require_org_context
def assignee_dashboard():
    if 'user_id' not in session or session.get('role') != 'assignee':
        flash("Unauthorized access.", "error")
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    region = session.get('region')
    org_id = session.get('org_id')

    try:
        conn = get_db_connection()
        if not conn:
            flash("Database connection failed.", "error")
            assigned_tickets = []
            submitted_tickets = []
            closed_tickets = []
            transferred_tickets = []
            assignees_in_region = []
        else:
            cur = conn.cursor()

        user_id = session['user_id']
        region = session['region']

        # Assigned tickets (any status)
        cur.execute("""
            SELECT t.ticket_id, t.title, t.description, t.account_number, t.meter_number, 
                       t.status, t.created_at, t.resolved_at,
                       creator.name AS created_by_name, creator.surname AS created_by_surname
            FROM tickets t
            JOIN users creator ON t.created_by = creator.user_id
            WHERE t.assigned_to = %s 
                  AND t.org_id = %s
                  AND t.status IN ('open', 'in-progress', 'transferred')
                ORDER BY t.created_at DESC
        """, (user_id, org_id))
        assigned_tickets = cur.fetchall()

        # Submitted tickets in region with status 'open'
        cur.execute("""
            SELECT t.ticket_id, t.title, t.description, t.account_number, t.meter_number, 
                       t.status, t.created_at, t.resolved_at,
                       assignee.name AS assigned_to_name, assignee.surname AS assigned_to_surname
            FROM tickets t
            JOIN users assignee ON t.assigned_to = assignee.user_id
                WHERE t.created_by = %s 
                  AND t.org_id = %s
                  AND t.status IN ('open', 'in-progress', 'transferred')
                ORDER BY t.created_at DESC
            """, (user_id, org_id))
        submitted_tickets = cur.fetchall()

        # closed tickets in region
        cur.execute("""
                SELECT t.ticket_id, t.title, t.description, t.account_number, t.meter_number, 
                       t.status, t.created_at, t.resolved_at,
                       creator.name AS created_by_name, creator.surname AS created_by_surname,
                       assignee.name AS assigned_to_name, assignee.surname AS assigned_to_surname
                FROM tickets t
                JOIN users creator ON t.created_by = creator.user_id
                JOIN users assignee ON t.assigned_to = assignee.user_id
                WHERE (t.assigned_to = %s OR t.created_by = %s)
                  AND t.org_id = %s
                  AND t.status = 'closed'
                ORDER BY t.resolved_at DESC
            """, (user_id, user_id, org_id))
        closed_tickets = cur.fetchall()

        # Transferred tickets in region
        cur.execute("""
                SELECT DISTINCT t.ticket_id, t.title, t.description, t.account_number, 
                       t.meter_number, t.status, t.created_at, t.resolved_at,
                       current_assignee.name AS current_assigned_to_name,
                       current_assignee.surname AS current_assigned_to_surname,
                       creator.name AS created_by_name,
                       creator.surname AS created_by_surname,
                       th.notes AS transfer_reason,
                       th.performed_at AS transfer_date,
                       original_assignee.name AS transferred_by_name,
                       original_assignee.surname AS transferred_by_surname
                FROM tickets t
                JOIN users creator ON t.created_by = creator.user_id
                JOIN users current_assignee ON t.assigned_to = current_assignee.user_id
                JOIN ticket_history th ON t.ticket_id = th.ticket_id
                JOIN users original_assignee ON th.performed_by = original_assignee.user_id
                WHERE t.org_id = %s
                  AND creator.region = %s 
                  AND th.action = 'Transferred' 
                  AND th.performed_by = %s
                ORDER BY th.performed_at DESC
            """, (org_id, region, user_id))
        transferred_tickets = cur.fetchall()

        # Other assignees in region excluding self
        cur.execute("""
                SELECT user_id, name, surname 
                FROM users 
                WHERE role = 'assignee' 
                  AND region = %s 
                  AND org_id = %s
                  AND user_id != %s
                ORDER BY name
            """, (region, org_id, user_id))
        assignees_in_region = cur.fetchall()

        cur.close()
        conn.close()

    except Exception as e:
        flash("Error loading dashboard data.", "error")
        print("Assignee dashboard load error:", e)
        traceback.print_exc()
        assigned_tickets = []
        submitted_tickets = []
        closed_tickets = []
        transferred_tickets = []
        assignees_in_region = []

    name = session.get('name')
    region = session.get('region')

    return render_template(
    'assignee_dashboard.html',
    assigned_tickets=assigned_tickets,
    submitted_tickets=submitted_tickets,
    closed_tickets=closed_tickets,
    transferred_tickets=transferred_tickets,
    assignees=assignees_in_region,
    name=name,
    region=region,
    org_name=session.get('org_name', 'Your Organization')  # ADD THIS
) 



@app.route('/submit_ticket', methods=['POST'])
@require_org_context
def submit_ticket():
    if 'user_id' not in session:
        return jsonify({'error': 'You must be logged in to submit a ticket.'}), 401

    org_id = session.get('org_id')

    limits = check_organization_limits(org_id)
    if not limits.get('can_create_tickets', False):
        flash(f'Your organization has reached its monthly ticket limit ({limits.get("max_tickets_per_month", 0)} tickets). Please upgrade your plan.', 'error')
        return redirect_to_dashboard()
    
    # Get basic form data
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    assigned_to = request.form.get('assigned_to', '').strip()
    ticket_type = request.form.get('ticket_type', 'meter').strip()
    
    # Get type-specific data
    if ticket_type == 'meter':
        account_number = request.form.get('account_number', '').strip()
        meter_number = request.form.get('meter_number', '').strip()
        category = None
        location = None
        contact_info = None
        
        # Validate meter-specific fields
        if not all([title, description, account_number, meter_number, assigned_to]):
            flash('All fields are required for meter tickets.', 'error')
            return redirect_to_dashboard()
            
        # Account number validation for meter tickets
        if not account_number.isdigit():
            flash('Account number must contain only numbers.', 'error')
            return redirect_to_dashboard()
            
        if len(account_number) < 3 or len(account_number) > 15:
            flash('Account number must be between 3 and 15 digits long.', 'error')
            return redirect_to_dashboard()
            
        try:
            account_number_int = int(account_number)
        except ValueError:
            flash('Invalid account number format.', 'error')
            return redirect_to_dashboard()
    
    else:  # general ticket
        account_number = None
        meter_number = None
        category = request.form.get('category', '').strip()
        location = request.form.get('location', '').strip() or None
        contact_info = request.form.get('contact_info', '').strip() or None
        account_number_int = None
        
        # Validate general ticket fields
        if not all([title, description, category, assigned_to]):
            flash('Title, description, category, and assignee are required for general tickets.', 'error')
            return redirect_to_dashboard()

    # Handle file upload (same for both types)
    attachment = request.files.get('attachment')
    attachment_path = None
    if attachment and attachment.filename != '':
        if allowed_file(attachment.filename):
            filename = secure_filename(attachment.filename)
            unique_prefix = str(uuid.uuid4())
            filename = f"{unique_prefix}_{filename}"
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            attachment.save(save_path)
            attachment_path = filename
        else:
            flash('Invalid file type for attachment.', 'error')
            return redirect_to_dashboard()

    try:
        conn = get_db_connection()
        if not conn:
            flash('Database connection failed. Please try again.', 'error')
            return redirect_to_dashboard()
            
        cur = conn.cursor()

        # Insert ticket with type-specific data
        cur.execute("""
            INSERT INTO tickets (
                org_id, title, description, ticket_type, account_number, meter_number, 
                category, location, contact_info, status, created_by, assigned_to, 
                created_at, attachment_path
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'open', %s, %s, NOW(), %s)
            RETURNING ticket_id
        """, (
            org_id,  # ADD THIS LINE
            title, description, ticket_type, account_number_int, meter_number,
            category, location, contact_info, session['user_id'], assigned_to, attachment_path
        ))
        
        ticket_id = cur.fetchone()[0]

        # Log ticket submission in history
        ticket_type_display = "Meter" if ticket_type == 'meter' else "General"
        
        cur.execute("""
            INSERT INTO ticket_history (ticket_id, action, name, role, performed_by, notes, performed_at)
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        """, (
            ticket_id, 'Created', session['name'], session['role'], 
            session['user_id'], f'Ticket created and assigned'
        ))

        conn.commit()
        cur.close()
        conn.close()

        # Send email notification
        notify_ticket_action(ticket_id, 'created')

        flash(f'{ticket_type_display} ticket submitted successfully!', 'success')
        return redirect_to_dashboard()

    except Exception as e:
        print("Submit ticket error:", e)
        traceback.print_exc()
        flash('An error occurred while submitting the ticket. Please try again.', 'error')
        return redirect_to_dashboard()

def redirect_to_dashboard():
    """Helper function to redirect based on user role"""
    if session.get('role') == 'assignee':
        return redirect(url_for('assignee_dashboard'))
    else:
        return redirect(url_for('user_dashboard'))
    
@app.route('/api/user_tickets', methods=['GET'])
@require_org_context
def get_user_tickets():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    user_id = session['user_id']
    org_id = session.get('org_id')

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Updated query with org_id filter
        cur.execute("""
            SELECT t.ticket_id, t.title, t.description, t.account_number, t.meter_number, 
                   t.status, t.created_at, t.resolved_at,
                   at.name AS assigned_to_name, at.surname AS assigned_to_surname,
                   cb.name AS created_by_name,
                   cb.surname AS created_by_surname,
                   th.performed_by AS transferred_by_id,
                   transfer_user.name AS transferred_by_name,
                   transfer_user.surname AS transferred_by_surname,
                   th.performed_at AS transferred_at,
                   th.notes AS transfer_notes,
                   t.attachment_path
            FROM tickets t
            LEFT JOIN users at ON t.assigned_to = at.user_id
            LEFT JOIN users cb ON t.created_by = cb.user_id
            LEFT JOIN (
                SELECT DISTINCT ON (ticket_id) 
                       ticket_id, performed_by, performed_at, notes
                FROM ticket_history 
                WHERE action = 'Transferred'
                ORDER BY ticket_id, performed_at DESC
            ) th ON t.ticket_id = th.ticket_id
            LEFT JOIN users transfer_user ON th.performed_by = transfer_user.user_id
            WHERE t.created_by = %s AND t.org_id = %s
            ORDER BY t.created_at DESC
        """, (user_id, org_id))

        all_tickets = cur.fetchall()

        # Separate into submitted (open/in-progress/transferred) and closed
        submitted_tickets = []
        closed_tickets = []

        for ticket in all_tickets:
            formatted_ticket = {
                'ticket_id': ticket[0],
                'title': ticket[1],
                'description': ticket[2],
                'account_number': ticket[3],
                'meter_number': ticket[4],
                'status': ticket[5],
                'created_at': ticket[6].strftime('%Y-%m-%d %H:%M:%S') if ticket[6] else None,
                'resolved_at': ticket[7].strftime('%Y-%m-%d %H:%M:%S') if ticket[7] else None,
                'assigned_to_name': f"{ticket[8]} {ticket[9]}" if ticket[8] and ticket[9] else ticket[8] or "Unassigned",
                'created_by_name': f"{ticket[10]} {ticket[11]}" if ticket[10] and ticket[11] else ticket[10] or "Unknown",
                'transferred_by_name': f"{ticket[13]} {ticket[14]}" if ticket[13] and ticket[14] else None,
                'transferred_at': ticket[15].strftime('%Y-%m-%d %H:%M:%S') if ticket[15] else None,
                'transfer_notes': ticket[16],
                'attachment_path': ticket[17]
            }

            # Include transferred tickets in submitted tickets section
            if ticket[5].lower() == 'closed':
                closed_tickets.append(formatted_ticket)
            else:
                # This will include 'open', 'transferred', 'in-progress', etc.
                submitted_tickets.append(formatted_ticket)

        cur.close()
        conn.close()

        return jsonify({
            'in_progress_tickets': submitted_tickets,
            'closed_tickets': closed_tickets
        })

    except Exception as e:
        print("Error fetching user tickets:", e)
        traceback.print_exc()
        return jsonify({'error': 'Error fetching tickets'}), 500

    
@app.route('/api/submitted_tickets', methods=['GET'])
@require_org_context
def get_submitted_tickets():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    user_id = session['user_id']
    org_id = session.get('org_id')

    print(f"=== SUBMITTED TICKETS DEBUG ===")
    print(f"Current user requesting: {session.get('name')}")
    print(f"User ID in session: {session.get('user_id')} (type: {type(session.get('user_id'))})")
    print(f"User role: {session.get('role')}")
    print(f"===============================")

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT t.ticket_id, t.title, t.description, t.account_number, t.meter_number, 
                   t.status, t.created_at, t.resolved_at,
                   at.name AS assigned_to_name, at.surname AS assigned_to_surname,
                   cb.name AS created_by_name,
                   cb.surname AS created_by_surname,
                   th.performed_by AS transferred_by_id,
                   transfer_user.name AS transferred_by_name,
                   transfer_user.surname AS transferred_by_surname,
                   th.performed_at AS transferred_at,
                   th.notes AS transfer_notes,
                   t.attachment_path
            FROM tickets t
            LEFT JOIN users at ON t.assigned_to = at.user_id
            LEFT JOIN users cb ON t.created_by = cb.user_id
            LEFT JOIN (
                SELECT DISTINCT ON (ticket_id) 
                       ticket_id, performed_by, performed_at, notes
                FROM ticket_history 
                WHERE action = 'Transferred'
                ORDER BY ticket_id, performed_at DESC
            ) th ON t.ticket_id = th.ticket_id
            LEFT JOIN users transfer_user ON th.performed_by = transfer_user.user_id
            WHERE t.created_by = %s AND t.org_id = %s AND LOWER(t.status) != 'closed'
            ORDER BY t.created_at DESC
        """, (user_id, org_id))
        
        submitted_tickets = cur.fetchall()

        def format_tickets(tickets):
            return [{
                'ticket_id': t[0],
                'title': t[1],
                'description': t[2],
                'account_number': t[3],
                'meter_number': t[4],
                'status': t[5],
                'created_at': t[6].strftime('%Y-%m-%d %H:%M:%S') if t[6] else None,
                'resolved_at': t[7].strftime('%Y-%m-%d %H:%M:%S') if t[7] else None,
                'assigned_to_name': f"{t[8]} {t[9]}" if t[8] and t[9] else t[8] or "Unassigned",
                'created_by_name': f"{t[10]} {t[11]}" if t[10] and t[11] else t[10] or "Unknown",
                'transferred_by_name': f"{t[13]} {t[14]}" if t[13] and t[14] else None,
                'transferred_at': t[15].strftime('%Y-%m-%d %H:%M:%S') if t[15] else None,
                'transfer_notes': t[16],
                'attachment_path': t[17]
            } for t in tickets]
        
        cur.close()
        conn.close()
        
        return jsonify({'submitted_tickets': format_tickets(submitted_tickets)})
        
    except Exception as e:
        print("Error fetching submitted tickets:", e)
        traceback.print_exc()
        return jsonify({'error': 'Error fetching tickets'}), 500
    
@app.route('/api/closed_tickets', methods=['GET'])
@require_org_context
def get_closed_tickets():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    user_id = session['user_id']
    org_id = session.get('org_id')

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT t.ticket_id, t.title, t.description, t.account_number, t.meter_number, 
                   t.status, t.created_at, t.resolved_at,
                   at.name AS assigned_to_name, at.surname AS assigned_to_surname,
                   cb.name AS created_by_name,
                   cb.surname AS created_by_surname,
                   th.performed_by AS transferred_by_id,
                   transfer_user.name AS transferred_by_name,
                   transfer_user.surname AS transferred_by_surname,
                   th.performed_at AS transferred_at,
                   th.notes AS transfer_notes,
                   t.attachment_path
            FROM tickets t
            LEFT JOIN users at ON t.assigned_to = at.user_id
            LEFT JOIN users cb ON t.created_by = cb.user_id
            LEFT JOIN (
                SELECT DISTINCT ON (ticket_id) 
                       ticket_id, performed_by, performed_at, notes
                FROM ticket_history 
                WHERE action = 'Transferred'
                ORDER BY ticket_id, performed_at DESC
            ) th ON t.ticket_id = th.ticket_id
            LEFT JOIN users transfer_user ON th.performed_by = transfer_user.user_id
            WHERE (t.created_by = %s OR t.assigned_to = %s) 
              AND t.org_id = %s 
              AND t.status = 'closed'
            ORDER BY t.created_at DESC
        """, (user_id, user_id, org_id))
        
        tickets = cur.fetchall()

        def format_tickets(tickets):
            return [{
                'ticket_id': t[0],
                'title': t[1],
                'description': t[2],
                'account_number': t[3],
                'meter_number': t[4],
                'status': t[5],
                'created_at': t[6].strftime('%Y-%m-%d %H:%M:%S') if t[6] else None,
                'resolved_at': t[7].strftime('%Y-%m-%d %H:%M:%S') if t[7] else None,
                'assigned_to_name': f"{t[8]} {t[9]}" if t[8] and t[9] else t[8] or "Unassigned",
                'created_by_name': f"{t[10]} {t[11]}" if t[10] and t[11] else t[10] or "Unknown",
                'transferred_by_name': f"{t[13]} {t[14]}" if t[13] and t[14] else None,
                'transferred_at': t[15].strftime('%Y-%m-%d %H:%M:%S') if t[15] else None,
                'transfer_notes': t[16],
                'attachment_path': t[17]
            } for t in tickets]

        cur.close()
        conn.close()
        
        return jsonify({'closed_tickets': format_tickets(tickets)})
        
    except Exception as e:
        print("Error fetching closed tickets:", e)
        traceback.print_exc()
        return jsonify({'error': 'Error fetching tickets'}), 500

# Find your transfer_ticket function and add this line at the end, before the return statement:

@app.route('/api/tickets/<int:ticket_id>/transfer', methods=['POST'])
def transfer_ticket(ticket_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    data = request.json
    new_assignee_id = data.get('assignee_id')
    reason = data.get('reason', '')

    if not new_assignee_id:
        return jsonify({'error': 'assignee_id is required'}), 400

    try:
        new_assignee_id = int(new_assignee_id)
    except (ValueError, TypeError):
        return jsonify({'error': 'assignee_id must be a valid integer'}), 400

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
            
        cur = conn.cursor()

        # Get new assignee info
        cur.execute("SELECT user_id, name FROM users WHERE user_id = %s", (new_assignee_id,))
        new_assignee = cur.fetchone()
        if not new_assignee:
            return jsonify({'error': 'Selected assignee does not exist'}), 400

        # Get current ticket info
        cur.execute("""
            SELECT assigned_to, status, title 
            FROM tickets 
            WHERE ticket_id = %s
        """, (ticket_id,))
        ticket = cur.fetchone()
        if not ticket:
            return jsonify({'error': 'Ticket not found'}), 404

        current_assignee_id = ticket[0]
        if current_assignee_id == new_assignee_id:
            return jsonify({'error': 'Ticket is already assigned to this user'}), 400

        # Get previous assignee name
        if current_assignee_id:
            cur.execute("SELECT name FROM users WHERE user_id = %s", (current_assignee_id,))
            prev_assignee_row = cur.fetchone()
            prev_assignee_name = prev_assignee_row[0] if prev_assignee_row else "Unassigned"
        else:
            prev_assignee_name = "Unassigned"

        # Update ticket: change assignee and set status to 'transferred'
        cur.execute("""
            UPDATE tickets 
            SET assigned_to = %s, status = 'transferred', updated_at = CURRENT_TIMESTAMP
            WHERE ticket_id = %s
        """, (new_assignee_id, ticket_id))

        # Log the transfer in ticket_history
        transfer_note = f"Transferred from {prev_assignee_name} to {new_assignee[1]} (ID: {new_assignee_id})"
        if reason:
            transfer_note += f" - Reason: {reason}"

        cur.execute("""
            INSERT INTO ticket_history (ticket_id, action, name, role, performed_by, notes, performed_at)
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        """, (
            ticket_id,
            'Transferred',
            session['name'],
            session['role'],
            session['user_id'],
            transfer_note
        ))

        conn.commit()
        cur.close()
        conn.close()

        # NEW: Send email notification for transfer
        notify_ticket_action(ticket_id, 'transferred')

        return jsonify({
            'message': 'Ticket transferred successfully',
            'transferred_to': new_assignee[1],
            'ticket_id': ticket_id
        }), 200

    except Exception as e:
        print(f"Transfer ticket error: {e}")
        traceback.print_exc()
        if conn:
            conn.rollback()
            conn.close()
        return jsonify({'error': 'An error occurred while transferring the ticket'}), 500
    
@app.route('/api/transferred_tickets', methods=['GET'])
@require_org_context
def get_transferred_tickets():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    user_id = session['user_id']
    region = session['region']
    org_id = session.get('org_id')
    
    print(f"DEBUG: Looking for transfers by user_id={user_id}, region={region}")

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT DISTINCT 
                t.ticket_id, t.title, t.description, t.account_number, t.meter_number, 
                t.status, t.created_at, t.resolved_at,
                current_assignee.name AS current_assigned_to_name, 
                current_assignee.surname AS current_assigned_to_surname,
                cb.name AS created_by_name, cb.surname AS created_by_surname,
                th.notes AS transfer_reason,
                th.performed_at AS transfer_date,
                original_assignee.name AS transferred_by_name, 
                original_assignee.surname AS transferred_by_surname
            FROM tickets t
            JOIN ticket_history th ON t.ticket_id = th.ticket_id 
            JOIN users u ON t.created_by = u.user_id
            LEFT JOIN users current_assignee ON t.assigned_to = current_assignee.user_id
            LEFT JOIN users cb ON t.created_by = cb.user_id
            LEFT JOIN users original_assignee ON th.performed_by = original_assignee.user_id
            WHERE t.org_id = %s
              AND u.region = %s 
              AND th.action = 'Transferred' 
              AND th.performed_by = %s
            ORDER BY th.performed_at DESC
        """, (org_id, region, user_id))

        transferred_tickets = cur.fetchall()
        print(f"DEBUG: Query returned {len(transferred_tickets) if transferred_tickets else 0} tickets")
        
        if transferred_tickets:
            print(f"DEBUG: First ticket: {transferred_tickets[0]}")

        def format_tickets(tickets):
            if not tickets:
                return []
            return [{
                'ticket_id': t[0],
                'title': t[1],
                'description': t[2],
                'account_number': t[3],
                'meter_number': t[4],
                'status': t[5],
                'created_at': t[6].strftime('%Y-%m-%d %H:%M:%S') if t[6] else None,
                'resolved_at': t[7].strftime('%Y-%m-%d %H:%M:%S') if t[7] else None,
                'current_assigned_to_name': f"{t[8]} {t[9]}" if t[8] and t[9] else t[8] or "Unassigned",
                'created_by_name': f"{t[10]} {t[11]}" if t[10] and t[11] else t[10] or "Unknown",
                'transfer_reason': t[12],
                'transfer_date': t[13].strftime('%Y-%m-%d %H:%M:%S') if t[13] else None,
                'transferred_by_name': f"{t[14]} {t[15]}" if t[14] and t[15] else t[14] or "Unknown"
            } for t in tickets]
        
        formatted_tickets = format_tickets(transferred_tickets)
        print(f"DEBUG: Formatted {len(formatted_tickets)} tickets")

        cur.close()
        conn.close()

        return jsonify({'transferred_tickets': formatted_tickets})

    except Exception as e:
        print("Error fetching transferred tickets:", e)
        traceback.print_exc()
        return jsonify({'error': 'Error fetching tickets'}), 500

# Find your update_ticket_status function and add this line before the return statement:

@app.route('/api/tickets/<int:ticket_id>/status', methods=['PUT'])
def update_ticket_status(ticket_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed.'}), 500

        data = request.get_json()
        new_status = data.get('status', '').lower()

        # Validate status using our helper function
        if not validate_status(new_status):
            return jsonify({'error': 'Invalid status. Must be one of: open, in-progress, transferred, closed'}), 400

        cur = conn.cursor()
        
        # Check if ticket exists and user has permission to update it
        cur.execute("""
            SELECT t.ticket_id, t.status, t.assigned_to, t.created_by 
            FROM tickets t 
            WHERE t.ticket_id = %s
        """, (ticket_id,))
        ticket = cur.fetchone()
        
        if not ticket:
            cur.close()
            conn.close()
            return jsonify({'error': 'Ticket not found'}), 404

        # Check permissions (only assignee, creator, or admin can update status)
        user_id = session['user_id']
        user_role = session['role']
        ticket_assigned_to = ticket[2]
        ticket_created_by = ticket[3]
        
        if user_role != 'admin' and user_id != ticket_assigned_to and user_id != ticket_created_by:
            return jsonify({'error': 'You do not have permission to update this ticket'}), 403

        # Update ticket status and resolved_at if closed
        if new_status == 'closed':
            cur.execute("""
                UPDATE tickets 
                SET status = %s, resolved_at = NOW(), updated_at = CURRENT_TIMESTAMP
                WHERE ticket_id = %s
            """, (new_status, ticket_id))
        else:
            cur.execute("""
                UPDATE tickets 
                SET status = %s, resolved_at = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE ticket_id = %s
            """, (new_status, ticket_id))

        # Log the status change in history
        cur.execute("""
            INSERT INTO ticket_history (ticket_id, action, name, role, performed_by, notes)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            ticket_id,
            f'Status changed to {new_status}',
            session['name'],
            session['role'],
            user_id,
            f'Ticket status updated to {new_status}'
        ))

        conn.commit()
        cur.close()
        conn.close()

        # NEW: Send email notification for status change
        if new_status == 'closed':
            notify_ticket_action(ticket_id, 'closed')
        elif new_status == 'in-progress':
            notify_ticket_action(ticket_id, 'in-progress')
        else:
            notify_ticket_action(ticket_id, 'status_changed')

        return jsonify({'message': 'Status updated successfully', 'new_status': new_status})

    except Exception as e:
        print(f"Error updating ticket status: {e}")
        traceback.print_exc()
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return jsonify({'error': 'Internal server error while updating ticket status.'}), 500
    
# Replace your get_assigned_tickets route with this fixed version:

@app.route('/api/assigned_tickets', methods=['GET'])
@require_org_context
def get_assigned_tickets():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    user_id = session['user_id']
    org_id = session.get('org_id')

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Updated query to include surnames for all name fields
        cur.execute("""
            SELECT t.ticket_id, t.title, t.description, t.account_number, t.meter_number, 
                   t.status, t.created_at, t.resolved_at,
                   at.name AS assigned_to_name, at.surname AS assigned_to_surname,
                   cb.name AS created_by_name,
                   cb.surname AS created_by_surname,
                   th.performed_by AS transferred_by_id,
                   transfer_user.name AS transferred_by_name,
                   transfer_user.surname AS transferred_by_surname,
                   th.performed_at AS transferred_at,
                   th.notes AS transfer_notes,
                   t.attachment_path
            FROM tickets t
            LEFT JOIN users at ON t.assigned_to = at.user_id
            LEFT JOIN users cb ON t.created_by = cb.user_id
            LEFT JOIN (
                SELECT DISTINCT ON (ticket_id) 
                       ticket_id, performed_by, performed_at, notes
                FROM ticket_history 
                WHERE action = 'Transferred'
                ORDER BY ticket_id, performed_at DESC
            ) th ON t.ticket_id = th.ticket_id
            LEFT JOIN users transfer_user ON th.performed_by = transfer_user.user_id
            WHERE t.assigned_to = %s AND t.org_id = %s AND t.status != 'closed'
            ORDER BY t.created_at DESC
        """, (user_id, org_id))

        assigned_tickets = cur.fetchall()

        def format_tickets(tickets):
            return [{
                'ticket_id': t[0],
                'title': t[1],
                'description': t[2],
                'account_number': t[3],
                'meter_number': t[4],
                'status': t[5],
                'created_at': t[6].strftime('%Y-%m-%d %H:%M:%S') if t[6] else None,
                'resolved_at': t[7].strftime('%Y-%m-%d %H:%M:%S') if t[7] else None,
                'assigned_to_name': f"{t[8]} {t[9]}" if t[8] and t[9] else t[8] or "Unassigned",
                'created_by_name': f"{t[10]} {t[11]}" if t[10] and t[11] else t[10] or "Unknown",
                'transferred_by_name': f"{t[13]} {t[14]}" if t[13] and t[14] else None,
                'transferred_at': t[15].strftime('%Y-%m-%d %H:%M:%S') if t[15] else None,
                'transfer_notes': t[16],
                'attachment_path': t[17]
            } for t in tickets]
        
        cur.close()
        conn.close()

        return jsonify({'assigned_tickets': format_tickets(assigned_tickets)})

    except Exception as e:
        print("Error fetching assigned tickets:", e)
        traceback.print_exc()
        return jsonify({'error': 'Error fetching tickets'}), 500


    
@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.clear()
    
    # Handle AJAX requests differently
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        flash("You have been logged out successfully.", "info")
        return jsonify({"success": True, "redirect": url_for('login')})
    else:
        flash("You have been logged out successfully.", "info")
        return redirect(url_for('login'))

@app.route('/admin/dashboard')
@require_org_context
def admin_dashboard():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('login'))
    
    org_id = session.get('org_id')

    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get total tickets
    cur.execute("SELECT COUNT(*) FROM tickets WHERE org_id = %s", (org_id,))
    total = cur.fetchone()[0]
    
    # Get open tickets
    cur.execute("SELECT COUNT(*) FROM tickets WHERE org_id = %s AND LOWER(status) = 'open'", (org_id,))
    open_count = cur.fetchone()[0]
    
    # Get in-progress tickets
    cur.execute("SELECT COUNT(*) FROM tickets WHERE org_id = %s AND LOWER(status) = 'in-progress'", (org_id,))
    in_progress = cur.fetchone()[0]
    
    # Get transferred tickets
    cur.execute("SELECT COUNT(*) FROM tickets WHERE org_id = %s AND LOWER(status) = 'transferred'", (org_id,))
    transferred = cur.fetchone()[0]
    
    # Get completed tickets
    cur.execute("SELECT COUNT(*) FROM tickets WHERE org_id = %s AND LOWER(status) IN ('completed', 'closed')", (org_id,))
    completed = cur.fetchone()[0]
    
    cur.close()
    conn.close()

    return render_template(
        'admin_dashboard.html',
        total=total,
        open=open_count,
        inProgress=in_progress,
        transferred=transferred,
        completed=completed
    )

@app.route('/admin/users')
def admin_users():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect('/login')
    return render_template('admin_users.html')

@app.route('/admin/settings')
def admin_settings():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect('/login')
    
    try:
        conn = get_db_connection()
        if not conn:
            flash('Database connection failed', 'error')
            return redirect('/admin/dashboard')

        cur = conn.cursor()
        
        # Get counts for system overview
        cur.execute("SELECT COUNT(*) FROM users WHERE role IN ('user', 'assignee')")
        total_users = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM users WHERE role IN ('admin')")
        total_admins = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM tickets")
        total_tickets = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM announcements WHERE is_active = true")
        active_announcements = cur.fetchone()[0]
        
        # Get regions for dropdown
        cur.execute("SELECT DISTINCT region FROM users WHERE region IS NOT NULL ORDER BY region")
        regions = [row[0] for row in cur.fetchall()]
        
        cur.close()
        conn.close()
        
        return render_template('admin_settings.html', 
                             total_users=total_users,
                             total_admins=total_admins,
                             total_tickets=total_tickets,
                             active_announcements=active_announcements,
                             regions=regions)
    
    except Exception as e:
        print("Error loading admin settings:", e)
        flash('Error loading settings', 'error')
        return redirect('/admin/dashboard')

@app.route('/api/admin/users')
@require_org_context
def get_users():
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401

    org_id = session.get('org_id')

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500

        cur = conn.cursor()
        
        # Get all users with their ticket counts
        cur.execute("""
            SELECT 
                u.user_id,
                u.name,
                u.surname,
                u.email,
                u.region,
                u.role,
                u.created_at,
                COUNT(DISTINCT t.ticket_id) as total_tickets,
                COUNT(DISTINCT CASE WHEN t.status = 'open' THEN t.ticket_id END) as open_tickets,
                COUNT(DISTINCT CASE WHEN t.status = 'closed' THEN t.ticket_id END) as closed_tickets
            FROM users u
            LEFT JOIN tickets t ON u.user_id = t.created_by
            WHERE u.org_id = %s
            GROUP BY u.user_id
            ORDER BY u.created_at DESC
        """, (org_id,))
        
        users = []
        for row in cur.fetchall():
            users.append({
                'user_id': row[0],
                'name': f"{row[1]} {row[2]}",
                'email': row[3],
                'region': row[4],
                'role': row[5],
                'created_at': row[6].strftime('%Y-%m-%d %H:%M:%S'),
                'total_tickets': row[7],
                'open_tickets': row[8],
                'closed_tickets': row[9]
            })

        cur.close()
        conn.close()

        return jsonify({'users': users})

    except Exception as e:
        print("Error fetching users:", e)
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/admin/users/<int:user_id>/tickets')
def admin_get_user_tickets(user_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500

        cur = conn.cursor()
        
        # Get user's tickets with history
        cur.execute("""
            WITH ticket_history_agg AS (
                SELECT 
                    ticket_id,
                    json_agg(
                        json_build_object(
                            'action', action,
                            'performed_by', u.name,
                            'performed_at', th.performed_at,
                            'notes', notes
                        ) ORDER BY th.performed_at DESC
                    ) as history
                FROM ticket_history th
                JOIN users u ON th.performed_by = u.user_id
                GROUP BY ticket_id
            )
            SELECT 
                t.ticket_id,
                t.title,
                t.description,
                t.status,
                t.created_at,
                t.resolved_at,
                th.history
            FROM tickets t
            LEFT JOIN ticket_history_agg th ON t.ticket_id = th.ticket_id
            WHERE t.created_by = %s
            ORDER BY t.created_at DESC
        """, (user_id,))
        
        tickets = []
        for row in cur.fetchall():
            tickets.append({
                'ticket_id': row[0],
                'title': row[1],
                'description': row[2],
                'status': row[3],
                'created_at': row[4].strftime('%Y-%m-%d %H:%M:%S'),
                'resolved_at': row[5].strftime('%Y-%m-%d %H:%M:%S') if row[5] else None,
                'history': row[6] if row[6] else []
            })

        cur.close()
        conn.close()

        return jsonify({'tickets': tickets})

    except Exception as e:
        print("Error fetching user tickets:", e)
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/admin/chart-data')
@require_org_context
def get_chart_data():
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401

    region_filter = request.args.get('region', '')
    org_id = session.get('org_id')

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500

        cur = conn.cursor()
        
        base_query = """
            FROM tickets t
            JOIN users u ON t.created_by = u.user_id
            WHERE t.org_id = %s
        """
        
        params = [org_id]
        
        if region_filter:
            base_query += " AND u.region = %s"
            params.append(region_filter)
        
        # Get ticket distribution data
        distribution_query = f"""
            SELECT 
                t.status,
                COUNT(*) as count
            {base_query}
            GROUP BY t.status
        """
        cur.execute(distribution_query, params)
        distribution_data = cur.fetchall()
        
        # Get ticket trends data
        trends_query = f"""
            SELECT 
                DATE_TRUNC('month', t.created_at) as month,
                COUNT(*) as count
            {base_query}
            AND t.created_at >= NOW() - INTERVAL '6 months'
            GROUP BY DATE_TRUNC('month', t.created_at)
            ORDER BY month ASC
        """
        cur.execute(trends_query, params)
        trends_data = cur.fetchall()

        distribution = {
            'labels': [],
            'data': []
        }
        status_map = {'closed': 'Completed'}
        for status, count in distribution_data:
            mapped_status = status_map.get(status.lower(), status)
            if mapped_status in distribution['labels']:
                idx = distribution['labels'].index(mapped_status)
                distribution['data'][idx] += count
            else:
                distribution['labels'].append(mapped_status)
                distribution['data'].append(count)

        trends = {
            'labels': [],
            'data': []
        }
        for month, count in trends_data:
            formatted_month = month.strftime('%b %Y')
            trends['labels'].append(formatted_month)
            trends['data'].append(count)

        cur.close()
        conn.close()

        return jsonify({
            'distribution': distribution,
            'trends': trends,
            'region_filter': region_filter
        })

    except Exception as e:
        print("Error fetching chart data:", e)
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/admin/regions')
def get_regions():
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500

        cur = conn.cursor()
        
        # Get all unique regions from users table
        cur.execute("""
            SELECT DISTINCT region 
            FROM users 
            WHERE region IS NOT NULL AND region != ''
            ORDER BY region
        """)
        
        regions = [row[0] for row in cur.fetchall()]
        
        cur.close()
        conn.close()

        return jsonify({'regions': regions})

    except Exception as e:
        print("Error fetching regions:", e)
        traceback.print_exc()
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/admin/dashboard-stats')
@require_org_context
def get_dashboard_stats():
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401

    # Get region filter from query parameters
    region_filter = request.args.get('region', '')
    org_id = session.get('org_id')

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500

        cur = conn.cursor()
        
        base_query = """
            SELECT COUNT(*) FROM tickets t
            JOIN users u ON t.created_by = u.user_id
            WHERE t.org_id = %s
        """
        
        params = [org_id]
        region_clause = ""
        
        if region_filter:
            region_clause = " AND u.region = %s"
            params.append(region_filter)
        
        # Get total tickets
        cur.execute(base_query + region_clause, params)
        total = cur.fetchone()[0]
        
        # Get open tickets
        cur.execute(base_query + region_clause + " AND LOWER(t.status) = 'open'", params + [region_filter] if region_filter else params)
        open_count = cur.fetchone()[0]
        
        # Get in-progress tickets
        cur.execute(base_query + region_clause + " AND LOWER(t.status) = 'in-progress'", params + [region_filter] if region_filter else params)
        in_progress = cur.fetchone()[0]
        
        # Get transferred tickets
        cur.execute(base_query + region_clause + " AND LOWER(t.status) = 'transferred'", params + [region_filter] if region_filter else params)
        transferred = cur.fetchone()[0]
        
        # Get completed tickets
        cur.execute(base_query + region_clause + " AND LOWER(t.status) IN ('completed', 'closed')", params + [region_filter] if region_filter else params)
        completed = cur.fetchone()[0]

        cur.close()
        conn.close()

        return jsonify({
            'total': total,
            'open': open_count,
            'inProgress': in_progress,
            'transferred': transferred,
            'completed': completed,
            'region_filter': region_filter
        })

    except Exception as e:
        print("Error fetching dashboard stats:", e)
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/admin/recent-activity')
def get_recent_activity():
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401

    # Get region filter from query parameters
    region_filter = request.args.get('region', '')

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500

        cur = conn.cursor()
        
        # Get recent ticket history with user information and optional region filter
        activity_query = """
            SELECT 
                th.action,
                th.notes,
                th.performed_at,
                u.name,
                t.title as ticket_title,
                creator.region
            FROM ticket_history th
            JOIN users u ON th.performed_by = u.user_id
            JOIN tickets t ON th.ticket_id = t.ticket_id
            JOIN users creator ON t.created_by = creator.user_id
        """
        
        if region_filter:
            activity_query += " WHERE creator.region = %s"
            cur.execute(activity_query + " ORDER BY th.performed_at DESC LIMIT 10", (region_filter,))
        else:
            cur.execute(activity_query + " ORDER BY th.performed_at DESC LIMIT 10")
        
        activities = []
        for row in cur.fetchall():
            action, notes, timestamp, user_name, ticket_title, region = row
            
            # Map actions to icons
            icon_map = {
                'created': 'plus-circle',
                'updated': 'pencil',
                'assigned': 'person-plus',
                'closed': 'check-circle',
                'reopened': 'arrow-counterclockwise',
                'transferred': 'arrow-left-right'
            }
            
            activities.append({
                'icon': icon_map.get(action.lower(), 'info-circle'),
                'description': f"{user_name} {action} ticket: {ticket_title} ({region})",
                'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S')
            })

        cur.close()
        conn.close()

        return jsonify(activities)

    except Exception as e:
        print("Error fetching recent activity:", e)
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/admin/export-data', methods=['POST'])
@require_org_context  
def export_data():
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401

    format_type = request.json.get('format', 'csv')
    start_date = request.json.get('start_date', '')
    end_date = request.json.get('end_date', '')
    region = request.json.get('region', '')
    org_id = session.get('org_id')  # ADD THIS
    
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500

        cur = conn.cursor()
        
        # Build the query with filters
        query = """
            SELECT 
                t.ticket_id,
                t.title,
                t.description,
                t.account_number,
                t.meter_number,
                t.status,
                t.created_at,
                t.resolved_at,
                creator.name as created_by_name,
                creator.surname as created_by_surname,
                creator.region as creator_region,
                assignee.name as assigned_to_name,
                assignee.surname as assigned_to_surname,
                th.performed_by AS transferred_by_id,
                transfer_user.name AS transferred_by_name,
                transfer_user.surname AS transferred_by_surname,
                th.performed_at AS transferred_at,
                th.notes AS transfer_notes,
                t.attachment_path
            FROM tickets t
            LEFT JOIN users creator ON t.created_by = creator.user_id
            LEFT JOIN users assignee ON t.assigned_to = assignee.user_id
            LEFT JOIN (
                SELECT DISTINCT ON (ticket_id) 
                       ticket_id, performed_by, performed_at, notes
                FROM ticket_history 
                WHERE action = 'Transferred'
                ORDER BY ticket_id, performed_at DESC
            ) th ON t.ticket_id = th.ticket_id
            LEFT JOIN users transfer_user ON th.performed_by = transfer_user.user_id
            WHERE t.org_id = %s
        """
        
        params = [org_id]  # START WITH org_id
        
        # Add date range filters
        if start_date:
            query += " AND t.created_at >= %s"
            params.append(start_date)
        
        if end_date:
            query += " AND t.created_at <= %s"
            params.append(end_date + " 23:59:59")
        
        # Add region filter
        if region:
            query += " AND creator.region = %s"
            params.append(region)
        
        query += " ORDER BY t.created_at DESC"
        
        cur.execute(query, params)
        
        tickets = []
        for row in cur.fetchall():
            # Extract only the transfer reason from the notes
            transfer_notes = row[17] if row[17] else ''
            transfer_reason = ''
            if transfer_notes and ' - Reason: ' in transfer_notes:
                transfer_reason = transfer_notes.split(' - Reason: ')[1]
            elif transfer_notes:
                transfer_reason = transfer_notes
            
            tickets.append({
                'Ticket ID': row[0],
                'Title': row[1],
                'Description': row[2],
                'Account Number': row[3],
                'Meter Number': row[4],
                'Status': row[5],
                'Created At': row[6].strftime('%Y-%m-%d %H:%M:%S') if row[6] else '',
                'Resolved At': row[7].strftime('%Y-%m-%d %H:%M:%S') if row[7] else '',
                'Created By': f"{row[8]} {row[9]}" if row[8] and row[9] else row[8] or 'Unknown',
                'Region': row[10] if row[10] else 'Unknown',
                'Assigned To': f"{row[11]} {row[12]}" if row[11] and row[12] else row[11] or 'Unassigned',
                'Transferred By': f"{row[14]} {row[15]}" if row[14] and row[15] else 'Not Transferred',
                'Transferred At': row[16].strftime('%Y-%m-%d %H:%M:%S') if row[16] else '',
                'Transfer Reason': transfer_reason,
                'Attachment Path': row[17]
            })

        cur.close()
        conn.close()

        if format_type == 'csv':
            # Generate TSV (Tab-Separated Values) for better Excel compatibility
            if not tickets:
                # Create empty TSV with headers
                fieldnames = ['Ticket ID', 'Title', 'Description', 'Account Number', 'Meter Number', 
                             'Status', 'Created At', 'Resolved At', 'Created By', 'Region', 'Assigned To', 'Transferred By', 'Transferred At', 'Transfer Reason', 'Attachment Path']
                output = io.StringIO()
                # Use tab as delimiter for better Excel compatibility
                writer = csv.DictWriter(output, fieldnames=fieldnames, delimiter='\t')
                writer.writeheader()
            else:
                # Generate TSV with data
                output = io.StringIO()
                # Use tab as delimiter for better Excel compatibility
                writer = csv.DictWriter(output, fieldnames=tickets[0].keys(), delimiter='\t')
                writer.writeheader()
                writer.writerows(tickets)
            
            # Create filename with timestamp and filters
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filter_info = []
            if start_date:
                filter_info.append(f"from_{start_date}")
            if end_date:
                filter_info.append(f"to_{end_date}")
            if region:
                filter_info.append(f"region_{region}")
            
            filter_suffix = "_" + "_".join(filter_info) if filter_info else ""
            filename = f'tickets_export{filter_suffix}_{timestamp}.tsv'
            
            return Response(
                output.getvalue(),
                mimetype='text/tab-separated-values',
                headers={
                    'Content-Disposition': f'attachment; filename={filename}'
                }
            )
        else:
            return jsonify({'error': 'Unsupported format'}), 400

    except Exception as e:
        print("Error exporting data:", e)
        traceback.print_exc()
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/admin/announcements', methods=['POST'])
def create_announcement():
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        data = request.get_json()
        title = data.get('title')
        content = data.get('content')
        target_audience = data.get('target_audience')
        is_active = data.get('is_active', True)
        
        if not all([title, content, target_audience]):
            return jsonify({'error': 'Missing required fields'}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500

        cur = conn.cursor()
        
        # Insert new announcement
        cur.execute("""
            INSERT INTO announcements (title, content, target_audience, is_active, created_by)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING announcement_id
        """, (title, content, target_audience, is_active, session['user_id']))
        
        announcement_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({'success': True, 'announcement_id': announcement_id}), 201

    except Exception as e:
        print(f"Error creating announcement: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/admin/announcements', methods=['GET'])
def get_admin_announcements():
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500

        cur = conn.cursor()
        
        # Get all announcements with creator information
        cur.execute("""
            SELECT 
                a.announcement_id,
                a.title,
                a.content,
                a.target_audience,
                a.is_active,
                a.created_at,
                a.updated_at,
                u.name as created_by_name
            FROM announcements a
            LEFT JOIN users u ON a.created_by = u.user_id
            ORDER BY a.created_at DESC
        """)
        
        announcements = []
        for row in cur.fetchall():
            announcements.append({
                'announcement_id': row[0],
                'title': row[1],
                'content': row[2],
                'target_audience': row[3],
                'active': row[4],
                'created_at': row[5].strftime('%Y-%m-%d %H:%M:%S') if row[5] else None,
                'updated_at': row[6].strftime('%Y-%m-%d %H:%M:%S') if row[6] else None,
                'created_by_name': row[7] or 'Unknown'
            })

        cur.close()
        conn.close()

        return jsonify({'announcements': announcements})

    except Exception as e:
        print(f"Error fetching announcements: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/user/announcements', methods=['GET'])
@require_org_context
def get_user_announcements():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    user_role = session.get('role', 'user')
    org_id = session.get('org_id')

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500

        cur = conn.cursor()
        
        target_conditions = ["a.target_audience = 'all'"]
        if user_role == 'user':
            target_conditions.append("a.target_audience = 'users'")
        elif user_role == 'assignee':
            target_conditions.append("a.target_audience = 'assignees'")
        elif user_role == 'admin':
            target_conditions.append("a.target_audience = 'admins'")
        
        target_condition = " OR ".join(target_conditions)
        
        cur.execute(f"""
            SELECT 
                a.announcement_id,
                a.title,
                a.content,
                a.target_audience,
                a.created_at,
                u.name as created_by_name
            FROM announcements a
            LEFT JOIN users u ON a.created_by = u.user_id
            WHERE a.org_id = %s 
              AND a.is_active = true 
              AND ({target_condition})
            ORDER BY a.created_at DESC
        """, (org_id,))
        
        announcements = []
        for row in cur.fetchall():
            announcements.append({
                'announcement_id': row[0],
                'title': row[1],
                'content': row[2],
                'target_audience': row[3],
                'created_at': row[4].strftime('%Y-%m-%d %H:%M:%S') if row[4] else None,
                'created_by_name': row[5] or 'System'
            })

        cur.close()
        conn.close()

        return jsonify({'announcements': announcements})

    except Exception as e:
        print(f"Error fetching user announcements: {e}")
        return jsonify({'error': 'Internal server error'}), 500
    
@app.route('/api/admin/announcements/<int:announcement_id>', methods=['PUT'])
def update_announcement(announcement_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        data = request.get_json()
        title = data.get('title')
        content = data.get('content')
        target_audience = data.get('target_audience')
        is_active = data.get('is_active', True)

        if not all([title, content, target_audience]):
            return jsonify({'error': 'Missing required fields'}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500

        cur = conn.cursor()
        
        # Update announcement
        cur.execute("""
            UPDATE announcements 
            SET title = %s, content = %s, target_audience = %s, is_active = %s
            WHERE announcement_id = %s
        """, (title, content, target_audience, is_active, announcement_id))
        
        if cur.rowcount == 0:
            cur.close()
            conn.close()
            return jsonify({'error': 'Announcement not found'}), 404

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({'success': True}), 200

    except Exception as e:
        print(f"Error updating announcement: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/admin/announcements/<int:announcement_id>', methods=['DELETE'])
def delete_announcement(announcement_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500

        cur = conn.cursor()
        
        # Delete announcement
        cur.execute("DELETE FROM announcements WHERE announcement_id = %s", (announcement_id,))
        
        if cur.rowcount == 0:
            cur.close()
            conn.close()
            return jsonify({'error': 'Announcement not found'}), 404

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({'success': True}), 200

    except Exception as e:
        print(f"Error deleting announcement: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/admin/administrators', methods=['GET'])
def get_administrators():
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500

        cur = conn.cursor()
        
        # Get all administrators (users with role 'admin')
        cur.execute("""
            SELECT user_id, name, surname, email, region, role, created_at
            FROM users 
            WHERE role IN ('admin')
            ORDER BY created_at DESC
        """)
        
        admins = []
        for row in cur.fetchall():
            admins.append({
                'user_id': row[0],
                'name': row[1],
                'surname': row[2],
                'email': row[3],
                'region': row[4],
                'role': row[5],
                'created_at': row[6].strftime('%Y-%m-%d %H:%M:%S') if row[6] else None
            })

        cur.close()
        conn.close()

        return jsonify({'admins': admins})

    except Exception as e:
        print("Error fetching administrators:", e)
        traceback.print_exc()
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/admin/administrators', methods=['POST'])
def create_administrator():
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        data = request.json
        name = data.get('name', '').strip()
        surname = data.get('surname', '').strip()
        email = data.get('email', '').strip().lower()
        region = data.get('region', '').strip()
        password = data.get('password', '').strip()
        role = data.get('role', 'admin').strip()

        # Validation
        if not all([name, surname, email, region, password]):
            return jsonify({'error': 'All fields are required'}), 400

        if not validate_role(role):
            return jsonify({'error': 'Invalid role. Must be admin'}), 400

        # Check if email already exists
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500

        cur = conn.cursor()
        cur.execute("SELECT user_id FROM users WHERE email = %s", (email,))
        if cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({'error': 'Email already exists'}), 400

        # Hash password
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        # Insert new administrator
        cur.execute("""
            INSERT INTO users (name, surname, email, password_hash, region, role)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING user_id
        """, (name, surname, email, hashed_password.decode('utf-8'), region, role))
        
        user_id = cur.fetchone()[0]
        conn.commit()
        
        cur.close()
        conn.close()

        return jsonify({
            'success': True,
            'message': 'Administrator created successfully',
            'user_id': user_id
        })

    except Exception as e:
        print("Error creating administrator:", e)
        traceback.print_exc()
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/admin/administrators/<int:user_id>', methods=['PUT'])
def update_administrator(user_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        data = request.json
        name = data.get('name', '').strip()
        surname = data.get('surname', '').strip()
        email = data.get('email', '').strip().lower()
        region = data.get('region', '').strip()
        role = data.get('role', 'admin').strip()
        password = data.get('password', '').strip()  # Optional for updates

        # Validation
        if not all([name, surname, email, region]):
            return jsonify({'error': 'Name, surname, email, and region are required'}), 400

        if not validate_role(role):
            return jsonify({'error': 'Invalid role. Must be admin'}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500

        cur = conn.cursor()
        
        # Check if user exists and is an administrator
        cur.execute("SELECT user_id FROM users WHERE user_id = %s AND role IN ('admin')", (user_id,))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({'error': 'Administrator not found'}), 404

        # Check if email already exists for another user
        cur.execute("SELECT user_id FROM users WHERE email = %s AND user_id != %s", (email, user_id))
        if cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({'error': 'Email already exists'}), 400

        # Update administrator
        if password:
            # Update with password
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            cur.execute("""
                UPDATE users 
                SET name = %s, surname = %s, email = %s, region = %s, role = %s, password_hash = %s
                WHERE user_id = %s
            """, (name, surname, email, region, role, hashed_password.decode('utf-8'), user_id))
        else:
            # Update without password
            cur.execute("""
                UPDATE users 
                SET name = %s, surname = %s, email = %s, region = %s, role = %s
                WHERE user_id = %s
            """, (name, surname, email, region, role, user_id))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            'success': True,
            'message': 'Administrator updated successfully'
        })

    except Exception as e:
        print("Error updating administrator:", e)
        traceback.print_exc()
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/admin/administrators/<int:user_id>', methods=['DELETE'])
def delete_administrator(user_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401

    # Prevent admin from deleting themselves
    if user_id == session['user_id']:
        return jsonify({'error': 'Cannot delete your own account'}), 400

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500

        cur = conn.cursor()
        
        # Check if user exists and is an administrator
        cur.execute("SELECT user_id FROM users WHERE user_id = %s AND role IN ('admin')", (user_id,))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({'error': 'Administrator not found'}), 404

        # Check if admin has any assigned tickets
        cur.execute("SELECT COUNT(*) FROM tickets WHERE assigned_to = %s AND status != 'closed'", (user_id,))
        active_tickets = cur.fetchone()[0]
        
        if active_tickets > 0:
            cur.close()
            conn.close()
            return jsonify({'error': f'Cannot delete administrator with {active_tickets} active assigned tickets'}), 400

        # Delete administrator
        cur.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
        conn.commit()
        
        cur.close()
        conn.close()

        return jsonify({
            'success': True,
            'message': 'Administrator deleted successfully'
        })

    except Exception as e:
        print("Error deleting administrator:", e)
        traceback.print_exc()
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/admin/system-config', methods=['GET'])
def get_system_config():
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500

        cur = conn.cursor()
        
        # Fetch system configuration from database
        cur.execute("SELECT config_key, config_value FROM system_config")
        config_rows = cur.fetchall()
        
        config = {}
        for row in config_rows:
            config[row[0]] = row[1]
        
        # Convert numeric values
        if 'auto_close_days' in config:
            config['auto_close_days'] = int(config['auto_close_days'])
        if 'max_file_size' in config:
            config['max_file_size'] = int(config['max_file_size'])
        if 'session_timeout' in config:
            config['session_timeout'] = int(config['session_timeout'])
        
        cur.close()
        conn.close()
        
        return jsonify({'config': config})

    except Exception as e:
        print("Error fetching system config:", e)
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/admin/system-config', methods=['POST'])
def save_system_config():
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        data = request.json
        
        # Validate configuration values
        if not validate_status(data.get('default_ticket_status')):
            return jsonify({'error': 'Invalid default ticket status'}), 400
            
        if not isinstance(data.get('auto_close_days'), int) or data.get('auto_close_days') < 1:
            return jsonify({'error': 'Auto close days must be a positive integer'}), 400
            
        if not isinstance(data.get('max_file_size'), int) or data.get('max_file_size') < 1:
            return jsonify({'error': 'Max file size must be a positive integer'}), 400
            
        if not isinstance(data.get('session_timeout'), int) or data.get('session_timeout') < 15:
            return jsonify({'error': 'Session timeout must be at least 15 minutes'}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500

        cur = conn.cursor()
        
        # Update system configuration in database
        config_updates = [
            ('default_ticket_status', str(data.get('default_ticket_status'))),
            ('auto_close_days', str(data.get('auto_close_days'))),
            ('max_file_size', str(data.get('max_file_size'))),
            ('session_timeout', str(data.get('session_timeout')))
        ]
        
        for config_key, config_value in config_updates:
            cur.execute("""
                UPDATE system_config 
                SET config_value = %s, updated_at = CURRENT_TIMESTAMP
                WHERE config_key = %s
            """, (config_value, config_key))
        
        conn.commit()
        cur.close()
        conn.close()
        
        # Reload session configuration if session_timeout was updated
        if 'session_timeout' in [config[0] for config in config_updates]:
            configure_session_timeout()
        
        return jsonify({
            'success': True,
            'message': 'System configuration saved successfully'
        })

    except Exception as e:
        print("Error saving system config:", e)
        traceback.print_exc()
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/admin/update-session-timeout', methods=['POST'])
def update_session_timeout():
    """Update session timeout configuration and reload it"""
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        data = request.json
        timeout_minutes = data.get('session_timeout')
        
        if not isinstance(timeout_minutes, int) or timeout_minutes < 15:
            return jsonify({'error': 'Session timeout must be at least 15 minutes'}), 400

        # Update the configuration in database
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500

        cur = conn.cursor()
        cur.execute("""
            UPDATE system_config 
            SET config_value = %s, updated_at = CURRENT_TIMESTAMP
            WHERE config_key = 'session_timeout'
        """, (str(timeout_minutes),))
        
        conn.commit()
        cur.close()
        conn.close()
        
        # Reload session configuration
        configure_session_timeout()
        
        return jsonify({
            'success': True,
            'message': f'Session timeout updated to {timeout_minutes} minutes'
        })

    except Exception as e:
        print("Error updating session timeout:", e)
        traceback.print_exc()
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/admin/backup', methods=['POST'])
def create_backup():
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        import os
        from datetime import datetime
        
        # Create backup directory if it doesn't exist
        backup_dir = os.path.join(os.getcwd(), 'backups')
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        
        # Generate backup filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f'ticket_tracker_backup_{timestamp}.sql'
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # Parse the connection string format: "dbname='BCM_Ticket_tracker' user='postgres' password='123' host='localhost' port='5432'"
        conn_str = TARGET_CONN_STR
        
        # Extract connection parameters using string parsing
        import re
        
        # Extract database name
        dbname_match = re.search(r"dbname='([^']*)'", conn_str)
        database = dbname_match.group(1) if dbname_match else 'BCM_Ticket_tracker'
        
        # Extract username
        user_match = re.search(r"user='([^']*)'", conn_str)
        username = user_match.group(1) if user_match else 'postgres'
        
        # Extract password
        password_match = re.search(r"password='([^']*)'", conn_str)
        password = password_match.group(1) if password_match else '123'
        
        # Extract host
        host_match = re.search(r"host='([^']*)'", conn_str)
        host = host_match.group(1) if host_match else 'localhost'
        
        # Extract port
        port_match = re.search(r"port='([^']*)'", conn_str)
        port = port_match.group(1) if port_match else '5432'
        
        # Try to find pg_dump in common locations
        pg_dump_paths = [
            'pg_dump',  # If it's in PATH
            r'C:\Program Files\PostgreSQL\15\bin\pg_dump.exe',  # PostgreSQL 15
            r'C:\Program Files\PostgreSQL\14\bin\pg_dump.exe',  # PostgreSQL 14
            r'C:\Program Files\PostgreSQL\13\bin\pg_dump.exe',  # PostgreSQL 13
            r'C:\Program Files\PostgreSQL\12\bin\pg_dump.exe',  # PostgreSQL 12
            r'C:\Program Files\PostgreSQL\11\bin\pg_dump.exe',  # PostgreSQL 11
        ]
        
        pg_dump_found = None
        for path in pg_dump_paths:
            try:
                result = subprocess.run([path, '--version'], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    pg_dump_found = path
                    break
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        
        if not pg_dump_found:
            # Fallback: Create a simple SQL dump using Python
            return create_simple_backup(backup_path, database, username, password, host, port)
        
        # Set environment variable for password
        env = os.environ.copy()
        env['PGPASSWORD'] = password
        
        # Run pg_dump command
        cmd = [
            pg_dump_found,
            '-h', host,
            '-p', port,
            '-U', username,
            '-d', database,
            '-f', backup_path,
            '--no-password'
        ]
        
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        if result.returncode == 0:
            # Get file size
            file_size = os.path.getsize(backup_path)
            file_size_mb = round(file_size / (1024 * 1024), 2)
            
            return jsonify({
                'success': True,
                'message': f'Backup created successfully! File: {backup_filename} ({file_size_mb} MB)',
                'filename': backup_filename,
                'size_mb': file_size_mb
            })
        else:
            return jsonify({
                'error': f'Backup failed: {result.stderr}'
            }), 500

    except Exception as e:
        print("Error creating backup:", e)
        traceback.print_exc()
        return jsonify({'error': 'Internal server error'}), 500

def create_simple_backup(backup_path, database, username, password, host, port):
    """Create a simple backup using Python when pg_dump is not available"""
    try:
        # Connect to database
        conn = psycopg2.connect(
            dbname=database,
            user=username,
            password=password,
            host=host,
            port=port
        )
        
        cur = conn.cursor()
        
        # Get all tables
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """)
        tables = [row[0] for row in cur.fetchall()]
        
        with open(backup_path, 'w', encoding='utf-8') as f:
            # Write header
            f.write("-- Ticket Tracker Database Backup\n")
            f.write(f"-- Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("-- Database: " + database + "\n\n")
            
            # For each table, get structure and data
            for table in tables:
                f.write(f"\n-- Table: {table}\n")
                f.write(f"-- Structure\n")
                
                # Get table structure
                cur.execute(f"""
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns 
                    WHERE table_name = '{table}' 
                    ORDER BY ordinal_position
                """)
                columns = cur.fetchall()
                
                f.write(f"CREATE TABLE IF NOT EXISTS {table} (\n")
                column_defs = []
                for col in columns:
                    col_name, data_type, is_nullable, col_default = col
                    nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
                    default = f" DEFAULT {col_default}" if col_default else ""
                    column_defs.append(f"    {col_name} {data_type} {nullable}{default}")
                f.write(",\n".join(column_defs))
                f.write("\n);\n\n")
                
                # Get table data
                f.write(f"-- Data\n")
                cur.execute(f"SELECT * FROM {table}")
                rows = cur.fetchall()
                
                if rows:
                    # Get column names
                    cur.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table}' ORDER BY ordinal_position")
                    col_names = [row[0] for row in cur.fetchall()]
                    
                    for row in rows:
                        values = []
                        for val in row:
                            if val is None:
                                values.append("NULL")
                            elif isinstance(val, str):
                                # Escape single quotes
                                escaped_val = val.replace("'", "''")
                                values.append(f"'{escaped_val}'")
                            else:
                                values.append(str(val))
                        
                        f.write(f"INSERT INTO {table} ({', '.join(col_names)}) VALUES ({', '.join(values)});\n")
                else:
                    f.write(f"-- No data in table {table}\n")
                
                f.write("\n")
        
        cur.close()
        conn.close()
        
        # Get file size
        file_size = os.path.getsize(backup_path)
        file_size_mb = round(file_size / (1024 * 1024), 2)
        
        return jsonify({
            'success': True,
            'message': f'Simple backup created successfully! File: {os.path.basename(backup_path)} ({file_size_mb} MB) - Note: pg_dump not found, using Python backup method',
            'filename': os.path.basename(backup_path),
            'size_mb': file_size_mb
        })
        
    except Exception as e:
        print("Error creating simple backup:", e)
        traceback.print_exc()
        return jsonify({'error': f'Simple backup failed: {str(e)}'}), 500

@app.route('/api/admin/cleanup', methods=['POST'])
def run_cleanup():
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500

        cur = conn.cursor()
        
        # Clean up old closed tickets (older than 1 year)
        cur.execute("""
            DELETE FROM tickets 
            WHERE status = 'closed' 
            AND resolved_at < NOW() - INTERVAL '1 year'
        """)
        
        deleted_tickets = cur.rowcount
        
        # Clean up old announcements (older than 6 months)
        cur.execute("""
            DELETE FROM announcements 
            WHERE created_at < NOW() - INTERVAL '6 months'
            AND is_active = false
        """)
        
        deleted_announcements = cur.rowcount
        
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            'success': True,
            'message': f'Cleanup completed. Deleted {deleted_tickets} old tickets and {deleted_announcements} old announcements.'
        })

    except Exception as e:
        print("Error running cleanup:", e)
        traceback.print_exc()
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/admin/clear-cache', methods=['POST'])
def clear_cache():
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        import os
        import shutil
        from datetime import datetime
        
        cache_cleared = []
        
        # 1. Clear temporary files
        temp_dir = os.path.join(os.getcwd(), 'temp')
        if os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                os.makedirs(temp_dir, exist_ok=True)
                cache_cleared.append('temporary files')
            except Exception as e:
                print(f"Error clearing temp directory: {e}")
        
        # 2. Clear session cache (if using file-based sessions)
        session_dir = os.path.join(os.getcwd(), 'flask_session')
        if os.path.exists(session_dir):
            try:
                shutil.rmtree(session_dir)
                os.makedirs(session_dir, exist_ok=True)
                cache_cleared.append('session cache')
            except Exception as e:
                print(f"Error clearing session cache: {e}")
        
        # 3. Clear any uploaded file cache
        upload_dir = os.path.join(os.getcwd(), 'uploads')
        if os.path.exists(upload_dir):
            try:
                # Remove temporary upload files (older than 1 hour)
                current_time = datetime.now()
                for filename in os.listdir(upload_dir):
                    file_path = os.path.join(upload_dir, filename)
                    if os.path.isfile(file_path):
                        file_time = datetime.fromtimestamp(os.path.getctime(file_path))
                        if (current_time - file_time).total_seconds() > 3600:  # 1 hour
                            os.remove(file_path)
                cache_cleared.append('upload cache')
            except Exception as e:
                print(f"Error clearing upload cache: {e}")
        
        # 4. Clear any log cache files
        log_dir = os.path.join(os.getcwd(), 'logs')
        if os.path.exists(log_dir):
            try:
                # Remove old log files (older than 7 days)
                current_time = datetime.now()
                for filename in os.listdir(log_dir):
                    if filename.endswith('.log'):
                        file_path = os.path.join(log_dir, filename)
                        if os.path.isfile(file_path):
                            file_time = datetime.fromtimestamp(os.path.getctime(file_path))
                            if (current_time - file_time).total_seconds() > 604800:  # 7 days
                                os.remove(file_path)
                cache_cleared.append('log cache')
            except Exception as e:
                print(f"Error clearing log cache: {e}")
        
        # 5. Clear any backup cache (old backup files)
        backup_dir = os.path.join(os.getcwd(), 'backups')
        if os.path.exists(backup_dir):
            try:
                # Keep only the 5 most recent backup files
                backup_files = []
                for filename in os.listdir(backup_dir):
                    if filename.endswith('.sql'):
                        file_path = os.path.join(backup_dir, filename)
                        if os.path.isfile(file_path):
                            backup_files.append((file_path, os.path.getctime(file_path)))
                
                # Sort by creation time (newest first) and remove old ones
                backup_files.sort(key=lambda x: x[1], reverse=True)
                if len(backup_files) > 5:
                    for file_path, _ in backup_files[5:]:
                        os.remove(file_path)
                    cache_cleared.append('backup cache')
            except Exception as e:
                print(f"Error clearing backup cache: {e}")
        
        if cache_cleared:
            return jsonify({
                'success': True,
                'message': f'Cache cleared successfully! Cleared: {", ".join(cache_cleared)}'
            })
        else:
            return jsonify({
                'success': True,
                'message': 'Cache cleared successfully! (No cache files found)'
            })

    except Exception as e:
        print("Error clearing cache:", e)
        traceback.print_exc()
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/admin/database-health', methods=['GET'])
def database_health_check():
    """Check database health and provide status information"""
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({
                'status': 'error',
                'message': 'Database connection failed',
                'details': 'Cannot connect to PostgreSQL database'
            }), 500

        cur = conn.cursor()
        
        # Test basic connectivity
        cur.execute("SELECT 1")
        connectivity_test = cur.fetchone()[0] == 1
        
        # Get database version
        cur.execute("SELECT version()")
        version = cur.fetchone()[0]
        
        # Get database size
        cur.execute("""
            SELECT pg_size_pretty(pg_database_size(current_database())) as size
        """)
        db_size = cur.fetchone()[0]
        
        # Get table counts
        cur.execute("""
            SELECT 
                (SELECT COUNT(*) FROM users) as users_count,
                (SELECT COUNT(*) FROM tickets) as tickets_count,
                (SELECT COUNT(*) FROM announcements) as announcements_count,
                (SELECT COUNT(*) FROM ticket_history) as history_count
        """)
        counts = cur.fetchone()
        
        # Get recent activity (last 24 hours)
        cur.execute("""
            SELECT COUNT(*) FROM ticket_history 
            WHERE performed_at >= NOW() - INTERVAL '24 hours'
        """)
        recent_activity = cur.fetchone()[0]
        
        # Check for any long-running queries (if any)
        cur.execute("""
            SELECT COUNT(*) FROM pg_stat_activity 
            WHERE state = 'active' AND query NOT LIKE '%pg_stat_activity%'
        """)
        active_queries = cur.fetchone()[0]
        
        cur.close()
        conn.close()
        
        return jsonify({
            'status': 'healthy',
            'message': 'Database is healthy and accessible',
            'details': {
                'connectivity': 'OK',
                'version': version,
                'database_size': db_size,
                'table_counts': {
                    'users': counts[0],
                    'tickets': counts[1],
                    'announcements': counts[2],
                    'ticket_history': counts[3]
                },
                'recent_activity_24h': recent_activity,
                'active_queries': active_queries,
                'last_check': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        })

    except Exception as e:
        print("Database health check error:", e)
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': 'Database health check failed',
            'details': str(e)
        }), 500

@app.route('/api/user/unread_announcements_count', methods=['GET'])
def unread_announcements_count():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    user_id = session['user_id']
    user_role = session.get('role', 'user')

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Build target audience conditions based on user role
        target_conditions = ["a.target_audience = 'all'"]
        if user_role == 'user':
            target_conditions.append("a.target_audience = 'users'")
        elif user_role == 'assignee':
            target_conditions.append("a.target_audience = 'assignees'")
        elif user_role == 'admin':
            target_conditions.append("a.target_audience = 'admins'")

        target_condition = " OR ".join(target_conditions)

        # Count unread announcements
        cur.execute(f"""
            SELECT COUNT(*)
            FROM announcements a
            WHERE a.is_active = true
              AND ({target_condition})
              AND a.announcement_id NOT IN (
                  SELECT announcement_id FROM announcement_reads WHERE user_id = %s
              )
        """, (user_id,))
        count = cur.fetchone()[0]

        cur.close()
        conn.close()

        return jsonify({'unread_count': count})

    except Exception as e:
        print("Error fetching unread announcements count:", e)
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/user/mark_announcements_read', methods=['POST'])
def mark_announcements_read():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    user_id = session['user_id']
    user_role = session.get('role', 'user')

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get all active announcement IDs for this user
        target_conditions = ["a.target_audience = 'all'"]
        if user_role == 'user':
            target_conditions.append("a.target_audience = 'users'")
        elif user_role == 'assignee':
            target_conditions.append("a.target_audience = 'assignees'")
        elif user_role == 'admin':
            target_conditions.append("a.target_audience = 'admins'")

        target_condition = " OR ".join(target_conditions)

        cur.execute(f"""
            SELECT a.announcement_id
            FROM announcements a
            WHERE a.is_active = true
              AND ({target_condition})
              AND a.announcement_id NOT IN (
                  SELECT announcement_id FROM announcement_reads WHERE user_id = %s
              )
        """, (user_id,))
        unread_ids = [row[0] for row in cur.fetchall()]

        # Insert as read
        for ann_id in unread_ids:
            cur.execute("""
                INSERT INTO announcement_reads (user_id, announcement_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
            """, (user_id, ann_id))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({'success': True, 'marked_read': len(unread_ids)})

    except Exception as e:
        print("Error marking announcements as read:", e)
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    # Security: Only serve files from the uploads folder
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

# --- Run App ---
if __name__ == '__main__':
    initialize_database()
    configure_session_timeout()
    app.run(debug=True)