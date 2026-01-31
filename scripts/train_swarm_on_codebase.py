#!/usr/bin/env python3
"""
Train Swarm on x0tta6bl4 Codebase
==================================

Uses PARL Federated Learning to train agents on code patterns.
Learns:
- Code structure patterns
- Module dependencies
- Complexity patterns
- Best practices from the codebase
"""

import asyncio
import logging
import os
import sys
import re
import time
import json
from pathlib import Path
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import hashlib

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.swarm import SwarmOrchestrator, SwarmConfig, Task
from src.federated_learning.parl_integration import (
    PARLFederatedOrchestrator,
    PARLFLConfig
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class CodePattern:
    """Represents a learned code pattern."""
    pattern_type: str
    pattern_name: str
    examples: List[str] = field(default_factory=list)
    frequency: int = 0
    files: List[str] = field(default_factory=list)


@dataclass
class TrainingData:
    """Training data extracted from codebase."""
    file_path: str
    module: str
    imports: List[str] = field(default_factory=list)
    classes: List[Dict[str, Any]] = field(default_factory=list)
    functions: List[Dict[str, Any]] = field(default_factory=list)
    patterns: List[str] = field(default_factory=list)


class CodebaseTrainer:
    """
    Trains swarm agents on codebase patterns using PARL FL.
    """

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.fl_orchestrator: PARLFederatedOrchestrator = None
        self.swarm: SwarmOrchestrator = None

        # Learned patterns
        self.patterns: Dict[str, CodePattern] = {}
        self.module_graph: Dict[str, List[str]] = defaultdict(list)
        self.class_hierarchy: Dict[str, str] = {}

        # Training state
        self.training_rounds = 0
        self.global_model: Dict[str, Any] = {
            'patterns': {},
            'imports': defaultdict(int),
            'decorators': defaultdict(int),
            'naming_conventions': defaultdict(int),
            'async_ratio': 0.0,
            'test_coverage_ratio': 0.0
        }

    async def initialize(self):
        """Initialize swarm and FL orchestrator."""
        logger.info("Initializing CodebaseTrainer...")

        # Initialize swarm
        swarm_config = SwarmConfig(
            name="codebase-trainer",
            max_agents=50,
            min_agents=10,
            enable_parl=True
        )
        self.swarm = SwarmOrchestrator(swarm_config)
        await self.swarm.initialize()
        logger.info(f"Swarm initialized: {self.swarm.swarm_id}")

        # Initialize FL orchestrator
        fl_config = PARLFLConfig(
            max_workers=50,
            max_parallel_steps=1500,
            max_nodes_per_round=100,
            aggregation_method="fedavg"
        )
        self.fl_orchestrator = PARLFederatedOrchestrator(fl_config)
        await self.fl_orchestrator.initialize()
        logger.info("FL orchestrator initialized")

    async def extract_training_data(self, file_path: Path) -> TrainingData:
        """Extract training data from a single file."""
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            rel_path = str(file_path.relative_to(self.project_root))
            module = str(file_path.parent.relative_to(self.project_root)).replace('/', '.')

            data = TrainingData(file_path=rel_path, module=module)

            # Extract imports
            import_pattern = r'^(?:from\s+([\w.]+)\s+)?import\s+(.+)$'
            for match in re.finditer(import_pattern, content, re.MULTILINE):
                if match.group(1):
                    data.imports.append(match.group(1))
                else:
                    imports = match.group(2).split(',')
                    data.imports.extend(i.strip().split()[0] for i in imports)

            # Extract classes
            class_pattern = r'class\s+(\w+)(?:\(([^)]*)\))?:'
            for match in re.finditer(class_pattern, content):
                class_name = match.group(1)
                bases = match.group(2).split(',') if match.group(2) else []
                data.classes.append({
                    'name': class_name,
                    'bases': [b.strip() for b in bases if b.strip()]
                })

            # Extract functions
            func_pattern = r'(?:async\s+)?def\s+(\w+)\s*\(([^)]*)\)'
            for match in re.finditer(func_pattern, content):
                func_name = match.group(1)
                params = match.group(2)
                is_async = 'async def' in content[max(0, match.start()-10):match.start()+10]
                data.functions.append({
                    'name': func_name,
                    'async': is_async,
                    'params': len(params.split(',')) if params.strip() else 0
                })

            # Extract patterns
            patterns = []

            # Decorator patterns
            decorator_pattern = r'@(\w+)(?:\([^)]*\))?'
            for match in re.finditer(decorator_pattern, content):
                patterns.append(f"decorator:{match.group(1)}")

            # Naming conventions
            if re.search(r'_[a-z]+[A-Z]', content):
                patterns.append("naming:mixedCase")
            if re.search(r'[a-z]+_[a-z]+', content):
                patterns.append("naming:snake_case")

            # Async patterns
            if 'async def' in content:
                patterns.append("pattern:async")
            if 'await' in content:
                patterns.append("pattern:await")
            if 'asyncio' in content:
                patterns.append("pattern:asyncio")

            # Error handling patterns
            if 'try:' in content and 'except' in content:
                patterns.append("pattern:try_except")
            if 'raise ' in content:
                patterns.append("pattern:raise")

            # Logging patterns
            if 'logger.' in content or 'logging.' in content:
                patterns.append("pattern:logging")

            # Type hints
            if ': ' in content and '->' in content:
                patterns.append("pattern:type_hints")

            # Dataclass usage
            if '@dataclass' in content:
                patterns.append("pattern:dataclass")

            # Testing patterns
            if 'pytest' in content or 'unittest' in content:
                patterns.append("pattern:testing")
            if 'mock' in content.lower() or 'Mock' in content:
                patterns.append("pattern:mocking")

            data.patterns = patterns
            return data

        except Exception as e:
            logger.error(f"Error extracting data from {file_path}: {e}")
            return TrainingData(file_path=str(file_path), module="unknown")

    async def collect_training_data(self) -> List[TrainingData]:
        """Collect training data from all source files."""
        logger.info("Collecting training data from codebase...")

        training_data = []
        src_path = self.project_root / 'src'

        if not src_path.exists():
            logger.error(f"Source directory not found: {src_path}")
            return training_data

        for py_file in src_path.rglob('*.py'):
            if '__pycache__' in str(py_file):
                continue

            data = await self.extract_training_data(py_file)
            training_data.append(data)

        logger.info(f"Collected training data from {len(training_data)} files")
        return training_data

    async def train_round(
        self,
        training_data: List[TrainingData],
        round_num: int
    ) -> Dict[str, Any]:
        """Execute one training round with PARL FL."""
        logger.info(f"Training round {round_num}...")

        # Create virtual nodes from training data batches
        batch_size = max(1, len(training_data) // 10)
        batches = [
            training_data[i:i + batch_size]
            for i in range(0, len(training_data), batch_size)
        ]

        node_ids = [f"node_{i:03d}" for i in range(len(batches))]

        # Execute FL round
        result = await self.fl_orchestrator.execute_training_round(
            node_ids=node_ids,
            training_config={
                "round": round_num,
                "batches": len(batches)
            }
        )

        # Aggregate patterns from this round
        round_patterns = defaultdict(int)
        round_imports = defaultdict(int)
        round_decorators = defaultdict(int)

        for data in training_data:
            for pattern in data.patterns:
                round_patterns[pattern] += 1
                if pattern.startswith("decorator:"):
                    round_decorators[pattern.split(":")[1]] += 1

            for imp in data.imports:
                round_imports[imp] += 1

        # Update global model
        for pattern, count in round_patterns.items():
            self.global_model['patterns'][pattern] = \
                self.global_model['patterns'].get(pattern, 0) + count

        for imp, count in round_imports.items():
            self.global_model['imports'][imp] += count

        for dec, count in round_decorators.items():
            self.global_model['decorators'][dec] += count

        # Calculate async ratio
        total_funcs = sum(len(d.functions) for d in training_data)
        async_funcs = sum(
            sum(1 for f in d.functions if f.get('async'))
            for d in training_data
        )
        if total_funcs > 0:
            self.global_model['async_ratio'] = async_funcs / total_funcs

        self.training_rounds += 1

        return {
            "round": round_num,
            "nodes": len(node_ids),
            "patterns_learned": len(round_patterns),
            "fl_result": result
        }

    async def train(self, num_rounds: int = 5) -> Dict[str, Any]:
        """Run full training loop."""
        logger.info(f"Starting training with {num_rounds} rounds...")
        start_time = time.time()

        # Collect training data
        training_data = await self.collect_training_data()

        if not training_data:
            logger.error("No training data collected!")
            return {"error": "No training data"}

        # Run training rounds
        round_results = []
        for round_num in range(1, num_rounds + 1):
            result = await self.train_round(training_data, round_num)
            round_results.append(result)
            logger.info(f"Round {round_num} complete: {result['patterns_learned']} patterns")

        training_time = time.time() - start_time

        # Generate final report
        report = self.generate_report(training_data, training_time)

        return {
            "rounds": round_results,
            "report": report,
            "training_time": training_time,
            "global_model": dict(self.global_model)
        }

    def generate_report(
        self,
        training_data: List[TrainingData],
        training_time: float
    ) -> Dict[str, Any]:
        """Generate training report."""

        # Top patterns
        top_patterns = sorted(
            self.global_model['patterns'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:20]

        # Top imports
        top_imports = sorted(
            self.global_model['imports'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:20]

        # Top decorators
        top_decorators = sorted(
            self.global_model['decorators'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]

        # Module statistics
        modules = defaultdict(lambda: {'files': 0, 'classes': 0, 'functions': 0})
        for data in training_data:
            top_module = data.module.split('.')[0]
            modules[top_module]['files'] += 1
            modules[top_module]['classes'] += len(data.classes)
            modules[top_module]['functions'] += len(data.functions)

        return {
            "training_time_seconds": training_time,
            "total_files": len(training_data),
            "total_patterns": len(self.global_model['patterns']),
            "total_rounds": self.training_rounds,
            "async_ratio": round(self.global_model['async_ratio'] * 100, 1),
            "top_patterns": top_patterns,
            "top_imports": top_imports,
            "top_decorators": top_decorators,
            "modules": dict(modules)
        }

    async def terminate(self):
        """Clean up resources."""
        if self.fl_orchestrator:
            await self.fl_orchestrator.terminate()
        if self.swarm:
            await self.swarm.terminate()


async def main():
    """Main training function."""
    print("\n" + "=" * 70)
    print("🎓 x0tta6bl4 Swarm Training")
    print("=" * 70 + "\n")

    project_root = Path(__file__).parent.parent

    trainer = CodebaseTrainer(str(project_root))

    try:
        await trainer.initialize()

        print("🏋️ Training swarm on codebase patterns...\n")
        result = await trainer.train(num_rounds=5)

        report = result['report']

        print("\n" + "=" * 70)
        print("📊 TRAINING RESULTS")
        print("=" * 70)

        print(f"\n⏱️ Training Statistics:")
        print(f"   Training time: {report['training_time_seconds']:.2f}s")
        print(f"   Files processed: {report['total_files']}")
        print(f"   Patterns learned: {report['total_patterns']}")
        print(f"   Training rounds: {report['total_rounds']}")
        print(f"   Async code ratio: {report['async_ratio']}%")

        print(f"\n📝 Top 10 Code Patterns:")
        for i, (pattern, count) in enumerate(report['top_patterns'][:10], 1):
            print(f"   {i:2}. {pattern}: {count} occurrences")

        print(f"\n📦 Top 10 Imports:")
        for i, (imp, count) in enumerate(report['top_imports'][:10], 1):
            print(f"   {i:2}. {imp}: {count} uses")

        print(f"\n🏷️ Top Decorators:")
        for i, (dec, count) in enumerate(report['top_decorators'][:10], 1):
            print(f"   {i:2}. @{dec}: {count} uses")

        print(f"\n📁 Module Breakdown:")
        sorted_modules = sorted(
            report['modules'].items(),
            key=lambda x: x[1]['files'],
            reverse=True
        )
        for module, stats in sorted_modules[:10]:
            print(f"   {module}: {stats['files']} files, {stats['classes']} classes, {stats['functions']} functions")

        # FL metrics
        fl_metrics = trainer.fl_orchestrator.get_metrics()
        print(f"\n🔄 Federated Learning Metrics:")
        print(f"   Total FL rounds: {fl_metrics['total_rounds']}")
        print(f"   Nodes trained: {fl_metrics['total_nodes_trained']}")
        print(f"   Avg round time: {fl_metrics['avg_round_time_ms']:.2f}ms")
        print(f"   PARL speedup: {fl_metrics['speedup_vs_sequential']:.2f}x")

        print("\n" + "=" * 70)
        print("✅ Training complete! Model ready.")
        print("=" * 70 + "\n")

        # Save model
        model_path = project_root / 'scripts' / 'trained_model.json'
        with open(model_path, 'w') as f:
            json.dump({
                'global_model': dict(trainer.global_model),
                'report': report
            }, f, indent=2, default=str)
        print(f"💾 Model saved to: {model_path}\n")

    finally:
        await trainer.terminate()


if __name__ == "__main__":
    asyncio.run(main())
