#!/usr/bin/env python3
"""
ShadowRealms AI - Module Test Runner
Run standalone tests for all Python modules before integration
"""

import os
import sys
import subprocess
from pathlib import Path

def run_module_test(module_path: str, module_name: str) -> bool:
    """Run standalone test for a specific module"""
    print(f"\n🧪 Testing {module_name}...")
    print("=" * 50)
    
    try:
        # Run the module test from the current directory
        result = subprocess.run([
            sys.executable, 
            module_path
        ], capture_output=True, text=True, timeout=30, cwd=os.getcwd())
        
        # Print output
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)
        
        # Check result
        if result.returncode == 0:
            print(f"✅ {module_name} tests PASSED")
            return True
        else:
            print(f"❌ {module_name} tests FAILED (exit code: {result.returncode})")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"⏰ {module_name} tests TIMEOUT (took longer than 30 seconds)")
        return False
    except Exception as e:
        print(f"💥 {module_name} tests ERROR: {e}")
        return False

def main():
    """Run tests for all modules"""
    print("🚀 ShadowRealms AI - Module Test Runner")
    print("=" * 60)
    
    # Define modules to test
    modules = [
        ("backend/config.py", "Configuration Module"),
        ("backend/database.py", "Database Module"),
        ("backend/services/gpu_monitor.py", "GPU Monitor Service"),
        ("monitoring/monitor.py", "Monitoring Service"),
        ("backend/main.py", "Main Application")
    ]
    
    # Track results
    results = {}
    total_modules = len(modules)
    passed_modules = 0
    
    # Test each module
    for module_path, module_name in modules:
        if Path(module_path).exists():
            success = run_module_test(module_path, module_name)
            results[module_name] = success
            if success:
                passed_modules += 1
        else:
            print(f"\n⚠️  Module not found: {module_path}")
            results[module_name] = False
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 60)
    
    for module_name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {module_name}")
    
    print(f"\n📈 Overall: {passed_modules}/{total_modules} modules passed")
    
    if passed_modules == total_modules:
        print("🎉 All modules are ready for integration!")
        return True
    else:
        print("⚠️  Some modules need fixes before integration.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
