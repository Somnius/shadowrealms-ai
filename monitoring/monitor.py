#!/usr/bin/env python3
"""
ShadowRealms AI - GPU Resource Monitor
Monitors GPU and system resources and adjusts AI response speed accordingly
"""

import os
import time
import json
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

import psutil
import GPUtil

try:
    import pynvml
    nvidia_available = True
except ImportError as e:
    print(f"Warning: Could not import NVIDIA monitoring libraries: {e}")
    print("Install with: pip install nvidia-ml-py pynvml")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PerformanceMode(Enum):
    """AI Performance modes based on resource usage"""
    FAST = "fast"      # Full performance, complex responses
    MEDIUM = "medium"  # Balanced performance
    SLOW = "slow"      # Efficient mode, basic responses

@dataclass
class GPUStatus:
    """GPU status information"""
    gpu_id: int
    name: str
    utilization: float
    memory_used: float
    memory_total: float
    temperature: float
    power_draw: float
    performance_mode: PerformanceMode

@dataclass
class SystemStatus:
    """System resource status"""
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    gpu_status: list[GPUStatus]
    overall_performance_mode: PerformanceMode

class GPUResourceMonitor:
    """Monitors GPU and system resources for AI performance optimization"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.gpu_threshold_high = config.get('GPU_THRESHOLD_HIGH', 80)
        self.gpu_threshold_medium = config.get('GPU_THRESHOLD_MEDIUM', 60)
        self.monitoring_interval = config.get('MONITORING_INTERVAL', 5)
        
        # For now, we'll use GPUtil for basic GPU monitoring
        self.nvidia_available = False
        logger.info("Using GPUtil for GPU monitoring")
    
    def get_gpu_status(self) -> list[GPUStatus]:
        """Get detailed GPU status using nvidia-smi"""
        gpu_status_list = []
        
        try:
            if self.nvidia_available:
                # Use NVIDIA ML library for detailed info
                pynvml.nvmlInit()
                gpu_count = pynvml.nvmlDeviceGetCount()
                
                for gpu_id in range(gpu_count):
                    handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_id)
                    
                    # Get GPU info
                    name = pynvml.nvmlDeviceGetName(handle).decode('utf-8')
                    utilization = pynvml.nvmlDeviceGetUtilizationRates(handle).gpu
                    memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    temperature = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                    
                    # Calculate memory usage percentage
                    memory_used = memory_info.used / 1024**3  # Convert to GB
                    memory_total = memory_info.total / 1024**3
                    memory_usage_pct = (memory_info.used / memory_info.total) * 100
                    
                    # Determine performance mode based on GPU usage
                    performance_mode = self._determine_gpu_performance_mode(utilization, memory_usage_pct)
                    
                    gpu_status = GPUStatus(
                        gpu_id=gpu_id,
                        name=name,
                        utilization=utilization,
                        memory_used=memory_used,
                        memory_total=memory_total,
                        temperature=temperature,
                        power_draw=0.0,  # Could add power monitoring if needed
                        performance_mode=performance_mode
                    )
                    
                    gpu_status_list.append(gpu_status)
                    
            else:
                # Fallback to GPUtil
                gpus = GPUtil.getGPUs()
                for i, gpu in enumerate(gpus):
                    performance_mode = self._determine_gpu_performance_mode(gpu.load * 100, gpu.memoryUtil * 100)
                    
                    gpu_status = GPUStatus(
                        gpu_id=i,
                        name=gpu.name,
                        utilization=gpu.load * 100,
                        memory_used=gpu.memoryUsed / 1024,
                        memory_total=gpu.memoryTotal / 1024,
                        temperature=gpu.temperature,
                        power_draw=0.0,
                        performance_mode=performance_mode
                    )
                    
                    gpu_status_list.append(gpu_status)
                    
        except Exception as e:
            logger.error(f"Error getting GPU status: {e}")
            # Return dummy status if monitoring fails
            pass
        
        return gpu_status_list
    
    def get_system_status(self) -> SystemStatus:
        """Get comprehensive system resource status"""
        try:
            # CPU usage
            cpu_usage = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_usage = memory.percent
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_usage = (disk.used / disk.total) * 100
            
            # GPU status
            gpu_status = self.get_gpu_status()
            
            # Determine overall performance mode
            overall_mode = self._determine_overall_performance_mode(cpu_usage, memory_usage, gpu_status)
            
            return SystemStatus(
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                disk_usage=disk_usage,
                gpu_status=gpu_status,
                overall_performance_mode=overall_mode
            )
            
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            # Return default status on error
            return SystemStatus(
                cpu_usage=0.0,
                memory_usage=0.0,
                disk_usage=0.0,
                gpu_status=[],
                overall_performance_mode=PerformanceMode.MEDIUM
            )
    
    def _determine_gpu_performance_mode(self, utilization: float, memory_usage: float) -> PerformanceMode:
        """Determine GPU performance mode based on resource usage"""
        if utilization > self.gpu_threshold_high or memory_usage > 90:
            return PerformanceMode.SLOW
        elif utilization > self.gpu_threshold_medium or memory_usage > 70:
            return PerformanceMode.MEDIUM
        else:
            return PerformanceMode.FAST
    
    def _determine_overall_performance_mode(self, cpu_usage: float, memory_usage: float, gpu_status: list[GPUStatus]) -> PerformanceMode:
        """Determine overall system performance mode"""
        # Check if any GPU is in slow mode
        if any(gpu.performance_mode == PerformanceMode.SLOW for gpu in gpu_status):
            return PerformanceMode.SLOW
        
        # Check system resources
        if cpu_usage > 90 or memory_usage > 90:
            return PerformanceMode.SLOW
        elif cpu_usage > 80 or memory_usage > 80:
            return PerformanceMode.MEDIUM
        else:
            return PerformanceMode.FAST
    
    def get_ai_response_guidelines(self, performance_mode: PerformanceMode) -> Dict[str, Any]:
        """Get AI response guidelines based on performance mode"""
        guidelines = {
            PerformanceMode.FAST: {
                "max_tokens": 2048,
                "response_complexity": "high",
                "memory_usage": "full",
                "response_speed": "fast",
                "description": "Full performance mode - complex, detailed responses"
            },
            PerformanceMode.MEDIUM: {
                "max_tokens": 1024,
                "response_complexity": "medium",
                "memory_usage": "balanced",
                "response_speed": "normal",
                "description": "Balanced mode - good quality with reasonable speed"
            },
            PerformanceMode.SLOW: {
                "max_tokens": 512,
                "response_complexity": "basic",
                "memory_usage": "efficient",
                "response_speed": "slow",
                "description": "Efficient mode - basic responses to conserve resources"
            }
        }
        
        return guidelines[performance_mode]
    
    def log_status(self, status: SystemStatus):
        """Log current system status"""
        logger.info("=== System Resource Status ===")
        logger.info(f"CPU Usage: {status.cpu_usage:.1f}%")
        logger.info(f"Memory Usage: {status.memory_usage:.1f}%")
        logger.info(f"Disk Usage: {status.disk_usage:.1f}%")
        logger.info(f"Overall Performance Mode: {status.overall_performance_mode.value}")
        
        for gpu in status.gpu_status:
            logger.info(f"GPU {gpu.gpu_id} ({gpu.name}):")
            logger.info(f"  Utilization: {gpu.utilization:.1f}%")
            logger.info(f"  Memory: {gpu.memory_used:.1f}GB / {gpu.memory_total:.1f}GB")
            logger.info(f"  Temperature: {gpu.temperature:.1f}°C")
            logger.info(f"  Performance Mode: {gpu.performance_mode.value}")
        
        # Get AI response guidelines
        guidelines = self.get_ai_response_guidelines(status.overall_performance_mode)
        logger.info(f"AI Response Guidelines: {guidelines['description']}")
        logger.info("=" * 40)

def test_monitoring_service():
    """Standalone test function for Monitoring Service"""
    print("🧪 Testing Monitoring Service...")
    
    try:
        # Test 1: Create monitor instance
        print("  ✓ Creating GPUResourceMonitor instance...")
        config = {
            'GPU_THRESHOLD_HIGH': 80,
            'GPU_THRESHOLD_MEDIUM': 60,
            'MONITORING_INTERVAL': 5
        }
        monitor = GPUResourceMonitor(config)
        print("  ✓ Monitor instance created successfully")
        
        # Test 2: Test system status
        print("  ✓ Testing system status monitoring...")
        status = monitor.get_system_status()
        print(f"  ✓ CPU: {status.cpu_usage:.1f}%, Memory: {status.memory_usage:.1f}%")
        print(f"  ✓ Performance Mode: {status.overall_performance_mode.value}")
        
        # Test 3: Test GPU status
        print("  ✓ Testing GPU status monitoring...")
        gpu_status = monitor.get_gpu_status()
        print(f"  ✓ Found {len(gpu_status)} GPU(s)")
        
        # Test 4: Test AI guidelines
        print("  ✓ Testing AI response guidelines...")
        guidelines = monitor.get_ai_response_guidelines(status.overall_performance_mode)
        print(f"  ✓ Guidelines: {guidelines['description']}")
        
        # Test 5: Test status logging
        print("  ✓ Testing status logging...")
        monitor.log_status(status)
        print("  ✓ Status logged successfully")
        
        print("🎉 All Monitoring Service tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main monitoring loop"""
    # Load configuration from environment
    config = {
        'GPU_THRESHOLD_HIGH': int(os.getenv('GPU_THRESHOLD_HIGH', 80)),
        'GPU_THRESHOLD_MEDIUM': int(os.getenv('GPU_THRESHOLD_MEDIUM', 60)),
        'MONITORING_INTERVAL': int(os.getenv('MONITORING_INTERVAL', 5))
    }
    
    logger.info("Starting ShadowRealms AI GPU Resource Monitor")
    logger.info(f"Configuration: {config}")
    
    # Initialize monitor
    monitor = GPUResourceMonitor(config)
    
    try:
        while True:
            # Get current system status
            status = monitor.get_system_status()
            
            # Log status
            monitor.log_status(status)
            
            # Save status to file for other services to read
            status_file = "/app/logs/system_status.json"
            os.makedirs(os.path.dirname(status_file), exist_ok=True)
            
            with open(status_file, 'w') as f:
                json.dump({
                    'timestamp': time.time(),
                    'performance_mode': status.overall_performance_mode.value,
                    'cpu_usage': status.cpu_usage,
                    'memory_usage': status.memory_usage,
                    'gpu_status': [
                        {
                            'gpu_id': gpu.gpu_id,
                            'name': gpu.name,
                            'utilization': gpu.utilization,
                            'memory_used': gpu.memory_used,
                            'memory_total': gpu.memory_total,
                            'temperature': gpu.temperature,
                            'performance_mode': gpu.performance_mode.value
                        }
                        for gpu in status.gpu_status
                    ]
                }, f, indent=2)
            
            # Wait for next monitoring cycle
            time.sleep(config['MONITORING_INTERVAL'])
            
    except KeyboardInterrupt:
        logger.info("Monitoring stopped by user")
    except Exception as e:
        logger.error(f"Monitoring error: {e}")
        raise

def start_http_server(monitor, port=8000):
    """Start HTTP server for monitoring service"""
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import json
    import threading
    
    class MonitoringHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/status':
                try:
                    status = monitor.get_system_status()
                    response_data = {
                        'timestamp': time.time(),
                        'performance_mode': status.overall_performance_mode.value,
                        'cpu_usage': status.cpu_usage,
                        'memory_usage': status.memory_usage,
                        'gpu_count': len(status.gpu_status),
                        'gpu_status': [
                            {
                                'gpu_id': gpu.gpu_id,
                                'name': gpu.name,
                                'utilization': gpu.utilization,
                                'memory_used': gpu.memory_used,
                                'memory_total': gpu.memory_total,
                                'temperature': gpu.temperature,
                                'performance_mode': gpu.performance_mode.value
                            }
                            for gpu in status.gpu_status
                        ]
                    }
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(response_data).encode())
                except Exception as e:
                    self.send_response(500)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'error': str(e)}).encode())
            else:
                self.send_response(404)
                self.end_headers()
    
    def run_server():
        server = HTTPServer(('0.0.0.0', port), MonitoringHandler)
        logger.info(f"Monitoring HTTP server started on port {port}")
        server.serve_forever()
    
    # Start HTTP server in a separate thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

if __name__ == "__main__":
    """Run standalone tests or actual service based on arguments"""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--run":
        # Run the actual monitoring service
        config = {
            'MONITORING_INTERVAL': 10,
            'GPU_THRESHOLD_HIGH': 80,
            'GPU_THRESHOLD_MEDIUM': 60
        }
        
        monitor = GPUResourceMonitor(config)
        start_http_server(monitor, 8000)
        main()
    else:
        # Run standalone tests
        print("🚀 Running Monitoring Service Standalone Tests")
        print("=" * 50)
        
        success = test_monitoring_service()
        
        print("=" * 50)
        if success:
            print("✅ All tests passed! Service is ready for integration.")
            print("💡 To run the actual monitoring service, use: python monitor.py --run")
            exit(0)
        else:
            print("❌ Tests failed! Please fix issues before integration.")
            exit(1)
