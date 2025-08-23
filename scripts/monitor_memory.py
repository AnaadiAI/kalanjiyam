#!/usr/bin/env python3
"""
Memory monitoring script for Kalanjiyam Celery workers and Surya OCR processes.
This script helps identify memory issues and provides recommendations.
"""

import subprocess
import psutil
import os
import sys
from typing import List, Dict, Any


def get_celery_processes() -> List[Dict[str, Any]]:
    """Get information about running Celery worker processes."""
    processes = []
    
    for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'cmdline']):
        try:
            if proc.info['cmdline'] and any('celery' in cmd.lower() for cmd in proc.info['cmdline']):
                memory_mb = proc.info['memory_info'].rss / 1024 / 1024
                processes.append({
                    'pid': proc.info['pid'],
                    'memory_mb': memory_mb,
                    'cmdline': ' '.join(proc.info['cmdline'])
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    return processes


def get_surya_processes() -> List[Dict[str, Any]]:
    """Get information about processes that might be running Surya OCR."""
    processes = []
    
    for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'cmdline']):
        try:
            if proc.info['cmdline'] and any('python' in cmd.lower() for cmd in proc.info['cmdline']):
                memory_mb = proc.info['memory_info'].rss / 1024 / 1024
                cmdline_str = ' '.join(proc.info['cmdline'])
                
                # Skip training processes and other non-OCR processes
                if any(skip_term in cmdline_str.lower() for skip_term in [
                    'train_', 'sentpiece', 'tokenizer', 'corpus', 'cluster'
                ]):
                    continue
                
                # Check if it's likely a Surya OCR process (high memory usage and OCR-related)
                if memory_mb > 500 and any(ocr_term in cmdline_str.lower() for ocr_term in [
                    'surya', 'ocr', 'kalanjiyam', 'celery'
                ]):
                    processes.append({
                        'pid': proc.info['pid'],
                        'memory_mb': memory_mb,
                        'cmdline': cmdline_str
                    })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    return processes


def get_system_memory() -> Dict[str, float]:
    """Get system memory information."""
    memory = psutil.virtual_memory()
    return {
        'total_gb': memory.total / 1024 / 1024 / 1024,
        'available_gb': memory.available / 1024 / 1024 / 1024,
        'used_gb': memory.used / 1024 / 1024 / 1024,
        'percent_used': memory.percent
    }


def print_memory_report():
    """Print a comprehensive memory usage report."""
    print("=" * 60)
    print("KALANJIYAM MEMORY USAGE REPORT")
    print("=" * 60)
    
    # System memory
    system_memory = get_system_memory()
    print(f"\nSYSTEM MEMORY:")
    print(f"  Total: {system_memory['total_gb']:.1f} GB")
    print(f"  Used: {system_memory['used_gb']:.1f} GB ({system_memory['percent_used']:.1f}%)")
    print(f"  Available: {system_memory['available_gb']:.1f} GB")
    
    # Celery processes
    celery_processes = get_celery_processes()
    print(f"\nCELERY WORKER PROCESSES ({len(celery_processes)} found):")
    if celery_processes:
        total_celery_memory = sum(p['memory_mb'] for p in celery_processes)
        for proc in celery_processes:
            print(f"  PID {proc['pid']}: {proc['memory_mb']:.1f} MB")
        print(f"  Total Celery memory: {total_celery_memory:.1f} MB ({total_celery_memory/1024:.1f} GB)")
    else:
        print("  No Celery worker processes found")
    
    # High memory processes (potential Surya OCR)
    surya_processes = get_surya_processes()
    print(f"\nHIGH MEMORY PROCESSES ({len(surya_processes)} found):")
    if surya_processes:
        total_surya_memory = sum(p['memory_mb'] for p in surya_processes)
        for proc in surya_processes:
            print(f"  PID {proc['pid']}: {proc['memory_mb']:.1f} MB")
        print(f"  Total high memory processes: {total_surya_memory:.1f} MB ({total_surya_memory/1024:.1f} GB)")
    else:
        print("  No high memory processes found")
    
    # Recommendations
    print(f"\nRECOMMENDATIONS:")
    if len(celery_processes) > 4:
        print(f"  ⚠️  Too many Celery workers ({len(celery_processes)}). Consider reducing to 2-4 workers.")
    if system_memory['percent_used'] > 80:
        print(f"  ⚠️  High system memory usage ({system_memory['percent_used']:.1f}%). Consider restarting workers.")
    if len(surya_processes) > 0:
        print(f"  ⚠️  High memory processes detected. These might be Surya OCR processes.")
        print(f"     Consider restarting Celery workers to free memory.")
    
    print(f"\n  ✅ Conservative settings applied:")
    print(f"     - Celery concurrency: 2 workers")
    print(f"     - Prefetch multiplier: 1")
    print(f"     - Max memory per child: 200MB")
    print(f"     - Max tasks per child: 50")
    
    print("\n" + "=" * 60)


def main():
    """Main function."""
    if len(sys.argv) > 1 and sys.argv[1] == '--kill-workers':
        print("Stopping all Celery worker processes...")
        subprocess.run(['pkill', '-f', 'celery.*worker'], check=False)
        print("Celery workers stopped.")
        return
    
    print_memory_report()


if __name__ == '__main__':
    main()
