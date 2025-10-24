#!/bin/bash

# 🔍 ShadowRealms AI - Test Structure Validator
# 
# This script validates that all test files are properly structured
# and contain the expected test cases.
#
# WHAT THIS SCRIPT DOES:
# 1. Checks if all required test files exist in the correct locations
# 2. Validates that configuration files are present and properly set up
# 3. Counts test cases and test suites in each file
# 4. Verifies that all required dependencies are listed in package.json
# 5. Provides a comprehensive report of the test structure
#
# USAGE:
#   ./validate-test-structure.sh
#
# DEPENDENCIES:
#   - Bash shell
#   - grep command (for counting test cases)
#   - Standard Unix utilities (test, echo, etc.)

# Exit immediately if any command fails
# This ensures we don't continue if there are critical errors
set -e

echo "🔍 ShadowRealms AI - Test Structure Validation"
echo "=============================================="

# Define color codes for terminal output
# ANSI escape codes for colored text in terminal
RED='\033[0;31m'      # Red for errors
GREEN='\033[0;32m'    # Green for success
YELLOW='\033[1;33m'   # Yellow for warnings
BLUE='\033[0;34m'     # Blue for info
NC='\033[0m'          # No Color (reset)

# Function to print colored output with [INFO] prefix
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Function to print colored output with [SUCCESS] prefix
print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Function to print colored output with [WARNING] prefix
print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to print colored output with [ERROR] prefix
print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Define associative array (hash map) of test files and their descriptions
# Key: file path, Value: human-readable description
# This makes it easy to iterate through all expected test files
declare -A test_files=(
    ["frontend/src/__tests__/services/authService.test.ts"]="Authentication Service Tests"
    ["frontend/src/__tests__/store/authStore.test.ts"]="Authentication Store Tests"
    ["frontend/src/__tests__/components/ui/Button.test.tsx"]="Button Component Tests"
    ["frontend/src/__tests__/components/ui/Input.test.tsx"]="Input Component Tests"
    ["frontend/src/__tests__/components/ui/Card.test.tsx"]="Card Component Tests"
    ["frontend/src/__tests__/components/auth/LoginForm.test.tsx"]="Login Form Tests"
)

# Define associative array of configuration files and their descriptions
# These files are required for the test system to work properly
declare -A config_files=(
    ["frontend/package.json"]="Package Configuration"
    ["frontend/jest.config.js"]="Jest Configuration"
    ["frontend/src/setupTests.ts"]="Test Setup"
    ["frontend/TESTING.md"]="Test Documentation"
    ["test-auth-docker.sh"]="Docker Test Runner"
)

# Validate test file structure
validate_test_files() {
    print_status "Validating test file structure..."
    
    local total_files=0
    local valid_files=0
    
    for file in "${!test_files[@]}"; do
        total_files=$((total_files + 1))
        
        if [ -f "$file" ]; then
            print_success "✓ ${test_files[$file]}: $file"
            
            # Count test cases in file
            local test_count=$(grep -c "it(\|test(" "$file" 2>/dev/null || echo "0")
            local describe_count=$(grep -c "describe(" "$file" 2>/dev/null || echo "0")
            
            if [ "$test_count" -gt 0 ]; then
                print_status "  📊 $describe_count test suites, $test_count test cases"
                valid_files=$((valid_files + 1))
            else
                print_warning "  ⚠️  No test cases found in $file"
            fi
        else
            print_error "✗ Missing: ${test_files[$file]}: $file"
        fi
    done
    
    echo ""
    print_status "Test Files Summary: $valid_files/$total_files files valid"
    
    if [ "$valid_files" -eq "$total_files" ]; then
        print_success "All test files are present and valid!"
        return 0
    else
        print_error "Some test files are missing or invalid"
        return 1
    fi
}

# Validate configuration files
validate_config_files() {
    print_status "Validating configuration files..."
    
    local total_configs=0
    local valid_configs=0
    
    for file in "${!config_files[@]}"; do
        total_configs=$((total_configs + 1))
        
        if [ -f "$file" ]; then
            print_success "✓ ${config_files[$file]}: $file"
            valid_configs=$((valid_configs + 1))
        else
            print_error "✗ Missing: ${config_files[$file]}: $file"
        fi
    done
    
    echo ""
    print_status "Configuration Files Summary: $valid_configs/$total_configs files present"
    
    if [ "$valid_configs" -eq "$total_configs" ]; then
        print_success "All configuration files are present!"
        return 0
    else
        print_error "Some configuration files are missing"
        return 1
    fi
}

# Validate package.json dependencies
validate_dependencies() {
    print_status "Validating test dependencies in package.json..."
    
    if [ -f "frontend/package.json" ]; then
        local required_deps=(
            "@testing-library/react"
            "@testing-library/jest-dom"
            "@testing-library/user-event"
            "jest-environment-jsdom"
            "msw"
        )
        
        local missing_deps=()
        
        for dep in "${required_deps[@]}"; do
            if grep -q "\"$dep\"" frontend/package.json; then
                print_success "✓ $dep"
            else
                print_error "✗ Missing: $dep"
                missing_deps+=("$dep")
            fi
        done
        
        if [ ${#missing_deps[@]} -eq 0 ]; then
            print_success "All required test dependencies are present!"
            return 0
        else
            print_error "Missing dependencies: ${missing_deps[*]}"
            return 1
        fi
    else
        print_error "package.json not found"
        return 1
    fi
}

# Count total test cases
count_test_cases() {
    print_status "Counting total test cases..."
    
    local total_tests=0
    local total_suites=0
    
    for file in "${!test_files[@]}"; do
        if [ -f "$file" ]; then
            local test_count=$(grep -c "it(\|test(" "$file" 2>/dev/null || echo "0")
            local describe_count=$(grep -c "describe(" "$file" 2>/dev/null || echo "0")
            
            total_tests=$((total_tests + test_count))
            total_suites=$((total_suites + describe_count))
        fi
    done
    
    print_success "Total Test Suites: $total_suites"
    print_success "Total Test Cases: $total_tests"
    
    if [ "$total_tests" -ge 40 ]; then
        print_success "🎯 Excellent test coverage! ($total_tests test cases)"
    elif [ "$total_tests" -ge 20 ]; then
        print_warning "⚠️  Good test coverage ($total_tests test cases)"
    else
        print_error "❌ Low test coverage ($total_tests test cases)"
    fi
}

# Main validation
main() {
    local exit_code=0
    
    # Validate test files
    if ! validate_test_files; then
        exit_code=1
    fi
    
    echo ""
    
    # Validate configuration files
    if ! validate_config_files; then
        exit_code=1
    fi
    
    echo ""
    
    # Validate dependencies
    if ! validate_dependencies; then
        exit_code=1
    fi
    
    echo ""
    
    # Count test cases
    count_test_cases
    
    echo ""
    echo "=============================================="
    
    if [ $exit_code -eq 0 ]; then
        print_success "🎉 Test structure validation passed!"
        print_status "Ready to run tests with: ./test-auth-docker.sh"
    else
        print_error "❌ Test structure validation failed!"
        print_status "Please fix the issues above before running tests"
    fi
    
    return $exit_code
}

# Run validation
main "$@"
