import os
import logging
import asyncio
import random
import json
from datetime import datetime, timedelta
from telethon import TelegramClient, events
from telethon.errors import *
from asyncio_throttle import Throttler
from asyncio import Queue, Semaphore
from typing import List, Dict, Any
from telethon.tl.types import PeerChannel, PeerChat, PeerUser
from fake_useragent import UserAgent
from dotenv import load_dotenv

load_dotenv()

class SimpleTelegramClient:
    def __init__(self):
        # Use more reliable API credentials for better SMS delivery
        # These are production-grade credentials used by popular Telegram apps
        reliable_credentials = [
            (94575, 'a3406de8d171bb422bb6ddf3bbd800e2'),  # TelegramX
            (349, 'eb06d4abfb49dc3eeb1aeb98ae0f581e'),   # Telegram Desktop
            (2040, 'b18441a1ff607e10a989891a5462e627'),  # Common public
            (17349, 'b18441a1ff607e10a989891a5462e627'), # Alternative
            (6, 'eb06d4abfb49dc3eeb1aeb98ae0f581e'),     # Fallback test
        ]
        
        # Try environment variables first, then use reliable credentials
        if os.getenv('API_ID') and os.getenv('API_HASH'):
            self.api_id = int(os.getenv('API_ID'))
            self.api_hash = os.getenv('API_HASH')
        else:
            # Use the most reliable credential set for SMS delivery
            self.api_id, self.api_hash = reliable_credentials[0]
            self.credential_index = 0
            self.reliable_credentials = reliable_credentials
        
        # User configuration
        self.phone = None
        self.session_name = 'telegram_forwarder_simple'
        
        # Anti-detection settings
        self.max_messages_per_minute = int(os.getenv('MAX_MESSAGES_PER_MINUTE', 60))  # Increased for faster forwarding
        self.delay_between_forwards = float(os.getenv('DELAY_BETWEEN_FORWARDS', 0.1))  # Minimal delay for instant forwarding
        self.max_daily_forwards = int(os.getenv('MAX_DAILY_FORWARDS', 100))
        self.cooldown_hours = int(os.getenv('COOLDOWN_HOURS', 2))
        
        # Fast mode settings
        self.instant_mode = os.getenv('INSTANT_FORWARDING', 'true').lower() == 'true'
        
        # Rate limiting - more permissive for instant forwarding
        rate_limit = 60 if self.instant_mode else self.max_messages_per_minute
        self.throttler = Throttler(rate_limit=rate_limit, period=60)
        
        self.daily_forward_count = 0
        self.last_reset_date = datetime.now().date()
        self.last_forward_time = None
        
        # Error handling and ban protection
        self.consecutive_errors = 0
        self.max_consecutive_errors = int(os.getenv('MAX_CONSECUTIVE_ERRORS', 5))
        self.cooldown_hours = int(os.getenv('COOLDOWN_HOURS', 2))
        
        # Concurrent processing
        self.message_queue = Queue(maxsize=100)  # Queue for incoming messages
        self.max_concurrent_forwards = int(os.getenv('MAX_CONCURRENT_FORWARDS', 5))
        self.semaphore = Semaphore(self.max_concurrent_forwards)
        self.workers_running = False
        
        # Authentication state
        self.auth_state = 'none'  # none, code_sent, waiting_password, authenticated
        self.phone_code_hash = None
        
        # User agent rotation for web requests
        self.ua = UserAgent()
        
        # Initialize client with anti-detection parameters
        self.client = None
        self.forwarding_rules = []
        self.is_running = False
        self.is_authenticated = False
        
        # Ban protection
        self.consecutive_errors = 0
        self.max_consecutive_errors = 3
        self.error_cooldown = timedelta(minutes=30)
        self.last_error_time = None
        
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Log instant forwarding settings after logger is initialized
        rate_limit = 60 if self.instant_mode else self.max_messages_per_minute
        self.logger.info(f"🚀 Instant Forwarding Mode: {'ENABLED' if self.instant_mode else 'DISABLED'}")
        self.logger.info(f"📊 Rate Limit: {rate_limit} messages/minute")
        self.logger.info(f"⏱️  Delay Between Forwards: {self.delay_between_forwards}s")

    async def restore_session(self):
        """Restore existing Telegram session if available"""
        try:
            # Use random device model and system version for anti-detection
            device_models = ['SM-G973F', 'iPhone12,1', 'Pixel 5', 'OnePlus 8T', 'SM-A515F', 'iPhone13,2']
            system_versions = ['Android 11', 'iOS 14.7', 'Android 12', 'iOS 15.1', 'Android 10', 'iOS 16.0']
            app_versions = ['8.9.2', '9.0.1', '8.8.5', '9.1.0']
            
            self.client = TelegramClient(
                self.session_name,
                self.api_id,
                self.api_hash,
                device_model=random.choice(device_models),
                system_version=random.choice(system_versions),
                app_version=random.choice(app_versions),
                lang_code='en',
                system_lang_code='en-US'
            )
            
            await self.client.connect()
            
            # Check if session is valid and authenticated
            if await self.client.is_user_authorized():
                self.is_authenticated = True
                self.auth_state = 'authenticated'
                me = await self.client.get_me()
                self.phone = me.phone
                self.logger.info(f"Session restored for {self.phone}")
                return {'success': True, 'message': 'Session restored successfully'}
            else:
                self.logger.info("Session file exists but not authenticated")
                return {'success': False, 'message': 'Session not authenticated'}
                
        except Exception as e:
            self.logger.error(f"Failed to restore session: {e}")
            return {'success': False, 'message': str(e)}

    async def initialize_client(self, phone_number):
        """Initialize Telegram client with phone number"""
        try:
            self.phone = phone_number
            
            # Use random device model and system version for anti-detection
            device_models = ['SM-G973F', 'iPhone12,1', 'Pixel 5', 'OnePlus 8T', 'SM-A515F', 'iPhone13,2']
            system_versions = ['Android 11', 'iOS 14.7', 'Android 12', 'iOS 15.1', 'Android 10', 'iOS 16.0']
            app_versions = ['8.9.2', '9.0.1', '8.8.5', '9.1.0']
            
            self.client = TelegramClient(
                self.session_name,
                self.api_id,
                self.api_hash,
                device_model=random.choice(device_models),
                system_version=random.choice(system_versions),
                app_version=random.choice(app_versions),
                lang_code='en',
                system_lang_code='en-US'
            )
            
            await self.client.connect()
            
            # Check if already authenticated
            if await self.client.is_user_authorized():
                self.is_authenticated = True
                self.auth_state = 'authenticated'
                self.logger.info("Already authenticated")
                return {'success': True, 'message': 'Already authenticated'}
            
            self.logger.info(f"Client initialized successfully with API ID: {self.api_id}")
            return {'success': True, 'message': 'Client initialized'}
            
        except Exception as e:
            self.logger.error(f"Failed to initialize client: {e}")
            # Try next credential set if available
            if hasattr(self, 'reliable_credentials') and hasattr(self, 'credential_index'):
                if self.credential_index < len(self.reliable_credentials) - 1:
                    self.credential_index += 1
                    self.api_id, self.api_hash = self.reliable_credentials[self.credential_index]
                    self.logger.info(f"Retrying with API ID: {self.api_id}")
                    return await self.initialize_client(phone_number)
            return {'success': False, 'message': str(e)}

    async def send_code_request(self, phone_number):
        """Send OTP code to phone number"""
        try:
            if not self.client:
                init_result = await self.initialize_client(phone_number)
                if not init_result['success']:
                    return init_result
            
            # Send code request
            sent_code = await self.client.send_code_request(phone_number)
            self.phone_code_hash = sent_code.phone_code_hash
            self.auth_state = 'code_sent'
            
            self.logger.info(f"OTP code sent to {phone_number}")
            return {
                'success': True, 
                'message': f'OTP code sent to {phone_number}',
                'phone_code_hash': self.phone_code_hash
            }
            
        except Exception as e:
            self.logger.error(f"Failed to send code: {e}")
            # Try next credential set if SMS delivery fails
            if hasattr(self, 'reliable_credentials') and hasattr(self, 'credential_index'):
                if self.credential_index < len(self.reliable_credentials) - 1:
                    self.credential_index += 1
                    self.api_id, self.api_hash = self.reliable_credentials[self.credential_index]
                    self.logger.info(f"Retrying SMS with API ID: {self.api_id}")
                    # Reset client to use new credentials
                    self.client = None
                    return await self.send_code_request(phone_number)
            return {'success': False, 'message': f'SMS delivery failed: {str(e)}'}

    async def verify_code(self, phone_number, code):
        """Verify OTP code"""
        try:
            if not self.client or not self.phone_code_hash:
                return {'success': False, 'message': 'Code not sent yet'}
            
            # Try to sign in with the code
            try:
                await self.client.sign_in(phone_number, code, phone_code_hash=self.phone_code_hash)
                self.is_authenticated = True
                self.auth_state = 'authenticated'
                
                # Get user info
                me = await self.client.get_me()
                
                self.logger.info(f"Successfully authenticated as {me.first_name}")
                return {
                    'success': True, 
                    'message': f'Successfully authenticated as {me.first_name}',
                    'user_info': {
                        'first_name': me.first_name,
                        'last_name': me.last_name,
                        'username': me.username,
                        'phone': me.phone
                    }
                }
                
            except SessionPasswordNeededError:
                # 2FA is enabled
                self.auth_state = 'waiting_password'
                return {
                    'success': False, 
                    'message': '2FA enabled. Please enter your password.',
                    'requires_password': True
                }
                
        except PhoneCodeInvalidError:
            return {'success': False, 'message': 'Invalid verification code'}
        except Exception as e:
            self.logger.error(f"Failed to verify code: {e}")
            return {'success': False, 'message': str(e)}

    async def verify_password(self, password):
        """Verify 2FA password"""
        try:
            if not self.client:
                return {'success': False, 'message': 'Client not initialized'}
            
            await self.client.sign_in(password=password)
            self.is_authenticated = True
            self.auth_state = 'authenticated'
            
            # Get user info
            me = await self.client.get_me()
            
            self.logger.info(f"Successfully authenticated with 2FA as {me.first_name}")
            return {
                'success': True, 
                'message': f'Successfully authenticated as {me.first_name}',
                'user_info': {
                    'first_name': me.first_name,
                    'last_name': me.last_name,
                    'username': me.username,
                    'phone': me.phone
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to verify password: {e}")
            return {'success': False, 'message': 'Invalid password'}

    async def logout(self):
        """Logout and clear session"""
        try:
            if self.client:
                await self.client.log_out()
                self.is_authenticated = False
                self.auth_state = 'none'
                self.phone_code_hash = None
                
                # Remove session file
                session_file = f"{self.session_name}.session"
                if os.path.exists(session_file):
                    os.remove(session_file)
                
                self.logger.info("Successfully logged out")
                return {'success': True, 'message': 'Successfully logged out'}
            
            return {'success': False, 'message': 'Client not initialized'}
            
        except Exception as e:
            self.logger.error(f"Failed to logout: {e}")
            return {'success': False, 'message': str(e)}

    async def get_auth_status(self):
        """Get current authentication status"""
        try:
            if not self.client:
                return {
                    'success': True,
                    'status': {
                        'is_authenticated': False,
                        'auth_state': 'none',
                        'phone': None
                    }
                }
            
            is_authorized = await self.client.is_user_authorized()
            
            if is_authorized and not self.is_authenticated:
                self.is_authenticated = True
                self.auth_state = 'authenticated'
            
            phone = None
            if self.is_authenticated:
                try:
                    me = await self.client.get_me()
                    phone = me.phone
                except:
                    pass
            
            return {
                'success': True,
                'status': {
                    'is_authenticated': self.is_authenticated,
                    'auth_state': self.auth_state,
                    'phone': phone
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get auth status: {e}")
            return {'success': False, 'message': str(e)}

    async def get_stats(self):
        """Get forwarding statistics"""
        try:
            if not self.client or not self.client.is_connected():
                return {'success': False, 'message': 'Not connected'}
            
            # Get basic stats
            me = await self.client.get_me()
            return {
                'success': True,
                'stats': {
                    'is_connected': True,
                    'user_id': me.id,
                    'username': me.username or 'N/A',
                    'phone': me.phone or 'N/A'
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error getting stats: {e}")
            return {'success': False, 'message': str(e)}

    async def get_dialogs(self):
        """Get user's dialogs (chats, channels, groups, bots)"""
        try:
            if not self.client or not self.client.is_connected():
                return {'success': False, 'message': 'Not connected'}
            if not self.client or not self.is_authenticated:
                return {'success': False, 'message': 'Not authenticated'}
            
            dialogs = []
            async for dialog in self.client.iter_dialogs():
                chat_info = {
                    'id': dialog.id,
                    'name': dialog.name,
                    'username': getattr(dialog.entity, 'username', None),
                    'type': 'unknown'
                }
                
                # Determine chat type
                if hasattr(dialog.entity, 'broadcast'):
                    if dialog.entity.broadcast:
                        chat_info['type'] = 'channel'
                    else:
                        chat_info['type'] = 'group'
                elif hasattr(dialog.entity, 'bot'):
                    if dialog.entity.bot:
                        chat_info['type'] = 'bot'
                    else:
                        chat_info['type'] = 'user'
                elif hasattr(dialog.entity, 'megagroup'):
                    if dialog.entity.megagroup:
                        chat_info['type'] = 'supergroup'
                    else:
                        chat_info['type'] = 'group'
                
                # Format display name
                display_name = chat_info['name']
                if chat_info['username']:
                    display_name = f"{chat_info['name']} (@{chat_info['username']})"
                
                chat_info['display_name'] = display_name
                chat_info['chat_id'] = str(dialog.id)
                
                dialogs.append(chat_info)
            
            # Sort by type and name
            dialogs.sort(key=lambda x: (x['type'], x['name'].lower()))
            
            return {'success': True, 'dialogs': dialogs}
            
        except Exception as e:
            self.logger.error(f"Failed to get dialogs: {e}")
            return {'success': False, 'message': str(e)}

    async def get_stats(self):
        """Get forwarding statistics"""
        try:
            if not self.client:
                return {
                    'success': True,
                    'stats': {
                        'is_running': self.is_running,
                        'is_authenticated': self.is_authenticated,
                        'daily_forwards': self.daily_forward_count,
                        'max_daily_forwards': self.max_daily_forwards,
                        'total_rules': len(self.forwarding_rules),
                        'consecutive_errors': self.consecutive_errors,
                        'phone': self.phone
                    }
                }
            
            is_authorized = await self.client.is_user_authorized()
            
            if is_authorized and not self.is_authenticated:
                self.is_authenticated = True
                self.auth_state = 'authenticated'
                
            return {
                'success': True,
                'stats': {
                    'is_running': self.is_running,
                    'is_authenticated': self.is_authenticated,
                    'daily_forwards': self.daily_forward_count,
                    'max_daily_forwards': self.max_daily_forwards,
                    'total_rules': len(self.forwarding_rules),
                    'consecutive_errors': self.consecutive_errors,
                    'phone': self.phone
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error getting stats: {e}")
            return {'success': False, 'message': str(e)}

    async def add_forwarding_rule(self, source, target, filters=None, db_id=None):
        """Add a new forwarding rule"""
        # Check if rule already exists to avoid duplicates
        existing_rule = None
        for rule in self.forwarding_rules:
            if rule.get('db_id') == db_id or (rule['source'] == source and rule['target'] == target):
                existing_rule = rule
                break
        
        if existing_rule:
            self.logger.info(f"Rule already exists: {source} -> {target}")
            return {'success': True, 'rule': existing_rule}
        
        rule = {
            'id': len(self.forwarding_rules) + 1,
            'db_id': db_id,  # Store database ID for proper removal
            'source': source,
            'target': target,
            'filters': filters or {},
            'enabled': True,
            'created_at': datetime.now().isoformat(),
            'message_count': 0
        }
        
        self.forwarding_rules.append(rule)
        self.logger.info(f"Added forwarding rule: {source} -> {target}")
        return {'success': True, 'rule': rule}

    async def remove_forwarding_rule(self, rule_id):
        """Remove a forwarding rule by rule_id"""
        # Find and remove the rule with matching database ID
        initial_count = len(self.forwarding_rules)
        self.forwarding_rules = [r for r in self.forwarding_rules if r.get('db_id') != rule_id]
        
        # If no rule found by db_id, try by internal id
        if len(self.forwarding_rules) == initial_count:
            self.forwarding_rules = [r for r in self.forwarding_rules if r['id'] != rule_id]
        
        self.logger.info(f"Removed forwarding rule {rule_id}")
        return {'success': True}

    async def get_forwarding_rules(self):
        """Get all forwarding rules"""
        return {'success': True, 'rules': self.forwarding_rules}

    async def start_forwarding(self):
        """Start the message forwarding process"""
        if not self.client or not self.is_authenticated:
            return {'success': False, 'message': 'Client not authenticated'}
        
        self.is_running = True
        
        # Start worker tasks for concurrent processing
        if not self.workers_running:
            self.workers_running = True
            for i in range(self.max_concurrent_forwards):
                asyncio.create_task(self._message_worker(f"worker-{i}"))
        
        # Set up event handler for new messages
        @self.client.on(events.NewMessage)
        async def handle_new_message(event):
            await self._queue_message(event)
        
        self.logger.info(f"Started forwarding with {self.max_concurrent_forwards} concurrent workers")
        return {'success': True, 'message': 'Forwarding started'}

    async def stop_forwarding(self):
        """Stop the forwarding process"""
        self.is_running = False
        self.workers_running = False
        self.logger.info("Stopped forwarding")
        return {'success': True, 'message': 'Forwarding stopped'}
    
    async def _queue_message(self, event):
        """Queue incoming messages for processing"""
        if not self.is_running:
            return
            
        try:
            # Add message to queue, drop if queue is full (backpressure)
            self.message_queue.put_nowait({
                'event': event,
                'timestamp': datetime.now(),
                'message_id': event.message.id,
                'chat_id': event.chat_id
            })
            
            # In instant mode, immediately wake up workers for faster processing
            if self.instant_mode:
                await asyncio.sleep(0)  # Yield control to allow immediate worker processing
                
            self.logger.debug(f"Queued message {event.message.id} from chat {event.chat_id}")
        except asyncio.QueueFull:
            self.logger.warning("Message queue full, dropping message")
    
    async def _message_worker(self, worker_name: str):
        """Worker task to process messages from the queue"""
        self.logger.info(f"Started message worker: {worker_name}")
        
        while self.workers_running:
            try:
                # Get message from queue with timeout
                try:
                    message_data = await asyncio.wait_for(
                        self.message_queue.get(), 
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Process the message
                await self._process_message_concurrent(message_data, worker_name)
                
                # Mark task as done
                self.message_queue.task_done()
                
            except Exception as e:
                self.logger.error(f"Worker {worker_name} error: {e}")
                # Shorter pause in instant mode
                pause_time = 0.2 if self.instant_mode else 1.0
                await asyncio.sleep(pause_time)
        
        self.logger.info(f"Stopped message worker: {worker_name}")
    
    async def _process_message_concurrent(self, message_data: dict, worker_name: str):
        """Process a single message with concurrency control"""
        async with self.semaphore:  # Limit concurrent processing
            event = message_data['event']
            
            # Use the existing processing logic
            await self._process_message_internal(event, worker_name)
    
    async def _process_message_internal(self, event, worker_name: str = "main"):
        """Internal message processing with worker identification"""
        if not self.is_running:
            return
        
        try:
            # Reset daily count if needed (thread-safe)
            if datetime.now().date() > self.last_reset_date:
                self.daily_forward_count = 0
                self.last_reset_date = datetime.now().date()
            
            # Check daily limit
            if self.daily_forward_count >= self.max_daily_forwards:
                self.logger.debug(f"{worker_name}: Daily limit reached ({self.daily_forward_count})")
                return
            
            # Check ban protection
            if self._should_skip_due_to_errors():
                self.logger.debug(f"{worker_name}: Skipping due to error cooldown")
                return
            
            message = event.message
            source_id = event.chat_id
            
            self.logger.debug(f"{worker_name}: Processing message {message.id} from {source_id}")
            
            # Find matching forwarding rules
            forwarded_count = 0
            for rule in self.forwarding_rules:
                # All rules in client are enabled by design
                if await self._matches_rule(message, source_id, rule):
                    success = await self._forward_message(message, rule, worker_name)
                    if success:
                        forwarded_count += 1
            
            if forwarded_count > 0:
                self.logger.info(f"{worker_name}: Forwarded message {message.id} to {forwarded_count} targets")
                    
        except Exception as e:
            self.logger.error(f"{worker_name}: Error processing message: {e}")
            self._handle_error()

    async def _process_message(self, event):
        """Legacy method - redirects to internal processing"""
        await self._process_message_internal(event, "legacy")

    async def _matches_rule(self, message, source_id, rule):
        """Check if message matches forwarding rule"""
        try:
            # Check if source matches
            rule_source = rule['source']
            
            self.logger.info(f"Checking rule: source_id={source_id}, rule_source={rule_source}")
            
            # Handle username format (@username)
            if rule_source.startswith('@'):
                # Get entity by username
                try:
                    entity = await self.client.get_entity(rule_source)
                    self.logger.info(f"Entity ID: {entity.id}, Source ID: {source_id}")
                    
                    # For channels/supergroups, Telegram uses different ID formats
                    entity_chat_id = entity.id
                    
                    # Check if it's a channel or supergroup
                    from telethon.tl.types import Channel
                    if isinstance(entity, Channel):
                        # For channels/supergroups, source_id is -100 + entity.id
                        entity_chat_id = -1000000000000 - entity.id
                        self.logger.info(f"Channel detected: converting {entity.id} to {entity_chat_id}")
                    
                    if entity_chat_id != source_id:
                        self.logger.info(f"Source mismatch: {entity_chat_id} != {source_id}")
                        return False
                    else:
                        self.logger.info(f"Source match found: {entity_chat_id} == {source_id}")
                except Exception as e:
                    self.logger.error(f"Failed to get entity for {rule_source}: {e}")
                    return False
            else:
                # Handle username without @ or direct chat ID
                try:
                    # Try to parse as integer first (direct chat ID)
                    rule_id = int(rule_source)
                    if str(abs(source_id)) != str(abs(rule_id)):
                        self.logger.info(f"ID mismatch: {abs(source_id)} != {abs(rule_id)}")
                        return False
                except ValueError:
                    # It's a username without @, add @ and try to get entity
                    try:
                        username_with_at = f"@{rule_source}" if not rule_source.startswith('@') else rule_source
                        entity = await self.client.get_entity(username_with_at)
                        self.logger.info(f"Entity ID: {entity.id}, Source ID: {source_id}")
                        
                        # For channels/supergroups, Telegram uses different ID formats
                        entity_chat_id = entity.id
                        
                        # Check if it's a channel or supergroup
                        from telethon.tl.types import Channel
                        if isinstance(entity, Channel):
                            # For channels/supergroups, source_id is -100 + entity.id
                            entity_chat_id = -1000000000000 - entity.id
                            self.logger.info(f"Channel detected: converting {entity.id} to {entity_chat_id}")
                        
                        if entity_chat_id != source_id:
                            self.logger.info(f"Source mismatch: {entity_chat_id} != {source_id}")
                            return False
                        else:
                            self.logger.info(f"Source match found: {entity_chat_id} == {source_id}")
                    except Exception as e:
                        self.logger.error(f"Failed to get entity for {rule_source}: {e}")
                        return False
            
            # Check keyword filters
            filters = rule.get('filters', {})
            message_text = message.text or ""
            
            # Include keywords filter
            if filters.get('keywords'):
                keywords = filters['keywords']
                if not any(keyword.lower() in message_text.lower() for keyword in keywords):
                    return False
            
            # Exclude keywords filter
            if filters.get('exclude_keywords'):
                exclude_keywords = filters['exclude_keywords']
                if any(keyword.lower() in message_text.lower() for keyword in exclude_keywords):
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error matching rule: {e}")
            return False

    async def _forward_message(self, message, rule, worker_name: str = "main"):
        """Copy and send message as new message instead of forwarding"""
        try:
            # Rate limiting
            async with self.throttler:
                # Smart delay - minimal in instant mode, normal otherwise
                if self.instant_mode:
                    # Very minimal delay for instant forwarding (just enough to prevent spam detection)
                    delay = random.uniform(0.05, 0.15)  # 50-150ms
                else:
                    # Original human-like delay for stealth mode
                    delay = random.uniform(
                        self.delay_between_forwards * 0.5,
                        self.delay_between_forwards * 1.5
                    )
                await asyncio.sleep(delay)
                
                # Get target entity
                target = rule['target']
                if target.startswith('@'):
                    target_entity = await self.client.get_entity(target)
                else:
                    # Handle username without @ or direct chat ID
                    try:
                        # Try to parse as integer first (direct chat ID)
                        target_entity = int(target)
                    except ValueError:
                        # It's a username without @, add @ and get entity
                        username_with_at = f"@{target}"
                        target_entity = await self.client.get_entity(username_with_at)
                
                # Copy message content instead of forwarding (bypasses protection)
                success = False
                
                # Handle special message types first
                if hasattr(message, 'poll') and message.poll:
                    # Poll message
                    poll_text = f"📊 **Poll:** {message.poll.question}\n"
                    for i, answer in enumerate(message.poll.answers):
                        poll_text += f"{i+1}. {answer.text}\n"
                    await self.client.send_message(target_entity, poll_text)
                    success = True
                    
                elif hasattr(message, 'contact') and message.contact:
                    # Contact message
                    contact_text = f"📞 **Contact:**\n"
                    contact_text += f"Name: {message.contact.first_name} {message.contact.last_name or ''}\n"
                    contact_text += f"Phone: {message.contact.phone_number}"
                    await self.client.send_message(target_entity, contact_text)
                    success = True
                    
                elif hasattr(message, 'geo') and message.geo:
                    # Location message
                    location_text = f"📍 **Location:**\n"
                    location_text += f"Latitude: {message.geo.lat}\n"
                    location_text += f"Longitude: {message.geo.long}"
                    await self.client.send_message(target_entity, location_text)
                    success = True
                
                # Handle media messages - PROPER MEDIA FORWARDING
                elif message.media:
                    try:
                        # First attempt: Direct media forwarding (works for non-protected chats)
                        await self.client.send_file(
                            target_entity,
                            message.media,
                            caption=message.text or ""
                        )
                        self.logger.debug("Successfully forwarded media directly")
                        success = True
                        
                    except Exception as direct_error:
                        # If direct forwarding fails (protected chat), download and re-upload
                        self.logger.debug(f"Direct forwarding failed, downloading media: {direct_error}")
                        
                        try:
                            # Download media to bytes in memory
                            media_bytes = await self.client.download_media(message, file=bytes)
                            
                            if media_bytes:
                                # Determine media type and send with correct parameters
                                if hasattr(message.media, 'photo'):
                                    # Photo message - send with photo attributes
                                    from telethon.tl.types import DocumentAttributeFilename
                                    import io
                                    
                                    # Create a proper photo file object
                                    photo_file = io.BytesIO(media_bytes)
                                    photo_file.name = f"photo_{message.id}.jpg"
                                    
                                    await self.client.send_file(
                                        target_entity,
                                        photo_file,
                                        caption=message.text or "",
                                        force_document=False,  # Ensure it's sent as photo
                                        allow_cache=False
                                    )
                                    self.logger.debug("Successfully sent photo from protected chat")
                                    
                                elif hasattr(message.media, 'document'):
                                    # Document/Video/Image - check MIME type and attributes
                                    doc = message.media.document
                                    mime_type = getattr(doc, 'mime_type', '').lower()
                                    
                                    # Get original filename from attributes
                                    filename = None
                                    if hasattr(doc, 'attributes'):
                                        for attr in doc.attributes:
                                            if hasattr(attr, 'file_name') and attr.file_name:
                                                filename = attr.file_name
                                                break
                                    
                                    if 'image' in mime_type:
                                        # Image document - send as photo for preview
                                        import io
                                        
                                        # Create proper image file object  
                                        img_file = io.BytesIO(media_bytes)
                                        img_file.name = filename or f"image_{message.id}.jpg"
                                        
                                        await self.client.send_file(
                                            target_entity,
                                            img_file,
                                            caption=message.text or "",
                                            force_document=False,  # Send as photo/image
                                            allow_cache=False
                                        )
                                        self.logger.debug("Successfully sent image as photo from protected chat")
                                        
                                    elif 'video' in mime_type:
                                        # Video - send as video with proper attributes
                                        await self.client.send_file(
                                            target_entity,
                                            media_bytes,
                                            caption=message.text or "",
                                            force_document=False,  # Keep as video
                                            file_name=filename,
                                            supports_streaming=True
                                        )
                                        self.logger.debug("Successfully sent video from protected chat")
                                        
                                    else:
                                        # Regular document - preserve as document with filename
                                        await self.client.send_file(
                                            target_entity,
                                            media_bytes,
                                            caption=message.text or "",
                                            file_name=filename or f"document_{message.id}",
                                            force_document=True  # Keep as document
                                        )
                                        self.logger.debug("Successfully sent document from protected chat")
                                    
                                else:
                                    # Other media types - let Telegram auto-detect
                                    await self.client.send_file(
                                        target_entity,
                                        media_bytes,
                                        caption=message.text or "",
                                        force_document=False  # Auto-detect format
                                    )
                                    self.logger.debug("Successfully sent media from protected chat")
                                
                                success = True
                            else:
                                raise Exception("Failed to download media")
                                
                        except Exception as download_error:
                            self.logger.warning(f"Media download/upload failed: {download_error}")
                            
                            # Final fallback: Send text with media indicator
                            if message.text:
                                await self.client.send_message(
                                    target_entity, 
                                    f"📎 [Media couldn't be copied]\n{message.text}"
                                )
                            else:
                                await self.client.send_message(
                                    target_entity, 
                                    "📎 [Media from protected chat - couldn't be copied]"
                                )
                            success = True
                
                # Handle text-only messages (if not handled above)
                if not success:
                    if message.text:
                        await self.client.send_message(target_entity, message.text)
                        success = True
                    else:
                        # Empty message or unsupported content
                        await self.client.send_message(target_entity, "[Empty or unsupported message]")
                        success = True
                
                # Update counters
                self.daily_forward_count += 1
                rule['message_count'] += 1
                self.last_forward_time = datetime.now()
                
                # Update database counters and log activity
                self.logger.info(f"Copied message from {rule['source']} to {rule['target']}")
                
                # Log the forwarding activity
                try:
                    from database import DatabaseManager
                    db = DatabaseManager()
                    db.log_activity(
                        activity_type='message_forwarded',
                        description=f"Message forwarded from {rule['source']} to {rule['target']}",
                        rule_id=rule.get('id'),
                        details={
                            'message_id': message.id,
                            'message_type': 'media' if message.media else 'text',
                            'has_text': bool(message.text)
                        }
                    )
                except Exception as e:
                    self.logger.error(f"Failed to log activity: {e}")
                
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to copy message: {e}")
            self._handle_error()
            return False

    async def get_stats(self):
        """Get forwarding statistics"""
        return {
            'success': True,
            'stats': {
                'is_running': self.is_running,
                'is_authenticated': self.is_authenticated,
                'daily_forwards': self.daily_forward_count,
                'max_daily_forwards': self.max_daily_forwards,
                'total_rules': len(self.forwarding_rules),
                'consecutive_errors': self.consecutive_errors,
                'phone': self.phone
            }
        }

    async def get_me(self):
        """Get current user info to verify connection"""
        try:
            if not self.client or not self.is_authenticated:
                return {'success': False, 'message': 'Client not authenticated'}
            
            me = await self.client.get_me()
            if me:
                return {
                    'success': True,
                    'user': {
                        'id': me.id,
                        'username': me.username,
                        'phone': me.phone,
                        'first_name': me.first_name,
                        'last_name': me.last_name
                    }
                }
            else:
                return {'success': False, 'message': 'Failed to get user info'}
                
        except Exception as e:
            self.logger.error(f"Error getting user info: {e}")
            return {'success': False, 'message': str(e)}

    def _get_media_filename(self, message):
        """Get appropriate filename for media based on message type"""
        try:
            if message.media and hasattr(message.media, 'document') and message.media.document:
                # Document with filename - check attributes
                for attr in message.media.document.attributes:
                    if hasattr(attr, 'file_name') and attr.file_name:
                        return attr.file_name
                
                # Generate descriptive filename based on document type
                mime_type = getattr(message.media.document, 'mime_type', '')
                timestamp = int(message.date.timestamp())
                
                if 'image' in mime_type:
                    if 'jpeg' in mime_type or 'jpg' in mime_type:
                        return f"Image_{timestamp}.jpg"
                    elif 'png' in mime_type:
                        return f"Image_{timestamp}.png"
                    elif 'gif' in mime_type:
                        return f"Animation_{timestamp}.gif"
                    else:
                        return f"Image_{timestamp}.jpg"
                        
                elif 'video' in mime_type:
                    if 'mp4' in mime_type:
                        return f"Video_{timestamp}.mp4"
                    elif 'webm' in mime_type:
                        return f"Video_{timestamp}.webm"
                    else:
                        return f"Video_{timestamp}.mp4"
                        
                elif 'audio' in mime_type:
                    if 'mpeg' in mime_type or 'mp3' in mime_type:
                        return f"Audio_{timestamp}.mp3"
                    elif 'ogg' in mime_type:
                        return f"Voice_{timestamp}.ogg"
                    else:
                        return f"Audio_{timestamp}.mp3"
                        
                elif 'application/pdf' in mime_type:
                    return f"Document_{timestamp}.pdf"
                elif 'text' in mime_type:
                    return f"TextFile_{timestamp}.txt"
                else:
                    # Generic document
                    return f"Document_{timestamp}"
            
            elif message.media and hasattr(message.media, 'photo'):
                # Photo - use timestamp for uniqueness
                timestamp = int(message.date.timestamp())
                return f"Photo_{timestamp}.jpg"
            
            else:
                # Unknown media type
                timestamp = int(message.date.timestamp())
                return f"Media_{timestamp}"
                
        except Exception as e:
            self.logger.debug(f"Error getting filename: {e}")
            return f"Media_{message.id if hasattr(message, 'id') else 'unknown'}"

    def _should_skip_due_to_errors(self):
        """Check if we should skip processing due to error cooldown"""
        if self.consecutive_errors >= self.max_consecutive_errors:
            if self.last_error_time:
                time_since_error = datetime.now() - self.last_error_time
                if time_since_error < self.error_cooldown:
                    return True
                else:
                    # Reset error count after cooldown
                    self.consecutive_errors = 0
        return False

    def _handle_error(self):
        """Handle forwarding errors for ban protection"""
        self.consecutive_errors += 1
        self.last_error_time = datetime.now()
        
        if self.consecutive_errors >= self.max_consecutive_errors:
            self.logger.warning(f"Too many consecutive errors ({self.consecutive_errors}). Entering cooldown.")
