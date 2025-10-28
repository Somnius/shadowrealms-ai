# 🚀 GitHub Repository Setup Guide

This guide will walk you through setting up your ShadowRealms AI project on GitHub, including repository creation, initial setup, and ongoing workflow.

## 📋 Prerequisites

- GitHub account
- Git installed on your local machine
- SSH key set up (recommended) or GitHub token
- Basic knowledge of Git commands

## 🎯 Step 1: Create GitHub Repository

### 1.1 Go to GitHub
- Visit [github.com](https://github.com) and sign in
- Click the "+" icon in the top right corner
- Select "New repository"

### 1.2 Repository Settings
```
Repository name: shadowrealms-ai
Description: AI-Powered Tabletop RPG Platform with local LLM integration
Visibility: Public (recommended for portfolio)
Initialize with: 
  ☐ README (we'll create our own)
  ☐ .gitignore (we have a comprehensive one)
  ☐ License (we'll add MIT license)
```

### 1.3 Click "Create repository"

## 🔧 Step 2: Local Repository Setup

### 2.1 Initialize Git (if not already done)
```bash
# Check if git is already initialized
ls -la | grep .git

# If no .git directory, initialize git
git init
```

### 2.2 Add GitHub Remote
```bash
# Replace 'yourusername' with your actual GitHub username
git remote add origin https://github.com/Somnius/shadowrealms-ai.git

# Verify remote was added
git remote -v
```

### 2.3 Create Initial Branch Structure
```bash
# Create and switch to main branch
git checkout -b main

# Create development branch
git checkout -b develop

# Switch back to main
git checkout main
```

## 📁 Step 3: Prepare Files for Upload

### 3.1 Check Current Status
```bash
# Use our git workflow script
./scripts/git_workflow.sh status
```

### 3.2 Create .env File from Template
```bash
# Copy the template to create your actual .env file
cp env.template .env

# Edit .env with your actual values
nano .env  # or use your preferred editor
```

### 3.3 Verify .gitignore
The `.gitignore` file should already exclude:
- `.env` (sensitive information)
- `backup/` (backup files)
- `data/` (runtime data)
- `*.db` (database files)
- `node_modules/` (dependencies)

## 🚀 Step 4: Initial Commit and Push

### 4.1 Initial Commit
```bash
# Stage all files (except those in .gitignore)
git add .

# Check what will be committed
git status

# Make initial commit
./scripts/git_workflow.sh commit "Initial commit: ShadowRealms AI v0.4.4 - Complete Phase 1"
```

### 4.2 Push to GitHub
```bash
# Push main branch
./scripts/git_workflow.sh push

# Push develop branch
git checkout develop
./scripts/git_workflow.sh push
```

## 🏷️ Step 5: Create First Release

### 5.1 Create Release Tag
```bash
# Switch to main branch
git checkout main

# Create release tag
./scripts/git_workflow.sh release 0.4.4
```

### 5.2 GitHub Release
- Go to your repository on GitHub
- Click "Releases" on the right side
- Click "Create a new release"
- Select tag: `v0.4.4`
- Title: `ShadowRealms AI v0.4.4 - Phase 1 Complete`
- Description: Copy from `CHANGELOG.md`
- Click "Publish release"

## 🔄 Step 6: Ongoing Development Workflow

### 6.1 Feature Development
```bash
# Create feature branch
./scripts/git_workflow.sh feature user-authentication

# Make changes and commit
./scripts/git_workflow.sh commit "Add user authentication system"

# Push feature branch
./scripts/git_workflow.sh push
```

### 6.2 Pull Request Process
1. Go to GitHub repository
2. Click "Compare & pull request" for your feature branch
3. Fill in PR description
4. Request review (if collaborating)
5. Merge when approved

### 6.3 Merging Features
```bash
# Switch to develop branch
git checkout develop

# Pull latest changes
./scripts/git_workflow.sh pull

# Merge feature branch
./scripts/git_workflow.sh merge feature/user-authentication
```

### 6.4 Creating Releases
```bash
# Switch to main branch
git checkout main

# Merge develop into main
git merge develop

# Create release
./scripts/git_workflow.sh release 0.5.0
```

## 📚 Step 7: Repository Management

### 7.1 Repository Settings
- **General**: Set repository name and description
- **Branches**: Protect main and develop branches
- **Collaborators**: Add team members if needed
- **Webhooks**: Set up CI/CD if desired

### 7.2 Branch Protection Rules
```
Branch: main
☑️ Require pull request reviews
☑️ Require status checks to pass
☑️ Include administrators
☑️ Restrict pushes that create files
☑️ Require linear history
```

### 7.3 Issue Templates
Create `.github/ISSUE_TEMPLATE/` directory with:
- `bug_report.md`
- `feature_request.md`
- `enhancement.md`

## 🎨 Step 8: Repository Customization

### 8.1 Repository Topics
Add relevant topics to help discovery:
- `rpg`
- `ai`
- `gaming`
- `flask`
- `react`
- `docker`
- `local-llm`
- `vector-database`

### 8.2 Repository Description
```
🎮 AI-Powered Tabletop RPG Platform

Transform your tabletop gaming with local AI Dungeon Masters, vector memory, and immersive storytelling. Built with Flask, React, Docker, and local LLM integration.

🚀 Features: AI Dungeon Master, Vector Memory, Role-Based Access, GPU Monitoring
🛠️ Tech: Python, Flask, React, ChromaDB, Docker, Local LLMs
```

### 8.3 Social Preview
- Add social preview image (1200x630px)
- Update repository description
- Pin important repositories

## 🔍 Step 9: Verification

### 9.1 Check Repository
- [ ] All files uploaded correctly
- [ ] .env file NOT in repository
- [ ] README.md displays properly
- [ ] .gitignore working correctly
- [ ] License file present
- [ ] Release created successfully

### 9.2 Test Clone
```bash
# Test cloning from another location
cd /tmp
git clone https://github.com/Somnius/shadowrealms-ai.git
cd shadowrealms-ai
ls -la  # Verify files are present
```

## 🚨 Important Security Notes

### 9.1 Never Commit Sensitive Files
- ✅ `.env` files
- ✅ API keys
- ✅ Database files
- ✅ Log files
- ✅ Backup files
- ✅ Personal configuration

### 9.2 Use Environment Variables
- Store sensitive data in `.env` files
- Use `env.template` for documentation
- Keep `.env` in `.gitignore`

### 9.3 Regular Security Updates
- Update dependencies regularly
- Monitor for security advisories
- Use GitHub's security features

## 🎯 Next Steps

### 9.1 Community Engagement
- Share on social media
- Post in relevant forums
- Engage with the RPG community
- Respond to issues and discussions

### 9.2 Continuous Improvement
- Regular updates and releases
- Feature requests from community
- Bug reports and fixes
- Documentation improvements

### 9.3 Collaboration
- Accept contributions
- Code reviews
- Issue triage
- Community guidelines

## 📞 Support

If you encounter issues:
1. Check GitHub documentation
2. Review Git workflow script help: `./scripts/git_workflow.sh help`
3. Check repository settings
4. Verify .gitignore configuration

---

**Congratulations! 🎉 Your ShadowRealms AI project is now on GitHub and ready to showcase your development skills!**
