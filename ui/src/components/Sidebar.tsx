import React, { useState, useRef, useEffect } from 'react';
import { Plus, Settings, ListTodo, Sun, Moon, Check, X, AlertTriangle } from 'lucide-react';

interface SidebarProps {
  groups: any[];
  selectedGroupId: string | null;
  onSelectGroup: (id: string) => void;
  onCreateGroup: (name: string, description: string) => Promise<void>;
  isDarkMode: boolean;
  toggleDarkMode: () => void;
  onOpenSettings: () => void;
  llmConfigured: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({
  groups,
  selectedGroupId,
  onSelectGroup,
  onCreateGroup,
  isDarkMode,
  toggleDarkMode,
  onOpenSettings,
  llmConfigured,
}) => {
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const nameInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (showForm) {
      nameInputRef.current?.focus();
    }
  }, [showForm]);

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

  return (
    <div className="w-64 h-full bg-gray-50 dark:bg-gray-900 border-r border-gray-200 dark:border-gray-800 flex flex-col transition-colors duration-200">

      {/* New Group Button or Inline Form */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-800">
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
          <button
            key={group.id}
            onClick={() => onSelectGroup(group.id)}
            className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-colors ${
              selectedGroupId === group.id
                ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300'
                : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800/50'
            }`}
          >
            <ListTodo size={16} className="flex-shrink-0" />
            <div className="flex-1 overflow-hidden">
              <div className="truncate text-sm font-medium">{group.name}</div>
              {group.description && (
                <div className="text-xs truncate opacity-60">{group.description}</div>
              )}
            </div>
          </button>
        ))}
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-gray-200 dark:border-gray-800 space-y-1">
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
