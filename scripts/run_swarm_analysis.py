#!/usr/bin/env python3
"""
Swarm Analysis of x0tta6bl4 Codebase
=====================================

Uses Kimi K2.5 Agent Swarm to analyze and learn from the codebase.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass
import time

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.swarm import (
    SwarmOrchestrator,
    SwarmConfig,
    Task,
    create_swarm
)
from src.swarm.parl.controller import PARLController

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class CodebaseStats:
    """Statistics about the codebase."""
    total_files: int = 0
    total_lines: int = 0
    python_files: int = 0
    test_files: int = 0
    modules: List[str] = None

    def __post_init__(self):
        if self.modules is None:
            self.modules = []


async def collect_codebase_files(root_path: str) -> List[Dict[str, Any]]:
    """Collect all Python files from the codebase."""
    files = []
    root = Path(root_path)

    # Directories to analyze
    src_dirs = ['src', 'tests']

    for src_dir in src_dirs:
        dir_path = root / src_dir
        if not dir_path.exists():
            continue

        for py_file in dir_path.rglob('*.py'):
            # Skip __pycache__ and other generated files
            if '__pycache__' in str(py_file):
                continue
            if '.pyc' in str(py_file):
                continue

            try:
                content = py_file.read_text(encoding='utf-8', errors='ignore')
                lines = len(content.splitlines())

                files.append({
                    'path': str(py_file.relative_to(root)),
                    'name': py_file.name,
                    'lines': lines,
                    'size': len(content),
                    'module': str(py_file.parent.relative_to(root)).replace('/', '.'),
                    'is_test': 'test' in py_file.name.lower() or 'tests' in str(py_file)
                })
            except Exception as e:
                logger.warning(f"Could not read {py_file}: {e}")

    return files


async def analyze_file_content(file_path: str) -> Dict[str, Any]:
    """Analyze a single file's content."""
    try:
        content = Path(file_path).read_text(encoding='utf-8', errors='ignore')
        lines = content.splitlines()

        # Count different types of content
        code_lines = 0
        comment_lines = 0
        docstring_lines = 0
        import_lines = 0
        class_count = 0
        function_count = 0
        async_function_count = 0

        in_docstring = False
        docstring_char = None

        for line in lines:
            stripped = line.strip()

            # Track docstrings
            if '"""' in stripped or "'''" in stripped:
                if not in_docstring:
                    in_docstring = True
                    docstring_char = '"""' if '"""' in stripped else "'''"
                    docstring_lines += 1
                    # Check if single-line docstring
                    if stripped.count(docstring_char) >= 2:
                        in_docstring = False
                else:
                    docstring_lines += 1
                    in_docstring = False
                continue

            if in_docstring:
                docstring_lines += 1
                continue

            # Count other line types
            if stripped.startswith('#'):
                comment_lines += 1
            elif stripped.startswith('import ') or stripped.startswith('from '):
                import_lines += 1
            elif stripped.startswith('class '):
                class_count += 1
                code_lines += 1
            elif stripped.startswith('async def '):
                async_function_count += 1
                code_lines += 1
            elif stripped.startswith('def '):
                function_count += 1
                code_lines += 1
            elif stripped:
                code_lines += 1

        return {
            'total_lines': len(lines),
            'code_lines': code_lines,
            'comment_lines': comment_lines,
            'docstring_lines': docstring_lines,
            'import_lines': import_lines,
            'class_count': class_count,
            'function_count': function_count,
            'async_function_count': async_function_count,
            'complexity_score': (class_count * 5 + function_count * 2 + async_function_count * 3) / max(1, code_lines) * 100
        }
    except Exception as e:
        return {'error': str(e)}


async def run_swarm_analysis():
    """Run the swarm analysis on the codebase."""
    print("\n" + "=" * 70)
    print("🐝 x0tta6bl4 Swarm Analysis")
    print("=" * 70 + "\n")

    project_root = Path(__file__).parent.parent

    # Step 1: Collect files
    print("📂 Collecting codebase files...")
    files = await collect_codebase_files(str(project_root))
    print(f"   Found {len(files)} Python files\n")

    # Step 2: Create and initialize swarm
    print("🚀 Initializing Agent Swarm...")
    config = SwarmConfig(
        name="x0tta6bl4-analyzer",
        max_agents=50,
        min_agents=10,
        max_parallel_steps=1500,
        enable_parl=True,
        enable_vision=False  # Not needed for code analysis
    )

    swarm = SwarmOrchestrator(config)
    await swarm.initialize()

    print(f"   Swarm ID: {swarm.swarm_id}")
    print(f"   Agents: {len(swarm.agents)}")
    print(f"   PARL enabled: {swarm.parl_controller is not None}\n")

    # Step 3: Create analysis tasks
    print("📋 Creating analysis tasks...")

    tasks = []
    for i, file_info in enumerate(files):
        task = Task(
            task_type="analysis",
            payload={
                "file_path": str(project_root / file_info['path']),
                "file_info": file_info,
                "task_index": i
            },
            priority=5
        )
        tasks.append(task)

    print(f"   Created {len(tasks)} tasks\n")

    # Step 4: Execute tasks with swarm
    print("⚡ Executing analysis with PARL (parallel execution)...")
    start_time = time.time()

    # Submit all tasks
    task_ids = await swarm.submit_tasks_batch(tasks)

    # Wait for completion and collect results
    await asyncio.sleep(2)  # Allow tasks to process

    execution_time = time.time() - start_time
    print(f"   Execution time: {execution_time:.2f}s")
    print(f"   Tasks processed: {len(task_ids)}\n")

    # Step 5: Analyze results
    print("📊 Analyzing results...")

    # Collect detailed analysis for each file
    analysis_results = []
    for file_info in files:
        file_path = str(project_root / file_info['path'])
        analysis = await analyze_file_content(file_path)
        analysis['file'] = file_info['path']
        analysis['module'] = file_info['module']
        analysis_results.append(analysis)

    # Calculate statistics
    stats = CodebaseStats()
    stats.total_files = len(files)
    stats.python_files = len([f for f in files if f['name'].endswith('.py')])
    stats.test_files = len([f for f in files if f['is_test']])
    stats.total_lines = sum(f['lines'] for f in files)
    stats.modules = list(set(f['module'] for f in files))

    # Aggregate analysis
    total_classes = sum(a.get('class_count', 0) for a in analysis_results)
    total_functions = sum(a.get('function_count', 0) for a in analysis_results)
    total_async_functions = sum(a.get('async_function_count', 0) for a in analysis_results)
    total_code_lines = sum(a.get('code_lines', 0) for a in analysis_results)
    total_comment_lines = sum(a.get('comment_lines', 0) for a in analysis_results)
    total_docstring_lines = sum(a.get('docstring_lines', 0) for a in analysis_results)

    # Find most complex files
    complex_files = sorted(
        [a for a in analysis_results if 'complexity_score' in a],
        key=lambda x: x.get('complexity_score', 0),
        reverse=True
    )[:10]

    # Find largest files
    largest_files = sorted(files, key=lambda x: x['lines'], reverse=True)[:10]

    # Get swarm metrics
    swarm_metrics = await swarm.get_metrics()

    # Step 6: Print results
    print("\n" + "=" * 70)
    print("📈 ANALYSIS RESULTS")
    print("=" * 70)

    print(f"\n📁 Codebase Statistics:")
    print(f"   Total Python files: {stats.python_files}")
    print(f"   Test files: {stats.test_files}")
    print(f"   Total lines: {stats.total_lines:,}")
    print(f"   Unique modules: {len(stats.modules)}")

    print(f"\n🔍 Code Analysis:")
    print(f"   Classes: {total_classes}")
    print(f"   Functions: {total_functions}")
    print(f"   Async functions: {total_async_functions}")
    print(f"   Code lines: {total_code_lines:,}")
    print(f"   Comment lines: {total_comment_lines:,}")
    print(f"   Docstring lines: {total_docstring_lines:,}")
    print(f"   Documentation ratio: {(total_comment_lines + total_docstring_lines) / max(1, total_code_lines) * 100:.1f}%")

    print(f"\n🏆 Top 10 Largest Files:")
    for i, f in enumerate(largest_files, 1):
        print(f"   {i:2}. {f['path']}: {f['lines']:,} lines")

    print(f"\n🧩 Top 10 Most Complex Files:")
    for i, f in enumerate(complex_files, 1):
        score = f.get('complexity_score', 0)
        print(f"   {i:2}. {f['file']}: {score:.1f} complexity score")

    print(f"\n🐝 Swarm Performance:")
    print(f"   Active agents: {swarm_metrics['agents']['active']}")
    print(f"   Throughput: {swarm_metrics['performance']['throughput_tps']:.2f} tasks/sec")
    print(f"   Speedup: {swarm_metrics['performance']['speedup']:.2f}x vs sequential")

    print(f"\n📦 Module Breakdown:")
    module_stats = {}
    for f in files:
        module = f['module'].split('.')[0] if '.' in f['module'] else f['module']
        if module not in module_stats:
            module_stats[module] = {'files': 0, 'lines': 0}
        module_stats[module]['files'] += 1
        module_stats[module]['lines'] += f['lines']

    for module, mstats in sorted(module_stats.items(), key=lambda x: x[1]['lines'], reverse=True)[:15]:
        print(f"   {module}: {mstats['files']} files, {mstats['lines']:,} lines")

    # Step 7: Cleanup
    print("\n🧹 Terminating swarm...")
    await swarm.terminate()

    print("\n" + "=" * 70)
    print("✅ Analysis complete!")
    print("=" * 70 + "\n")

    return {
        'stats': stats,
        'analysis': analysis_results,
        'swarm_metrics': swarm_metrics,
        'execution_time': execution_time
    }


if __name__ == "__main__":
    result = asyncio.run(run_swarm_analysis())
