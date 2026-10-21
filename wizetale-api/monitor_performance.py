#!/usr/bin/env python3
"""
Performance monitoring script for Wizetale API
Monitors CPU, memory, and response times
"""

import psutil
import time
import requests
import json
from datetime import datetime
import os

class PerformanceMonitor:
    def __init__(self, api_url="http://localhost:8000"):
        self.api_url = api_url
        self.start_time = time.time()
        
    def get_system_stats(self):
        """Get current system statistics"""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            'timestamp': datetime.now().isoformat(),
            'cpu_percent': cpu_percent,
            'memory_percent': memory.percent,
            'memory_available_gb': memory.available / (1024**3),
            'disk_percent': disk.percent,
            'disk_free_gb': disk.free / (1024**3)
        }
    
    def test_api_response(self):
        """Test API response time"""
        try:
            start_time = time.time()
            response = requests.get(f"{self.api_url}/health", timeout=5)
            response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            return {
                'status_code': response.status_code,
                'response_time_ms': response_time,
                'success': response.status_code == 200
            }
        except Exception as e:
            return {
                'status_code': None,
                'response_time_ms': None,
                'success': False,
                'error': str(e)
            }
    
    def monitor_loop(self, interval=30):
        """Main monitoring loop"""
        print(f"🚀 Starting performance monitoring for {self.api_url}")
        print(f"📊 Monitoring interval: {interval} seconds")
        print("-" * 80)
        
        while True:
            try:
                # Get system stats
                system_stats = self.get_system_stats()
                
                # Test API
                api_stats = self.test_api_response()
                
                # Combine stats
                stats = {**system_stats, **api_stats}
                
                # Print status
                status_emoji = "✅" if api_stats['success'] else "❌"
                print(f"{status_emoji} {stats['timestamp']}")
                print(f"   CPU: {stats['cpu_percent']:.1f}% | "
                      f"Memory: {stats['memory_percent']:.1f}% | "
                      f"API: {stats['response_time_ms']:.0f}ms")
                
                # Alert if thresholds exceeded
                if stats['cpu_percent'] > 80:
                    print(f"⚠️  HIGH CPU USAGE: {stats['cpu_percent']:.1f}%")
                
                if stats['memory_percent'] > 85:
                    print(f"⚠️  HIGH MEMORY USAGE: {stats['memory_percent']:.1f}%")
                
                if api_stats['response_time_ms'] and api_stats['response_time_ms'] > 2000:
                    print(f"⚠️  SLOW API RESPONSE: {api_stats['response_time_ms']:.0f}ms")
                
                if not api_stats['success']:
                    print(f"❌ API ERROR: {api_stats.get('error', 'Unknown error')}")
                
                print("-" * 80)
                
                time.sleep(interval)
                
            except KeyboardInterrupt:
                print("\n🛑 Monitoring stopped by user")
                break
            except Exception as e:
                print(f"❌ Monitoring error: {e}")
                time.sleep(interval)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Monitor Wizetale API performance")
    parser.add_argument("--url", default="http://localhost:8000", 
                       help="API URL to monitor")
    parser.add_argument("--interval", type=int, default=30,
                       help="Monitoring interval in seconds")
    
    args = parser.parse_args()
    
    monitor = PerformanceMonitor(args.url)
    monitor.monitor_loop(args.interval) 