import React, { useState, useEffect } from 'react';
import { Sidebar } from './components/Sidebar';
import { ChatInterface } from './components/ChatInterface';
import { TestConsole } from './components/TestConsole';
import { fetchGroups, createGroup, checkLLMConnection } from './api';
import { Bot, Settings, X, Save, Plus } from 'lucide-react';

function App() {
  const [groups, setGroups] = useState<any[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null);
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

  // LLM Config — seeded from sessionStorage so values survive page refresh
  const [provider, setProvider] = useState(() => sessionStorage.getItem('llm_provider') || 'openai');
  const [model, setModel] = useState(() => sessionStorage.getItem('llm_model') || 'gpt-4o');
  const [apiKey, setApiKey] = useState(() => sessionStorage.getItem('llm_api_key') || '');
  const [llmConfig, setLlmConfig] = useState<any>(() => {
    const key = sessionStorage.getItem('llm_api_key');
    const m = sessionStorage.getItem('llm_model');
    const p = sessionStorage.getItem('llm_provider');
    return key && m && p ? { provider: p, model: m, api_key: key } : null;
  });
  const [isTestingLlm, setIsTestingLlm] = useState(false);
  const [llmError, setLlmError] = useState<string | null>(null);

  // Testing Support
  const [ruleToTest, setRuleToTest] = useState<any>(null);
  const [testDatapointDefs, setTestDatapointDefs] = useState<any[]>([]);

  useEffect(() => {
    if (isDarkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDarkMode]);

  useEffect(() => {
    loadGroups();
  }, []);

  const loadGroups = async () => {
    try {
      const data = await fetchGroups();
      setGroups(data);
      if (data.length > 0 && !selectedGroupId) {
        setSelectedGroupId(data[0].id);
      }
    } catch (err) {
      console.error('Failed to load groups:', err);
    }
  };

  const handleCreateGroup = async (name: string, description: string) => {
    const g = await createGroup(name, description);
    setGroups((prev) => [...prev, g]);
    setSelectedGroupId(g.id);
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
    } catch (err: any) {
      setLlmError(err.message || 'Connection failed. Please check your API key.');
    } finally {
      setIsTestingLlm(false);
    }
  };

  return (
    <div className="flex h-screen bg-white transition-colors dark:bg-gray-900 overflow-hidden font-sans">

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

      <main className="flex-1 flex flex-col min-w-0 bg-white dark:bg-gray-900 transition-colors">
        {selectedGroupId ? (
          <ChatInterface
            key={selectedGroupId}
            groupId={selectedGroupId}
            llmConfig={llmConfig}
            onRuleCreated={() => loadGroups()}
            onStartTest={(rule, defs) => { setRuleToTest(rule); setTestDatapointDefs(defs); }}
          />
        ) : (
          <EmptyState
            hasGroups={groups.length > 0}
            llmConfigured={!!llmConfig}
            onOpenSettings={() => setShowSettings(true)}
          />
        )}
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
                  placeholder="e.g. gpt-4o, claude-sonnet-4-6"
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
