import sys
import os
from pathlib import Path

# Add the current directory to sys.path
current_dir = Path(__file__).parent.resolve()
sys.path.append(str(current_dir))

# Add src to sys.path
src_dir = current_dir / "src"
sys.path.append(str(src_dir))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.core.app:app", host="0.0.0.0", port=8120, reload=False)
