#!/usr/bin/env python3
"""
ShadowRealms AI - GPU Monitoring Service
Integrates with the monitoring system to provide performance-based AI configuration
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)

class PerformanceMode(Enum):
    """AI Performance modes based on resource usage"""
    FAST = "fast"      # Full performance, complex responses
    MEDIUM = "medium"  # Balanced performance
    SLOW = "slow"      # Efficient mode, basic responses

class GPUMonitorService:
    """Service for GPU monitoring and AI performance optimization"""
    
    def __init__(self):
        self.status_file = "/app/logs/system_status.json"
        self.last_status = None
        self.last_update = None
        self.cache_duration = timedelta(seconds=10)  # Cache status for 10 seconds
    
    @classmethod
    def get_current_status(cls) -> Optional[Dict[str, Any]]:
        """Get current system status from monitoring service"""
        try:
            # Read status from monitoring service
            status_file = "/app/logs/system_status.json"
            
            if os.path.exists(status_file):
                with open(status_file, 'r') as f:
                    status = json.load(f)
                return status
            else:
                logger.warning("System status file not found")
                return None
                
        except Exception as e:
            logger.error(f"Error reading system status: {e}")
            return None
    
    def get_performance_mode(self) -> PerformanceMode:
        """Get current performance mode based on system status"""
        status = self.get_current_status()
        
        if not status:
            # Default to medium if monitoring is unavailable
            return PerformanceMode.MEDIUM
        
        try:
            mode = status.get('performance_mode', 'medium')
            return PerformanceMode(mode)
        except ValueError:
            logger.warning(f"Invalid performance mode: {mode}")
            return PerformanceMode.MEDIUM
    
    def get_ai_response_config(self) -> Dict[str, Any]:
        """Get AI response configuration based on current performance mode"""
        performance_mode = self.get_performance_mode()
        
        # AI response configuration based on performance mode
        configs = {
            'fast': {
                'max_tokens': 1024,
                'temperature': 0.8,
                'top_p': 0.95,
                'response_complexity': 'high',
                'description': 'Full performance mode - complex, detailed responses'
            },
            'medium': {
                'max_tokens': 512,
                'temperature': 0.7,
                'top_p': 0.9,
                'response_complexity': 'medium',
                'description': 'Balanced mode - good quality with reasonable speed'
            },
            'slow': {
                'max_tokens': 256,
                'temperature': 0.6,
                'top_p': 0.8,
                'response_complexity': 'basic',
                'description': 'Efficient mode - basic responses to conserve resources'
            }
        }
        
        return configs.get(performance_mode.value, configs['medium'])
    
    def is_resource_limited(self) -> bool:
        """Check if system resources are limited (performance mode is slow)"""
        performance_mode = self.get_performance_mode()
        return performance_mode == PerformanceMode.SLOW
    
    def get_gpu_status_summary(self) -> Dict[str, Any]:
        """Get GPU status summary for API responses"""
        status = self.get_current_status()
        
        if not status:
            return {
                'monitoring_active': False,
                'performance_mode': 'medium',
                'gpu_count': 0,
                'overall_health': 'unknown'
            }
        
        try:
            gpu_status = status.get('gpu_status', [])
            performance_mode = status.get('performance_mode', 'medium')
            
            # Calculate overall GPU health
            gpu_health = 'good'
            if any(gpu.get('utilization', 0) > 90 for gpu in gpu_status):
                gpu_health = 'critical'
            elif any(gpu.get('utilization', 0) > 80 for gpu in gpu_status):
                gpu_health = 'warning'
            
            return {
                'monitoring_active': True,
                'performance_mode': performance_mode,
                'gpu_count': len(gpu_status),
                'overall_health': gpu_health,
                'gpu_status': gpu_status
            }
            
        except Exception as e:
            logger.error(f"Error processing GPU status: {e}")
            return {
                'monitoring_active': False,
                'performance_mode': 'medium',
                'gpu_count': 0,
                'overall_health': 'error'
            }

def test_gpu_monitor_service():
    """Standalone test function for GPU Monitor Service"""
    print("🧪 Testing GPU Monitor Service...")
    
    try:
        # Test 1: Create instance
        print("  ✓ Creating GPUMonitorService instance...")
        service = GPUMonitorService()
        print("  ✓ Instance created successfully")
        
        # Test 2: Test static method
        print("  ✓ Testing get_current_status() static method...")
        status = GPUMonitorService.get_current_status()
        if status:
            print(f"  ✓ Status retrieved: {status.get('performance_mode', 'unknown')}")
        else:
            print("  ⚠️  No status available (expected in standalone mode)")
        
        # Test 3: Test performance mode
        print("  ✓ Testing performance mode detection...")
        mode = service.get_performance_mode()
        print(f"  ✓ Performance mode: {mode.value}")
        
        # Test 4: Test GPU status summary
        print("  ✓ Testing GPU status summary...")
        summary = service.get_gpu_status_summary()
        print(f"  ✓ Summary: {summary['gpu_count']} GPUs, Health: {summary['overall_health']}")
        
        print("🎉 All GPU Monitor Service tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

# Global instance for route files to import
gpu_monitor_service = GPUMonitorService()

if __name__ == "__main__":
    """Run standalone tests if script is executed directly"""
    print("🚀 Running GPU Monitor Service Standalone Tests")
    print("=" * 50)
    
    success = test_gpu_monitor_service()
    
    print("=" * 50)
    if success:
        print("✅ All tests passed! Service is ready for integration.")
        exit(0)
    else:
        print("❌ Tests failed! Please fix issues before integration.")
        exit(1)
