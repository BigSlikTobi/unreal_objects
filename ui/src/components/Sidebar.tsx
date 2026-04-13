import React, { useState, useRef, useEffect } from 'react';
import {
  Plus,
  Settings,
  ListTodo,
  Sun,
  Moon,
  Check,
  X,
  AlertTriangle,
  ShieldCheck,
  Layers,
  ScrollText,
  Trash2,
  LayoutDashboard,
} from 'lucide-react';
import type { RuleGroup } from '../types';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
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
  onOpenDashboard: () => void;
  llmConfigured: boolean;
  activeView?: string;
}

export const Sidebar: React.FC<SidebarProps> = ({
  isOpen,
  onClose,
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
  onOpenDashboard,
  llmConfigured,
  activeView,
}) => {
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [groupPendingDelete, setGroupPendingDelete] = useState<RuleGroup | null>(null);
  const [deleteConfirmation, setDeleteConfirmation] = useState('');
  const [adminToken, setAdminToken] = useState(
    () => sessionStorage.getItem('rule_engine_admin_token') || '',
  );
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const nameInputRef = useRef<HTMLInputElement>(null);
  const deleteConfirmInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (showForm) nameInputRef.current?.focus();
  }, [showForm]);

  useEffect(() => {
    if (groupPendingDelete) deleteConfirmInputRef.current?.focus();
  }, [groupPendingDelete]);

  // Close on Escape key
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isOpen, onClose]);

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

  const footerBtnBase =
    'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-colors text-sm font-medium';
  const footerBtnIdle =
    'text-gray-600 dark:text-gray-400 hover:bg-white/60 dark:hover:bg-white/5';
  const footerBtnActive =
    'bg-blue-50/80 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300';

  return (
    <>
      {/* Backdrop */}
      <div
        className={`fixed inset-0 z-40 bg-black/30 backdrop-blur-sm transition-opacity duration-300 ${
          isOpen ? 'opacity-100' : 'pointer-events-none opacity-0'
        }`}
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Panel */}
      <div
        className={`fixed bottom-0 left-0 top-14 z-50 flex w-full flex-col border-r border-white/20 bg-white/85 shadow-2xl backdrop-blur-xl transition-transform duration-300 ease-out dark:border-white/10 dark:bg-gray-950/88 sm:w-80 ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
        aria-modal={isOpen}
        aria-hidden={!isOpen}
        inert={!isOpen ? true : undefined}
        role="dialog"
      >
        {/* New Group Button or Inline Form */}
        <div className="sticky top-0 z-10 border-b border-white/30 bg-white/60 p-4 backdrop-blur-sm dark:border-white/10 dark:bg-gray-950/60">
          {!showForm ? (
            <button
              onClick={() => setShowForm(true)}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 font-medium text-white transition-colors hover:bg-blue-700"
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
                className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder-gray-400 outline-none focus:border-transparent focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
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
                className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder-gray-400 outline-none focus:border-transparent focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
              />
              <div className="flex gap-2">
                <button
                  onClick={handleCreate}
                  disabled={!name.trim() || isSubmitting}
                  className="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
                >
                  <Check size={14} />
                  {isSubmitting ? 'Creating…' : 'Create'}
                </button>
                <button
                  onClick={handleCancel}
                  className="rounded-lg p-1.5 text-gray-500 transition-colors hover:bg-gray-200 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-gray-700 dark:hover:text-gray-200"
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
            <div className="pb-2 text-xs font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
              Rule Groups
            </div>
          )}

          {groups.map((group) => (
            <div key={group.id} className="space-y-2">
              <div
                className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left transition-colors ${
                  selectedGroupId === group.id
                    ? 'bg-blue-50/80 text-blue-700 dark:bg-blue-900/20 dark:text-blue-300'
                    : 'text-gray-600 hover:bg-white/60 dark:text-gray-400 dark:hover:bg-white/5'
                }`}
              >
                <button
                  onClick={() => {
                    onSelectGroup(group.id);
                    onClose();
                  }}
                  className="flex min-w-0 flex-1 items-center gap-3 text-left"
                >
                  <ListTodo size={16} className="flex-shrink-0" />
                  <div className="flex-1 overflow-hidden">
                    <div className="truncate text-sm font-medium">{group.name}</div>
                    {group.description && (
                      <div className="truncate text-xs opacity-60">{group.description}</div>
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
                  <div className="font-semibold text-red-800 dark:text-red-200">
                    Destroy rule group
                  </div>
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
                      {isDeleting ? 'Destroying…' : 'Destroy Group'}
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
        <div className="border-t border-white/30 bg-white/60 p-4 backdrop-blur-sm dark:border-white/10 dark:bg-gray-950/60 space-y-0.5">
          <button
            onClick={() => { onOpenDashboard(); onClose(); }}
            className={`${footerBtnBase} ${activeView === 'dashboard' ? footerBtnActive : footerBtnIdle}`}
          >
            <LayoutDashboard size={16} />
            Dashboard
          </button>
          <button
            onClick={() => { onOpenAgentAdmin(); onClose(); }}
            className={`${footerBtnBase} ${activeView === 'agent-admin' ? footerBtnActive : footerBtnIdle}`}
          >
            <ShieldCheck size={16} />
            Agent Admin
          </button>
          {onOpenSchemaWorkshop && (
            <button
              onClick={() => { onOpenSchemaWorkshop(); onClose(); }}
              className={`${footerBtnBase} ${activeView === 'schema-workshop' ? footerBtnActive : footerBtnIdle}`}
            >
              <Layers size={16} />
              Schema Workshop
            </button>
          )}
          <button
            onClick={() => { onOpenDecisionLog(); onClose(); }}
            className={`${footerBtnBase} ${activeView === 'decision-log' ? footerBtnActive : footerBtnIdle}`}
          >
            <ScrollText size={16} />
            Decision Log
          </button>
          <button
            onClick={() => { onOpenSettings(); onClose(); }}
            className={`${footerBtnBase} ${
              !llmConfigured
                ? 'text-amber-600 hover:bg-amber-50/60 dark:text-amber-400 dark:hover:bg-amber-900/10'
                : footerBtnIdle
            }`}
          >
            {llmConfigured ? <Settings size={16} /> : <AlertTriangle size={16} />}
            {llmConfigured ? 'LLM Settings' : 'Configure LLM'}
          </button>
          <button
            onClick={toggleDarkMode}
            className={`${footerBtnBase} ${footerBtnIdle}`}
          >
            {isDarkMode ? <Sun size={16} /> : <Moon size={16} />}
            {isDarkMode ? 'Light Mode' : 'Dark Mode'}
          </button>
        </div>
      </div>
    </>
  );
};
