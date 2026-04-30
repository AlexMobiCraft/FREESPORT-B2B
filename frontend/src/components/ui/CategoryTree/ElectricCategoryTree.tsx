/**
 * Electric Category Tree Component
 *
 * Рекурсивный компонент дерева категорий в стиле Electric Orange
 * Портировано из стандартного каталога с Electric-стилизацией
 *
 * @see docs/4-ux-design/02-catalog/03-page-specs.md
 */

'use client';

import React, { useState } from 'react';
import { ChevronRight, ChevronDown } from 'lucide-react';
import { cn } from '@/utils/cn';

// ============================================
// Types
// ============================================

export interface CategoryNode {
  id: number;
  label: string;
  slug?: string;
  icon?: string;
  children?: CategoryNode[];
}

export interface ElectricCategoryTreeProps {
  /** Category tree nodes */
  nodes: CategoryNode[];
  /** Currently active category ID */
  activeCategoryId: number | null;
  /** Callback when a category is selected */
  onSelectCategory: (node: CategoryNode) => void;
  /** Additional class names */
  className?: string;
}

// ============================================
// Helpers
// ============================================

const getNodeKey = (path: number[]) => path.join(' > ');

// ============================================
// Tree Node Component
// ============================================

interface TreeNodeProps {
  node: CategoryNode;
  level: number;
  activeId: number | null;
  expandedKeys: Set<string>;
  onToggle: (key: string) => void;
  onSelect: (node: CategoryNode) => void;
  path: number[];
}

function TreeNode({
  node,
  level,
  activeId,
  expandedKeys,
  onToggle,
  onSelect,
  path,
}: TreeNodeProps) {
  const currentPath = [...path, node.id];
  const nodeKey = getNodeKey(currentPath);
  const isActive = node.id === activeId;
  const hasChildren = Boolean(node.children && node.children.length > 0);
  const isExpanded = expandedKeys.has(nodeKey);

  return (
    <li className="space-y-1">
      <div className="flex items-center gap-1">
        {/* Expand/Collapse Button */}
        {hasChildren ? (
          <button
            type="button"
            onClick={() => onToggle(nodeKey)}
            aria-label={isExpanded ? 'Свернуть' : 'Развернуть'}
            className={cn(
              'p-1 text-[var(--color-text-muted)] hover:text-[var(--color-primary)] transition-colors',
              isExpanded && 'text-[var(--color-primary)]'
            )}
          >
            {isExpanded ? (
              <ChevronDown className="w-4 h-4" />
            ) : (
              <ChevronRight className="w-4 h-4" />
            )}
          </button>
        ) : (
          <span className="w-6" aria-hidden="true" />
        )}

        {/* Category Button */}
        <button
          type="button"
          onClick={() => {
            onSelect(node);
            // Also toggle expansion when clicking on name
            if (hasChildren) {
              onToggle(nodeKey);
            }
          }}
          className={cn(
            'flex-1 text-left py-1 px-2 text-sm transition-all duration-200',
            isActive
              ? 'text-[var(--color-primary)] font-bold border-l-2 border-[var(--color-primary)] -ml-[2px] pl-[10px]'
              : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:pl-3'
          )}
        >
          <span className="flex items-center gap-2">
            {node.icon && <span>{node.icon}</span>}
            <span>{node.label}</span>
          </span>
        </button>
      </div>

      {/* Children */}
      {hasChildren && isExpanded && (
        <ul className="pl-4 space-y-1 border-l border-[var(--border-default)] ml-3">
          {node.children!.map(child => (
            <TreeNode
              key={child.id}
              node={child}
              level={level + 1}
              activeId={activeId}
              expandedKeys={expandedKeys}
              onToggle={onToggle}
              onSelect={onSelect}
              path={currentPath}
            />
          ))}
        </ul>
      )}
    </li>
  );
}

// ============================================
// Main Component
// ============================================

export function ElectricCategoryTree({
  nodes,
  activeCategoryId,
  onSelectCategory,
  className,
}: ElectricCategoryTreeProps) {
  const [expandedKeys, setExpandedKeys] = useState<Set<string>>(new Set());

  // Categories are collapsed by default
  // User must manually expand categories by clicking the chevron

  const handleToggle = (key: string) => {
    setExpandedKeys(prev => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  if (nodes.length === 0) {
    return null;
  }

  return (
    <nav className={cn('space-y-2', className)} aria-label="Категории">
      <ul className="space-y-1">
        {nodes.map(node => (
          <TreeNode
            key={node.id}
            node={node}
            level={0}
            activeId={activeCategoryId}
            expandedKeys={expandedKeys}
            onToggle={handleToggle}
            onSelect={onSelectCategory}
            path={[]}
          />
        ))}
      </ul>
    </nav>
  );
}

ElectricCategoryTree.displayName = 'ElectricCategoryTree';

export default ElectricCategoryTree;
