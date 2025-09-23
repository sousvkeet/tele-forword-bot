import sqlite3
import json
from datetime import datetime
import logging

class DatabaseManager:
    def __init__(self, db_path='telegram_forwarder.db'):
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        self.create_tables()
        self.create_default_user()
    
    def get_connection(self):
        """Get a database connection with proper timeout and retry logic"""
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                conn = sqlite3.connect(self.db_path, timeout=30.0)
                conn.execute('PRAGMA journal_mode=WAL')
                conn.execute('PRAGMA synchronous=NORMAL')
                conn.execute('PRAGMA cache_size=10000')
                conn.execute('PRAGMA temp_store=MEMORY')
                conn.execute('PRAGMA busy_timeout=30000')
                # Test the connection
                conn.execute('SELECT 1')
                return conn
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                    self.logger.warning(f"Database locked, retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries})")
                    import time
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    raise
    
    def create_tables(self):
        """Create necessary tables if they don't exist"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Create forwarding_rules table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS forwarding_rules (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source TEXT NOT NULL,
                        target TEXT NOT NULL,
                        filters TEXT DEFAULT '{}',
                        enabled BOOLEAN DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        message_count INTEGER DEFAULT 0
                    )
                ''')
                
                # Create settings table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS settings (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Create forwarding_status table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS forwarding_status (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        is_running BOOLEAN DEFAULT 0,
                        daily_forward_count INTEGER DEFAULT 0,
                        last_reset_date TEXT DEFAULT (date('now')),
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Create users table for authentication
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        email TEXT UNIQUE,
                        display_name TEXT,
                        password_hash TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_login TIMESTAMP,
                        is_active BOOLEAN DEFAULT 1
                    )
                ''')
                
                # Create activity_log table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS activity_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        activity_type TEXT NOT NULL,
                        description TEXT NOT NULL,
                        rule_id INTEGER,
                        details TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (rule_id) REFERENCES forwarding_rules (id)
                    )
                ''')
                
                # Add display_name column if it doesn't exist (for existing databases)
                try:
                    cursor.execute('ALTER TABLE users ADD COLUMN display_name TEXT')
                except:
                    pass  # Column already exists
                
                # Add filters column if it doesn't exist (for existing databases)
                try:
                    cursor.execute("ALTER TABLE forwarding_rules ADD COLUMN filters TEXT DEFAULT '{}'")
                except:
                    pass  # Column already exists
                
                # Add updated_at column if it doesn't exist (for existing databases)
                try:
                    cursor.execute('ALTER TABLE forwarding_rules ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
                except:
                    pass  # Column already exists
                
                conn.commit()
                self.logger.info("Database tables created successfully")
                
                # Create default admin user if no users exist
                self.create_default_user()
                
        except Exception as e:
            self.logger.error(f"Error creating tables: {e}")
            raise
    
    def add_rule(self, source, target, filters=None):
        """Add a new forwarding rule"""
        if filters is None:
            filters = {}
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                filters_json = json.dumps(filters or {})
                
                cursor.execute('''
                    INSERT INTO forwarding_rules (source, target, filters, enabled)
                    VALUES (?, ?, ?, 1)
                ''', (source, target, filters_json))
                
                rule_id = cursor.lastrowid
                conn.commit()
                
                # Return the created rule
                return self.get_rule(rule_id)
                
        except Exception as e:
            self.logger.error(f"Error adding rule: {e}")
            raise
    
    def get_rule(self, rule_id):
        """Get a specific rule by ID"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT id, source, target, filters, enabled, created_at, message_count
                    FROM forwarding_rules WHERE id = ?
                ''', (rule_id,))
                
                row = cursor.fetchone()
                if row:
                    return {
                        'id': row[0],
                        'source': row[1],
                        'target': row[2],
                        'filters': json.loads(row[3]),
                        'enabled': bool(row[4]),
                        'created_at': row[5],
                        'message_count': row[6]
                    }
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting rule: {e}")
            return None
    
    def get_all_rules(self):
        """Get all forwarding rules"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT id, source, target, filters, enabled, created_at, message_count
                    FROM forwarding_rules ORDER BY created_at DESC
                ''')
                
                rules = []
                for row in cursor.fetchall():
                    rules.append({
                        'id': row[0],
                        'source': row[1],
                        'target': row[2],
                        'filters': json.loads(row[3]) if row[3] else {},
                        'enabled': bool(row[4]),
                        'created_at': row[5],
                        'message_count': row[6] if row[6] else 0
                    })
                
                return rules
                
        except Exception as e:
            self.logger.error(f"Error getting rules: {e}")
            return []
    
    def get_enabled_rules(self):
        """Get only enabled forwarding rules"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT id, source, target, filters, enabled, created_at, message_count
                    FROM forwarding_rules WHERE enabled = 1 ORDER BY created_at DESC
                ''')
                
                rules = []
                for row in cursor.fetchall():
                    rules.append({
                        'id': row[0],
                        'source': row[1],
                        'target': row[2],
                        'filters': json.loads(row[3]),
                        'enabled': bool(row[4]),
                        'created_at': row[5],
                        'message_count': row[6]
                    })
                
                return rules
                
        except Exception as e:
            self.logger.error(f"Error getting enabled rules: {e}")
            return []
    
    def toggle_rule(self, rule_id):
        """Toggle rule enabled/disabled status"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get current status
                cursor.execute('SELECT enabled FROM forwarding_rules WHERE id = ?', (rule_id,))
                row = cursor.fetchone()
                
                if row is None:
                    raise ValueError(f"Rule {rule_id} not found")
                
                new_status = not bool(row[0])
                
                # Update status
                cursor.execute('''
                    UPDATE forwarding_rules 
                    SET enabled = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE id = ?
                ''', (new_status, rule_id))
                
                conn.commit()
                
                return self.get_rule(rule_id)
                
        except Exception as e:
            self.logger.error(f"Error toggling rule: {e}")
            raise
    
    def delete_rule(self, rule_id):
        """Delete a forwarding rule"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('DELETE FROM forwarding_rules WHERE id = ?', (rule_id,))
                conn.commit()
                
                return cursor.rowcount > 0
                
        except Exception as e:
            self.logger.error(f"Error deleting rule: {e}")
            raise
    
    def log_activity(self, activity_type, description, rule_id=None, details=None):
        """Log an activity event"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO activity_log 
                    (activity_type, description, rule_id, details, timestamp) 
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (activity_type, description, rule_id, json.dumps(details) if details else None))
                
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"Error logging activity: {e}")
            # Don't raise here to avoid breaking main functionality
    
    def get_recent_activity(self, limit=50):
        """Get recent activity entries"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT 
                        al.id,
                        al.activity_type,
                        al.description,
                        al.rule_id,
                        al.details,
                        al.timestamp,
                        fr.source,
                        fr.target
                    FROM activity_log al
                    LEFT JOIN forwarding_rules fr ON al.rule_id = fr.id
                    ORDER BY al.timestamp DESC
                    LIMIT ?
                ''', (limit,))
                
                rows = cursor.fetchall()
                
                activities = []
                for row in rows:
                    activity = {
                        'id': row[0],
                        'activity_type': row[1],
                        'description': row[2],
                        'rule_id': row[3],
                        'details': json.loads(row[4]) if row[4] else None,
                        'timestamp': row[5],
                        'source': row[6],
                        'target': row[7]
                    }
                    activities.append(activity)
                
                return activities
                
        except Exception as e:
            self.logger.error(f"Error getting recent activity: {e}")
            return []
    
    def set_forwarding_status(self, is_running):
        """Set the forwarding status"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Update or insert forwarding status
                cursor.execute('''
                    INSERT OR REPLACE INTO forwarding_status 
                    (id, is_running, updated_at) 
                    VALUES (1, ?, CURRENT_TIMESTAMP)
                ''', (is_running,))
                
                conn.commit()
                self.logger.info(f"Set forwarding status to: {is_running}")
                
        except Exception as e:
            self.logger.error(f"Error setting forwarding status: {e}")
            raise
    
    def increment_message_count(self, rule_id):
        """Increment message count for a rule"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    UPDATE forwarding_rules 
                    SET message_count = message_count + 1 
                    WHERE id = ?
                ''', (rule_id,))
                
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"Error incrementing message count: {e}")
    
    def update_forwarding_status(self, is_running):
        """Update forwarding status"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                if is_running:
                    cursor.execute('''
                        UPDATE forwarding_status 
                        SET is_running = 1, started_at = CURRENT_TIMESTAMP 
                        WHERE id = 1
                    ''')
                else:
                    cursor.execute('''
                        UPDATE forwarding_status 
                        SET is_running = 0, stopped_at = CURRENT_TIMESTAMP 
                        WHERE id = 1
                    ''')
                
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"Error updating forwarding status: {e}")
    
    def get_forwarding_status(self):
        """Get forwarding service status"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT is_running, started_at, stopped_at, daily_forward_count, last_reset_date
                    FROM forwarding_status WHERE id = 1
                ''')
                
                row = cursor.fetchone()
                if row:
                    return {
                        'is_running': bool(row[0]),
                        'started_at': row[1],
                        'stopped_at': row[2],
                        'daily_forward_count': row[3],
                        'last_reset_date': row[4]
                    }
                
                return {'is_running': False, 'daily_forward_count': 0}
                
        except Exception as e:
            self.logger.error(f"Error getting forwarding status: {e}")
            return {'is_running': False, 'daily_forward_count': 0}
    
    def update_daily_count(self, count=None):
        """Update daily forward count"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                if count is not None:
                    cursor.execute('''
                        UPDATE forwarding_status 
                        SET daily_forward_count = ?, last_reset_date = CURRENT_DATE 
                        WHERE id = 1
                    ''', (count,))
                else:
                    cursor.execute('''
                        UPDATE forwarding_status 
                        SET daily_forward_count = daily_forward_count + 1 
                        WHERE id = 1
                    ''')
                
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"Error updating daily count: {e}")
    
    def get_settings(self):
        """Get all settings"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('SELECT key, value FROM settings')
                
                settings = {}
                for row in cursor.fetchall():
                    key, value = row
                    # Convert string values to appropriate types
                    if value.lower() in ('true', 'false'):
                        settings[key] = value.lower() == 'true'
                    elif value.isdigit():
                        settings[key] = int(value)
                    else:
                        settings[key] = value
                
                return settings
                
        except Exception as e:
            self.logger.error(f"Error getting settings: {e}")
            return {}
    
    def create_default_user(self):
        """Create default admin user if no users exist"""
        try:
            import hashlib
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Check if any users exist
                cursor.execute('SELECT COUNT(*) FROM users')
                user_count = cursor.fetchone()[0]
                
                if user_count == 0:
                    # Create default admin user
                    password_hash = hashlib.sha256('Admin'.encode()).hexdigest()
                    cursor.execute('''
                        INSERT INTO users (username, email, password_hash) 
                        VALUES (?, ?, ?)
                    ''', ('admin', 'admin@localhost', password_hash))
                    
                    conn.commit()
                    self.logger.info("Default admin user created (username: admin, password: Admin)")
                    
        except Exception as e:
            self.logger.error(f"Error creating default user: {e}")
    
    def authenticate_user(self, username, password):
        """Authenticate user with username/email and password"""
        try:
            import hashlib
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Check by username or email
                cursor.execute('''
                    SELECT id, username, email FROM users 
                    WHERE (username = ? OR email = ?) AND password_hash = ? AND is_active = 1
                ''', (username, username, password_hash))
                
                user = cursor.fetchone()
                if user:
                    # Update last login
                    cursor.execute('''
                        UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?
                    ''', (user[0],))
                    conn.commit()
                    
                    return {
                        'success': True,
                        'user': {
                            'id': user[0],
                            'username': user[1],
                            'email': user[2]
                        }
                    }
                else:
                    return {'success': False, 'message': 'Invalid credentials'}
                    
        except Exception as e:
            self.logger.error(f"Error authenticating user: {e}")
            return {'success': False, 'message': 'Authentication error'}
    
    def change_password(self, user_id, old_password, new_password):
        """Change user password"""
        try:
            import hashlib
            old_hash = hashlib.sha256(old_password.encode()).hexdigest()
            new_hash = hashlib.sha256(new_password.encode()).hexdigest()
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Verify old password
                cursor.execute('SELECT id FROM users WHERE id = ? AND password_hash = ?', (user_id, old_hash))
                if not cursor.fetchone():
                    return {'success': False, 'message': 'Current password is incorrect'}
                
                # Update password
                cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', (new_hash, user_id))
                conn.commit()
                
                return {'success': True, 'message': 'Password changed successfully'}
                
        except Exception as e:
            self.logger.error(f"Error changing password: {e}")
            return {'success': False, 'message': 'Error changing password'}
    
    def get_user_by_id(self, user_id):
        """Get user by ID"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT id, username, email, created_at, last_login FROM users WHERE id = ?', (user_id,))
                user = cursor.fetchone()
                
                if user:
                    return {
                        'id': user[0],
                        'username': user[1],
                        'email': user[2],
                        'created_at': user[3],
                        'last_login': user[4]
                    }
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting user: {e}")
            return None
    
    def update_setting(self, key, value):
        """Update or insert a setting"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO settings (key, value, updated_at) 
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                ''', (key, str(value)))
                
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"Error updating settings: {e}")
            raise
    
    def update_settings(self, settings_dict):
        """Update multiple settings at once"""
        try:
            self.logger.info(f"Updating settings: {settings_dict}")
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                for key, value in settings_dict.items():
                    self.logger.info(f"Setting {key} = {value} (type: {type(value)})")
                    cursor.execute('''
                        INSERT OR REPLACE INTO settings (key, value, updated_at) 
                        VALUES (?, ?, CURRENT_TIMESTAMP)
                    ''', (key, str(value)))
                
                conn.commit()
                self.logger.info(f"Successfully updated {len(settings_dict)} settings in database")
                
                # Verify the update
                cursor.execute('SELECT key, value FROM settings')
                all_settings = cursor.fetchall()
                self.logger.info(f"Current settings in database: {dict(all_settings)}")
                
        except Exception as e:
            self.logger.error(f"Error updating settings: {e}")
            raise
    
    def get_stats(self):
        """Get forwarding statistics"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get forwarding status
                cursor.execute('SELECT is_running, daily_forward_count FROM forwarding_status ORDER BY id DESC LIMIT 1')
                status_row = cursor.fetchone()
                is_running = bool(status_row[0]) if status_row else False
                todays_forwards = status_row[1] if status_row else 0
                
                # Get active rules count
                cursor.execute('SELECT COUNT(*) FROM forwarding_rules WHERE enabled = 1')
                active_rules = cursor.fetchone()[0]
                
                # Get total message count
                cursor.execute('SELECT SUM(message_count) FROM forwarding_rules')
                total_messages = cursor.fetchone()[0] or 0
                
                # Get max daily forwards from settings
                settings = self.get_settings()
                max_daily_forwards = settings.get('max_daily_forwards', 100)
                
                return {
                    'is_running': is_running,
                    'active_rules': active_rules,
                    'todays_forwards': todays_forwards,
                    'total_messages': total_messages,
                    'max_daily_forwards': max_daily_forwards
                }
                
        except Exception as e:
            self.logger.error(f"Error getting stats: {e}")
            return {
                'is_running': False,
                'active_rules': 0,
                'todays_forwards': 0,
                'total_messages': 0,
                'max_daily_forwards': 100
            }
    
    def update_user_profile(self, current_username, new_username, display_name=None, email=None):
        """Update user profile information"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE users 
                    SET username = ?, display_name = ?, email = ?
                    WHERE username = ?
                ''', (new_username, display_name, email, current_username))
                
                return cursor.rowcount > 0
                
        except Exception as e:
            self.logger.error(f"Error updating user profile: {e}")
            return False
