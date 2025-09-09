#!/usr/bin/env python3

import yaml
from os import getenv as _
from dotenv import load_dotenv
from datetime import datetime
from sys import argv

imageVersion = (
    argv[1] if len(argv) > 1 else "latest"
)
load_dotenv(dotenv_path="stanthonynovato.env")

# === CONFIGURATION ===
num_backends = 2  # Change this to add/remove backend instances
mysql_password = _("MYSQL_PASSWORD")  # Replace with your real password or load from env
mysql_root_password = _("MYSQL_ROOT_PASSWORD")
mysql_db = _("MYSQL_DATABASE")
mysql_user = _("MYSQL_USER")
network_subnet = "172.20.0.0/16"

nginx_restricted_routes = [
    "/stub_status",
    "/metrics"
]
# === BASE SERVICES ===
compose = {
    'version': '3.8',
    'services': {
        'mysql': {
            'image': 'mysql:5.7',
            'container_name': 'mysql',
            'restart': 'unless-stopped',
            'environment': {
                'MYSQL_ROOT_PASSWORD': mysql_root_password,
                'MYSQL_DATABASE': mysql_db,
                'MYSQL_USER': mysql_user,
                'MYSQL_PASSWORD': mysql_password
            },
            'volumes': ['mysql_data:/var/lib/mysql'],
            'networks': ['backend']
        },
        'nginx': {
            'image': 'nginx:latest',
            'container_name': 'nginx',
            'restart': 'unless-stopped',
            'volumes': ['./nginx.conf:/etc/nginx/nginx.conf:ro'],
            'ports': ['80:80'],
            "depends_on": {},
            'networks': ['backend']
        },
        "prometheus-nginx-exporter": {
            "image": "nginx/nginx-prometheus-exporter:1.4",
            "container_name": "prometheus-nginx-exporter",
            "restart": "unless-stopped",
            "ports": ["9113:9113"],
            "environment": {
                "NGINX_SCRAPE_URI": "http://nginx:80/stub_status"
            },
            "command": [
                "--nginx.scrape-uri=http://nginx:80/stub_status"
            ],
            "depends_on": ["nginx"],
            'networks': ['backend']
        }
    },
    'volumes': {
        'mysql_data': {}
    },
    'networks': {
        'backend': {
            "ipam": {
                "driver": "default",
                "config": [
                    {
                        "subnet": network_subnet
                    }
                ]
            }
        }
    }
}

# === DYNAMIC BACKEND SERVICES ===
for i in range(1, num_backends + 1):
    name = f"say-backend-{i}"
    compose['services'][name] = {
        'image': f'alphagamedev/say-backend:{imageVersion}',
        "hostname": name,
        'container_name': name,
        'restart': 'unless-stopped',
        'environment': {
            'MYSQL_HOST': 'mysql',
            'MYSQL_USER': mysql_user,
            'MYSQL_PASSWORD': mysql_password,
            'MYSQL_DATABASE': mysql_db,
            "DISCORD_WEBHOOK_URL": _("DISCORD_WEBHOOK_URL"),
            "RECAPTCHA_SECRET_KEY": _("RECAPTCHA_SECRET_KEY"),
            "PROMETHEUS_MULTIPROC_DIR": _("PROMETHEUS_MULTIPROC_DIR"),
            "GOOGLE_APP_PASSWORD": _("GOOGLE_APP_PASSWORD"),
            "SMTP_FROM_EMAIL": _("SMTP_FROM_EMAIL")
        },
        'depends_on': ['mysql'],
        "healthcheck": {
            'test': ['CMD', 'curl', "-A", f"HealthcheckChecker/1 (compatible; SAY-Backend/{imageVersion} +damien@alphagame.dev)", '-f', 'http://localhost:5000/healthcheck?reason=DockerAutomatedHealthcheck'],
            'interval': '30s',
            'timeout': '10s',
            'retries': 5
        },
        'networks': ['backend']
    }
    # Add backend to nginx depends_on
    compose['services']['nginx']['depends_on'].update({
        f"say-backend-{i}": {
            'condition': 'service_healthy'
        } for i in range(1, num_backends + 1)
    })

    # === Prometheus ===
    compose['services']['prometheus'] = {
        'image': 'prom/prometheus:latest',
        'container_name': 'prometheus',
        'restart': 'unless-stopped',
        'volumes': [
            './prometheus.yml:/etc/prometheus/prometheus.yml'
        ],
        'ports': ['9090:9090'],
        'networks': ['backend'],
        'depends_on': {f"say-backend-{i}": {'condition': 'service_healthy'} for i in range(1, num_backends + 1)}
    }

# === OUTPUT ===
with open('docker-compose.yml', 'w') as f:
    f.write(f"# generated at: {datetime.now().isoformat()}\n")
    yaml.dump(compose, f, default_flow_style=False)

with open("nginx.conf", "w") as f:
    fc = ""
    fc += f"# generated at {datetime.now()}\n"
    fc += "user  nginx;\n"
    fc += "worker_processes  auto;\n\n"
    fc += "error_log  /var/log/nginx/error.log notice;\n"
    fc += "pid        /run/nginx.pid;\n\n\n"
    fc += "events {\n"
    fc += "    worker_connections  1024;\n"
    fc += "}\n"
    fc += "http {\n"
    fc += "    include       /etc/nginx/mime.types;\n"
    fc += "    default_type  application/octet-stream;\n\n"
    fc += "    log_format  main  '$remote_addr - $remote_user [$time_local] \"$request\" '\n"
    fc += "                  '$status $body_bytes_sent \"$http_referer\" '\n"
    fc += "                  '\"$http_user_agent\" \"$http_x_forwarded_for\"';\n\n"
    fc += "    access_log  /var/log/nginx/access.log  main;\n\n"
    fc += "    sendfile        on;\n"
    fc += "    #tcp_nopush     on;\n\n"
    fc += "    keepalive_timeout  65;\n\n"
    fc += "    #gzip  on;\n\n"

    # Define upstream block for load balancing
    fc += "    upstream app_backend {\n"
    for i in range(1, num_backends + 1):
        fc += f"        server say-backend-{i}:5000;\n"
    fc += "    }\n\n"

    # Configure server block to use the upstream
    fc += "    server {\n"
    fc += "        listen 80;\n\n"
    fc += "        location / {\n"
    fc += "            proxy_pass http://app_backend;\n"
    fc += "            proxy_set_header Host $host;\n"
    fc += "            proxy_set_header X-Real-IP $remote_addr;\n"
    fc += "            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n"
    fc += "            proxy_set_header X-Forwarded-Proto $scheme;\n"
    fc += "        }\n"
    for route in nginx_restricted_routes:
        fc += f"        location {route} {{\n"
        fc += f"            allow {network_subnet};\n"
        fc +=  "            deny all;\n"
        fc +=  "        }\n"
    fc += "    }\n"
    fc += "}\n"

    # build nginx.conf with all backend instances inside the http block
    f.write(fc)

with open("prometheus.yml", "w") as f:
    promConfig = {
        'global': {
            'scrape_interval': '15s',
            'evaluation_interval': '15s',
            'external_labels': {
                'monitor': 'codelab'
            }
        },
        'scrape_configs': [
            {
                'job_name': 'nginx',
                'static_configs': [
                    {
                        'targets': ['prometheus-nginx-exporter:9113']
                    }
                ]
            },
            {
                'job_name': 'backend',
                'static_configs': [
                    {
                        'targets': [f'say-backend-{i}:5000' for i in range(1, num_backends + 1)]
                    }
                ]
            }
        ]
    }
    with open('prometheus.yml', 'w') as f:
        f.write(f"# generated at: {datetime.now().isoformat()}\n")
        yaml.dump(promConfig, f, default_flow_style=False)
        
print(f"docker-compose.yml generated with {num_backends} backend instance(s).")
