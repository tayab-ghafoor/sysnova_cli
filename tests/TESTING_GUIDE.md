# Detailed Testing Guide - P3 Test Coverage

This guide provides detailed information for running, understanding, and extending the P3 test coverage.

## Quick Start

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-mock pytest-cov httpx aiosqlite

# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=Backend_CLI --cov=src --cov-report=html -v
```

---

## Test Suite Details

### 1. Authentication Services Tests (`test_auth_services.py`)

**Purpose:** Validate user authentication, registration, verification, and password management.

**Key Features:**
- In-memory SQLite database for isolated testing
- Async database fixtures using SQLAlchemy
- Mock email services to prevent actual email sending
- Comprehensive error scenario coverage

**Running Specific Tests:**

```bash
# Run all auth tests
pytest tests/test_auth_services.py -v

# Run only registration tests
pytest tests/test_auth_services.py::TestRegisterUser -v

# Run specific test
pytest tests/test_auth_services.py::TestRegisterUser::test_register_new_user_success -v

# Run with async debugging
pytest tests/test_auth_services.py -v -s
```

**Test Categories:**

1. **Registration Tests** (5 tests)
   - Successful registration with valid data
   - Duplicate email prevention
   - Email normalization (lowercase)
   - Email sending validation
   - Password hashing verification

2. **Email Verification Tests** (4 tests)
   - Valid code verification
   - Wrong code rejection
   - Expired code rejection
   - Nonexistent user handling

3. **Login Tests** (3 tests)
   - Successful login flow
   - Invalid credentials rejection
   - Unverified user enforcement

4. **Logout Tests** (1 test)
   - Session termination

5. **Password Reset Tests** (3 tests)
   - Reset request creation
   - Successful confirmation
   - Invalid code rejection

6. **Resend Verification Tests** (2 tests)
   - Successful resend
   - Already verified rejection

**Dependencies:**
- sqlalchemy >= 2.0.23
- asyncpg >= 0.29.0
- passlib[bcrypt] >= 1.7.4

---

### 2. Task Scheduler Tests (`test_task_scheduler.py`)

**Purpose:** Validate task scheduling, execution tracking, and next-run calculations.

**Key Features:**
- Temporary file fixtures for JSON persistence
- Timezone-aware datetime handling
- Schedule type validation (daily, weekly, monthly, every-minute)
- Task state management

**Running Specific Tests:**

```bash
# Run all scheduler tests
pytest tests/test_task_scheduler.py -v

# Run only next-run calculation tests
pytest tests/test_task_scheduler.py::TestNextRunCalculation -v

# Run with timing information
pytest tests/test_task_scheduler.py -v --durations=10
```

**Test Categories:**

1. **Task Addition Tests** (5 tests)
   - Basic task creation
   - Unique ID assignment
   - Backup paths configuration
   - Logs configuration
   - Persistence verification

2. **Due Tasks Tests** (4 tests)
   - No due tasks scenario
   - Overdue task detection
   - Status filtering
   - Every-minute schedule handling

3. **Task Execution Tests** (3 tests)
   - Update on execution
   - Nonexistent task handling
   - Persistence of execution state

4. **Next-Run Calculation Tests** (5 tests)
   - Daily schedule calculation
   - Weekly schedule calculation
   - Monthly schedule calculation
   - Every-minute schedule calculation
   - Recalculation on schedule change

5. **Task Update Tests** (3 tests)
   - Basic field updates
   - Nonexistent task handling
   - Persistence verification

6. **Task Removal Tests** (3 tests)
   - Successful removal
   - Nonexistent task handling
   - Persistence verification

7. **Getter Tests** (4 tests)
   - Get all tasks
   - Get by ID
   - ID not found handling
   - List independence

**Edge Cases Covered:**
- Tasks with invalid times (defaults to 00:00)
- Month-end handling (e.g., Feb 30 → Feb 28)
- DST transitions
- Leap year handling

---

### 3. File Categorizer Tests (`test_file_categorizer.py`)

**Purpose:** Validate file categorization, organization, and temporary file handling.

**Key Features:**
- Temporary directory fixtures
- Multiple file type testing
- Name collision resolution
- Safe file handling

**Running Specific Tests:**

```bash
# Run all file categorizer tests
pytest tests/test_file_categorizer.py -v

# Run only categorization tests
pytest tests/test_file_categorizer.py::TestFileCategorizeTypes -v

# Run batch organization tests
pytest tests/test_file_categorizer.py::TestBatchOrganization -v
```

**Test Categories:**

1. **Basic Functionality Tests** (5 tests)
   - Empty folder handling
   - Category folder creation
   - File movement
   - Nonexistent folder error
   - File path error handling

2. **File Type Categorization Tests** (7 tests)
   - Document categorization
   - Image categorization
   - Video categorization
   - Audio categorization
   - Archive categorization
   - Code file categorization
   - Uncategorized files

3. **Temporary File Handling Tests** (7 tests)
   - Extension-based detection (.tmp, .bak, etc.)
   - Quarantine mode (move to _TempFiles)
   - Permanent deletion mode
   - MS Office lock files (~$file)
   - LibreOffice lock files (.~lock.file#)
   - Windows Thumbs.db detection
   - macOS .DS_Store detection

4. **File Name Collision Tests** (4 tests)
   - No collision scenario
   - Single collision handling (appends _1)
   - Multiple collisions handling
   - Re-run collision handling

5. **Skip Rules Tests** (3 tests)
   - Hidden files skipped
   - Subdirectories skipped
   - Category folders protected

6. **Code File Tests** (3 tests)
   - Python file identification
   - JavaScript file identification
   - Config file categorization

7. **Batch Organization Tests** (3 tests)
   - Mixed file types
   - Performance with many files
   - Error recovery

**Supported Categories:**
- Documents: .pdf, .doc, .docx, .xls, .xlsx, .ppt, .pptx, .txt, .md, etc.
- Images: .jpg, .png, .gif, .svg, .webp, etc.
- Videos: .mp4, .avi, .mkv, .mov, etc.
- Audio: .mp3, .wav, .flac, .aac, etc.
- Archives: .zip, .rar, .7z, .tar, .gz, etc.
- Code: .py, .js, .ts, .html, .css, .java, .cpp, etc.
- Executables: .exe, .msi, .apk, etc.
- Fonts: .ttf, .otf, .woff, etc.
- Data: .db, .sqlite, .parquet, etc.

---

### 4. Encryption Service Tests (`test_encryption_service.py`)

**Purpose:** Validate data encryption, decryption, and key management.

**Key Features:**
- Roundtrip integrity testing
- Key validation and rejection
- Fernet encryption scheme testing
- Legacy plaintext support

**Running Specific Tests:**

```bash
# Run all encryption tests
pytest tests/test_encryption_service.py -v

# Run only roundtrip tests
pytest tests/test_encryption_service.py::TestEncryptDecryptRoundtrip -v

# Run key rejection tests
pytest tests/test_encryption_service.py::TestWrongKeyRejection -v
```

**Test Categories:**

1. **Basic Encryption Tests** (4 tests)
   - Successful encryption
   - Empty data encryption
   - Large data encryption (1MB)
   - Binary data encryption

2. **Basic Decryption Tests** (2 tests)
   - Successful decryption
   - Empty data decryption

3. **Roundtrip Tests** (5 tests)
   - Simple string roundtrip
   - JSON data roundtrip
   - Binary payload roundtrip
   - Multiple consecutive roundtrips
   - Unicode data roundtrip

4. **Key Management Tests** (6 tests)
   - Key material retrieval
   - Empty key rejection
   - Whitespace-only key rejection
   - Key must differ from JWT secret
   - Fernet key generation
   - Key caching verification

5. **Wrong Key Rejection Tests** (3 tests)
   - Explicit error on wrong key
   - Corrupted data detection
   - No silent failures

6. **Prefix Handling Tests** (4 tests)
   - Prefix addition on encryption
   - Prefix removal on decryption
   - Legacy plaintext support
   - No prefix in decrypted data

7. **Data Integrity Tests** (3 tests)
   - Non-deterministic encryption (security)
   - Tampering detection
   - No data loss on roundtrip

8. **Edge Cases Tests** (4 tests)
   - Very large data (10MB)
   - Special byte sequences
   - Prefix-only data rejection
   - Multiple sequential values

**Security Features:**
- Fernet symmetric encryption (256-bit AES)
- HMAC authentication tags
- Timestamp inclusion
- Tamper detection

---

### 5. Backend Client Tests (`test_backend_client.py`)

**Purpose:** Validate HTTP client functionality and all API endpoint wrappers.

**Key Features:**
- Mock HTTP transport for isolated testing
- Token persistence testing
- All endpoint wrappers validated
- Error scenario coverage

**Running Specific Tests:**

```bash
# Run all backend client tests
pytest tests/test_backend_client.py -v

# Run only auth endpoint tests
pytest tests/test_backend_client.py::TestAuthEndpoints -v

# Run only error handling tests
pytest tests/test_backend_client.py::TestErrorHandling -v
```

**Test Categories:**

1. **Token Persistence Tests** (4 tests)
   - Save and load token
   - Nonexistent token handling
   - Token clearing
   - File permissions (0o600)

2. **Connectivity Tests** (5 tests)
   - Successful ping
   - Ping failure
   - Unhealthy status
   - Authentication check with token
   - Authentication check without token

3. **Auth Endpoint Tests** (7 tests)
   - User registration
   - Email verification
   - User login
   - User logout
   - Verification resend
   - Forgot password
   - Reset password

4. **User Endpoint Tests** (2 tests)
   - Get profile
   - Get usage statistics

5. **AI Endpoint Tests** (4 tests)
   - Log analysis
   - Log truncation (50KB max)
   - AI tier checking
   - AI suggestions

6. **Backup Endpoint Tests** (3 tests)
   - Log backup event
   - Create backup log (alias)
   - Get backups list

7. **Log Endpoint Tests** (3 tests)
   - Save log report
   - Create log report (alias)
   - Get log reports

8. **Payment Endpoint Tests** (2 tests)
   - Create checkout session
   - Get subscription

9. **Error Handling Tests** (2 tests)
   - HTTP error responses
   - Network errors

10. **Base URL Handling Tests** (3 tests)
    - Load from environment
    - Trailing slash removal
    - Constructor parameter

**Endpoints Covered:**
- `/api/v1/auth/*` (7 auth endpoints)
- `/api/v1/user/*` (2 user endpoints)
- `/api/v1/ai/*` (3 AI endpoints)
- `/api/v1/backups/*` (2 backup endpoints)
- `/api/v1/logs/*` (2 log endpoints)
- `/api/v1/payment/*` (2 payment endpoints)

---

### 6. FastAPI Routes Tests (`test_fastapi_routes.py`)

**Purpose:** Validate all FastAPI route endpoints and their behavior.

**Key Features:**
- TestClient for synchronous testing
- Mock service layer for isolation
- Comprehensive error scenario testing
- Rate limiting and validation testing

**Running Specific Tests:**

```bash
# Run all FastAPI route tests
pytest tests/test_fastapi_routes.py -v

# Run only auth endpoint tests
pytest tests/test_fastapi_routes.py::TestAuthRegisterEndpoint -v

# Run only error handling tests
pytest tests/test_fastapi_routes.py::TestEndpointErrorHandling -v
```

**Test Categories:**

1. **Auth Register Endpoint Tests** (2 tests)
   - Successful registration
   - Validation error handling

2. **Auth Verify Email Endpoint Tests** (2 tests)
   - Successful verification
   - Invalid code handling

3. **Auth Login Endpoint Tests** (2 tests)
   - Successful login
   - Invalid credentials

4. **Auth Logout Endpoint Tests** (1 test)
   - Session termination

5. **Auth Resend Verification Tests** (1 test)
   - Code resend

6. **Password Reset Endpoint Tests** (2 tests)
   - Request password reset
   - Confirm reset

7. **AI Endpoint Tests** (3 tests)
   - Log analysis
   - AI tier check
   - Suggestions

8. **Backup Endpoint Tests** (2 tests)
   - Log backup
   - Get backups

9. **Log Endpoint Tests** (2 tests)
   - Save report
   - Get reports

10. **Payment Endpoint Tests** (2 tests)
    - Create checkout
    - Webhook

11. **Error Handling Tests** (4 tests)
    - 400 Bad Request
    - 401 Unauthorized
    - 404 Not Found
    - 500 Server Error

12. **Rate Limiting Tests** (2 tests)
    - Verify email rate limit
    - Resend verification rate limit

13. **Input Validation Tests** (3 tests)
    - Password validation
    - Email validation
    - Content type validation

14. **CORS Tests** (1 test)
    - CORS headers present

15. **Content Negotiation Tests** (2 tests)
    - JSON content type
    - Invalid content type rejection

16. **Async Endpoint Tests** (1 test)
    - Async handling

17. **Documentation Tests** (2 tests)
    - OpenAPI schema
    - Swagger UI

---

## Common Tasks

### Adding a New Test

1. **Choose appropriate test file** based on component
2. **Create test class** with descriptive name
3. **Add docstring** explaining test purpose
4. **Use fixtures** for common setup
5. **Assert clearly** with helpful messages
6. **Handle cleanup** appropriately

Example:
```python
class TestNewFeature:
    """Test suite for new feature."""

    def test_new_feature_success(self, fixture):
        """Test successful operation of new feature."""
        # Arrange
        expected = "value"
        
        # Act
        result = new_feature()
        
        # Assert
        assert result == expected
```

### Debugging Failed Tests

```bash
# Run with extra output
pytest test_file.py::TestClass::test_method -vv --tb=long

# Drop into debugger
pytest test_file.py::TestClass::test_method --pdb

# Show print statements
pytest test_file.py::TestClass::test_method -s

# Run only failed tests
pytest --lf

# Run failed tests and stop on first failure
pytest --lf -x
```

### Checking Test Coverage

```bash
# Generate coverage report
pytest --cov=Backend_CLI --cov=src --cov-report=html

# View HTML report (opens in browser)
start htmlcov/index.html  # Windows
open htmlcov/index.html   # macOS
xdg-open htmlcov/index.html  # Linux
```

### Running Tests in Different Ways

```bash
# Run specific markers
pytest -m asyncio  # Only async tests
pytest -m "not slow"  # Skip slow tests

# Run tests by keyword
pytest -k "register"  # Only tests with "register" in name

# Run with specific Python version
tox -e py310  # Requires tox

# Run in parallel (requires pytest-xdist)
pytest -n auto
```

---

## Continuous Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.10', '3.11']
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio pytest-cov pytest-mock
      
      - name: Run tests
        run: pytest tests/ --cov=Backend_CLI --cov=src
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

## Performance Optimization

### Running Tests Faster

```bash
# Run only unit tests (skip integration tests)
pytest -m unit

# Run with fail-fast (stop on first failure)
pytest -x

# Run with parallel workers (requires pytest-xdist)
pip install pytest-xdist
pytest -n auto

# Skip slow tests
pytest -m "not slow"
```

### Profile Test Performance

```bash
# Show slowest tests
pytest --durations=10

# Full timing report
pytest --durations=0
```

---

## Troubleshooting

### Module Not Found Errors

**Solution:** Verify sys.path entries in conftest.py
```python
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "Backend_CLI"))
```

### Async Test Failures

**Solution:** Ensure pytest-asyncio is installed and configured
```bash
pip install pytest-asyncio
# Verify asyncio_mode = auto in pytest.ini
```

### Database Lock Errors

**Solution:** Use in-memory database for tests
```python
engine = create_async_engine("sqlite+aiosqlite:///:memory:")
```

### Import Path Issues

**Solution:** Run tests from project root
```bash
cd /path/to/SystemManagerCLI
pytest tests/ -v
```

---

## Best Practices

### Do:
✅ Use descriptive test names
✅ Test one thing per test
✅ Use fixtures for setup/teardown
✅ Mock external dependencies
✅ Keep tests fast
✅ Maintain test isolation
✅ Document complex scenarios

### Don't:
❌ Test multiple concerns in one test
❌ Use real external services
❌ Share state between tests
❌ Write tests that depend on test order
❌ Use sleep() for synchronization
❌ Test implementation details
❌ Ignore test failures

---

**Last Updated:** May 19, 2026  
**Maintained By:** Development Team  
**Status:** Production Ready ✅
