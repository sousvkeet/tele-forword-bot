import json
import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_socketio import SocketIO, emit
from telegram_client_simple import SimpleTelegramClient
from async_helper import AsyncHelper
from database import DatabaseManager
import logging
from async_helper import async_helper
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Global telegram client instance
telegram_client = None
client_thread = None

# Initialize database manager
db_manager = DatabaseManager()

# Initialize client on startup to restore existing session
def initialize_client_on_startup():
    global telegram_client
    try:
        # Add a small delay to ensure any existing database connections are closed
        import time
        time.sleep(0.5)
        # Check if session file exists
        session_file = 'telegram_forwarder_simple.session'
        if os.path.exists(session_file):
            telegram_client = SimpleTelegramClient()
            
            # Try to restore session with multiple attempts
            max_attempts = 2
            result = None
            
            for attempt in range(max_attempts):
                try:
                    app.logger.info(f"Attempting session restoration (attempt {attempt + 1}/{max_attempts})")
                    result = async_helper.run_async_safe(telegram_client.restore_session())
                    if result and result.get('success'):
                        break
                    else:
                        app.logger.warning(f"Session restoration attempt {attempt + 1} failed: {result.get('message', 'Unknown error') if result else 'No result'}")
                        if attempt < max_attempts - 1:
                            import time
                            time.sleep(1)  # Wait before retry
                except Exception as e:
                    app.logger.error(f"Session restoration attempt {attempt + 1} error: {e}")
                    if attempt < max_attempts - 1:
                        import time
                        time.sleep(1)
            
            if result and result.get('success'):
                app.logger.info("Session restored successfully on startup")
                
                # The restore_session already sets is_authenticated and phone
                # Store in app config for quick access
                app.config['TELEGRAM_AUTHENTICATED'] = True
                app.config['TELEGRAM_PHONE'] = getattr(telegram_client, 'phone', None)
                app.logger.info(f"Telegram authenticated with phone: {app.config.get('TELEGRAM_PHONE')}")
                
                # Load enabled rules from database and start forwarding
                enabled_rules = db_manager.get_enabled_rules()
                if enabled_rules:
                    app.logger.info(f"Loading {len(enabled_rules)} enabled rules on startup")
                    # Clear existing rules first
                    telegram_client.forwarding_rules = []
                    
                    # Add all enabled rules to client
                    for rule in enabled_rules:
                        async_helper.run_async_safe(telegram_client.add_forwarding_rule(
                            rule['source'], rule['target'], rule['filters'], rule['id']
                        ))
                    
                    # Start forwarding if we have enabled rules
                    async_helper.run_async_safe(telegram_client.start_forwarding())
                    app.logger.info("Forwarding started with enabled rules on startup")
                
                # Store session info for later use when user accesses the app
                with app.app_context():
                    app.config['RESTORED_SESSION'] = {
                        'authenticated': True,
                        'phone_number': telegram_client.phone if hasattr(telegram_client, 'phone') else None
                    }
            else:
                app.logger.info("No valid session found on startup")
                # Check if we have stored auth status in database
                try:
                    settings = db_manager.get_settings()
                    auth_status = settings.get('telegram_authenticated')
                    phone_from_db = settings.get('telegram_phone')
                    
                    if auth_status == 'true' and phone_from_db:
                        app.logger.info(f"Found stored auth status in database: {phone_from_db}")
                        
                        if os.path.exists(session_file):
                            app.logger.info("Session file exists but not authenticated, removing corrupted session")
                            try:
                                os.remove(session_file)
                                app.logger.info("Removed corrupted session file")
                            except Exception as e:
                                app.logger.error(f"Error removing session file: {e}")
                        
                        # Clear the invalid auth status from database since session is corrupted
                        try:
                            db_manager.update_setting('telegram_authenticated', 'false')
                            app.logger.info("Cleared invalid auth status from database - user will need to re-authenticate")
                        except Exception as e:
                            app.logger.error(f"Error clearing auth status: {e}")
                    else:
                        app.logger.info("No stored auth status found in database")
                except Exception as e:
                    app.logger.error(f"Error checking database for auth status: {e}")
        else:
            app.logger.info("No session file found on startup")
    except Exception as e:
        app.logger.error(f"Error initializing client on startup: {e}")

# Initialize client when app starts
initialize_client_on_startup()

# Cleanup function for graceful shutdown
def cleanup_on_shutdown():
    global telegram_client
    try:
        if telegram_client and hasattr(telegram_client, 'client') and telegram_client.client:
            import asyncio
            asyncio.get_event_loop().run_until_complete(telegram_client.client.disconnect())
            app.logger.info("Telegram client disconnected on shutdown")
    except Exception as e:
        app.logger.error(f"Error during cleanup: {e}")

# Register cleanup function
import atexit
atexit.register(cleanup_on_shutdown)

@app.route('/')
def index():
    # Check if user is already authenticated via session
    if session.get('authenticated'):
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Check if user is already authenticated
    if session.get('authenticated'):
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        app.logger.info(f"Login attempt - Username: '{username}'")
        
        # Simple admin login (case-insensitive)
        if username.lower() == 'admin' and password.lower() == 'admin':
            session['authenticated'] = True
            session['username'] = username
            app.logger.info(f"Login successful for user: {username}")
            
            # Redirect to dashboard after successful login
            return redirect(url_for('dashboard'))
        else:
            app.logger.info(f"Login failed for user: {username}")
            flash('Invalid username or password', 'error')
            return render_template('modern_login.html')
    
    # GET request - show login page
    return render_template('modern_login.html')

@app.route('/telegram_auth')
def telegram_auth():
    # Check if user is authenticated to access this page
    if 'authenticated' not in session:
        return redirect(url_for('login'))
    
    # Check if already authenticated with Telegram
    if session.get('telegram_authenticated'):
        return redirect(url_for('dashboard'))
    
    # Redirect to dashboard with telegram section
    return redirect(url_for('dashboard') + '#telegram')

@app.route('/logout')
def logout():
    username = session.get('username', 'Unknown')
    session.clear()
    app.logger.info(f"User {username} logged out")
    flash('You have been logged out successfully')
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    # Check authentication
    if not session.get('authenticated'):
        return redirect(url_for('login'))
    
    # Get rules from database
    rules = db_manager.get_all_rules()
    
    # Get stats
    stats = db_manager.get_stats()
    
    # Check Telegram authentication from existing client
    telegram_authenticated = False
    telegram_phone = None
    
    # Check if we have a restored session or active client
    if telegram_client and hasattr(telegram_client, 'is_authenticated') and telegram_client.is_authenticated:
        telegram_authenticated = True
        telegram_phone = getattr(telegram_client, 'phone', 'Unknown')
        app.logger.info(f"Dashboard: Telegram authenticated = {telegram_authenticated}, phone = {telegram_phone}")
    elif app.config.get('TELEGRAM_AUTHENTICATED'):
        # Use stored config from startup initialization
        telegram_authenticated = True
        telegram_phone = app.config.get('TELEGRAM_PHONE', 'Unknown')
        app.logger.info(f"Dashboard: Using stored auth status, phone = {telegram_phone}")
    else:
        app.logger.info("Dashboard: Telegram not authenticated")
    
    # Count active rules
    active_rules = sum(1 for rule in rules if rule.get('enabled', False))
    is_forwarding = active_rules > 0
    
    # Load settings
    settings = db_manager.get_settings()
    
    # Check if modern UI is requested (default to modern)
    use_modern = request.args.get('ui', 'modern') == 'modern'
    template = 'modern_dashboard.html' if use_modern else 'dashboard.html'
    
    return render_template(template, 
                         rules=rules,
                         stats=stats,
                         settings=settings,
                         telegram_authenticated=telegram_authenticated,
                         telegram_phone=telegram_phone,
                         active_rules=active_rules,
                         is_forwarding=is_forwarding)

def sync_rules_with_database():
    """Synchronize Telegram client rules with database state"""
    try:
        # Clear client rules
        telegram_client.forwarding_rules = []
        
        # Load enabled rules from database
        enabled_rules = db_manager.get_enabled_rules()
        
        # Add enabled rules to client
        for rule in enabled_rules:
            async_helper.run_async_safe(telegram_client.add_forwarding_rule(
                rule['source'], rule['target'], rule['filters'], rule['id']
            ))
        
        # Start or stop forwarding based on rules
        if enabled_rules and not telegram_client.is_running:
            async_helper.run_async_safe(telegram_client.start_forwarding())
        elif not enabled_rules and telegram_client.is_running:
            async_helper.run_async_safe(telegram_client.stop_forwarding())
            
        app.logger.info(f"Synced {len(enabled_rules)} enabled rules with client")
        
    except Exception as e:
        app.logger.error(f"Error syncing rules with database: {e}")

@app.route('/api/status')
def get_status():
    """Get current forwarding status and stats"""
    try:
        stats = db_manager.get_stats()
        rules = db_manager.get_all_rules()
        
        # Determine if forwarding is running based on enabled rules and client state
        has_enabled_rules = any(rule['enabled'] for rule in rules)
        is_client_running = telegram_client and telegram_client.is_running if telegram_client else False
        
        return jsonify({
            'success': True,
            'is_running': has_enabled_rules and is_client_running,
            'rules': rules,
            'stats': {
                **stats,
                'is_running': has_enabled_rules and is_client_running,
                'active_rules': len([r for r in rules if r['enabled']])
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/auth/send-code', methods=['POST'])
def send_code():
    global telegram_client
    
    try:
        data = request.json
        phone_number = data.get('phone_number')
        
        if not phone_number:
            return jsonify({'success': False, 'message': 'Phone number required'})
        
        if not telegram_client:
            telegram_client = SimpleTelegramClient()
        
        # Use async helper to run the operation
        result = async_helper.run_async_safe(telegram_client.send_code_request(phone_number))
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/auth/verify-code', methods=['POST'])
def verify_code():
    global telegram_client
    
    try:
        data = request.json
        phone_number = data.get('phone_number')
        code = data.get('code')
        
        if not phone_number or not code:
            return jsonify({'success': False, 'message': 'Phone number and code required'})
        
        if not telegram_client:
            return jsonify({'success': False, 'message': 'Code not sent yet'})
        
        # Use async helper to run the operation
        result = async_helper.run_async_safe(telegram_client.verify_code(phone_number, code))
        
        # If verification successful, set session
        if result.get('success'):
            session['authenticated'] = True
            session['phone_number'] = phone_number
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/auth/verify-password', methods=['POST'])
def verify_password():
    global telegram_client
    
    try:
        data = request.json
        password = data.get('password')
        
        if not password:
            return jsonify({'success': False, 'message': 'Password required'})
        
        if not telegram_client:
            return jsonify({'success': False, 'message': 'Not in authentication flow'})
        
        # Use async helper to run the operation
        result = async_helper.run_async_safe(telegram_client.verify_password(password))
        
        # If verification successful, set session
        if result.get('success'):
            session['authenticated'] = True
            session['phone_number'] = session.get('phone_number', '')
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    global telegram_client
    
    try:
        if telegram_client:
            # Use async helper to run the operation
            result = async_helper.run_async_safe(telegram_client.logout())
            telegram_client = None
        
        # Clear app config
        app.config['TELEGRAM_AUTHENTICATED'] = False
        app.config['TELEGRAM_PHONE'] = None
        
        # Clear database settings
        try:
            db_manager.update_setting('telegram_authenticated', 'false')
            db_manager.update_setting('telegram_phone', '')
            app.logger.info("Cleared Telegram auth status from database")
        except Exception as e:
            app.logger.error(f"Failed to clear auth status from database: {e}")
        
        # Clear session
        session.clear()
        return jsonify({'success': True, 'message': 'Logged out successfully'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/auth/status', methods=['GET'])
def auth_status():
    global telegram_client
    
    try:
        # Check both session and client authentication
        session_authenticated = session.get('authenticated', False)
        client_authenticated = telegram_client and telegram_client.is_authenticated if telegram_client else False
        
        if telegram_client and client_authenticated:
            # Use async helper to run the operation
            result = async_helper.run_async_safe(telegram_client.get_auth_status())
            result['session_authenticated'] = session_authenticated
            return jsonify({'success': True, 'status': result})
        
        return jsonify({'success': True, 'status': {
            'is_authenticated': session_authenticated and client_authenticated, 
            'auth_state': 'authenticated' if session_authenticated else 'none', 
            'phone': session.get('phone_number'),
            'session_authenticated': session_authenticated
        }})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/rules/<int:rule_id>', methods=['DELETE'])
def delete_rule(rule_id):
    try:
        # Get rule details before deletion for logging
        rule = db_manager.get_rule(rule_id)
        
        # Delete from database
        success = db_manager.delete_rule(rule_id)
        
        if not success:
            return jsonify({'success': False, 'message': 'Rule not found'})
        
        # Remove from running client if active
        if telegram_client and telegram_client.is_authenticated:
            result = async_helper.run_async_safe(telegram_client.remove_forwarding_rule(rule_id))
        
        # Log activity
        if rule:
            db_manager.log_activity(
                activity_type='rule_deleted',
                description=f"Deleted forwarding rule: {rule['source']} → {rule['target']}",
                rule_id=rule_id
            )
        
        return jsonify({'success': True, 'message': 'Rule deleted successfully'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/dialogs', methods=['GET'])
def get_dialogs():
    global telegram_client
    
    try:
        if not telegram_client or not telegram_client.is_authenticated:
            return jsonify({'success': False, 'message': 'Not authenticated'})
        
        # Use async helper to run the operation
        result = async_helper.run_async_safe(telegram_client.get_dialogs())
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/start', methods=['POST'])
def start_forwarding():
    global telegram_client, client_thread
    
    try:
        if not telegram_client or not telegram_client.is_authenticated:
            return jsonify({'success': False, 'message': 'Not authenticated'})
        
        if telegram_client.is_running:
            return jsonify({'success': False, 'message': 'Already running'})
        
        # Clear existing rules first
        telegram_client.forwarding_rules = []
        
        # First, enable ALL rules in database
        all_rules = db_manager.get_all_rules()
        enabled_rules = []
        for rule in all_rules:
            if not rule['enabled']:
                # Enable the rule in database
                updated_rule = db_manager.toggle_rule(rule['id'])
                enabled_rules.append(updated_rule)
            else:
                enabled_rules.append(rule)
        
        # Then add all enabled rules to running client
        for rule in enabled_rules:
            result = async_helper.run_async_safe(telegram_client.add_forwarding_rule(rule['source'], rule['target'], rule['filters']))
        
        # Update database status
        db_manager.set_forwarding_status(True)
        
        # Start forwarding
        # Use async helper to run the operation
        result = async_helper.run_async_safe(telegram_client.start_forwarding())
        
        if result.get('success'):
            db_manager.set_forwarding_status(True)
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/stop', methods=['POST'])
def stop_forwarding():
    global telegram_client
    
    try:
        if telegram_client:
            # Use async helper to run the operation
            result = async_helper.run_async_safe(telegram_client.stop_forwarding())
            
            if result.get('success'):
                # Clear client rules first
                telegram_client.forwarding_rules = []
                
                # Deactivate ALL rules in database when stopping
                all_rules = db_manager.get_all_rules()
                for rule in all_rules:
                    if rule['enabled']:
                        # Disable the rule in database
                        db_manager.toggle_rule(rule['id'])
                
                db_manager.set_forwarding_status(False)
            
            return jsonify(result)
        
        # Deactivate ALL rules even if client not available
        all_rules = db_manager.get_all_rules()
        for rule in all_rules:
            if rule['enabled']:
                db_manager.toggle_rule(rule['id'])
        
        db_manager.set_forwarding_status(False)
        return jsonify({'success': True, 'message': 'Already stopped'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/rules', methods=['GET'])
def get_rules():
    try:
        rules = db_manager.get_all_rules()
        return jsonify({'success': True, 'rules': rules})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/rules', methods=['POST'])
def add_rule():
    data = request.json
    
    try:
        rule = db_manager.add_rule(
            data['source'],
            data['target'],
            data.get('filters', {})
        )
        
        # Add to running client if active and rule is enabled
        if telegram_client and telegram_client.is_authenticated and rule['enabled']:
            # Use async helper to run the operation
            result = async_helper.run_async_safe(telegram_client.add_forwarding_rule(rule['source'], rule['target'], rule['filters']))
        
        # Log activity
        db_manager.log_activity(
            activity_type='rule_created',
            description=f"Created forwarding rule: {rule['source']} → {rule['target']}",
            rule_id=rule['id']
        )
        
        return jsonify({'success': True, 'rule': rule})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/rules/<int:rule_id>/toggle', methods=['PUT', 'POST'])
def toggle_rule(rule_id):
    try:
        rule = db_manager.toggle_rule(rule_id)
        
        if not rule:
            return jsonify({'success': False, 'message': 'Rule not found'})
        
        # Update running client if authenticated
        if telegram_client and telegram_client.is_authenticated:
            if rule['enabled']:
                # Add rule to client with database ID
                result = async_helper.run_async_safe(telegram_client.add_forwarding_rule(rule['source'], rule['target'], rule['filters'], rule['id']))
                # Start forwarding if not already running
                if not telegram_client.is_running:
                    async_helper.run_async_safe(telegram_client.start_forwarding())
                    
                # Log activity
                db_manager.log_activity(
                    activity_type='rule_enabled',
                    description=f"Enabled forwarding rule: {rule['source']} → {rule['target']}",
                    rule_id=rule_id
                )
            else:
                # Remove rule from client
                result = async_helper.run_async_safe(telegram_client.remove_forwarding_rule(rule_id))
                # Check if we should stop forwarding
                enabled_rules = [r for r in db_manager.get_all_rules() if r['enabled']]
                if not enabled_rules and telegram_client.is_running:
                    async_helper.run_async_safe(telegram_client.stop_forwarding())
                    app.logger.info("Stopped forwarding - no enabled rules remaining")
                    
                # Log activity
                db_manager.log_activity(
                    activity_type='rule_disabled',
                    description=f"Disabled forwarding rule: {rule['source']} → {rule['target']}",
                    rule_id=rule_id
                )
        
        return jsonify({'success': True, 'rule': rule})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """Get current settings"""
    if 'authenticated' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'})
    
    try:
        settings = db_manager.get_settings()
        app.logger.info(f"Retrieved settings: {settings}")
        return jsonify({'success': True, 'settings': settings})
    except Exception as e:
        app.logger.error(f"Error getting settings: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/settings', methods=['POST'])
def update_settings():
    if 'authenticated' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'})
    
    data = request.json
    app.logger.info(f"Updating settings with data: {data}")
    
    try:
        db_manager.update_settings(data)
        app.logger.info("Settings updated successfully in database")
        return jsonify({'success': True, 'message': 'Settings updated'})
    
    except Exception as e:
        app.logger.error(f"Error updating settings: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/activity', methods=['GET'])
def get_activity():
    """Get recent forwarding activity"""
    if 'authenticated' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'})
    
    try:
        # Get recent activity from database (last 50 entries)
        activity = db_manager.get_recent_activity(limit=50)
        return jsonify({'success': True, 'activity': activity})
    except Exception as e:
        app.logger.error(f"Error getting activity: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/stats', methods=['GET'])
def get_dashboard_stats_api():
    """Get dashboard statistics"""
    if 'authenticated' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'})
    
    try:
        rules = db_manager.get_all_rules()
        total_rules = len(rules)
        active_rules = sum(1 for rule in rules if rule.get('enabled', False))
        total_forwards = sum(rule.get('message_count', 0) for rule in rules)
        
        # Get Telegram client stats if available
        telegram_stats = {}
        if telegram_client and telegram_client.is_authenticated:
            stats_result = async_helper.run_async_safe(telegram_client.get_stats())
            if stats_result and stats_result.get('success'):
                telegram_stats = stats_result.get('stats', {})
        
        stats = {
            'total_rules': total_rules,
            'active_rules': active_rules,
            'total_forwards': total_forwards,
            'is_authenticated': telegram_client.is_authenticated if telegram_client else False,
            'is_forwarding': telegram_client.is_running if telegram_client else False,
            'daily_forwards': telegram_stats.get('daily_forwards', 0),
            'max_daily_forwards': telegram_stats.get('max_daily_forwards', 100)
        }
        
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        app.logger.error(f"Error getting stats: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/telegram-status', methods=['GET'])
def get_telegram_status():
    """Get real-time Telegram connection status"""
    if 'authenticated' not in session:
        return jsonify({
            'success': True,
            'status': {
                'is_authenticated': False,
                'phone': None,
                'auth_state': 'none'
            }
        })
    
    try:
        # Check if client exists and is authenticated
        is_authenticated = False
        phone = None
        
        if telegram_client:
            # Check if client is still connected
            try:
                # Try to get client info to verify connection
                result = async_helper.run_async_safe(telegram_client.get_stats())
                if result and result.get('success'):
                    stats = result.get('stats', {})
                    is_authenticated = stats.get('is_authenticated', False)
                    phone = stats.get('phone')
                    
                    # Double check by trying to get client info
                    if is_authenticated and telegram_client.client:
                        try:
                            me_result = async_helper.run_async_safe(telegram_client.get_me())
                            if not me_result or not me_result.get('success'):
                                is_authenticated = False
                                phone = None
                        except Exception:
                            is_authenticated = False
                            phone = None
                            
            except Exception as e:
                app.logger.error(f"Error checking Telegram status: {e}")
                is_authenticated = False
                phone = None
        
        return jsonify({
            'success': True,
            'status': {
                'is_authenticated': is_authenticated,
                'phone': phone,
                'auth_state': 'authenticated' if is_authenticated else 'none'
            }
        })
    
    except Exception as e:
        app.logger.error(f"Error getting Telegram status: {e}")
        return jsonify({
            'success': True,
            'status': {
                'is_authenticated': False,
                'phone': None,
                'auth_state': 'error',
                'error': str(e)
            }
        })

@app.route('/api/telegram-disconnect', methods=['POST'])
def disconnect_telegram():
    """Disconnect from Telegram and clear session"""
    if 'authenticated' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'})
    
    try:
        global telegram_client
        
        # Stop forwarding if running
        if telegram_client and telegram_client.is_authenticated:
            try:
                # Stop forwarding
                async_helper.run_async_safe(telegram_client.stop_forwarding())
                
                # Disconnect client
                async_helper.run_async_safe(telegram_client.disconnect())
                
                app.logger.info("Telegram client disconnected successfully")
            except Exception as e:
                app.logger.error(f"Error disconnecting Telegram client: {e}")
        
        # Clear session data
        session.pop('telegram_authenticated', None)
        session.pop('phone_number', None)
        
        # Clear app config
        app.config['TELEGRAM_AUTHENTICATED'] = False
        app.config['TELEGRAM_PHONE'] = None
        
        # Clear database settings
        try:
            db_manager.update_setting('telegram_authenticated', 'false')
            db_manager.update_setting('telegram_phone', '')
        except Exception as e:
            app.logger.error(f"Error updating database settings: {e}")
        
        # Reset client
        telegram_client = None
        
        # Log activity
        db_manager.log_activity(
            activity_type='telegram_disconnected',
            description='Telegram account disconnected from dashboard'
        )
        
        return jsonify({'success': True, 'message': 'Disconnected from Telegram'})
    
    except Exception as e:
        app.logger.error(f"Error disconnecting from Telegram: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/change-password', methods=['POST'])
def change_password():
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    data = request.get_json()
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    
    if not current_password or not new_password:
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400
    
    if len(new_password) < 4:
        return jsonify({'success': False, 'message': 'Password must be at least 4 characters long'}), 400
    
    # Verify current password
    username = session['username']
    if not db_manager.authenticate_user(username, current_password):
        return jsonify({'success': False, 'message': 'Current password is incorrect'}), 400
    
    # Change password
    if db_manager.change_password(username, new_password):
        app.logger.info(f"Password changed for user {username}")
        return jsonify({'success': True, 'message': 'Password changed successfully'})
    else:
        return jsonify({'success': False, 'message': 'Failed to change password'}), 500

@app.route('/api/update-profile', methods=['POST'])
def update_profile():
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    data = request.get_json()
    new_username = data.get('username', '').strip()
    display_name = data.get('display_name', '').strip()
    email = data.get('email', '').strip()
    
    if not new_username:
        return jsonify({'success': False, 'message': 'Username is required'}), 400
    
    if len(new_username) < 3:
        return jsonify({'success': False, 'message': 'Username must be at least 3 characters long'}), 400
    
    current_username = session['username']
    
    # Update profile in database
    if db_manager.update_user_profile(current_username, new_username, display_name, email):
        # Update session with new username
        session['username'] = new_username
        app.logger.info(f"Profile updated for user {current_username} -> {new_username}")
        return jsonify({'success': True, 'message': 'Profile updated successfully'})
    else:
        return jsonify({'success': False, 'message': 'Failed to update profile'}), 500

@socketio.on('connect')
def handle_connect():
    emit('connected', {'data': 'Connected to server'})

@socketio.on('get_status')
def handle_get_status():
    stats = {}
    if telegram_client:
        # Use async helper to run the operation
        stats_result = async_helper.run_async_safe(telegram_client.get_stats())
        if stats_result.get('success'):
            stats = stats_result.get('stats', {})
    
    emit('status_update', stats)

# Periodic status updates
def background_thread():
    while True:
        socketio.sleep(5)  # Update every 5 seconds
        if telegram_client:
            try:
                # Use async helper to run the operation
                stats_result = async_helper.run_async_safe(telegram_client.get_stats())
                if stats_result.get('success'):
                    stats = stats_result.get('stats', {})
                    socketio.emit('status_update', stats)
            except Exception as e:
                pass  # Silently ignore errors in background thread

if __name__ == '__main__':
    # Start background thread for status updates
    socketio.start_background_task(background_thread)
    
    socketio.run(
        app, 
        debug=True, 
        host='0.0.0.0', 
        port=int(os.getenv('FLASK_PORT', 5001)),
        allow_unsafe_werkzeug=True,
        use_reloader=False  # Disable auto-restart to prevent database locks
    )
