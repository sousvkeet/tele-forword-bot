# 🚀 Telegram Auto Forwarder - Production Installation Guide

## 📋 Prerequisites

### System Requirements
- **OS**: Ubuntu 20.04+ / Debian 10+ / CentOS 8+
- **Python**: 3.8 or higher
- **RAM**: 512MB minimum, 1GB recommended
- **Storage**: 2GB free space
- **Network**: Stable internet connection

### Required Credentials
- **Telegram API ID** & **API Hash** from https://my.telegram.org
- **Admin credentials** for dashboard access

## 🛠️ Installation Steps

### 1. Server Setup
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and dependencies
sudo apt install python3 python3-pip python3-venv git -y

# Create application user (optional but recommended)
sudo useradd -m -s /bin/bash telegram-forwarder
sudo su - telegram-forwarder
```

### 2. Download & Deploy
```bash
# Clone or upload the application files
cd /home/telegram-forwarder

# Run deployment script
./deploy.sh
```

### 3. Configuration
```bash
# Edit environment file
nano .env
```

**Required .env Configuration:**
```env
# Telegram API Credentials (Required)
TELEGRAM_API_ID=your_api_id_here
TELEGRAM_API_HASH=your_api_hash_here

# Application Settings
FLASK_PORT=5001
SECRET_KEY=your_secret_key_here

# Rate Limiting
MAX_MESSAGES_PER_MINUTE=10
MAX_DAILY_FORWARDS=400
DELAY_BETWEEN_FORWARDS=3

# Ban Protection
MAX_CONSECUTIVE_ERRORS=5
COOLDOWN_HOURS=2
MAX_CONCURRENT_FORWARDS=5

# Security
ENABLE_BAN_PROTECTION=True
```

### 4. Start Application
```bash
# Test run (development)
./start.sh

# For production, use systemd service:
sudo cp telegram-forwarder.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable telegram-forwarder
sudo systemctl start telegram-forwarder
```

## 🔧 Production Configuration

### Systemd Service Management
```bash
# Check status
sudo systemctl status telegram-forwarder

# View logs
sudo journalctl -u telegram-forwarder -f

# Restart service
sudo systemctl restart telegram-forwarder

# Stop service
sudo systemctl stop telegram-forwarder
```

### Nginx Reverse Proxy (Recommended)
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### SSL Certificate (Recommended)
```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d your-domain.com
```

## 🛡️ Security Hardening

### Firewall Configuration
```bash
# UFW Firewall
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable

# Block direct access to Flask port
sudo ufw deny 5001
```

### User Permissions
```bash
# Set proper file permissions
chmod 750 /home/telegram-forwarder/tg-auto-forward-bot
chmod 640 /home/telegram-forwarder/tg-auto-forward-bot/.env
chmod +x /home/telegram-forwarder/tg-auto-forward-bot/start.sh
chmod +x /home/telegram-forwarder/tg-auto-forward-bot/deploy.sh
```

## 📊 Monitoring & Maintenance

### Log Management
```bash
# Application logs
tail -f logs/app.log

# System logs
sudo journalctl -u telegram-forwarder -f

# Log rotation (add to crontab)
0 0 * * * find /home/telegram-forwarder/tg-auto-forward-bot/logs -name "*.log" -mtime +7 -delete
```

### Health Monitoring
```bash
# Check service health
curl -f http://localhost:5001 || echo "Service down"

# Monitor resource usage
htop
df -h
free -h
```

### Backup Strategy
```bash
# Backup script (daily)
#!/bin/bash
DATE=$(date +%Y%m%d)
tar -czf backup-$DATE.tar.gz .env *.db *.session
aws s3 cp backup-$DATE.tar.gz s3://your-backup-bucket/
```

## 🔄 Updates & Maintenance

### Application Updates
```bash
# Stop service
sudo systemctl stop telegram-forwarder

# Backup current installation
cp -r tg-auto-forward-bot tg-auto-forward-bot.backup

# Update application files
# ... copy new files ...

# Test configuration
./start.sh

# Restart service
sudo systemctl start telegram-forwarder
```

### Database Maintenance
```bash
# Vacuum database (monthly)
sqlite3 telegram_forwarder.db "VACUUM;"

# Clean old activity logs (weekly)
sqlite3 telegram_forwarder.db "DELETE FROM activity_log WHERE timestamp < datetime('now', '-30 days');"
```

## 🚨 Troubleshooting

### Common Issues

**Service won't start:**
```bash
# Check logs
sudo journalctl -u telegram-forwarder -n 50

# Check permissions
ls -la /home/telegram-forwarder/tg-auto-forward-bot/
```

**Dashboard not accessible:**
```bash
# Check if port is open
netstat -tlnp | grep 5001

# Check firewall
sudo ufw status
```

**Telegram authentication fails:**
```bash
# Remove session file
rm telegram_forwarder_simple.session

# Restart and re-authenticate
sudo systemctl restart telegram-forwarder
```

### Performance Tuning

**High memory usage:**
- Reduce `MAX_CONCURRENT_FORWARDS` in .env
- Increase `DELAY_BETWEEN_FORWARDS`

**Slow forwarding:**
- Increase `MAX_CONCURRENT_FORWARDS`
- Decrease `DELAY_BETWEEN_FORWARDS`
- Check network latency

## 📱 Dashboard Access

### First Login
1. Navigate to: `http://your-server-ip:5001`
2. Login: `admin` / `admin`
3. Change default password in Settings
4. Connect Telegram account
5. Create forwarding rules

### Features Available
- **Dashboard**: System overview and statistics
- **Rules**: Create and manage forwarding rules
- **Activity**: Real-time forwarding activity feed
- **Settings**: Configure rate limits and protection
- **Telegram**: Manage account connection

## 🎯 Production Checklist

- [ ] ✅ Server hardened and updated
- [ ] ✅ Application deployed and configured
- [ ] ✅ .env file properly configured
- [ ] ✅ Systemd service enabled and running
- [ ] ✅ Nginx reverse proxy configured
- [ ] ✅ SSL certificate installed
- [ ] ✅ Firewall configured
- [ ] ✅ Monitoring setup
- [ ] ✅ Backup strategy implemented
- [ ] ✅ Dashboard accessible
- [ ] ✅ Telegram account connected
- [ ] ✅ Test forwarding rule created

## 📞 Support

For production issues:
1. Check application logs: `sudo journalctl -u telegram-forwarder -f`
2. Review dashboard Activity Feed
3. Verify .env configuration
4. Test network connectivity
5. Check Telegram API status

---

**🎉 Your Telegram Auto Forwarder is ready for production!**
