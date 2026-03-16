# Test Cases

This directory contains test data and test case documentation for integration tests.

## Directory Structure

```
testcases/
├── workspace_switch_test/      # Workspace switching integration test data
│   ├── workspace_alpha/        # Test workspace Alpha
│   │   ├── README.md           # "This is workspace Alpha"
│   │   └── test_file.txt       # "Content from Alpha workspace"
│   └── workspace_beta/         # Test workspace Beta
│       ├── README.md           # "This is workspace Beta"
│       └── test_file.txt       # "Content from Beta workspace"
```

## Workspace Switch Test

**Purpose**: Test the workspace enumeration, switching, and file reading functionality.

**Test File**: `tests/integration/test_workspace_switch.py`

**Test Scenarios**:

1. ✅ Setup and validate test workspace structure
2. ✅ Enumerate workspaces via API
3. ✅ Switch to workspace Alpha
4. ✅ Read files in Alpha workspace
5. ✅ Switch to workspace Beta
6. ✅ Read files in Beta workspace
7. ✅ Switch back and forth between workspaces
8. ✅ Validate error handling for invalid workspace numbers
9. ✅ Validate error handling for non-numeric input

**How to Run**:

```bash
# Run workspace switch integration tests
uv run pytest tests/integration/test_workspace_switch.py -v

# Run with detailed output
uv run pytest tests/integration/test_workspace_switch.py -v --tb=short
```

**Test Coverage**:

- Workspace enumeration (`get_workspaces()`)
- Workspace switching (`switch_workspace()`)
- Current workspace detection (`get_current_workspace()`)
- File reading across workspaces
- Error handling for invalid inputs

**API Endpoints Tested**:

- `GET /api/workspace-state` - Get current workspace state
- `POST /api/workspace-switch` - Switch workspace
- `POST /api/read-file` - Read file content

**Notes**:

- The test uses pytest's `tmp_path` fixture for automatic cleanup
- Environment variables are set temporarily during tests
- Tests create isolated workspace directories with same-named files
- File content differs between workspaces to verify correct switching