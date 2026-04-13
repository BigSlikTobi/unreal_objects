import { useCallback, useEffect, useRef, useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { ChatInterface } from './components/ChatInterface';
import { RuleLibrary } from './components/RuleLibrary';
import { TestConsole } from './components/TestConsole';
import { AgentAdminPanel } from './components/AgentAdminPanel';
import { SchemaWorkshop } from './components/SchemaWorkshop';
import { DecisionLog } from './components/DecisionLog';
import { Dashboard } from './components/Dashboard';
import { fetchGroups, createGroup, deleteGroup, checkLLMConnection } from './api';
import { Bot, ChevronRight, Menu, Save, Settings, X } from 'lucide-react';
import type { DatapointDefinition, LlmConfig, Rule, RuleGroup } from './types';

type WorkspaceView = 'dashboard' | 'library' | 'builder' | 'agent-admin' | 'schema-workshop' | 'decision-log';

const VIEW_LABELS: Record<WorkspaceView, string> = {
  dashboard: 'Dashboard',
  library: 'Rule Library',
  builder: 'Rule Builder',
  'agent-admin': 'Agent Admin',
  'schema-workshop': 'Schema Workshop',
  'decision-log': 'Decision Log',
};

function App() {
  const [groups, setGroups] = useState<RuleGroup[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null);
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // LLM Config — seeded from sessionStorage so values survive page refresh
  const [provider, setProvider] = useState(() => sessionStorage.getItem('llm_provider') || 'openai');
  const [model, setModel] = useState(() => sessionStorage.getItem('llm_model') || 'gpt-5.2-2025-12-11');
  const [apiKey, setApiKey] = useState(() => sessionStorage.getItem('llm_api_key') || '');
  const [llmConfig, setLlmConfig] = useState<LlmConfig | null>(() => {
    const key = sessionStorage.getItem('llm_api_key');
    const m = sessionStorage.getItem('llm_model');
    const p = sessionStorage.getItem('llm_provider');
    return key && m && p ? { provider: p, model: m, api_key: key } : null;
  });
  const [isTestingLlm, setIsTestingLlm] = useState(false);
  const [llmError, setLlmError] = useState<string | null>(null);

  // Testing Support
  const [ruleToTest, setRuleToTest] = useState<Rule | null>(null);
  const [testDatapointDefs, setTestDatapointDefs] = useState<DatapointDefinition[]>([]);
  const [selectedRule, setSelectedRule] = useState<Rule | null>(null);
  const [selectedRuleToken, setSelectedRuleToken] = useState(0);
  const [rulePanelRefreshKey, setRulePanelRefreshKey] = useState(0);
  const [systemNotice, setSystemNotice] = useState<string | null>(null);
  const [systemNoticeToken, setSystemNoticeToken] = useState(0);
  const [workspaceView, setWorkspaceView] = useState<WorkspaceView>('dashboard');
  const providerSelectRef = useRef<HTMLSelectElement>(null);

  useEffect(() => {
    if (isDarkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDarkMode]);

  useEffect(() => {
    if (showSettings) {
      providerSelectRef.current?.focus();
    }
  }, [showSettings]);

  const loadGroups = useCallback(async () => {
    try {
      const data = await fetchGroups();
      setGroups(data);
      if (data.length > 0 && !selectedGroupId) {
        // Don't auto-select; let user pick from dashboard/sidebar
      }
    } catch (err) {
      console.error('Failed to load groups:', err);
    }
  }, [selectedGroupId]);

  useEffect(() => {
    loadGroups();
  }, [loadGroups]);

  useEffect(() => {
    setSelectedRule(null);
    setSelectedRuleToken(0);
    setSystemNotice(null);
    setSystemNoticeToken(0);
    if (selectedGroupId) {
      setWorkspaceView('library');
    }
  }, [selectedGroupId]);

  const handleCreateGroup = async (name: string, description: string) => {
    const g = await createGroup(name, description);
    setGroups((prev) => [...prev, g]);
    setSelectedGroupId(g.id);
    setWorkspaceView('library');
  };

  const handleSelectRuleForBuilder = (rule: Rule) => {
    setSelectedRule(rule);
    setSelectedRuleToken(Date.now());
    setWorkspaceView('builder');
  };

  const handleCreateRule = () => {
    setSelectedRule(null);
    setSelectedRuleToken(Date.now());
    setWorkspaceView('builder');
  };

  const handleRuleSaved = (rule: Rule) => {
    setRulePanelRefreshKey((prev) => prev + 1);
    setSelectedRule(rule);
    loadGroups();
  };

  const handleRuleUpdated = (rule: Rule) => {
    setSelectedRule((current) => (current?.id === rule.id ? rule : current));
  };

  const handleRuleStatusChanged = (rule: Rule) => {
    setSelectedRule((current) => (current?.id === rule.id ? rule : current));
    setSystemNotice(
      rule.active
        ? `Rule '${rule.name}' reactivated. It is live in evaluation again.`
        : `Rule '${rule.name}' deactivated. It remains documented but will be skipped during evaluation.`,
    );
    setSystemNoticeToken(Date.now());
  };

  const handleDeleteGroup = async (group: RuleGroup, adminToken?: string) => {
    await deleteGroup(group.id, adminToken);
    setGroups((prev) => {
      const nextGroups = prev.filter((item) => item.id !== group.id);
      setSelectedGroupId((current) => {
        if (current !== group.id) return current;
        return nextGroups[0]?.id ?? null;
      });
      return nextGroups;
    });
    setSelectedRule(null);
    setSelectedRuleToken(0);
    setRuleToTest(null);
    setTestDatapointDefs([]);
    setSystemNotice(`Rule group '${group.name}' destroyed.`);
    setSystemNoticeToken(Date.now());
    setWorkspaceView('dashboard');
  };

  const handleSaveLlmConfig = async () => {
    setIsTestingLlm(true);
    setLlmError(null);
    try {
      await checkLLMConnection(provider, model, apiKey);
      sessionStorage.setItem('llm_provider', provider);
      sessionStorage.setItem('llm_model', model);
      sessionStorage.setItem('llm_api_key', apiKey);
      setLlmConfig({ provider, model, api_key: apiKey });
      setShowSettings(false);
    } catch (err: unknown) {
      setLlmError(err instanceof Error ? err.message : 'Connection failed. Please check your API key.');
    } finally {
      setIsTestingLlm(false);
    }
  };

  const selectedGroup = groups.find((g) => g.id === selectedGroupId);

  return (
    <div className="flex h-screen flex-col bg-white font-sans transition-colors dark:bg-gray-900 overflow-hidden">

      {/* ── Top header bar ───────────────────────────────────────────── */}
      <header className="flex h-14 flex-shrink-0 items-center gap-3 border-b border-gray-200 bg-white px-4 dark:border-gray-800 dark:bg-gray-900">
        <button
          onClick={() => setSidebarOpen((v) => !v)}
          className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl border border-gray-200 bg-white/90 shadow-sm transition-colors hover:bg-gray-100 dark:border-gray-700 dark:bg-gray-800 dark:hover:bg-gray-700"
          aria-label={sidebarOpen ? 'Close sidebar' : 'Open sidebar'}
        >
          {sidebarOpen ? <X size={18} /> : <Menu size={18} />}
        </button>

        <div className="flex min-w-0 flex-1 items-center gap-1.5 text-sm">
          <span className="font-semibold text-gray-900 dark:text-gray-100">Unreal Objects</span>
          {workspaceView !== 'dashboard' && (
            <>
              <ChevronRight size={14} className="flex-shrink-0 text-gray-400" />
              <span className="truncate text-gray-500 dark:text-gray-400">
                {VIEW_LABELS[workspaceView]}
              </span>
            </>
          )}
          {selectedGroup && (workspaceView === 'library' || workspaceView === 'builder') && (
            <>
              <ChevronRight size={14} className="flex-shrink-0 text-gray-400" />
              <span className="truncate font-medium text-gray-700 dark:text-gray-300">
                {selectedGroup.name}
              </span>
            </>
          )}
        </div>
      </header>

      {/* ── Glassmorphism sidebar overlay ────────────────────────────── */}
      <Sidebar
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        groups={groups}
        selectedGroupId={selectedGroupId}
        activeView={workspaceView}
        onSelectGroup={(id) => {
          setSelectedGroupId(id);
          setWorkspaceView('library');
          setSidebarOpen(false);
        }}
        onOpenDashboard={() => {
          setWorkspaceView('dashboard');
          setSidebarOpen(false);
        }}
        onOpenAgentAdmin={() => {
          setWorkspaceView('agent-admin');
          setSidebarOpen(false);
        }}
        onOpenSchemaWorkshop={() => {
          setWorkspaceView('schema-workshop');
          setSidebarOpen(false);
        }}
        onOpenDecisionLog={() => {
          setWorkspaceView('decision-log');
          setSidebarOpen(false);
        }}
        onCreateGroup={handleCreateGroup}
        onDeleteGroup={handleDeleteGroup}
        isDarkMode={isDarkMode}
        toggleDarkMode={() => setIsDarkMode(!isDarkMode)}
        onOpenSettings={() => {
          setShowSettings(true);
          setSidebarOpen(false);
        }}
        llmConfigured={!!llmConfig}
      />

      {/* ── Main content area ─────────────────────────────────────────── */}
      <main className="flex min-h-0 flex-1 bg-white transition-colors dark:bg-gray-900">
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="min-h-0 flex-1">
            {workspaceView === 'dashboard' ? (
              <Dashboard
                onNavigateToDecisionLog={() => setWorkspaceView('decision-log')}
              />
            ) : workspaceView === 'agent-admin' ? (
              <div className="h-full overflow-y-auto p-6">
                <div className="mx-auto max-w-6xl">
                  <AgentAdminPanel />
                </div>
              </div>
            ) : workspaceView === 'schema-workshop' ? (
              <SchemaWorkshop llmConfig={llmConfig} onOpenSettings={() => setShowSettings(true)} />
            ) : workspaceView === 'decision-log' ? (
              <div className="h-full overflow-y-auto p-6">
                <div className="mx-auto max-w-6xl">
                  <DecisionLog />
                </div>
              </div>
            ) : selectedGroupId ? (
              workspaceView === 'library' ? (
                <div className="flex h-full min-h-0 flex-col">
                  {systemNotice && (
                    <div className="border-b border-amber-200 bg-amber-50 px-6 py-3 text-sm text-amber-800 dark:border-amber-900/40 dark:bg-amber-950/20 dark:text-amber-200">
                      {systemNotice}
                    </div>
                  )}
                  <RuleLibrary
                    groupId={selectedGroupId}
                    selectedRuleId={selectedRule?.id ?? null}
                    onCreateRule={handleCreateRule}
                    onSelectRule={handleSelectRuleForBuilder}
                    onRuleUpdated={handleRuleUpdated}
                    onRuleStatusChanged={handleRuleStatusChanged}
                    refreshKey={rulePanelRefreshKey}
                    className="w-full"
                  />
                </div>
              ) : (
                <ChatInterface
                  key={selectedGroupId}
                  groupId={selectedGroupId}
                  llmConfig={llmConfig}
                  selectedRule={selectedRule}
                  selectedRuleToken={selectedRuleToken}
                  systemNotice={systemNotice}
                  systemNoticeToken={systemNoticeToken}
                  onRuleCreated={handleRuleSaved}
                  onStartTest={(rule, defs) => {
                    setRuleToTest(rule);
                    setTestDatapointDefs(defs);
                  }}
                  onStopEditing={() => {
                    setSelectedRule(null);
                    setSelectedRuleToken(0);
                    setWorkspaceView('library');
                  }}
                />
              )
            ) : (
              <EmptyState
                hasGroups={groups.length > 0}
                llmConfigured={!!llmConfig}
                onOpenSettings={() => setShowSettings(true)}
                onOpenDashboard={() => setWorkspaceView('dashboard')}
              />
            )}
          </div>
        </div>
      </main>

      {ruleToTest && selectedGroupId && (
        <TestConsole
          groupId={selectedGroupId}
          ruleToTest={ruleToTest}
          datapointDefinitions={testDatapointDefs}
          onClose={() => setRuleToTest(null)}
        />
      )}

      {/* Settings Modal */}
      {showSettings && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
          <div className="max-h-[90vh] w-full max-w-2xl overflow-hidden rounded-xl bg-white shadow-2xl dark:bg-gray-800">
            <div className="flex items-center justify-between border-b border-gray-200 p-4 font-semibold text-gray-800 dark:border-gray-700 dark:text-gray-200">
              <div className="flex items-center gap-2">
                <Settings size={18} />
                LLM Provider Settings
              </div>
              <button
                onClick={() => setShowSettings(false)}
                className="rounded p-1 transition-colors hover:bg-gray-100 dark:hover:bg-gray-700"
              >
                <X size={18} />
              </button>
            </div>
            <div className="max-h-[calc(90vh-128px)] space-y-6 overflow-y-auto p-5">
              <section className="space-y-4">
                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
                    Provider
                  </label>
                  <select
                    ref={providerSelectRef}
                    value={provider}
                    onChange={(e) => setProvider(e.target.value)}
                    className="w-full rounded-lg border border-gray-300 bg-gray-50 px-3 py-2 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
                  >
                    <option value="openai">OpenAI</option>
                    <option value="anthropic">Anthropic</option>
                    <option value="gemini">Google Gemini</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
                    Model Name
                  </label>
                  <input
                    type="text"
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    placeholder="e.g. gpt-5.2-2025-12-11, claude-sonnet-4-6"
                    className="w-full rounded-lg border border-gray-300 bg-gray-50 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
                    API Key
                  </label>
                  <input
                    type="password"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder="sk-..."
                    className="w-full rounded-lg border border-gray-300 bg-gray-50 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
                  />
                </div>
                {llmError && (
                  <div className="text-sm font-medium text-red-600 dark:text-red-400">{llmError}</div>
                )}
              </section>
            </div>
            <div className="flex justify-end gap-2 border-t border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-900/50">
              <button
                onClick={() => setShowSettings(false)}
                className="px-4 py-2 text-sm font-medium text-gray-600 transition-colors hover:text-gray-800 dark:text-gray-300 dark:hover:text-white"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveLlmConfig}
                disabled={isTestingLlm || !apiKey}
                className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
              >
                {isTestingLlm ? <Bot size={16} className="animate-spin" /> : <Save size={16} />}
                {isTestingLlm ? 'Testing…' : 'Save & Connect'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function EmptyState({
  hasGroups,
  llmConfigured,
  onOpenSettings,
  onOpenDashboard,
}: {
  hasGroups: boolean;
  llmConfigured: boolean;
  onOpenSettings: () => void;
  onOpenDashboard: () => void;
}) {
  return (
    <div className="flex flex-1 items-center justify-center p-8">
      <div className="max-w-sm text-center">
        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-blue-50 dark:bg-blue-900/20">
          <Bot size={32} className="text-blue-500 dark:text-blue-400" />
        </div>
        <h2 className="mb-2 text-lg font-semibold text-gray-800 dark:text-gray-200">
          {hasGroups ? 'Select a Rule Group' : 'Get Started'}
        </h2>
        <p className="mb-4 text-sm text-gray-500 dark:text-gray-400">
          {hasGroups
            ? 'Choose a rule group from the sidebar to view and create rules.'
            : 'Set up your LLM provider, then create your first rule group to begin.'}
        </p>
        <button
          onClick={onOpenDashboard}
          className="text-sm text-blue-500 hover:text-blue-600 dark:text-blue-400 dark:hover:text-blue-300 transition-colors"
        >
          ← Back to Dashboard
        </button>
        {!hasGroups && !llmConfigured && (
          <div className="mt-4">
            <button
              onClick={onOpenSettings}
              className="inline-flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2 text-sm font-medium text-amber-700 transition-colors hover:bg-amber-100 dark:border-amber-800/50 dark:bg-amber-900/20 dark:text-amber-300"
            >
              ⚙️ Configure LLM Provider
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
