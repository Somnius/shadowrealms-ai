#!/bin/bash

# 🧪 ShadowRealms AI - Docker Authentication Test Runner
# 
# This script runs the authentication system tests inside Docker containers
# ensuring consistent environments and dependencies.
#
# WHAT THIS SCRIPT DOES:
# 1. Checks if Docker and Docker Compose are available
# 2. Builds the frontend container with all test dependencies
# 3. Runs different types of tests (all, coverage, specific files, etc.)
# 4. Provides colored output for better readability
# 5. Shows test results and coverage information
#
# USAGE EXAMPLES:
#   ./test-auth-docker.sh                    # Run all tests
#   ./test-auth-docker.sh coverage           # Run with coverage report
#   ./test-auth-docker.sh specific LoginForm.test.tsx  # Run specific test
#   ./test-auth-docker.sh custom             # Run custom test suite
#
# DEPENDENCIES:
#   - Docker and Docker Compose must be installed and running
#   - Frontend container must be buildable
#   - Test files must exist in frontend/src/__tests__/

# Exit immediately if any command fails
# This prevents the script from continuing if there are errors
set -e

echo "🎯 ShadowRealms AI - Docker Authentication Test Suite"
echo "======================================================"

# Define color codes for terminal output
# These ANSI escape codes allow us to colorize text in the terminal
RED='\033[0;31m'      # Red color for errors
GREEN='\033[0;32m'    # Green color for success messages
YELLOW='\033[1;33m'   # Yellow color for warnings
BLUE='\033[0;34m'     # Blue color for info messages
NC='\033[0m'          # No Color - resets color back to default

# Function to print colored output with [INFO] prefix
# Usage: print_status "This is an info message"
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Function to print colored output with [SUCCESS] prefix
# Usage: print_success "Operation completed successfully"
print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Function to print colored output with [WARNING] prefix
# Usage: print_warning "This is a warning message"
print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to print colored output with [ERROR] prefix
# Usage: print_error "Something went wrong"
print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if Docker and Docker Compose are available and running
# This is a prerequisite check before we can run any tests
check_docker() {
    print_status "Checking Docker availability..."
    
    # Check if 'docker' command exists in the system PATH
    # 'command -v' returns the path to the command if it exists, or nothing if it doesn't
    # '&> /dev/null' redirects both stdout and stderr to /dev/null (discards output)
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed or not in PATH"
        exit 1  # Exit with error code 1
    fi
    
    # Check if Docker daemon is running by trying to get Docker info
    # If Docker daemon is not running, this command will fail
    if ! docker info &> /dev/null; then
        print_error "Docker daemon is not running"
        exit 1
    fi
    
    # Check if 'docker-compose' command exists
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed or not in PATH"
        exit 1
    fi
    
    print_success "Docker and Docker Compose are available"
}

# Function to build the frontend Docker container
# This ensures all test dependencies are installed and ready
build_container() {
    print_status "Building frontend container with test dependencies..."
    
    # Run docker-compose build command for the frontend service
    # The 'if' statement checks if the command succeeded (exit code 0)
    if docker-compose build frontend; then
        print_success "Frontend container built successfully"
    else
        # If build failed, print error and exit with code 1
        print_error "Failed to build frontend container"
        exit 1
    fi
}

# Function to run different types of tests based on the first argument
# $1 is the test type (all, coverage, watch, specific, custom)
# $2 is optional and used for specific test file names
run_tests() {
    # Set local variable 'test_type' to first argument, default to "all" if not provided
    # ${1:-"all"} means "use $1 if it exists, otherwise use 'all'"
    local test_type=${1:-"all"}
    
    # Use case statement to handle different test types
    # This is like a switch statement in other programming languages
    case $test_type in
        "all")
            print_status "Running all authentication tests..."
            # Run all tests in CI mode (no watch, with coverage)
            # --rm flag removes the container after it finishes
            docker-compose run --rm frontend npm run test:ci
            ;;
        "coverage")
            print_status "Running tests with coverage..."
            # Run tests with detailed coverage report
            docker-compose run --rm frontend npm run test:coverage
            ;;
        "watch")
            print_status "Running tests in watch mode..."
            # Run tests in watch mode (re-runs when files change)
            # exec runs command in existing container instead of creating new one
            docker-compose exec frontend npm test -- --watch
            ;;
        "specific")
            # Set local variable for specific test file, default to LoginForm.test.tsx
            local test_file=${2:-"LoginForm.test.tsx"}
            print_status "Running specific test: $test_file"
            # Run only the specified test file
            docker-compose run --rm frontend npm test -- $test_file
            ;;
        "custom")
            print_status "Running custom test suite..."
            # Run our custom test runner script
            docker-compose run --rm frontend node test-auth-system.js
            ;;
        *)
            # Handle unknown test types
            print_error "Unknown test type: $test_type"
            print_status "Available options: all, coverage, watch, specific, custom"
            exit 1
            ;;
    esac
}

# Show test results
show_results() {
    print_status "Test execution completed"
    
    # Check if coverage report exists
    if docker-compose run --rm frontend test -f coverage/lcov-report/index.html; then
        print_success "Coverage report generated in container"
        print_status "To view coverage report:"
        echo "  docker-compose run --rm frontend cat coverage/lcov-report/index.html"
    fi
}

# Main execution
main() {
    local test_type=${1:-"all"}
    local test_file=${2:-""}
    
    print_status "Starting Docker-based authentication tests..."
    print_status "Test type: $test_type"
    
    # Pre-flight checks
    check_docker
    
    # Build container
    build_container
    
    # Run tests
    if [ "$test_type" = "specific" ] && [ -n "$test_file" ]; then
        run_tests "specific" "$test_file"
    else
        run_tests "$test_type"
    fi
    
    # Show results
    show_results
    
    print_success "🎉 Docker Authentication Test Suite Complete!"
    echo "======================================================"
}

# Help function
show_help() {
    echo "Usage: $0 [TEST_TYPE] [TEST_FILE]"
    echo ""
    echo "TEST_TYPE options:"
    echo "  all       - Run all tests (default)"
    echo "  coverage  - Run tests with coverage report"
    echo "  watch     - Run tests in watch mode"
    echo "  specific  - Run specific test file"
    echo "  custom    - Run custom test suite"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Run all tests"
    echo "  $0 coverage                          # Run with coverage"
    echo "  $0 specific LoginForm.test.tsx       # Run specific test"
    echo "  $0 custom                            # Run custom suite"
    echo ""
    echo "Prerequisites:"
    echo "  - Docker and Docker Compose installed"
    echo "  - Docker daemon running"
    echo "  - Frontend container buildable"
}

# Parse command line arguments
case "${1:-}" in
    -h|--help)
        show_help
        exit 0
        ;;
    *)
        main "$@"
        ;;
esac
