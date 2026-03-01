import asyncio
import json
import os
import logging
from src.ml.rag import RAGAnalyzer, Document

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Reindexer")

async def main():
    rag = RAGAnalyzer(persist_dir="./data/indexes")
    
    # 1. Load Knowledge Base
    kb_path = "data/raw/knowledge_base.json"
    if os.path.exists(kb_path):
        with open(kb_path, "r", encoding="utf-8") as f:
            kb_data = json.load(f)
        docs = [Document(id=item["id"], content=item["content"], metadata=item["metadata"]) for item in kb_data]
        await rag.index_knowledge(docs)
        logger.info(f"✅ Indexed {len(docs)} Knowledge Base docs")

    # 2. Load Incident Patterns
    inc_path = "data/raw/incident_patterns.json"
    if os.path.exists(inc_path):
        with open(inc_path, "r", encoding="utf-8") as f:
            inc_data = json.load(f)
        inc_docs = [Document(id=f"inc_{i}", content=str(item), metadata={"type": "incident"}) for i, item in enumerate(inc_data)]
        await rag.index_knowledge(inc_docs)
        logger.info(f"✅ Indexed {len(inc_docs)} incident patterns")

    # 3. Load Competitive Analysis
    comp_path = "data/raw/competitive_analysis.json"
    if os.path.exists(comp_path):
        with open(comp_path, "r", encoding="utf-8") as f:
            comp_data = json.load(f)
        comp_docs = [Document(id=item["id"], content=item["content"], metadata=item["metadata"]) for item in comp_data]
        await rag.index_knowledge(comp_docs)
        logger.info(f"✅ Indexed {len(comp_docs)} competitive points")

    # 4. Load Topology Variants
    topo_path = "data/samples/topology_variants.json"
    if os.path.exists(topo_path):
        with open(topo_path, "r", encoding="utf-8") as f:
            topo_data = json.load(f)
        topo_docs = [Document(id=f"topo_{i}", content=str(item), metadata={"type": "topology"}) for i, item in enumerate(topo_data)]
        await rag.index_knowledge(topo_docs)
        logger.info(f"✅ Indexed {len(topo_docs)} topology variants")

    # 5. Load DAO Governance
    dao_path = "data/raw/dao_governance.json"
    if os.path.exists(dao_path):
        with open(dao_path, "r", encoding="utf-8") as f:
            dao_data = json.load(f)
        dao_docs = [Document(id=f"dao_{i}", content=str(item), metadata={"type": "dao_proposal"}) for i, item in enumerate(dao_data)]
        await rag.index_knowledge(dao_docs)
        logger.info(f"✅ Indexed {len(dao_docs)} DAO proposals")

    # 6. Persist Index
    rag.save_index()
    logger.info("💾 All datasets indexed and saved to data/indexes")

if __name__ == "__main__":
    asyncio.run(main())
