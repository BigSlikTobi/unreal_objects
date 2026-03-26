import React, { useState, useRef, useEffect } from 'react';
import { Plus, Settings, ListTodo, Sun, Moon, Check, X, AlertTriangle, ShieldCheck, Layers, ScrollText, Trash2 } from 'lucide-react';
import type { RuleGroup } from '../types';

interface SidebarProps {
  groups: RuleGroup[];
  selectedGroupId: string | null;
  onSelectGroup: (id: string) => void;
  onCreateGroup: (name: string, description: string) => Promise<void>;
  onDeleteGroup: (group: RuleGroup, adminToken?: string) => Promise<void>;
  isDarkMode: boolean;
  toggleDarkMode: () => void;
  onOpenSettings: () => void;
  onOpenAgentAdmin: () => void;
  onOpenSchemaWorkshop?: () => void;
  onOpenDecisionLog: () => void;
  llmConfigured: boolean;
  className?: string;
}

export const Sidebar: React.FC<SidebarProps> = ({
  groups,
  selectedGroupId,
  onSelectGroup,
  onCreateGroup,
  onDeleteGroup,
  isDarkMode,
  toggleDarkMode,
  onOpenSettings,
  onOpenAgentAdmin,
  onOpenSchemaWorkshop,
  onOpenDecisionLog,
  llmConfigured,
  className = '',
}) => {
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [groupPendingDelete, setGroupPendingDelete] = useState<RuleGroup | null>(null);
  const [deleteConfirmation, setDeleteConfirmation] = useState('');
  const [adminToken, setAdminToken] = useState(() => sessionStorage.getItem('rule_engine_admin_token') || '');
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const nameInputRef = useRef<HTMLInputElement>(null);
  const deleteConfirmInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (showForm) {
      nameInputRef.current?.focus();
    }
  }, [showForm]);

  useEffect(() => {
    if (groupPendingDelete) {
      deleteConfirmInputRef.current?.focus();
    }
  }, [groupPendingDelete]);

  const handleCreate = async () => {
    if (!name.trim() || isSubmitting) return;
    setIsSubmitting(true);
    try {
      await onCreateGroup(name.trim(), description.trim());
      setName('');
      setDescription('');
      setShowForm(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancel = () => {
    setName('');
    setDescription('');
    setShowForm(false);
  };

  const openDeleteFlow = (group: RuleGroup) => {
    setGroupPendingDelete(group);
    setDeleteConfirmation('');
    setDeleteError(null);
  };

  const handleDeleteGroup = async () => {
    if (!groupPendingDelete || isDeleting) return;
    if (deleteConfirmation.trim() !== groupPendingDelete.name) {
      setDeleteError('Type the exact group name to destroy it.');
      return;
    }
    setIsDeleting(true);
    setDeleteError(null);
    try {
      sessionStorage.setItem('rule_engine_admin_token', adminToken);
      await onDeleteGroup(groupPendingDelete, adminToken);
      setGroupPendingDelete(null);
      setDeleteConfirmation('');
    } catch (error) {
      setDeleteError(error instanceof Error ? error.message : 'Failed to delete rule group');
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className={`h-full w-full bg-gray-50 dark:bg-gray-900 border-r border-gray-200 dark:border-gray-800 flex flex-col transition-colors duration-200 ${className}`}>

      {/* New Group Button or Inline Form */}
      <div className="sticky top-0 z-10 p-4 border-b border-gray-200 dark:border-gray-800 bg-gray-50/95 dark:bg-gray-900/95 backdrop-blur">
        {!showForm ? (
          <button
            onClick={() => setShowForm(true)}
            className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-medium transition-colors"
          >
            <Plus size={18} />
            New Rule Group
          </button>
        ) : (
          <div className="space-y-2">
            <input
              ref={nameInputRef}
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleCreate();
                if (e.key === 'Escape') handleCancel();
              }}
              placeholder="Group name *"
              className="w-full bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
            />
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleCreate();
                if (e.key === 'Escape') handleCancel();
              }}
              placeholder="Description (optional)"
              className="w-full bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
            />
            <div className="flex gap-2">
              <button
                onClick={handleCreate}
                disabled={!name.trim() || isSubmitting}
                className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
              >
                <Check size={14} />
                {isSubmitting ? 'Creating...' : 'Create'}
              </button>
              <button
                onClick={handleCancel}
                className="p-1.5 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors"
              >
                <X size={16} />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Groups List */}
      <div className="flex-1 overflow-y-auto p-4 space-y-1">
        {groups.length > 0 && (
          <div className="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider pb-2">
            Rule Groups
          </div>
        )}

        {groups.map((group) => (
          <div key={group.id} className="space-y-2">
            <div
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-colors ${
                selectedGroupId === group.id
                  ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300'
                  : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800/50'
              }`}
            >
              <button
                onClick={() => onSelectGroup(group.id)}
                className="flex min-w-0 flex-1 items-center gap-3 text-left"
              >
                <ListTodo size={16} className="flex-shrink-0" />
                <div className="flex-1 overflow-hidden">
                  <div className="truncate text-sm font-medium">{group.name}</div>
                  {group.description && (
                    <div className="text-xs truncate opacity-60">{group.description}</div>
                  )}
                </div>
              </button>
              <button
                type="button"
                aria-label="Destroy rule group"
                onClick={() => openDeleteFlow(group)}
                className="rounded-md p-1.5 text-gray-400 transition-colors hover:bg-red-100 hover:text-red-600 dark:hover:bg-red-900/30 dark:hover:text-red-300"
              >
                <Trash2 size={15} />
              </button>
            </div>

            {groupPendingDelete?.id === group.id && (
              <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm dark:border-red-900/40 dark:bg-red-950/20">
                <div className="font-semibold text-red-800 dark:text-red-200">Destroy rule group</div>
                <p className="mt-1 text-xs text-red-700 dark:text-red-300">
                  This permanently removes the group and every rule inside it.
                </p>
                <p className="mt-2 text-xs text-red-700 dark:text-red-300">
                  Type <span className="font-semibold">{group.name}</span> to confirm.
                </p>
                <input
                  ref={deleteConfirmInputRef}
                  type="text"
                  value={deleteConfirmation}
                  onChange={(e) => setDeleteConfirmation(e.target.value)}
                  placeholder="Exact group name"
                  className="mt-3 w-full rounded-lg border border-red-200 bg-white px-3 py-2 text-sm text-gray-900 outline-none focus:ring-2 focus:ring-red-500 dark:border-red-900/40 dark:bg-gray-900 dark:text-gray-100"
                />
                <input
                  type="password"
                  value={adminToken}
                  onChange={(e) => setAdminToken(e.target.value)}
                  placeholder="Admin token (only if server requires it)"
                  className="mt-2 w-full rounded-lg border border-red-200 bg-white px-3 py-2 text-sm text-gray-900 outline-none focus:ring-2 focus:ring-red-500 dark:border-red-900/40 dark:bg-gray-900 dark:text-gray-100"
                />
                {deleteError && (
                  <div className="mt-2 text-xs font-medium text-red-700 dark:text-red-300">
                    {deleteError}
                  </div>
                )}
                <div className="mt-3 flex gap-2">
                  <button
                    type="button"
                    onClick={handleDeleteGroup}
                    disabled={isDeleting}
                    className="flex-1 rounded-lg bg-red-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-red-700 disabled:opacity-50"
                  >
                    {isDeleting ? 'Destroying...' : 'Destroy Group'}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setGroupPendingDelete(null);
                      setDeleteConfirmation('');
                      setDeleteError(null);
                    }}
                    className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-100 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Footer */}
      <div className="sticky bottom-0 p-4 border-t border-gray-200 dark:border-gray-800 space-y-1 bg-gray-50/95 dark:bg-gray-900/95 backdrop-blur">
        <button
          onClick={onOpenAgentAdmin}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
        >
          <ShieldCheck size={16} />
          <span className="text-sm font-medium">Agent Admin</span>
        </button>
        {onOpenSchemaWorkshop && (
          <button
            onClick={onOpenSchemaWorkshop}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
          >
            <Layers size={16} />
            <span className="text-sm font-medium">Schema Workshop</span>
          </button>
        )}
        <button
          onClick={onOpenDecisionLog}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
        >
          <ScrollText size={16} />
          <span className="text-sm font-medium">Decision Log</span>
        </button>
        <button
          onClick={onOpenSettings}
          className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-colors ${
            llmConfigured
              ? 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'
              : 'text-amber-600 dark:text-amber-400 hover:bg-amber-50 dark:hover:bg-amber-900/20'
          }`}
        >
          {llmConfigured ? (
            <Settings size={16} />
          ) : (
            <AlertTriangle size={16} />
          )}
          <span className="text-sm font-medium">
            {llmConfigured ? 'LLM Settings' : 'Configure LLM'}
          </span>
        </button>
        <button
          onClick={toggleDarkMode}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
        >
          {isDarkMode ? <Sun size={16} /> : <Moon size={16} />}
          <span className="text-sm font-medium">{isDarkMode ? 'Light Mode' : 'Dark Mode'}</span>
        </button>
      </div>
    </div>
  );
};
