#!/bin/bash
# Pre-push hook script for Diamond Web project
# Performs automated verification before pushing to upstream

echo "--------------------------------------------------------"
echo "🔍 Running pre-push verification tests..."
echo "--------------------------------------------------------"

# Step 1: Run Pytest unit and integration test suite
echo "⚡ [1/2] Running Pytest unit & integration tests..."
pytest diamond_web/tests/ --tb=short -q
PYTEST_EXIT=$?

if [ $PYTEST_EXIT -ne 0 ]; then
    echo ""
    echo "❌ Unit tests failed! Aborting git push."
    echo "Please fix the failing unit tests before pushing."
    exit 1
fi
echo "✅ Unit tests passed."

# Step 2: Check & Run E2E Playwright tests if server is active
if [ -d "e2e" ]; then
    echo ""
    echo "🎭 [2/2] Preparing E2E Playwright tests..."
    
    # Setup test data (idempotent)
    python e2e/setup_test_data.py > /dev/null 2>&1
    
    # Check if dev server is running on port 8000
    HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000)
    
    if [ "$HTTP_STATUS" -ne 000 ]; then
        echo "🌐 Django dev server detected on http://127.0.0.1:8000."
        echo "🚀 Running E2E scenarios..."
        python e2e/run_all.py
        E2E_EXIT=$?
        
        if [ $E2E_EXIT -ne 0 ]; then
            echo ""
            echo "❌ E2E Playwright tests failed! Aborting git push."
            echo "Please check e2e/report/RESULTS.md for details."
            exit 1
        fi
        echo "✅ E2E tests passed."
    else
        echo "⚠️  Dev server (127.0.0.1:8000) is NOT running."
        echo "   Skipping E2E browser tests. (Run 'python manage.py runserver' to include E2E tests)."
    fi
fi

echo ""
echo "--------------------------------------------------------"
echo "🎉 All pre-push checks passed! Proceeding with push."
echo "--------------------------------------------------------"
exit 0
