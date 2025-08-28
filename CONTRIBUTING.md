# Contributing to ShadowRealms AI

Thank you for your interest in contributing to ShadowRealms AI! This document provides guidelines and information for contributors.

## 🤝 **Table of Contents**

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Contribution Types](#contribution-types)
- [Code Standards](#code-standards)
- [Testing Guidelines](#testing-guidelines)
- [Pull Request Process](#pull-request-process)
- [Release Process](#release-process)
- [Community Guidelines](#community-guidelines)
- [Getting Help](#getting-help)

## 📜 **Code of Conduct**

### **Our Pledge**
We are committed to providing a welcoming and inspiring community for all. By participating in this project, you agree to uphold our Code of Conduct.

### **Our Standards**
- **Be respectful** and inclusive of all contributors
- **Be collaborative** and open to different viewpoints
- **Be constructive** in feedback and discussions
- **Be professional** in all interactions
- **Be helpful** to newcomers and experienced developers alike

### **Unacceptable Behavior**
- Harassment, discrimination, or offensive behavior
- Spam, trolling, or disruptive conduct
- Violation of privacy or confidentiality
- Any form of intimidation or coercion

## 🚀 **Getting Started**

### **Prerequisites**
- Python 3.11+ (for backend development)
- Node.js 18+ (for frontend development)
- Docker and Docker Compose
- Git
- Basic understanding of RPG systems and AI/ML concepts

### **First Steps**
1. **Fork the repository** on GitHub
2. **Clone your fork** locally
3. **Set up the development environment** (see Development Setup)
4. **Create a feature branch** for your work
5. **Make your changes** following our standards
6. **Test thoroughly** before submitting
7. **Submit a pull request** with clear description

## 🛠️ **Development Setup**

### **Quick Setup**
```bash
# Clone your fork
git clone https://github.com/Somnius/shadowrealms-ai.git
cd shadowrealms-ai

# Set up Python environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r backend/requirements.txt

# Set up Node.js environment
cd frontend
npm install
cd ..

# Set up environment variables
cp env.template .env
# Edit .env with your configuration

# Start development environment
docker-compose up --build
```

### **Environment Configuration**
- Copy `env.template` to `.env`
- Configure your local LLM endpoints
- Set up database connections
- Configure API keys (if using external services)

## 📝 **Contribution Types**

### **Code Contributions**
- **Bug fixes** - Resolve issues and improve stability
- **Feature development** - Add new RPG mechanics or AI capabilities
- **Performance improvements** - Optimize algorithms and database queries
- **Security enhancements** - Strengthen authentication and data protection
- **Documentation** - Improve guides, API docs, and code comments

### **Non-Code Contributions**
- **Bug reporting** - Detailed issue descriptions with reproduction steps
- **Feature requests** - Well-thought-out proposals with use cases
- **Documentation** - Tutorials, guides, and examples
- **Testing** - Manual testing and test case development
- **Community support** - Helping other users and contributors

### **Priority Areas**
1. **Core RPG Engine** - Game mechanics and rule systems
2. **AI Integration** - LLM integration and prompt engineering
3. **User Experience** - UI/UX improvements and accessibility
4. **Performance** - Scalability and optimization
5. **Testing** - Test coverage and automation
6. **Documentation** - User guides and developer docs

## 🎯 **Code Standards**

### **Python (Backend)**
```python
# Follow PEP 8 style guide
# Use type hints for function parameters and return values
# Include docstrings for all public functions and classes
# Use meaningful variable and function names

def calculate_damage(weapon_power: int, armor_rating: int, 
                    critical_hit: bool = False) -> int:
    """
    Calculate damage dealt to a target.
    
    Args:
        weapon_power: Base damage of the weapon
        armor_rating: Target's armor protection
        critical_hit: Whether this is a critical hit
        
    Returns:
        Final damage amount after armor reduction
    """
    base_damage = weapon_power
    if critical_hit:
        base_damage *= 1.5
    
    final_damage = max(1, base_damage - armor_rating)
    return int(final_damage)
```

### **JavaScript/React (Frontend)**
```javascript
// Use ES6+ features
// Follow React best practices
// Use functional components with hooks
// Include PropTypes or TypeScript types
// Use meaningful component and variable names

import React, { useState, useEffect } from 'react';
import PropTypes from 'prop-types';

const CharacterSheet = ({ character, onUpdate }) => {
  const [isEditing, setIsEditing] = useState(false);
  
  useEffect(() => {
    // Component lifecycle logic
  }, [character]);
  
  const handleSave = () => {
    onUpdate(character);
    setIsEditing(false);
  };
  
  return (
    <div className="character-sheet">
      {/* Component JSX */}
    </div>
  );
};

CharacterSheet.propTypes = {
  character: PropTypes.object.isRequired,
  onUpdate: PropTypes.func.isRequired
};
```

### **General Standards**
- **Readability** - Code should be self-documenting
- **Consistency** - Follow established patterns in the codebase
- **Modularity** - Break complex functions into smaller, focused ones
- **Error handling** - Include proper exception handling and validation
- **Comments** - Explain complex logic, not obvious code
- **Testing** - Include tests for new functionality

## 🧪 **Testing Guidelines**

### **Test Requirements**
- **Unit tests** for all new functions and classes
- **Integration tests** for API endpoints and database operations
- **Frontend tests** for React components and user interactions
- **Performance tests** for critical paths and algorithms

### **Running Tests**
```bash
# Backend tests
cd backend
python -m pytest tests/ -v --cov=.

# Frontend tests
cd frontend
npm test

# Full test suite
./test_modules.py
```

### **Test Standards**
- **Coverage** - Aim for 80%+ code coverage
- **Naming** - Descriptive test names that explain the scenario
- **Isolation** - Tests should be independent and repeatable
- **Mocking** - Mock external dependencies appropriately
- **Assertions** - Use specific assertions with clear failure messages

## 🔄 **Pull Request Process**

### **Before Submitting**
1. **Ensure tests pass** locally
2. **Update documentation** if needed
3. **Check code style** with linters
4. **Rebase on main** to avoid conflicts
5. **Self-review** your changes

### **Pull Request Template**
```markdown
## Description
Brief description of changes and why they're needed

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update
- [ ] Performance improvement

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed
- [ ] Performance impact assessed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No breaking changes introduced

## Screenshots/Examples
Include screenshots or examples if applicable
```

### **Review Process**
1. **Automated checks** must pass (CI/CD)
2. **Code review** by maintainers
3. **Address feedback** and make requested changes
4. **Maintainer approval** required for merge
5. **Squash and merge** to main branch

## 🚀 **Release Process**

### **Version Management**
- **Semantic versioning** (MAJOR.MINOR.PATCH)
- **Feature branches** for new development
- **Release branches** for version preparation
- **Hotfix branches** for critical fixes

### **Release Checklist**
- [ ] All tests passing
- [ ] Documentation updated
- [ ] Changelog updated
- [ ] Version bumped
- [ ] Release notes prepared
- [ ] GitHub release created
- [ ] Docker images tagged

### **Release Commands**
```bash
# Create release branch
git checkout -b release/v1.0.0

# Update version and changelog
# Commit changes

# Create release tag
git tag v1.0.0

# Push to GitHub
git push origin release/v1.0.0
git push origin v1.0.0

# Create GitHub release
# Merge to main
```

## 👥 **Community Guidelines**

### **Communication Channels**
- **GitHub Issues** - Bug reports and feature requests
- **GitHub Discussions** - General questions and community chat
- **Pull Requests** - Code review and collaboration
- **Discord/Slack** - Real-time communication (if available)

### **Best Practices**
- **Be patient** with responses and reviews
- **Ask questions** when something is unclear
- **Share knowledge** and help other contributors
- **Respect time** of maintainers and contributors
- **Celebrate successes** and contributions

### **Getting Help**
- **Search existing issues** before creating new ones
- **Provide context** and reproduction steps
- **Use clear language** and examples
- **Be respectful** even when frustrated

## 🆘 **Getting Help**

### **Resources**
- **README.md** - Project overview and quick start
- **SHADOWREALMS_AI_COMPLETE.md** - Comprehensive documentation
- **Code comments** - Inline documentation
- **Issue templates** - Structured reporting

### **Contact Maintainers**
- **GitHub Issues** - For project-related questions
- **GitHub Discussions** - For community questions
- **Email** - For sensitive or private matters

### **Escalation Process**
1. **Check documentation** first
2. **Search existing issues** for similar problems
3. **Create new issue** with detailed description
4. **Tag maintainers** if urgent or blocking
5. **Follow up** if no response within reasonable time

## 🙏 **Acknowledgments**

Thank you to all contributors who have helped make ShadowRealms AI what it is today. Your contributions, whether big or small, help create an amazing platform for AI-powered tabletop RPGs.

---

**Remember**: Every contribution, no matter how small, makes a difference. Whether you're fixing a typo, adding a feature, or just asking questions, you're helping build something special.

**Happy contributing!** 🎲✨
