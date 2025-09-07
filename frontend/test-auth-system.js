#!/usr/bin/env node

/**
 * ShadowRealms AI - Authentication System Test Runner
 * 
 * This script runs comprehensive tests for the authentication system
 * and provides detailed reporting on test coverage and results.
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

console.log('🎯 ShadowRealms AI - Authentication System Test Suite');
console.log('=' .repeat(60));

// Test configuration
const testConfig = {
  coverage: true,
  verbose: true,
  watchAll: false,
  passWithNoTests: true,
  collectCoverageFrom: [
    'src/components/auth/**/*.{js,jsx,ts,tsx}',
    'src/components/ui/**/*.{js,jsx,ts,tsx}',
    'src/services/**/*.{js,jsx,ts,tsx}',
    'src/store/**/*.{js,jsx,ts,tsx}',
    'src/types/**/*.{js,jsx,ts,tsx}',
    '!src/**/*.d.ts',
    '!src/**/*.test.{js,jsx,ts,tsx}',
    '!src/**/*.spec.{js,jsx,ts,tsx}',
  ],
  coverageThreshold: {
    global: {
      branches: 80,
      functions: 80,
      lines: 80,
      statements: 80,
    },
  },
};

// Test categories
const testCategories = [
  {
    name: '🔐 Authentication Service',
    pattern: 'src/__tests__/services/authService.test.ts',
    description: 'API service layer tests',
  },
  {
    name: '🏪 Authentication Store',
    pattern: 'src/__tests__/store/authStore.test.ts',
    description: 'Zustand state management tests',
  },
  {
    name: '🎨 UI Components',
    pattern: 'src/__tests__/components/ui/*.test.tsx',
    description: 'Button, Input, Card component tests',
  },
  {
    name: '📝 Login Form',
    pattern: 'src/__tests__/components/auth/LoginForm.test.tsx',
    description: 'Login form integration tests',
  },
];

// Run tests
async function runTests() {
  try {
    console.log('\n🚀 Starting Authentication System Tests...\n');
    
    // Check if test files exist
    const testFiles = [];
    testCategories.forEach(category => {
      const testPath = path.join(__dirname, category.pattern);
      if (fs.existsSync(testPath)) {
        testFiles.push(testPath);
        console.log(`✅ Found: ${category.name}`);
      } else {
        console.log(`❌ Missing: ${category.name}`);
      }
    });
    
    if (testFiles.length === 0) {
      console.log('\n❌ No test files found!');
      return;
    }
    
    console.log(`\n📊 Running ${testFiles.length} test files...\n`);
    
    // Run tests with coverage
    const testCommand = [
      'npm run test:ci',
      '--',
      '--testPathPattern="(' + testFiles.map(f => path.basename(f, '.test.tsx').replace('.test.ts', '')).join('|') + ')"',
      '--verbose',
      '--coverage',
      '--coverageReporters=text',
      '--coverageReporters=text-summary',
      '--coverageReporters=html',
    ].join(' ');
    
    console.log(`🔧 Command: ${testCommand}\n`);
    
    execSync(testCommand, { 
      stdio: 'inherit',
      cwd: __dirname,
    });
    
    console.log('\n✅ All tests completed successfully!');
    
    // Check coverage report
    const coveragePath = path.join(__dirname, 'coverage', 'lcov-report', 'index.html');
    if (fs.existsSync(coveragePath)) {
      console.log(`\n📈 Coverage report generated: ${coveragePath}`);
    }
    
  } catch (error) {
    console.error('\n❌ Tests failed:', error.message);
    process.exit(1);
  }
}

// Test summary
function printTestSummary() {
  console.log('\n📋 Test Summary:');
  console.log('=' .repeat(40));
  
  testCategories.forEach(category => {
    console.log(`\n${category.name}`);
    console.log(`   ${category.description}`);
    
    const testPath = path.join(__dirname, category.pattern);
    if (fs.existsSync(testPath)) {
      const content = fs.readFileSync(testPath, 'utf8');
      const testCount = (content.match(/it\(|test\(/g) || []).length;
      const describeCount = (content.match(/describe\(/g) || []).length;
      
      console.log(`   📊 ${describeCount} test suites, ${testCount} tests`);
    } else {
      console.log('   ❌ Test file not found');
    }
  });
  
  console.log('\n🎯 Test Coverage Targets:');
  console.log('   • Branches: 80%');
  console.log('   • Functions: 80%');
  console.log('   • Lines: 80%');
  console.log('   • Statements: 80%');
}

// Main execution
async function main() {
  printTestSummary();
  await runTests();
  
  console.log('\n🎉 Authentication System Test Suite Complete!');
  console.log('=' .repeat(60));
}

// Run if called directly
if (require.main === module) {
  main().catch(console.error);
}

module.exports = { runTests, testCategories };
