// Modern App JavaScript - Telegram Auto Forwarder
// Clean, organized, and functional JavaScript with no conflicts

class TelegramForwarderApp {
    constructor() {
        this.socket = null;
        this.currentTheme = localStorage.getItem('theme') || 'light';
        this.sidebarCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
        this.rules = [];
        this.dialogs = [];
        this.stats = {
            todaysForwards: 0,
            activeRules: 0,
            maxDailyForwards: 100,
            errorCount: 0
        };
        this.telegramConnected = false;
        this.isForwarding = false;
    }

    // Initialize the application
    init() {
        this.applyTheme();
        this.initializeSocketIO();
        this.attachEventListeners();
        this.loadInitialData();
        this.startStatusUpdates();
        this.initializeTooltips();
        console.log('TelegramForwarder App initialized');
    }

    // Theme Management
    applyTheme() {
        document.documentElement.setAttribute('data-theme', this.currentTheme);
        this.updateThemeToggle();
    }

    toggleTheme() {
        this.currentTheme = this.currentTheme === 'light' ? 'dark' : 'light';
        localStorage.setItem('theme', this.currentTheme);
        this.applyTheme();
    }

    updateThemeToggle() {
        const themeIcon = document.querySelector('#themeToggle i');
        if (themeIcon) {
            themeIcon.className = this.currentTheme === 'light' ? 'fas fa-moon' : 'fas fa-sun';
        }
    }

    // Sidebar Management
    toggleSidebar() {
        const sidebar = document.querySelector('.sidebar');
        if (sidebar) {
            sidebar.classList.toggle('collapsed');
            this.sidebarCollapsed = sidebar.classList.contains('collapsed');
            localStorage.setItem('sidebarCollapsed', this.sidebarCollapsed);
        }
    }

    // Socket.IO Management
    initializeSocketIO() {
        this.socket = io();
        
        this.socket.on('connect', () => {
            console.log('Connected to server');
            this.updateConnectionStatus(true);
        });
        
        this.socket.on('disconnect', () => {
            console.log('Disconnected from server');
            this.updateConnectionStatus(false);
        });
        
        this.socket.on('status_update', (data) => {
            this.handleStatusUpdate(data);
        });
        
        this.socket.on('forwarding_event', (data) => {
            this.handleForwardingEvent(data);
        });
        
        this.socket.on('error', (error) => {
            console.error('Socket error:', error);
            this.showNotification('Connection error occurred', 'error');
        });
    }

    // Event Listeners
    attachEventListeners() {
        // Theme toggle
        document.getElementById('themeToggle')?.addEventListener('click', () => this.toggleTheme());
        
        // Sidebar toggle
        document.getElementById('sidebarToggle')?.addEventListener('click', () => this.toggleSidebar());
        
        // Mobile sidebar overlay
        document.querySelector('.sidebar-overlay')?.addEventListener('click', () => {
            document.querySelector('.sidebar')?.classList.remove('show');
        });
        
        // Rule management
        document.getElementById('addRuleBtn')?.addEventListener('click', () => this.showAddRuleModal());
        document.getElementById('saveRuleBtn')?.addEventListener('click', () => this.saveRule());
        
        // Telegram connection
        document.getElementById('connectTelegramBtn')?.addEventListener('click', () => this.connectTelegram());
        document.getElementById('disconnectTelegramBtn')?.addEventListener('click', () => this.disconnectTelegram());
        
        // Form submissions
        document.getElementById('addRuleForm')?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveRule();
        });
        
        // Close modals
        document.querySelectorAll('.modal-close').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const modal = e.target.closest('.modal');
                if (modal) this.closeModal(modal.id);
            });
        });
        
        // Rule actions delegation
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-action="toggle-rule"]')) {
                const ruleId = e.target.dataset.ruleId;
                this.toggleRule(ruleId);
            } else if (e.target.matches('[data-action="edit-rule"]')) {
                const ruleId = e.target.dataset.ruleId;
                this.editRule(ruleId);
            } else if (e.target.matches('[data-action="delete-rule"]')) {
                const ruleId = e.target.dataset.ruleId;
                this.deleteRule(ruleId);
            }
        });
        
        // Search functionality
        document.getElementById('searchInput')?.addEventListener('input', (e) => {
            this.handleSearch(e.target.value);
        });
    }

    // Data Loading
    async loadInitialData() {
        try {
            // Load status
            const statusResponse = await fetch('/api/status');
            const statusData = await statusResponse.json();
            if (statusData.success) {
                this.handleStatusUpdate(statusData);
            }
            
            // Load rules
            const rulesResponse = await fetch('/api/rules');
            const rulesData = await rulesResponse.json();
            if (rulesData.success) {
                this.rules = rulesData.rules;
                this.renderRules();
            }
            
            // Load dialogs
            const dialogsResponse = await fetch('/api/dialogs');
            const dialogsData = await dialogsResponse.json();
            if (dialogsData.success) {
                this.dialogs = dialogsData.dialogs;
                this.updateDialogSelects();
            }
        } catch (error) {
            console.error('Error loading initial data:', error);
        }
    }

    // Status Updates
    startStatusUpdates() {
        // Update every 3 seconds
        setInterval(() => this.updateStatus(), 3000);
    }

    async updateStatus() {
        try {
            const response = await fetch('/api/status');
            const data = await response.json();
            if (data.success) {
                this.handleStatusUpdate(data);
            }
        } catch (error) {
            console.error('Error updating status:', error);
        }
    }

    handleStatusUpdate(data) {
        // Update stats
        if (data.stats) {
            this.stats = { ...this.stats, ...data.stats };
            this.updateStatsDisplay();
        }
        
        // Update Telegram connection status
        if (data.telegram_connected !== undefined) {
            this.telegramConnected = data.telegram_connected;
            this.updateTelegramStatus();
        }
        
        // Update forwarding status
        if (data.is_forwarding !== undefined) {
            this.isForwarding = data.is_forwarding;
            this.updateForwardingStatus();
        }
        
        // Update rules if provided
        if (data.rules) {
            this.rules = data.rules;
            this.renderRules();
        }
    }

    // UI Updates
    updateStatsDisplay() {
        // Update stat cards
        document.querySelector('[data-stat="todays-forwards"]')?.textContent = this.stats.todaysForwards;
        document.querySelector('[data-stat="active-rules"]')?.textContent = this.stats.activeRules;
        document.querySelector('[data-stat="max-daily"]')?.textContent = this.stats.maxDailyForwards;
        document.querySelector('[data-stat="error-count"]')?.textContent = this.stats.errorCount;
        
        // Update progress bar
        const progress = (this.stats.todaysForwards / this.stats.maxDailyForwards) * 100;
        const progressBar = document.querySelector('.daily-progress-bar');
        if (progressBar) {
            progressBar.style.width = `${Math.min(progress, 100)}%`;
            progressBar.className = `daily-progress-bar ${progress > 80 ? 'bg-warning' : 'bg-success'}`;
        }
    }

    updateConnectionStatus(connected) {
        const indicator = document.querySelector('.connection-indicator');
        if (indicator) {
            indicator.className = `connection-indicator ${connected ? 'connected' : 'disconnected'}`;
            indicator.title = connected ? 'Connected' : 'Disconnected';
        }
    }

    updateTelegramStatus() {
        const connectBtn = document.getElementById('connectTelegramBtn');
        const disconnectBtn = document.getElementById('disconnectTelegramBtn');
        const statusBadge = document.querySelector('.telegram-status');
        
        if (this.telegramConnected) {
            connectBtn?.classList.add('hidden');
            disconnectBtn?.classList.remove('hidden');
            if (statusBadge) {
                statusBadge.className = 'telegram-status badge badge-success';
                statusBadge.textContent = 'Connected';
            }
        } else {
            connectBtn?.classList.remove('hidden');
            disconnectBtn?.classList.add('hidden');
            if (statusBadge) {
                statusBadge.className = 'telegram-status badge badge-warning';
                statusBadge.textContent = 'Not Connected';
            }
        }
    }

    updateForwardingStatus() {
        const statusIcon = document.querySelector('.forwarding-status-icon');
        const statusText = document.querySelector('.forwarding-status-text');
        
        if (this.isForwarding) {
            statusIcon?.classList.add('active');
            if (statusText) statusText.textContent = 'Active';
        } else {
            statusIcon?.classList.remove('active');
            if (statusText) statusText.textContent = 'Inactive';
        }
    }

    // Rules Management
    renderRules() {
        const rulesContainer = document.getElementById('rulesContainer');
        if (!rulesContainer) return;
        
        if (this.rules.length === 0) {
            rulesContainer.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-inbox fa-3x text-gray-400 mb-3"></i>
                    <h4 class="text-gray-600">No forwarding rules</h4>
                    <p class="text-gray-500">Create your first rule to start forwarding messages</p>
                    <button class="btn btn-primary mt-3" onclick="app.showAddRuleModal()">
                        <i class="fas fa-plus"></i> Add Rule
                    </button>
                </div>
            `;
            return;
        }
        
        const rulesHTML = this.rules.map(rule => this.createRuleCard(rule)).join('');
        rulesContainer.innerHTML = rulesHTML;
        
        // Update active rules count
        this.stats.activeRules = this.rules.filter(r => r.enabled).length;
        this.updateStatsDisplay();
    }

    createRuleCard(rule) {
        const filters = JSON.parse(rule.filters || '{}');
        const mediaTypes = filters.media_types || [];
        const keywords = filters.keywords || [];
        
        return `
            <div class="rule-card ${rule.enabled ? 'active' : 'inactive'}" data-rule-id="${rule.id}">
                <div class="rule-card-header">
                    <div class="rule-info">
                        <h5 class="rule-title">
                            <i class="fas fa-arrow-right text-primary"></i>
                            ${rule.source} → ${rule.target}
                        </h5>
                        <div class="rule-meta">
                            <span class="badge badge-info">
                                <i class="fas fa-exchange-alt"></i>
                                ${rule.message_count || 0} forwarded
                            </span>
                        </div>
                    </div>
                    <div class="rule-actions">
                        <label class="form-switch">
                            <input type="checkbox" ${rule.enabled ? 'checked' : ''} 
                                   data-action="toggle-rule" data-rule-id="${rule.id}">
                            <span class="form-switch-slider"></span>
                        </label>
                        <button class="btn btn-ghost btn-sm" data-action="edit-rule" data-rule-id="${rule.id}">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button class="btn btn-ghost btn-sm text-danger" data-action="delete-rule" data-rule-id="${rule.id}">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
                <div class="rule-card-body">
                    ${mediaTypes.length > 0 ? `
                        <div class="rule-filters">
                            <span class="filter-label">Media:</span>
                            ${mediaTypes.map(type => `<span class="badge badge-primary">${type}</span>`).join('')}
                        </div>
                    ` : ''}
                    ${keywords.length > 0 ? `
                        <div class="rule-filters">
                            <span class="filter-label">Keywords:</span>
                            ${keywords.map(kw => `<span class="badge badge-secondary">${kw}</span>`).join('')}
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    async toggleRule(ruleId) {
        try {
            const response = await fetch(`/api/rules/${ruleId}/toggle`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            const data = await response.json();
            if (data.success) {
                this.showNotification('Rule updated successfully', 'success');
                this.loadInitialData(); // Reload rules
            } else {
                this.showNotification(data.error || 'Failed to update rule', 'error');
            }
        } catch (error) {
            console.error('Error toggling rule:', error);
            this.showNotification('Error updating rule', 'error');
        }
    }

    async deleteRule(ruleId) {
        if (!confirm('Are you sure you want to delete this rule?')) return;
        
        try {
            const response = await fetch(`/api/rules/${ruleId}`, {
                method: 'DELETE'
            });
            
            const data = await response.json();
            if (data.success) {
                this.showNotification('Rule deleted successfully', 'success');
                this.loadInitialData(); // Reload rules
            } else {
                this.showNotification(data.error || 'Failed to delete rule', 'error');
            }
        } catch (error) {
            console.error('Error deleting rule:', error);
            this.showNotification('Error deleting rule', 'error');
        }
    }

    editRule(ruleId) {
        const rule = this.rules.find(r => r.id == ruleId);
        if (!rule) return;
        
        // Populate form with rule data
        const filters = JSON.parse(rule.filters || '{}');
        document.getElementById('ruleSource').value = rule.source;
        document.getElementById('ruleTarget').value = rule.target;
        document.getElementById('ruleKeywords').value = (filters.keywords || []).join(', ');
        
        // Set media types
        document.querySelectorAll('input[name="mediaTypes"]').forEach(checkbox => {
            checkbox.checked = (filters.media_types || []).includes(checkbox.value);
        });
        
        // Store rule ID for update
        document.getElementById('addRuleForm').dataset.ruleId = ruleId;
        
        // Show modal
        this.showModal('addRuleModal');
    }

    async saveRule() {
        const form = document.getElementById('addRuleForm');
        const ruleId = form.dataset.ruleId;
        
        // Get form data
        const source = document.getElementById('ruleSource').value.trim();
        const target = document.getElementById('ruleTarget').value.trim();
        const keywords = document.getElementById('ruleKeywords').value
            .split(',')
            .map(k => k.trim())
            .filter(k => k);
        
        const mediaTypes = Array.from(document.querySelectorAll('input[name="mediaTypes"]:checked'))
            .map(cb => cb.value);
        
        // Validation
        if (!source || !target) {
            this.showNotification('Please provide both source and target', 'error');
            return;
        }
        
        const ruleData = {
            source,
            target,
            filters: {
                keywords: keywords,
                media_types: mediaTypes
            }
        };
        
        try {
            const url = ruleId ? `/api/rules/${ruleId}` : '/api/rules';
            const method = ruleId ? 'PUT' : 'POST';
            
            const response = await fetch(url, {
                method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(ruleData)
            });
            
            const data = await response.json();
            if (data.success) {
                this.showNotification(
                    ruleId ? 'Rule updated successfully' : 'Rule created successfully',
                    'success'
                );
                this.closeModal('addRuleModal');
                form.reset();
                delete form.dataset.ruleId;
                this.loadInitialData(); // Reload rules
            } else {
                this.showNotification(data.error || 'Failed to save rule', 'error');
            }
        } catch (error) {
            console.error('Error saving rule:', error);
            this.showNotification('Error saving rule', 'error');
        }
    }

    // Telegram Connection
    async connectTelegram() {
        // Navigate to telegram section in dashboard
        window.location.hash = 'telegram';
    }

    async disconnectTelegram() {
        if (!confirm('Are you sure you want to disconnect from Telegram?')) return;
        
        try {
            const response = await fetch('/api/telegram/disconnect', {
                method: 'POST'
            });
            
            const data = await response.json();
            if (data.success) {
                this.showNotification('Disconnected from Telegram', 'success');
                this.telegramConnected = false;
                this.updateTelegramStatus();
            } else {
                this.showNotification(data.error || 'Failed to disconnect', 'error');
            }
        } catch (error) {
            console.error('Error disconnecting from Telegram:', error);
            this.showNotification('Error disconnecting from Telegram', 'error');
        }
    }

    // Dialog Management
    updateDialogSelects() {
        const sourceSelect = document.getElementById('ruleSource');
        const targetSelect = document.getElementById('ruleTarget');
        
        if (!sourceSelect || !targetSelect) return;
        
        const dialogOptions = this.dialogs.map(dialog => 
            `<option value="${dialog.id}">${dialog.name}</option>`
        ).join('');
        
        sourceSelect.innerHTML = `<option value="">Select source...</option>${dialogOptions}`;
        targetSelect.innerHTML = `<option value="">Select target...</option>${dialogOptions}`;
    }

    // Search
    handleSearch(query) {
        if (!query) {
            this.renderRules();
            return;
        }
        
        const filtered = this.rules.filter(rule => 
            rule.source.toLowerCase().includes(query.toLowerCase()) ||
            rule.target.toLowerCase().includes(query.toLowerCase())
        );
        
        this.rules = filtered;
        this.renderRules();
    }

    // Forwarding Events
    handleForwardingEvent(data) {
        // Add to activity feed
        this.addActivityItem(data);
        
        // Update stats
        if (data.type === 'forwarded') {
            this.stats.todaysForwards++;
            this.updateStatsDisplay();
        }
    }

    addActivityItem(data) {
        const activityFeed = document.getElementById('activityFeed');
        if (!activityFeed) return;
        
        const activityItem = document.createElement('div');
        activityItem.className = 'activity-item fade-in';
        activityItem.innerHTML = `
            <div class="activity-icon ${data.type}">
                <i class="fas ${data.type === 'forwarded' ? 'fa-check' : 'fa-exclamation'}"></i>
            </div>
            <div class="activity-content">
                <div class="activity-title">${data.message}</div>
                <div class="activity-time">${new Date().toLocaleTimeString()}</div>
            </div>
        `;
        
        activityFeed.insertBefore(activityItem, activityFeed.firstChild);
        
        // Keep only last 20 items
        while (activityFeed.children.length > 20) {
            activityFeed.removeChild(activityFeed.lastChild);
        }
    }

    // Modal Management
    showModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.add('show');
            document.body.style.overflow = 'hidden';
        }
    }

    closeModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('show');
            document.body.style.overflow = '';
        }
    }

    showAddRuleModal() {
        // Reset form
        document.getElementById('addRuleForm').reset();
        delete document.getElementById('addRuleForm').dataset.ruleId;
        this.showModal('addRuleModal');
    }

    // Notifications
    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type} fade-in`;
        notification.innerHTML = `
            <i class="fas ${type === 'success' ? 'fa-check-circle' : 
                           type === 'error' ? 'fa-exclamation-circle' : 
                           'fa-info-circle'}"></i>
            <span>${message}</span>
        `;
        
        const container = document.getElementById('notificationContainer') || this.createNotificationContainer();
        container.appendChild(notification);
        
        setTimeout(() => {
            notification.classList.add('fade-out');
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }

    createNotificationContainer() {
        const container = document.createElement('div');
        container.id = 'notificationContainer';
        container.className = 'notification-container';
        document.body.appendChild(container);
        return container;
    }

    // Tooltips
    initializeTooltips() {
        // Simple tooltip initialization
        document.querySelectorAll('[data-tooltip]').forEach(element => {
            element.classList.add('tooltip');
            const tooltipText = element.getAttribute('data-tooltip');
            const tooltipElement = document.createElement('span');
            tooltipElement.className = 'tooltip-content';
            tooltipElement.textContent = tooltipText;
            element.appendChild(tooltipElement);
        });
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.app = new TelegramForwarderApp();
    window.app.init();
});
