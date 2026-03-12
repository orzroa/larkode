Hooks Configuration
Overview
Hooks are an event-driven mechanism in iFlow CLI that allows you to automatically execute custom commands when specific lifecycle events occur. By configuring Hooks, you can implement automated processing before and after tool calls, environment setup enhancement, cleanup operations when sessions stop, and more.

Key Features
Tool Call Interception: Run custom logic before and after tool execution
Environment Enhancement: Dynamically set environment information when sessions begin
Lifecycle Management: Execute cleanup operations when sessions or subagents stop
Flexible Configuration: Support hierarchical configuration at user and project levels
Security Control: Can block tool execution or modify tool behavior
Hook Types
iFlow CLI supports the following 9 Hook types:

1. PreToolUse Hook
Trigger Time: Before tool execution Use Cases:

Validate tool parameters
Set execution environment
Log tool calls
Block unsafe operations
Example Configuration:

{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'File edit detected'"
          }
        ]
      }
    ]
  }
}

2. PostToolUse Hook
Trigger Time: After tool execution Use Cases:

Process tool execution results
Clean up temporary files
Send notifications
Record execution statistics
Example Configuration:

{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "write_file",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'File operation completed'"
          }
        ]
      }
    ]
  }
}

3. SetUpEnvironment Hook
Trigger Time: At session start, during environment information setup phase Use Cases:

Dynamically generate project information
Set runtime environment variables
Enhance AI context information
Load project-specific configurations
Example Configuration:

{
  "hooks": {
    "SetUpEnvironment": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "echo 'Session environment initialized'"
          }
        ]
      }
    ]
  }
}

4. Stop Hook
Trigger Time: When the main session ends Use Cases:

Clean up session resources
Save session information
Send session summary
Execute cleanup scripts
Example Configuration:

{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "echo 'Main session ended'"
          }
        ]
      }
    ]
  }
}

5. SubagentStop Hook
Trigger Time: When subagent session ends Use Cases:

Clean up subagent resources
Record subtask execution status
Merge subtask results
Execute post-subtask processing
Example Configuration:

{
  "hooks": {
    "SubagentStop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "echo 'Subagent task completed'"
          }
        ]
      }
    ]
  }
}

6. SessionStart Hook
Trigger Time: When session starts (startup, resume, clear, compress) Use Cases:

Initialize session environment
Set up logging
Send session start notifications
Execute startup preprocessing
Supports matcher: Yes - can match based on session start source (startup, resume, clear, compress)

Example Configuration:

{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'New session started'"
          }
        ]
      }
    ]
  }
}

7. SessionEnd Hook
Trigger Time: When session ends normally Use Cases:

Generate session summary reports
Backup session data
Send session end notifications
Execute session cleanup operations
Example Configuration:

{
  "hooks": {
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.iflow/hooks/session_report.py",
            "timeout": 30
          }
        ]
      }
    ]
  }
}

8. UserPromptSubmit Hook
Trigger Time: Before user submits prompt, before iFlow processing Use Cases:

Content filtering and review
Prompt preprocessing and enhancement
Block inappropriate user input
Log user interaction
Supports matcher: Yes - can match based on prompt content Special behavior: Can block prompt submission (return non-zero exit code)

Example Configuration:

{
  "hooks": {
    "UserPromptSubmit": [
      {
        "matcher": ".*sensitive.*",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.iflow/hooks/content_filter.py",
            "timeout": 10
          }
        ]
      }
    ]
  }
}

9. Notification Hook
Trigger Time: When iFlow sends notifications to user Use Cases:

Notification content logging
Third-party system integration
Notification format conversion
Custom notification handling
Supports matcher: Yes - can match based on notification message content Special behavior: Exit code 2 doesn't block notification, only displays stderr to user

Example Configuration:

{
  "hooks": {
    "Notification": [
      {
        "matcher": ".*permission.*",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'Permission notification logged' >> ~/.iflow/permission.log"
          }
        ]
      }
    ]
  }
}

Configuration Methods
1. Configuration Hierarchy
Hooks configuration follows iFlow CLI's hierarchical configuration system:

User Configuration: ~/.iflow/settings.json
Project Configuration: ./.iflow/settings.json
System Configuration: System-level configuration files
Higher-level configurations merge with lower-level configurations, and project configurations supplement user configurations.

2. Configuration Format
Add the hooks configuration item in the settings.json file:

{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "tool_pattern",
        "hooks": [
          {
            "type": "command",
            "command": "your_command",
            "timeout": 30
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "another_pattern",
        "hooks": [
          {
            "type": "command",
            "command": "cleanup_command"
          }
        ]
      }
    ],
    "SetUpEnvironment": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python ~/.iflow/hooks/env_enhancer.py",
            "timeout": 30
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "echo 'Session ended'"
          }
        ]
      }
    ],
    "SubagentStop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "cleanup_subagent.sh"
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "matcher": "startup",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'Session initialized'"
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python ~/.iflow/hooks/session_summary.py"
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "matcher": ".*sensitive.*",
        "hooks": [
          {
            "type": "command",
            "command": "python ~/.iflow/hooks/content_filter.py"
          }
        ]
      }
    ],
    "Notification": [
      {
        "matcher": ".*permission.*",
        "hooks": [
          {
            "type": "command",
            "command": "logger 'iFlow permission request'"
          }
        ]
      }
    ]
  }
}

3. Hook Configuration Field Description
Each Hook type contains a configuration array, with each configuration item including:

Common Fields
hooks (required): Hook command array, each command includes:
type: Command type, currently only supports "command"
command: Command string to execute
timeout: Timeout in seconds, optional, no timeout by default
Tool-related Hook (PreToolUse/PostToolUse) Specific Fields
matcher: Tool matching pattern, used to specify which tools should trigger the Hook
Matching Patterns
Matching Pattern	Syntax Example	Description
Wildcard Match	"*" or ""	Match all tools (default behavior)
Exact Match	"Edit"	Only match tools or aliases named "Edit"
Regular Expression	`"Edit\	MultiEdit\
Pattern Match	".*_file"	Match tool names ending with "_file"
MCP Tool Match	"mcp__.*"	Match all MCP tools
MCP Server Match	"mcp__github__.*"	Match all tools from a specific MCP server
Matching Rules
Case Sensitive: matcher matching is case-sensitive
Regular Expression: Automatically recognized as regex when containing |\\^$.*+?()[]{} characters
Tool Aliases: Both tool names and aliases are checked during matching
Error Handling: Invalid regex patterns fall back to exact match mode
Hook Type and matcher Support
Hook Type	Supports matcher	Description
PreToolUse	✅	Can specify matching specific tools
PostToolUse	✅	Can specify matching specific tools
SetUpEnvironment	❌	Always executes, doesn't support matcher
Stop	❌	Always executes, doesn't support matcher
SubagentStop	❌	Always executes, doesn't support matcher
SessionStart	✅	Can match based on session start source (startup, resume, clear, compress)
SessionEnd	❌	Always executes, doesn't support matcher
UserPromptSubmit	✅	Can match based on user prompt content
Notification	✅	Can match based on notification message content
Common Tool Name Reference
Tool Category	Actual Tool Name	Common Aliases
File Editing	replace	Edit, edit, Write, write
Batch Editing	multi_edit	MultiEdit, multiEdit
File Writing	write_file	write, create, save
File Reading	read_file	read
Shell Execution	run_shell_command	shell, Shell, bash, Bash
File Search	search_file_content	grep, search
Directory List	list_directory	ls, list
Special Constraints
SetUpEnvironment Hook: Does not support matcher field, applies to all sessions
Stop/SubagentStop/SessionEnd Hook: Does not support matcher field, executes at the end of corresponding lifecycle
UserPromptSubmit Hook: Can block prompt submission by returning non-zero exit code
Notification Hook: Exit code 2 has special meaning - doesn't block notification display, only shows stderr content to user
Complex Configuration Examples
1. File Protection Hook
Python Script (file_protection.py):

import json, sys
data = json.load(sys.stdin)
file_path = data.get('tool_input', {}).get('file_path', '')
sensitive_files = ['.env', 'package-lock.json', '.git/']
sys.exit(2 if any(p in file_path for p in sensitive_files) else 0)

Feature Description: Perform security checks before file editing operations to block modifications to sensitive files.

Prerequisites:

System needs python3 installed
Ensure Python can execute normally and access standard input
Specific Functions:

Monitor all file editing operations (Edit, MultiEdit, Write tools)
Check if target file path contains sensitive files (.env, package-lock.json, .git/ directory)
If sensitive files are detected, return exit code 2 to block tool execution
Provide security protection for file operations, avoiding accidental modification of important configuration files
Hook Configuration:

{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|MultiEdit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "python3 file_protection.py",
            "timeout": 10
          }
        ]
      }
    ]
  }
}

2. TypeScript Code Formatting
Feature Description: Automatically format TypeScript files after file editing operations to ensure code style consistency.

Prerequisites:

System needs jq tool installed (for JSON data processing)
Need prettier code formatter installed (npm install -g prettier or local project installation)
Ensure project has prettier configuration file or uses default configuration
Specific Functions:

Monitor file editing and writing operations (Edit, MultiEdit, write_file tools)
Extract file path information from tool parameters
Check if file is a TypeScript file (.ts extension)
Automatically execute prettier formatting on qualifying files
Improve code quality and team collaboration efficiency
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|MultiEdit|Write",
        "hooks": [
          {
            "type": "command", 
            "command": "bash -c 'path=$(jq -r \".tool_input.file_path\"); [[ $path == *.ts ]] && npx prettier --write \"$path\"'",
            "timeout": 30
          }
        ]
      }
    ]
  }
}


3. Session Management and Performance Monitoring
Python Script (session_summary.py):

import os, datetime, subprocess
session_id = os.environ.get('IFLOW_SESSION_ID', 'unknown')
timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
summary_dir = os.path.expanduser('~/.iflow/session-summaries')
os.makedirs(summary_dir, exist_ok=True)
try:
    git_log = subprocess.check_output(['git', 'log', '--oneline', '-3']).decode().strip()
except:
    git_log = 'No git repository'
summary_content = f'# Session Summary\\n\\n**ID:** {session_id}\\n**Time:** {timestamp}\\n\\n**Git Log:**\\n```\\n{git_log}\\n```'
with open(f'{summary_dir}/session-{session_id}.md', 'w') as f:
    f.write(summary_content)


Feature Description: Automatically generate session summaries when sessions end, record performance metrics when subagents end, implementing complete session lifecycle management.

Prerequisites:

System needs python3 installed
Need git command (for getting repository activity information)
Ensure sufficient disk space for storing session summaries and performance data
Specific Functions:

Session Summary Generation: Generate Markdown summary files containing session ID, end time, working directory, and recent Git activity when main session ends
Performance Metrics Collection: Record subagent runtime, type, success status and other performance data to JSONL format files
Automatic Directory Creation: Automatically create ~/.iflow/session-summaries and ~/.iflow/metrics directories
Environment Variable Support: Utilize environment variables like IFLOW_SESSION_ID, IFLOW_AGENT_TYPE, IFLOW_SUBAGENT_START_TIME
Error Tolerance: Provide default values when Git commands fail, ensuring summary generation is not interrupted
Hook Configuration:

{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 session_summary.py",
            "timeout": 15
          }
        ]
      }
    ]
  }
}

4. User Input Content Filtering
Python Script (content_filter.py):

import json, sys, re
data = json.load(sys.stdin)
prompt = data.get('prompt', '')
# Check for sensitive information
sensitive_patterns = [
    r'password\s*[=:]\s*\S+',
    r'api[_-]?key\s*[=:]\s*\S+',
    r'secret\s*[=:]\s*\S+',
    r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'  # Credit card numbers
]
for pattern in sensitive_patterns:
    if re.search(pattern, prompt, re.IGNORECASE):
        print(f"Sensitive information detected, please remove and resubmit", file=sys.stderr)
        sys.exit(1)  # Block prompt submission
print("Content review passed")

Feature Description: Filter content before user submits prompts, detect and block input containing sensitive information.

Prerequisites:

System needs python3 installed
Ensure Python's regex module is available
Specific Functions:

Monitor all user submitted prompt content
Use regex to detect passwords, API keys, credit card numbers and other sensitive information
If sensitive content is detected, return exit code 1 to block prompt submission
Provide clear error messages to guide user input modification
Protect user privacy and data security
Hook Configuration:

{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 content_filter.py",
            "timeout": 5
          }
        ]
      }
    ]
  }
}

5. Notification Handling and Integration
Bash Script (notification_handler.sh):

#!/bin/bash
# Read notification information from stdin
notification_data=$(cat)
message=$(echo "$notification_data" | jq -r '.message // "Unknown message"')
timestamp=$(date '+%Y-%m-%d %H:%M:%S')

# Log to file
echo "[$timestamp] iFlow Notification: $message" >> ~/.iflow/notifications.log

# If permission request, send to Slack
if [[ "$message" == *"permission"* ]]; then
    curl -X POST -H 'Content-type: application/json' \
         --data "{\"text\":\"iFlow Permission Request: $message\"}" \
         "$SLACK_WEBHOOK_URL" 2>/dev/null || true
fi

# If error notification, send email alert
if [[ "$message" == *"error"* ]] || [[ "$message" == *"failed"* ]]; then
    echo "iFlow Error: $message" | mail -s "iFlow Alert" admin@company.com 2>/dev/null || true
fi

Feature Description: Handle iFlow notification messages, implement logging and third-party system integration.

Prerequisites:

System needs jq, curl, mail commands installed
Configure SLACK_WEBHOOK_URL environment variable
Configure mail system
Specific Functions:

Capture all iFlow notification messages
Record notifications to local log files
Automatically send permission request notifications to Slack channels
Send email alerts for error notifications
Support multiple notification channel integration
Hook Configuration:

{
  "hooks": {
    "Notification": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/.iflow/hooks/notification_handler.sh",
            "timeout": 10
          }
        ]
      }
    ]
  }
}

6. Git Status Environment Enhancer
Python Script (git_status.py):

import subprocess, os
try:
    branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).decode().strip()
    status = subprocess.check_output(['git', 'status', '--porcelain']).decode().strip()
    commit = subprocess.check_output(['git', 'log', '-1', '--oneline']).decode().strip()
    print(f'## Git Information\\n\\n**Branch:** {branch}\\n**Status:** {"Clean" if not status else "Has Changes"}\\n**Latest Commit:** {commit}')
except:
    print('## Git Information\\n\\nNo Git repository found')


Feature Description: Automatically obtain and display detailed status information of the current Git repository when sessions start, providing project background context for AI.

Prerequisites:

System needs python3 installed
Need git command and a valid Git repository
Ensure current working directory is within a Git repository
Need read permissions for the repository
Specific Functions:

Branch Information Retrieval: Automatically identify and display current Git branch name
Working Directory Status: Check and display uncommitted changes in working directory (modified, added, deleted files)
Latest Commit Information: Retrieve and display brief information of the most recent commit (hash and commit message)
Formatted Output: Format Git status information into clear Markdown format for AI to understand project current state
Status Determination: Automatically determine if working directory is clean, displaying different status information accordingly
Enhanced AI Context: Help AI better understand project version control status and make more appropriate decisions
Hook Configuration:

{
  "hooks": {
    "SetUpEnvironment": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 git_status.py",
            "timeout": 10
          }
        ]
      }
    ]
  }
}

Hook Execution Mechanism
1. Execution Flow
Event Trigger: When corresponding lifecycle events occur
Match Check: Check Hook configuration matching conditions (such as tool names)
Parallel Execution: Hook commands that meet conditions execute in parallel
Result Processing: Collect execution results and output
Error Handling: Handle execution failure cases
2. Execution Environment
Hook commands execute in the following environment:

Working Directory: Current iFlow CLI working directory

Environment Variables: Inherit iFlow CLI environment variables

Common Special Variables:

IFLOW_SESSION_ID: Current session ID (all Hooks)
IFLOW_TRANSCRIPT_PATH: Session transcript file path (all Hooks)
IFLOW_CWD: Current working directory (all Hooks)
IFLOW_HOOK_EVENT_NAME: Triggered Hook event name (all Hooks)
Tool-related Hook Special Variables:

IFLOW_TOOL_NAME: Current tool name (PreToolUse/PostToolUse Hook)
IFLOW_TOOL_ARGS: Tool parameters as JSON string (PreToolUse/PostToolUse Hook)
IFLOW_TOOL_ALIASES: Tool aliases array as JSON string (PreToolUse/PostToolUse Hook)
Session-related Hook Special Variables:

IFLOW_SESSION_SOURCE: Session start source like startup, resume, clear, compress (SessionStart Hook)
User Input Hook Special Variables:

IFLOW_USER_PROMPT: User submitted original prompt content (UserPromptSubmit Hook)
Notification Hook Special Variables:

IFLOW_NOTIFICATION_MESSAGE: Notification message content (Notification Hook)
3. Return Value Processing
Blockable Execution Hooks:

PreToolUse Hook: Non-zero return code blocks tool execution, displays error message
UserPromptSubmit Hook: Non-zero return code blocks prompt submission, displays error message
Special Processing Hooks:

Notification Hook:
Return code 0: Normal processing, display standard output
Return code 2: Don't block notification display, only show stderr content to user
Other return codes: Display warning message, but don't affect notification flow
Other Hooks:

Return code doesn't affect main flow
Error output displays warning messages
Standard output is displayed to user
4. Timeout Handling
Hooks configured with timeout will terminate after specified time
Timeout won't interrupt main flow, but will log warnings
Hooks without timeout configuration use system default timeout
Advanced Features
1. Conditional Execution
Add conditional logic in Hook scripts:

#!/bin/bash
# Only execute in Git repositories
if [ -d ".git" ]; then
    echo "Executing special operations in Git repository"
    # Your logic
fi

2. Parameter Passing
Hooks can receive relevant parameters through environment variables:

import sys
import json

# Read JSON data from standard input
data = json.load(sys.stdin)

# Common fields (available for all Hooks)
session_id = data.get('session_id', '')
hook_event = data.get('hook_event_name', '')
cwd = data.get('cwd', '')

print(f"Session ID: {session_id}")
print(f"Hook Event: {hook_event}")
print(f"Working Directory: {cwd}")

# Tool-related Hook special fields
if hook_event in ['PreToolUse', 'PostToolUse']:
    tool_args = data.get('tool_input', {})
    tool_name = data.get('tool_name', '')
    print(f"Tool Name: {tool_name}")
    print(f"Tool Parameters: {tool_args}")

# User Input Hook special fields
if hook_event == 'UserPromptSubmit':
    user_prompt = data.get('user_prompt', '')  # Note: Original JSON example doesn't have this field, need to confirm actual structure
    print(f"User Prompt: {user_prompt}")

# Notification Hook special fields
if hook_event == 'Notification':
    notification_message = data.get('notification_message', '')  # Similarly, need to confirm actual field name
    print(f"Notification Message: {notification_message}")

# Session Start Hook special fields
if hook_event == 'SessionStart':
    session_source = data.get('session_source', '')  # Need to confirm if this field actually exists
    print(f"Session Start Source: {session_source}")


tool_response_result = data.get('tool_response', {}).get('result', {}).get('llmContent', '')
print(f"Model return result: {tool_response_result}")


3. Output Processing
Hook standard output is displayed to users:

#!/bin/bash
echo "INFO: Starting preprocessing"
echo "WARNING: Potential risk detected"
echo "ERROR: Operation blocked" >&2  # Error output
exit 1  # Block tool execution (PreToolUse Hook only)

4. Configuration Validation
iFlow CLI validates Hook configuration at startup:

Check JSON format correctness
Verify required fields exist
Check field types and value ranges
Validate Hook type-specific constraints
Troubleshooting
1. Hook Not Executing
Possible Causes:

Configuration file format error
Incorrect matching pattern
Hook script path error
Insufficient permissions
Troubleshooting Steps:

Check settings.json format
Verify Hook script exists and is executable
Check iFlow CLI error logs
Use simple test Hook to verify configuration
2. Hook Execution Failure
Possible Causes:

Script syntax error
Missing dependency programs
Insufficient permissions
Timeout
Troubleshooting Steps:

Manually execute Hook script for testing
Check if script dependencies are installed
Add debug output to Hook script
Adjust timeout settings
3. Performance Issues
Optimization Suggestions:

Reduce unnecessary Hooks
Optimize Hook script performance
Set reasonable timeout values
Avoid blocking operations
4. Debugging Tips
Enable Verbose Logging
export IFLOW_DEBUG=1
iflow

Create Test Hook
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "echo \"Hook triggered: $IFLOW_TOOL_NAME\""
          }
        ]
      }
    ]
  }
}

Output Debug Information
#!/bin/bash
echo "DEBUG: Hook starting execution"
echo "DEBUG: Tool name: $IFLOW_TOOL_NAME"
echo "DEBUG: Tool parameters: $IFLOW_TOOL_ARGS"
echo "DEBUG: Current directory: $(pwd)"
echo "DEBUG: Hook execution completed"

Security Considerations
1. Script Security
Input Validation: Always validate data obtained from environment variables
Path Checking: Avoid path injection attacks
Minimal Permissions: Hook scripts use minimal necessary permissions
2. Execution Environment
Sandboxing: Consider executing Hooks in restricted environments
Resource Limits: Set reasonable timeout and resource limits
Error Isolation: Hook errors should not affect main functionality
3. Configuration Security
Configuration Validation: Validate Hook configuration at startup
Path Restrictions: Limit Hook script storage paths
Permission Checking: Check configuration file and script permissions
Best Practices
1. Configuration Management
Version Control: Include project-level Hook configurations in version control
Documentation: Add clear descriptions for each Hook
Modularization: Organize related Hook logic into independent scripts
2. Script Writing
Error Handling: Add comprehensive error handling logic
Logging: Record key information about Hook execution
Performance Optimization: Avoid unnecessary repetitive operations
3. Testing and Validation
Unit Testing: Write tests for Hook scripts
Integration Testing: Test Hook integration with iFlow CLI
Regression Testing: Ensure Hook changes don't affect existing functionality
4. Monitoring and Maintenance
Execution Monitoring: Monitor Hook execution status and performance
Regular Review: Regularly review and update Hook configurations
Documentation Maintenance: Keep Hook documentation up to date
By properly configuring and using Hooks, you can significantly extend iFlow CLI functionality and implement more intelligent and automated development workflows. The Hook system provides powerful extension capabilities, allowing you to customize AI assistant behavior according to specific needs.
