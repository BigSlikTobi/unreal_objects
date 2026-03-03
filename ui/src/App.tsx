import { useCallback, useEffect, useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { ChatInterface } from './components/ChatInterface';
import { RuleLibrary } from './components/RuleLibrary';
import { TestConsole } from './components/TestConsole';
import { fetchGroups, createGroup, checkLLMConnection } from './api';
import { Bot, Settings, X, Save, Plus, PanelLeftOpen } from 'lucide-react';
import type { DatapointDefinition, LlmConfig, Rule, RuleGroup } from './types';

type WorkspaceView = 'library' | 'builder';

function App() {
  const [groups, setGroups] = useState<RuleGroup[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null);
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

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
  const [showGroupPanel, setShowGroupPanel] = useState(false);
  const [systemNotice, setSystemNotice] = useState<string | null>(null);
  const [systemNoticeToken, setSystemNoticeToken] = useState(0);
  const [workspaceView, setWorkspaceView] = useState<WorkspaceView>('library');

  useEffect(() => {
    if (isDarkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDarkMode]);

  const loadGroups = useCallback(async () => {
    try {
      const data = await fetchGroups();
      setGroups(data);
      if (data.length > 0 && !selectedGroupId) {
        setSelectedGroupId(data[0].id);
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
    setShowGroupPanel(false);
    setSystemNotice(null);
    setSystemNoticeToken(0);
    setWorkspaceView('library');
  }, [selectedGroupId]);

  const handleCreateGroup = async (name: string, description: string) => {
    const g = await createGroup(name, description);
    setGroups((prev) => [...prev, g]);
    setSelectedGroupId(g.id);
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
    setSelectedRule((current) => current?.id === rule.id ? rule : current);
  };

  const handleRuleStatusChanged = (rule: Rule) => {
    setSelectedRule((current) => current?.id === rule.id ? rule : current);
    setSystemNotice(
      rule.active
        ? `Rule '${rule.name}' reactivated. It is live in evaluation again.`
        : `Rule '${rule.name}' deactivated. It remains documented but will be skipped during evaluation.`
    );
    setSystemNoticeToken(Date.now());
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

  return (
    <div className="flex h-screen bg-white transition-colors dark:bg-gray-900 overflow-hidden font-sans">
      <div className="hidden lg:block lg:w-64 lg:flex-shrink-0">
        <Sidebar
          groups={groups}
          selectedGroupId={selectedGroupId}
          onSelectGroup={setSelectedGroupId}
          onCreateGroup={handleCreateGroup}
          isDarkMode={isDarkMode}
          toggleDarkMode={() => setIsDarkMode(!isDarkMode)}
          onOpenSettings={() => setShowSettings(true)}
          llmConfigured={!!llmConfig}
        />
      </div>

      {showGroupPanel && (
        <div className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm lg:hidden" onClick={() => setShowGroupPanel(false)}>
          <div className="panel-enter-left h-full w-80 max-w-[85vw] shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <Sidebar
              groups={groups}
              selectedGroupId={selectedGroupId}
              onSelectGroup={(id) => {
                setSelectedGroupId(id);
                setShowGroupPanel(false);
              }}
              onCreateGroup={handleCreateGroup}
              isDarkMode={isDarkMode}
              toggleDarkMode={() => setIsDarkMode(!isDarkMode)}
              onOpenSettings={() => {
                setShowSettings(true);
                setShowGroupPanel(false);
              }}
              llmConfigured={!!llmConfig}
            />
          </div>
        </div>
      )}

      <main className="flex min-w-0 flex-1 bg-white transition-colors dark:bg-gray-900">
        <div className="flex min-w-0 flex-1 flex-col">
          {selectedGroupId && (
            <div className="border-b border-gray-200 bg-white px-4 py-3 dark:border-gray-800 dark:bg-gray-900 lg:hidden">
              <div className="flex items-center justify-between gap-2">
                <button
                  onClick={() => setShowGroupPanel(true)}
                  className="inline-flex items-center gap-2 rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-100 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800"
                  aria-label="Open groups"
                >
                  <PanelLeftOpen size={16} />
                  Groups
                </button>
                <div className="min-w-0 flex-1 text-center text-sm font-semibold text-gray-800 dark:text-gray-100">
                  <span className="truncate">{groups.find((group) => group.id === selectedGroupId)?.name ?? 'Rule Group'}</span>
                </div>
                <div className="w-[76px]" aria-hidden="true" />
              </div>
            </div>
          )}

          <div className="min-h-0 flex-1">
            {selectedGroupId ? (
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
                  onStartTest={(rule, defs) => { setRuleToTest(rule); setTestDatapointDefs(defs); }}
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="bg-white dark:bg-gray-800 rounded-xl max-w-md w-full shadow-2xl overflow-hidden">
            <div className="p-4 border-b border-gray-200 dark:border-gray-700 font-semibold flex items-center justify-between text-gray-800 dark:text-gray-200">
              <div className="flex items-center gap-2">
                <Settings size={18} />
                LLM Provider Settings
              </div>
              <button
                onClick={() => setShowSettings(false)}
                className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              >
                <X size={18} />
              </button>
            </div>
            <div className="p-5 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Provider</label>
                <select
                  value={provider}
                  onChange={(e) => setProvider(e.target.value)}
                  className="w-full bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-900 dark:text-gray-100"
                >
                  <option value="openai">OpenAI</option>
                  <option value="anthropic">Anthropic</option>
                  <option value="gemini">Google Gemini</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Model Name</label>
                <input
                  type="text"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  placeholder="e.g. gpt-5.2-2025-12-11, claude-sonnet-4-6"
                  className="w-full bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-900 dark:text-gray-100 placeholder-gray-400"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">API Key</label>
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="sk-..."
                  className="w-full bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-900 dark:text-gray-100 placeholder-gray-400"
                />
              </div>
              {llmError && (
                <div className="text-red-600 dark:text-red-400 text-sm font-medium">
                  {llmError}
                </div>
              )}
            </div>
            <div className="p-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/50 flex justify-end gap-2">
              <button
                onClick={() => setShowSettings(false)}
                className="px-4 py-2 font-medium text-sm text-gray-600 dark:text-gray-300 hover:text-gray-800 dark:hover:text-white transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveLlmConfig}
                disabled={isTestingLlm || !apiKey}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium text-sm rounded-lg transition-colors disabled:opacity-50"
              >
                {isTestingLlm ? <Bot size={16} className="animate-spin" /> : <Save size={16} />}
                {isTestingLlm ? 'Testing...' : 'Save & Connect'}
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
}: {
  hasGroups: boolean;
  llmConfigured: boolean;
  onOpenSettings: () => void;
}) {
  return (
    <div className="flex-1 flex items-center justify-center p-8">
      <div className="text-center max-w-sm">
        <div className="w-16 h-16 rounded-2xl bg-blue-50 dark:bg-blue-900/20 flex items-center justify-center mx-auto mb-4">
          <Bot size={32} className="text-blue-500 dark:text-blue-400" />
        </div>
        <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-2">
          {hasGroups ? 'Select a Rule Group' : 'Get Started'}
        </h2>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-6">
          {hasGroups
            ? 'Choose a rule group from the sidebar to view and create rules.'
            : 'Set up your LLM provider, then create your first rule group to begin.'}
        </p>

        {!hasGroups && (
          <div className="space-y-3 text-left">
            <div
              className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-colors ${
                !llmConfigured
                  ? 'border-amber-200 dark:border-amber-800/50 bg-amber-50 dark:bg-amber-900/20 hover:bg-amber-100 dark:hover:bg-amber-900/30'
                  : 'border-green-200 dark:border-green-800/50 bg-green-50 dark:bg-green-900/20'
              }`}
              onClick={!llmConfigured ? onOpenSettings : undefined}
            >
              <span className="text-lg mt-0.5">{llmConfigured ? '✅' : '⚙️'}</span>
              <div>
                <div className="text-sm font-semibold text-gray-800 dark:text-gray-200">
                  Configure LLM Provider
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                  {llmConfigured ? 'Connected and ready.' : 'Click to set your API key and model.'}
                </div>
              </div>
            </div>

            <div className="flex items-start gap-3 p-3 rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
              <Plus size={18} className="text-gray-400 mt-0.5 flex-shrink-0" />
              <div>
                <div className="text-sm font-semibold text-gray-800 dark:text-gray-200">
                  Create a Rule Group
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                  Use the sidebar button to name and create your first group.
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
