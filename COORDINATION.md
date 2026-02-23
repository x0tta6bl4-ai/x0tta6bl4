# Swarm Coordination Protocol (SCP)

⛔ **STOP! BEFORE YOU EDIT ANY FILES:**

This project uses an automated locking system to prevent conflicts between multiple AI agents.

### Rule 1: Check Locks
Before proposing any code changes, check `.swarm/locks.json`.
If the file you want to edit is listed there, **YOU MUST NOT TOUCH IT**.
Wait for the lock to be released or choose a different task.

### Rule 2: Register Your Action (If you have shell access)
Run this command to lock your files:
```bash
python3 swarm.py start "Implementing Feature X" --agent "MyAgentName" --files src/file1.py src/file2.py
```

### Rule 3: Release on Completion
When you are done:
```bash
python3 swarm.py finish --agent "MyAgentName"
```

### Current Status
To see what others are doing:
```bash
python3 swarm.py status
```

---
**Failure to follow SCP will result in merge conflicts and lost work.**
