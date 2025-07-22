#!/usr/bin/env python3
# Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT

"""
Health Check Script for SAY Backend

Usage:
    python healthcheck.py                    # Check localhost:8000
    python healthcheck.py http://example.com # Check custom URL
"""

import sys
try:
    import requests
import json
from datetime import datetime

def run_healthcheck(base_url="http://127.0.0.1:8000"):
    """Run comprehensive health check against the SAY Backend"""
    
    print(f"🏥 Running SAY Backend Health Check")
    print(f"📍 Target: {base_url}")
    print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    try:
        # Make health check request
        health_url = f"{base_url}/api/health"
        print(f"📡 Requesting: {health_url}")
        
        response = requests.get(health_url, timeout=10)
        
        # Check HTTP status
        if response.status_code == 200:
            print("✅ HTTP Status: 200 OK")
        elif response.status_code == 503:
            print("❌ HTTP Status: 503 Service Unavailable")
        else:
            print(f"⚠️  HTTP Status: {response.status_code}")
        
        # Parse JSON response
        try:
            health_data = response.json()
            
            # Overall status
            status = health_data.get('status', 'unknown')
            if status == 'healthy':
                status_emoji = "🟢"
            elif status == 'degraded':
                status_emoji = "🟡"
            elif status == 'unhealthy':
                status_emoji = "🔴"
            else:
                status_emoji = "⚪"
            
            print(f"{status_emoji} Overall Status: {status.upper()}")
            print(f"🔢 Version: {health_data.get('version', 'unknown')}")
            print(f"🌍 Environment: {health_data.get('environment', 'unknown')}")
            print(f"⏱️  Server Time: {health_data.get('timestamp', 'unknown')}")
            
            # Individual checks
            checks = health_data.get('checks', {})
            if checks:
                print("\n📋 Individual Checks:")
                print("-" * 40)
                
                for check_name, check_data in checks.items():
                    check_status = check_data.get('status', 'unknown')
                    
                    if check_status == 'healthy':
                        emoji = "✅"
                    elif check_status == 'warning':
                        emoji = "⚠️"
                    elif check_status == 'unhealthy':
                        emoji = "❌"
                    else:
                        emoji = "❓"
                    
                    print(f"{emoji} {check_name}: {check_status}")
                    
                    # Show details if available
                    details = check_data.get('details', {})
                    if details and isinstance(details, dict):
                        for key, value in details.items():
                            if key != 'status':
                                print(f"   └─ {key}: {value}")
                    
                    # Show message if available
                    if 'message' in check_data:
                        print(f"   └─ {check_data['message']}")
                    
                    print()
            
            # Summary
            print("=" * 60)
            if status == 'healthy':
                print("🎉 All systems operational!")
                return 0
            elif status == 'degraded':
                print("⚠️  System operational with warnings")
                return 1
            else:
                print("❌ System experiencing issues")
                return 2
                
        except json.JSONDecodeError:
            print("❌ Invalid JSON response:")
            print(response.text[:500])
            return 3
            
    except requests.exceptions.ConnectionError:
        print(f"❌ Connection Error: Unable to connect to {base_url}")
        print("   Make sure the Flask application is running")
        return 4
        
    except requests.exceptions.Timeout:
        print(f"❌ Timeout Error: Request to {base_url} timed out")
        return 5
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Request Error: {e}")
        return 6
        
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
        return 7

def main():
    """Main entry point"""
    
    # Determine target URL
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
        
        # Add http:// if no protocol specified
        if not base_url.startswith(('http://', 'https://')):
            base_url = f"http://{base_url}"
    else:
        base_url = "http://127.0.0.1:8000"
    
    # Run health check
    exit_code = run_healthcheck(base_url)
    
    # Exit with appropriate code
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
