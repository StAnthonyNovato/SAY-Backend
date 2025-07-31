# Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT

import argparse
import os
import requests
from datetime import datetime
import logging
from socket import gethostname
logging.basicConfig(
    level = logging.DEBUG,
    format = "%(levelname)-8s | %(message)s"
)
logger = logging.getLogger("SAYMonitor")
# function to add query parameters to a URL

     
def add_query_params(url, params):
    if not params:
        return url
    query_string = '&'.join(f"{key}={value}" for key, value in params.items())
    return f"{url}?{query_string}"

def main():
    parser = argparse.ArgumentParser(
        prog = "SAYMonitor",
        description = "Monitor the health of the St Anthony Youth program backend service.",
        epilog = f"Copyright (c) {datetime.now().year} Damien Boisvert (AlphaGameDeveloper). This software is released under the MIT License. https://opensource.org/licenses/MIT"
    )

    parser.add_argument(
        "--url",
        type=str,
        default="http://localhost:5000/healthcheck",
        help="The URL to monitor (default: http://localhost:5000/healthcheck)"
    )

    parser.add_argument(
        "--discord-webhook",
        type=str,
        default=os.getenv("DISCORD_WEBHOOK_URL", ""),
        help="Discord webhook URL for notifications (default: from environment variable DISCORD_WEBHOOK_URL if set)"
    )

    args = parser.parse_args()
    url = add_query_params(args.url, {
        "src": "SAYMonitor",
        "fcnl": True
    })

    logger.info(f"Monitoring URL: {url}")

    logging.debug("Getting health check information...")
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        logger.info(f"Health check information aquired after {response.elapsed.total_seconds()} seconds.")

        # Log all checks in the data
        checks = data.get("checks", {})
        for check_name, check_info in checks.items():
            status = check_info.get("status", "unknown")
            message = check_info.get("message", "")
            details = check_info.get("details", {})
            logger.info(f"[{check_name}] Status: {status} | Message: {message} | Details: {details}")

        # DATA = {"checks":{"database":{"details":{},"message":"MySQL connection not initialized","status":"unhealthy"},"discord":{"details":{"webhook_configured":true},"message":"Discord notifications configured","status":"healthy"},"email":{"details":{"email_sending_enabled":true,"from_email":"not_set","smtp_configured":true},"message":"Email service configured","status":"healthy"},"environment":{"details":{"all_required_present":true,"missing_optional":[],"missing_required":[]},"message":"Environment variables configured properly","status":"healthy"}},"environment":"production","status":"unhealthy","timestamp":"2025-07-31T18:31:53.772656Z","version":"1.0.1.dev34+gc989dc8"}

        discord_webhook = args.discord_webhook
        if discord_webhook:
            discord_payload = {
                "content": f"Health check status: {data['status']}\nHost: {gethostname()}\nTimestamp: {data['timestamp']}\nVersion: {data['version']}\nEnvironment: {data['environment']}",
                "embeds": [
                    {
                        "title": f"Health Check Details - {gethostname()}",
                        "fields": [
                            {
                                "name": check_name,
                                "value": f"Status: {check_info['status']}\nMessage: {check_info['message']}\nDetails: {check_info.get('details', {})}",
                                "inline": False
                            } for check_name, check_info in checks.items()
                        ],
                        "color": 3066993 if data['status'] == "healthy" else 15158332
                    }
                ],
                "username": f"SAYMonitor [{gethostname()}]",
            }
            requests.post(discord_webhook, json=discord_payload)
            logger.info("Discord notification sent.")
    except requests.RequestException as e:
        logger.error(f"Failed to get health check information: {e}")
        return
    
if __name__ == "__main__":
    main()