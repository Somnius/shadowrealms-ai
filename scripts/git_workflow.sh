#!/bin/bash

# ShadowRealms AI - Git Workflow Script
# Comprehensive git operations for development workflow

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
REPO_NAME="shadowrealms-ai"
MAIN_BRANCH="main"
DEVELOPMENT_BRANCH="develop"

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}================================${NC}"
}

# Function to check if we're in a git repository
check_git_repo() {
    if [ ! -d ".git" ]; then
        print_error "Not in a git repository. Please run this script from the project root."
        exit 1
    fi
}

# Function to check git status
check_status() {
    print_header "Git Status Check"
    git status --short
    echo ""
    
    # Check for untracked files
    UNTRACKED=$(git status --porcelain | grep "^??" | wc -l)
    if [ $UNTRACKED -gt 0 ]; then
        print_warning "Found $UNTRACKED untracked files"
    fi
    
    # Check for modified files
    MODIFIED=$(git status --porcelain | grep "^ M" | wc -l)
    if [ $MODIFIED -gt 0 ]; then
        print_warning "Found $MODIFIED modified files"
    fi
    
    # Check for staged files
    STAGED=$(git status --porcelain | grep "^M " | wc -l)
    if [ $STAGED -gt 0 ]; then
        print_status "Found $STAGED staged files"
    fi
}

# Function to create a new feature branch
create_feature_branch() {
    if [ -z "$1" ]; then
        print_error "Please provide a feature name: ./git_workflow.sh feature <feature-name>"
        exit 1
    fi
    
    FEATURE_NAME="$1"
    BRANCH_NAME="feature/$FEATURE_NAME"
    
    print_header "Creating Feature Branch"
    print_status "Feature: $FEATURE_NAME"
    print_status "Branch: $BRANCH_NAME"
    
    # Check if we're on main or develop
    CURRENT_BRANCH=$(git branch --show-current)
    if [ "$CURRENT_BRANCH" != "$MAIN_BRANCH" ] && [ "$CURRENT_BRANCH" != "$DEVELOPMENT_BRANCH" ]; then
        print_warning "You're currently on branch: $CURRENT_BRANCH"
        read -p "Switch to $DEVELOPMENT_BRANCH first? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            git checkout $DEVELOPMENT_BRANCH
        fi
    fi
    
    # Create and switch to feature branch
    git checkout -b "$BRANCH_NAME"
    print_status "Created and switched to branch: $BRANCH_NAME"
}

# Function to stage and commit changes
commit_changes() {
    if [ -z "$1" ]; then
        print_error "Please provide a commit message: ./git_workflow.sh commit <message>"
        exit 1
    fi
    
    COMMIT_MESSAGE="$1"
    
    print_header "Committing Changes"
    print_status "Message: $COMMIT_MESSAGE"
    
    # Add all changes
    git add .
    
    # Check what's staged
    STAGED_FILES=$(git diff --cached --name-only)
    if [ -z "$STAGED_FILES" ]; then
        print_warning "No files staged for commit"
        return
    fi
    
    echo "Staged files:"
    echo "$STAGED_FILES" | sed 's/^/  /'
    echo ""
    
    # Commit
    git commit -m "$COMMIT_MESSAGE"
    print_status "Changes committed successfully"
}

# Function to push changes
push_changes() {
    print_header "Pushing Changes"
    
    CURRENT_BRANCH=$(git branch --show-current)
    print_status "Current branch: $CURRENT_BRANCH"
    
    # Check if remote exists
    if ! git remote get-url origin > /dev/null 2>&1; then
        print_error "No remote 'origin' found. Please add your GitHub remote first."
        print_status "Example: git remote add origin https://github.com/Somnius/shadowrealms-ai.git"
        exit 1
    fi
    
    # Push current branch
    if git push origin "$CURRENT_BRANCH"; then
        print_status "Successfully pushed to origin/$CURRENT_BRANCH"
    else
        print_error "Failed to push changes"
        exit 1
    fi
}

# Function to pull latest changes
pull_changes() {
    print_header "Pulling Latest Changes"
    
    CURRENT_BRANCH=$(git branch --show-current)
    print_status "Current branch: $CURRENT_BRANCH"
    
    # Check if remote exists
    if ! git remote get-url origin > /dev/null 2>&1; then
        print_error "No remote 'origin' found. Please add your GitHub remote first."
        exit 1
    fi
    
    # Pull latest changes
    if git pull origin "$CURRENT_BRANCH"; then
        print_status "Successfully pulled latest changes"
    else
        print_error "Failed to pull changes"
        exit 1
    fi
}

# Function to merge feature branch
merge_feature() {
    if [ -z "$1" ]; then
        print_error "Please provide a feature branch name: ./git_workflow.sh merge <feature-branch>"
        exit 1
    fi
    
    FEATURE_BRANCH="$1"
    
    print_header "Merging Feature Branch"
    print_status "Feature branch: $FEATURE_BRANCH"
    
    # Check if feature branch exists
    if ! git branch --list "$FEATURE_BRANCH" > /dev/null 2>&1; then
        print_error "Feature branch '$FEATURE_BRANCH' not found"
        exit 1
    fi
    
    # Check if we're on main or develop
    CURRENT_BRANCH=$(git branch --show-current)
    if [ "$CURRENT_BRANCH" != "$MAIN_BRANCH" ] && [ "$CURRENT_BRANCH" != "$DEVELOPMENT_BRANCH" ]; then
        print_warning "You're currently on branch: $CURRENT_BRANCH"
        read -p "Switch to $DEVELOPMENT_BRANCH for merge? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            git checkout $DEVELOPMENT_BRANCH
        fi
    fi
    
    # Merge feature branch
    if git merge "$FEATURE_BRANCH"; then
        print_status "Successfully merged $FEATURE_BRANCH into $CURRENT_BRANCH"
        
        # Ask if user wants to delete feature branch
        read -p "Delete feature branch $FEATURE_BRANCH? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            git branch -d "$FEATURE_BRANCH"
            print_status "Deleted feature branch: $FEATURE_BRANCH"
        fi
    else
        print_error "Merge failed. Please resolve conflicts and try again."
        exit 1
    fi
}

# Function to create a release
create_release() {
    if [ -z "$1" ]; then
        print_error "Please provide a version number: ./git_workflow.sh release <version>"
        exit 1
    fi
    
    VERSION="$1"
    TAG_NAME="v$VERSION"
    
    print_header "Creating Release"
    print_status "Version: $VERSION"
    print_status "Tag: $TAG_NAME"
    
    # Check if we're on main branch
    CURRENT_BRANCH=$(git branch --show-current)
    if [ "$CURRENT_BRANCH" != "$MAIN_BRANCH" ]; then
        print_warning "You're currently on branch: $CURRENT_BRANCH"
        read -p "Switch to $MAIN_BRANCH for release? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            git checkout $MAIN_BRANCH
        else
            print_error "Release must be created from main branch"
            exit 1
        fi
    fi
    
    # Create tag
    git tag -a "$TAG_NAME" -m "Release $VERSION"
    print_status "Created tag: $TAG_NAME"
    
    # Push tag
    if git push origin "$TAG_NAME"; then
        print_status "Successfully pushed tag to origin"
    else
        print_error "Failed to push tag"
        exit 1
    fi
    
    print_status "Release $VERSION created successfully!"
    print_status "Don't forget to create a release on GitHub with the tag $TAG_NAME"
}

# Function to show help
show_help() {
    print_header "Git Workflow Commands"
    echo ""
    echo "Usage: ./git_workflow.sh <command> [options]"
    echo ""
    echo "Commands:"
    echo "  status                    - Check git status and show changes"
    echo "  feature <name>            - Create and switch to feature branch"
    echo "  commit <message>          - Stage and commit all changes"
    echo "  push                      - Push current branch to origin"
    echo "  pull                      - Pull latest changes from origin"
    echo "  merge <feature-branch>    - Merge feature branch into current branch"
    echo "  release <version>         - Create and push a version tag"
    echo "  help                      - Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./git_workflow.sh status"
    echo "  ./git_workflow.sh feature user-authentication"
    echo "  ./git_workflow.sh commit 'Add user authentication system'"
    echo "  ./git_workflow.sh push"
    echo "  ./git_workflow.sh merge feature/user-authentication"
    echo "  ./git_workflow.sh release 0.5.0"
    echo ""
    echo "Workflow:"
    echo "  1. Create feature branch: ./git_workflow.sh feature <name>"
    echo "  2. Make changes and commit: ./git_workflow.sh commit <message>"
    echo "  3. Push feature branch: ./git_workflow.sh push"
    echo "  4. Create PR on GitHub"
    echo "  5. Merge feature: ./git_workflow.sh merge <feature-branch>"
    echo "  6. Create release: ./git_workflow.sh release <version>"
}

# Main script logic
main() {
    check_git_repo
    
    case "$1" in
        "status")
            check_status
            ;;
        "feature")
            create_feature_branch "$2"
            ;;
        "commit")
            commit_changes "$2"
            ;;
        "push")
            push_changes
            ;;
        "pull")
            pull_changes
            ;;
        "merge")
            merge_feature "$2"
            ;;
        "release")
            create_release "$2"
            ;;
        "help"|"--help"|"-h"|"")
            show_help
            ;;
        *)
            print_error "Unknown command: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"
