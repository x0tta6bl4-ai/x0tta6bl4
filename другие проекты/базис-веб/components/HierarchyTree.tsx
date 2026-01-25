/**
 * HierarchyTree Component
 * Отображение иерархии компонентов и сборок (Phase 3)
 */

import React, { useState, useMemo } from 'react';
import { Assembly, Component, ComponentType } from '../types/CADTypes';
import { HierarchyManager, HierarchyNode } from '../services/HierarchyManager';

interface HierarchyTreeProps {
  assembly: Assembly | null;
  onComponentSelect?: (component: Component) => void;
  onComponentDelete?: (componentId: string) => void;
  onComponentAdd?: () => void;
}

interface TreeNodeProps {
  node: HierarchyNode;
  onSelect?: (component: Component) => void;
  onDelete?: (id: string) => void;
}

/**
 * Узел дерева иерархии
 */
const TreeNode: React.FC<TreeNodeProps> = ({ node, onSelect, onDelete }) => {
  const [expanded, setExpanded] = useState(true);
  const hasChildren = node.children.length > 0;
  const isLeaf = !hasChildren;
  
  const getTypeIcon = (type: ComponentType) => {
    switch (type) {
      case ComponentType.PART:
        return '🔷';
      case ComponentType.ASSEMBLY:
        return '📦';
      case ComponentType.SUBASSEMBLY:
        return '📌';
      default:
        return '•';
    }
  };

  return (
    <div className="tree-node">
      <div className="tree-item">
        {hasChildren && (
          <button 
            className="expand-btn"
            onClick={() => setExpanded(!expanded)}
            title={expanded ? 'Collapse' : 'Expand'}
          >
            {expanded ? '▼' : '▶'}
          </button>
        )}
        {isLeaf && <span className="expand-placeholder" />}
        
        <span 
          className="item-label"
          onClick={() => onSelect?.(node.component)}
          title={node.name}
        >
          {getTypeIcon(node.type)} {node.name}
        </span>
        
        {isLeaf && (
          <button 
            className="delete-btn"
            onClick={() => onDelete?.(node.id)}
            title="Delete component"
          >
            ✕
          </button>
        )}
      </div>
      
      {hasChildren && expanded && (
        <div className="tree-children">
          {node.children.map((child) => (
            <TreeNode
              key={child.id}
              node={child}
              onSelect={onSelect}
              onDelete={onDelete}
            />
          ))}
        </div>
      )}
    </div>
  );
};

/**
 * Компонент для отображения иерархии сборок и компонентов
 */
export const HierarchyTree: React.FC<HierarchyTreeProps> = ({
  assembly,
  onComponentSelect,
  onComponentDelete,
  onComponentAdd
}) => {
  const [searchTerm, setSearchTerm] = useState('');

  const hierarchyTree = useMemo(() => {
    if (!assembly) return [];
    return HierarchyManager.buildHierarchyTree(assembly);
  }, [assembly]);

  const summary = useMemo(() => {
    if (!assembly) return null;
    return HierarchyManager.getHierarchySummary(assembly);
  }, [assembly]);

  const filteredTree = useMemo(() => {
    if (!searchTerm || !assembly) return hierarchyTree;

    const filterNodes = (nodes: HierarchyNode[]): HierarchyNode[] => {
      return nodes
        .filter(node => {
          const matches = node.name.toLowerCase().includes(searchTerm.toLowerCase());
          const childMatches = filterNodes(node.children);
          return matches || childMatches.length > 0;
        })
        .map(node => ({
          ...node,
          children: filterNodes(node.children)
        }));
    };

    return filterNodes(hierarchyTree);
  }, [hierarchyTree, searchTerm]);

  if (!assembly) {
    return (
      <div className="hierarchy-tree empty">
        <p>No active assembly</p>
      </div>
    );
  }

  return (
    <div className="hierarchy-tree">
      <div className="tree-header">
        <h3>Component Hierarchy</h3>
        {onComponentAdd && (
          <button onClick={onComponentAdd} className="add-btn">
            + Add Component
          </button>
        )}
      </div>

      {summary && (
        <div className="tree-summary">
          <div className="summary-item">
            <span className="label">Total:</span>
            <span className="value">{summary.totalComponents}</span>
          </div>
          <div className="summary-item">
            <span className="label">Depth:</span>
            <span className="value">{summary.hierarchyDepth}</span>
          </div>
          <div className="summary-item">
            <span className="label">Parts:</span>
            <span className="value">{summary.componentTypes[ComponentType.PART]}</span>
          </div>
          <div className="summary-item">
            <span className="label">Assemblies:</span>
            <span className="value">{summary.componentTypes[ComponentType.ASSEMBLY]}</span>
          </div>
          <div className="summary-item">
            <span className="label">Materials:</span>
            <span className="value">{summary.uniqueMaterials}</span>
          </div>
        </div>
      )}
      
      <div className="tree-search">
        <input
          type="text"
          placeholder="Search components..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="search-input"
        />
        {searchTerm && (
          <button 
            className="clear-btn"
            onClick={() => setSearchTerm('')}
            title="Clear search"
          >
            ✕
          </button>
        )}
      </div>
      
      <div className="tree-content">
        {filteredTree.length === 0 ? (
          <p className="no-results">No components found</p>
        ) : (
          filteredTree.map((node) => (
            <TreeNode
              key={node.id}
              node={node}
              onSelect={onComponentSelect}
              onDelete={onComponentDelete}
            />
          ))
        )}
      </div>
      
      <style>{`
        .hierarchy-tree {
          border: 1px solid #ddd;
          border-radius: 4px;
          padding: 10px;
          background: white;
          display: flex;
          flex-direction: column;
          height: 100%;
        }
        .hierarchy-tree.empty {
          text-align: center;
          color: #999;
          justify-content: center;
          padding: 20px;
        }
        .tree-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 8px;
          border-bottom: 1px solid #eee;
          padding-bottom: 8px;
        }
        .tree-header h3 {
          margin: 0;
          font-size: 14px;
          font-weight: 600;
        }
        .add-btn {
          background: #4CAF50;
          color: white;
          border: none;
          padding: 4px 8px;
          border-radius: 3px;
          cursor: pointer;
          font-size: 11px;
        }
        .add-btn:hover {
          background: #45a049;
        }
        .tree-summary {
          display: flex;
          gap: 8px;
          margin-bottom: 8px;
          padding: 6px;
          background: #f5f5f5;
          border-radius: 3px;
          font-size: 11px;
          flex-wrap: wrap;
        }
        .summary-item {
          display: flex;
          gap: 4px;
          align-items: center;
        }
        .summary-item .label {
          font-weight: 600;
          color: #666;
        }
        .summary-item .value {
          background: #fff;
          padding: 2px 4px;
          border-radius: 2px;
          font-weight: 600;
          color: #333;
        }
        .tree-search {
          position: relative;
          margin-bottom: 8px;
        }
        .search-input {
          width: 100%;
          padding: 6px;
          font-size: 12px;
          border: 1px solid #ddd;
          border-radius: 3px;
          box-sizing: border-box;
        }
        .search-input::placeholder {
          color: #aaa;
        }
        .clear-btn {
          position: absolute;
          right: 4px;
          top: 50%;
          transform: translateY(-50%);
          background: none;
          border: none;
          color: #999;
          cursor: pointer;
          font-size: 14px;
        }
        .clear-btn:hover {
          color: #333;
        }
        .tree-content {
          flex: 1;
          overflow-y: auto;
          border: 1px solid #eee;
          border-radius: 3px;
          padding: 4px;
          background: #fafafa;
        }
        .no-results {
          text-align: center;
          color: #999;
          font-size: 12px;
          padding: 20px;
        }
        .tree-node {
          margin: 2px 0;
        }
        .tree-item {
          display: flex;
          align-items: center;
          padding: 4px;
          border-radius: 3px;
          font-size: 12px;
          cursor: default;
        }
        .tree-item:hover {
          background: #e8f5e9;
        }
        .expand-btn {
          background: none;
          border: none;
          cursor: pointer;
          padding: 0 2px;
          font-size: 10px;
          width: 16px;
          color: #666;
        }
        .expand-btn:hover {
          color: #333;
        }
        .expand-placeholder {
          display: inline-block;
          width: 16px;
        }
        .item-label {
          flex: 1;
          margin: 0 4px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          user-select: none;
        }
        .delete-btn {
          background: #ff6b6b;
          color: white;
          border: none;
          padding: 2px 4px;
          border-radius: 2px;
          cursor: pointer;
          font-size: 10px;
        }
        .delete-btn:hover {
          background: #ff5252;
        }
        .tree-children {
          padding-left: 12px;
        }
      `}</style>
    </div>
  );
};
