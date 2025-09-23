# 🐳 Telegram Auto Forwarder - Docker Setup

Complete Docker containerization for production deployment of the Telegram Auto Forwarder.

## 🚀 Quick Start

### Prerequisites
- Docker 20.10+
- Docker Compose 2.0+
- Telegram API credentials from https://my.telegram.org

### 1-Command Setup
```bash
./docker-deploy.sh
```

## 📁 Docker Files Structure

```
telegram-auto-forwarder/
├── 🐳 Docker Configuration
│   ├── Dockerfile                 # Production container image
│   ├── docker-compose.yml         # Service orchestration
│   ├── .dockerignore              # Build optimization
│   └── .env.docker                # Environment template
│
├── 🛠️ Management Scripts
│   ├── docker-deploy.sh           # Deploy application
│   ├── docker-logs.sh             # View live logs
│   ├── docker-stop.sh             # Stop containers  
│   └── docker-update.sh           # Update deployment
│
└── 📖 Documentation
    └── DOCKER_SETUP.md            # This file
```

## ⚙️ Configuration

### Environment Setup
```bash
# 1. Copy environment template
cp .env.docker .env

# 2. Edit with your credentials
nano .env

# 3. Required settings:
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
SECRET_KEY=your-secure-secret-key
```

### Optional Configuration
```bash
# Rate Limiting
MAX_MESSAGES_PER_MINUTE=10
MAX_DAILY_FORWARDS=400
DELAY_BETWEEN_FORWARDS=3

# Security
MAX_CONSECUTIVE_ERRORS=5
COOLDOWN_HOURS=2
MAX_CONCURRENT_FORWARDS=5
```

## 🎯 Deployment Commands

### Deploy Application
```bash
./docker-deploy.sh
```

### View Live Logs
```bash
./docker-logs.sh
```

### Stop Application
```bash
./docker-stop.sh
```

### Update Application
```bash
./docker-update.sh
```

### Manual Commands
```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop containers
docker-compose down

# Rebuild image
docker-compose build --no-cache
```

## 📊 Container Features

### Security
- ✅ **Non-root user**: Runs as `appuser` for security
- ✅ **Resource limits**: CPU and memory constraints
- ✅ **Health checks**: Automatic service monitoring
- ✅ **Volume isolation**: Data persistence without host access

### Performance
- ✅ **Multi-stage build**: Optimized image size
- ✅ **Layer caching**: Fast rebuilds
- ✅ **Resource management**: 512MB RAM limit
- ✅ **Concurrent processing**: 5 worker threads

### Reliability
- ✅ **Auto-restart**: Container restarts on failure
- ✅ **Health monitoring**: Built-in health checks
- ✅ **Data persistence**: Volumes for database and sessions
- ✅ **Log rotation**: Automatic log management

## 🔍 Monitoring & Troubleshooting

### Container Status
```bash
# Check container status
docker-compose ps

# View resource usage
docker stats telegram-auto-forwarder

# Container health
docker-compose exec telegram-forwarder curl localhost:5001/api/status
```

### Debugging
```bash
# Access container shell
docker-compose exec telegram-forwarder bash

# View application logs
docker-compose logs telegram-forwarder

# Check health status
docker inspect telegram-auto-forwarder | grep Health -A 10
```

### Common Issues

**Container won't start:**
```bash
# Check logs
docker-compose logs

# Verify environment
docker-compose config
```

**Connection issues:**
```bash
# Check port mapping
docker-compose ps
netstat -tlnp | grep 5001
```

**Memory issues:**
```bash
# Monitor resources
docker stats
```

## 🔄 Data Management

### Volumes
- `telegram_data/` - Application data
- `telegram_logs/` - Application logs
- Database files mounted from host

### Backup
```bash
# Backup data volumes
docker run --rm -v telegram_data:/data -v $(pwd):/backup alpine tar czf /backup/telegram_data.tar.gz -C /data .

# Backup database
cp telegram_forwarder.db telegram_forwarder.db.backup
```

### Restore
```bash
# Restore data volumes
docker run --rm -v telegram_data:/data -v $(pwd):/backup alpine tar xzf /backup/telegram_data.tar.gz -C /data

# Restore database
cp telegram_forwarder.db.backup telegram_forwarder.db
```

## 🌐 Production Deployment

### Docker Swarm
```bash
# Initialize swarm
docker swarm init

# Deploy stack
docker stack deploy -c docker-compose.yml telegram-forwarder
```

### Kubernetes
```bash
# Generate Kubernetes manifests
kompose convert -f docker-compose.yml

# Deploy to cluster
kubectl apply -f .
```

### Reverse Proxy (nginx)
```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://localhost:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 📈 Performance Tuning

### Resource Optimization
```yaml
# In docker-compose.yml
deploy:
  resources:
    limits:
      cpus: '2.0'      # Increase for high traffic
      memory: 1G       # Increase for many rules
```

### Scaling
```bash
# Scale workers (if supported)
docker-compose up -d --scale telegram-forwarder=2
```

## 🛡️ Security Best Practices

1. **Environment Secrets**: Use Docker secrets for API keys
2. **Network Security**: Use custom networks
3. **User Permissions**: Non-root container execution
4. **Regular Updates**: Keep base images updated
5. **Log Management**: Rotate and secure logs

## 📞 Support

- **Dashboard**: http://localhost:5001
- **Health Check**: http://localhost:5001/api/status
- **Logs**: `./docker-logs.sh`
- **Status**: `docker-compose ps`

---

**🎉 Your Telegram Auto Forwarder is now containerized and production-ready!**
