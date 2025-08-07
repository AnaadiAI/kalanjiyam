# Siddhasagaram.in Deployment Configuration

## Environment Variables

To deploy Kalanjiyam at `siddhasagaram.in/kalanjiyam`, set the following environment variable:

```bash
APPLICATION_URL_PREFIX=/kalanjiyam
```

## Nginx Configuration

Add the following to your Nginx configuration:

```nginx
server {
    listen 80;
    server_name siddhasagaram.in;

    # Kalanjiyam application
    location /kalanjiyam {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Static files for Kalanjiyam
    location /kalanjiyam/static {
        alias /path/to/kalanjiyam/kalanjiyam/static;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

## Gunicorn Configuration

Create a Gunicorn configuration file (`gunicorn.conf.py`):

```python
bind = "127.0.0.1:8000"
workers = 4
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2
max_requests = 1000
max_requests_jitter = 100
preload_app = True
```

## Systemd Service

Create a systemd service file (`/etc/systemd/system/kalanjiyam.service`):

```ini
[Unit]
Description=Kalanjiyam Siddha Knowledge Systems
After=network.target

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/path/to/kalanjiyam
Environment="APPLICATION_URL_PREFIX=/kalanjiyam"
ExecStart=/path/to/venv/bin/gunicorn --config gunicorn.conf.py wsgi:app
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always

[Install]
WantedBy=multi-user.target
```

## SSL Configuration

For HTTPS, add SSL configuration to Nginx:

```nginx
server {
    listen 443 ssl http2;
    server_name siddhasagaram.in;

    ssl_certificate /path/to/ssl/certificate.crt;
    ssl_certificate_key /path/to/ssl/private.key;

    # Kalanjiyam application
    location /kalanjiyam {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Static files for Kalanjiyam
    location /kalanjiyam/static {
        alias /path/to/kalanjiyam/kalanjiyam/static;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name siddhasagaram.in;
    return 301 https://$server_name$request_uri;
}
```

## Deployment Steps

1. Set the environment variable:
   ```bash
   export APPLICATION_URL_PREFIX=/kalanjiyam
   ```

2. Update your `.env` file:
   ```
   APPLICATION_URL_PREFIX=/kalanjiyam
   ```

3. Configure Nginx with the provided configuration

4. Set up the systemd service

5. Start the service:
   ```bash
   sudo systemctl enable kalanjiyam
   sudo systemctl start kalanjiyam
   ```

6. Reload Nginx:
   ```bash
   sudo systemctl reload nginx
   ```

The application will now be accessible at `https://siddhasagaram.in/kalanjiyam` 