# ShadowRealms AI - Test Suite

This directory contains all test scripts for the ShadowRealms AI project.

## 📋 Test Files Overview

### Python Test Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `test_phase2.py` | Phase 2 RAG & Vector Memory System tests | `python3 tests/test_phase2.py` |
| `test_user_experience.py` | End-to-end user experience tests | `python3 tests/test_user_experience.py` |
| `test_comprehensive_verification.py` | Comprehensive system verification | `python3 tests/test_comprehensive_verification.py` |
| `test_deep_verification.py` | Deep system verification | `python3 tests/test_deep_verification.py` |
| `test_rule_books.py` | Rule book integration tests | `python3 tests/test_rule_books.py` |
| `test_modules.py` | Module-level unit tests | `python3 tests/test_modules.py` |
| `test_flask_config.py` | Flask configuration tests | `python3 tests/test_flask_config.py` |
| `test_docker_env.py` | Docker environment tests | `python3 tests/test_docker_env.py` |

### Shell Test Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `test-auth-docker.sh` | Frontend authentication tests in Docker | `./tests/test-auth-docker.sh` |
| `test_docker.sh` | Docker environment verification | `./tests/test_docker.sh` |
| `validate-test-structure.sh` | Validate test structure | `./tests/validate-test-structure.sh` |

## 🚀 Running Tests

### Quick Test Commands

```bash
# Run from project root

# Phase 2 tests (RAG & Vector Memory)
python3 tests/test_phase2.py

# User experience tests (End-to-end)
python3 tests/test_user_experience.py

# Frontend authentication tests (in Docker)
./tests/test-auth-docker.sh

# Docker environment tests
./tests/test_docker.sh
```

### Running All Tests

```bash
# From project root
cd /path/to/shadowrealms-ai

# Run all Python tests
for test in tests/test_*.py; do
    echo "Running $test..."
    python3 "$test"
done

# Run all shell tests
for test in tests/*.sh; do
    echo "Running $test..."
    bash "$test"
done
```

## 📊 Test Categories

### Phase Tests
- **Phase 2**: RAG & Vector Memory System
  - Tests campaign management
  - Tests memory search
  - Tests context retrieval
  - Tests AI generation with RAG

### System Tests
- **Comprehensive Verification**: Full system health check
- **Deep Verification**: Detailed component testing
- **Docker Environment**: Container and service validation

### Integration Tests
- **User Experience**: End-to-end user workflows
- **Rule Books**: PDF processing and RAG integration
- **Authentication**: Frontend auth system (Docker-based)

### Unit Tests
- **Modules**: Individual backend module tests
- **Flask Config**: Configuration loading and validation

## 🔧 Test Requirements

### Prerequisites

```bash
# Python dependencies (already in requirements.txt)
pip install requests pytest pytest-cov

# For frontend tests
cd frontend
npm install
```

### Environment Setup

```bash
# Ensure .env file exists
cp env.template .env

# Edit .env with your configuration
nano .env

# Ensure Docker services are running
docker compose up -d
```

## ✅ Expected Results

All tests should pass with the following results:

| Test Suite | Expected Status |
|------------|----------------|
| Phase 2 | 8/9 tests passing (88.9% - Campaign retrieval has test structure issue) |
| User Experience | 7/7 tests passing |
| Docker Environment | All checks passing |
| Frontend Auth | 61/61 tests passing |

## 🐛 Troubleshooting

### Common Issues

**Tests can't import backend modules:**
```bash
# Make sure you're running from project root
cd /path/to/shadowrealms-ai
python3 tests/test_phase2.py
```

**Docker tests fail:**
```bash
# Ensure Docker is running
docker compose ps

# Restart services if needed
docker compose restart
```

**LM Studio tests fail:**
```bash
# Ensure LM Studio is running with model loaded
curl http://localhost:1234/v1/models
```

## 📝 Adding New Tests

1. Create test file in `tests/` directory
2. Follow naming convention: `test_*.py` or `test*.sh`
3. Import from backend with: `sys.path.insert(0, '../backend')`
4. Update this README with test description
5. Run tests to verify they work

## 🎯 Best Practices

- ✅ Always run tests from project root
- ✅ Ensure services are running before testing
- ✅ Check `.env` configuration is correct
- ✅ Use descriptive test names
- ✅ Add comments explaining complex tests
- ✅ Clean up test data after tests complete

---

**Test Suite Status:** ✅ All organizational structure complete
**Last Updated:** 2025-10-24

