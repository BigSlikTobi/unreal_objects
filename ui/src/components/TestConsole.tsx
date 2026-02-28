import React, { useState } from 'react';
import { executeTest } from '../api';
import { FlaskConical, Play, X } from 'lucide-react';
import type { DatapointDefinition } from './DatapointConfigurator';

interface TestConsoleProps {
  groupId: string;
  ruleToTest: any;
  datapointDefinitions: DatapointDefinition[];
  onClose: () => void;
}

export const TestConsole: React.FC<TestConsoleProps> = ({ groupId, ruleToTest, datapointDefinitions, onClose }) => {
  const [description, setDescription] = useState('');
  const [context, setContext] = useState<Record<string, string>>({});
  const [result, setResult] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleContextChange = (dp: string, value: string) => {
    setContext(prev => ({ ...prev, [dp]: value }));
  };

  const handleTest = async () => {
    setIsLoading(true);
    setError(null);
    setResult(null);

    const parsedContext: Record<string, any> = {};
    for (const [k, v] of Object.entries(context)) {
      const def = datapointDefinitions.find(d => d.name === k);
      if (def?.type === 'boolean') {
        parsedContext[k] = v === 'true';
      } else if (def?.type === 'number' || (!def && !isNaN(Number(v)) && v.trim() !== '')) {
        parsedContext[k] = Number(v);
      } else {
        parsedContext[k] = v;
      }
    }

    try {
      const res = await executeTest(groupId, description, parsedContext);
      setResult(res);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const datapoints: string[] = ruleToTest?.datapoints || [];

  const renderInput = (dp: string) => {
    const def = datapointDefinitions.find(d => d.name === dp);
    const baseClass = "w-full text-sm bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg px-3 py-2 text-gray-900 dark:text-white focus:ring-2 focus:ring-purple-500 focus:border-transparent outline-none transition-all";

    if (def?.type === 'number') {
      return (
        <input
          type="number"
          value={context[dp] || ''}
          onChange={(e) => handleContextChange(dp, e.target.value)}
          placeholder="Value..."
          className={baseClass}
        />
      );
    }

    if (def?.type === 'boolean') {
      return (
        <select
          value={context[dp] || ''}
          onChange={(e) => handleContextChange(dp, e.target.value)}
          className={baseClass}
        >
          <option value="">Select...</option>
          <option value="true">true</option>
          <option value="false">false</option>
        </select>
      );
    }

    if (def?.type === 'enum' && def.values.length > 0) {
      return (
        <select
          value={context[dp] || ''}
          onChange={(e) => handleContextChange(dp, e.target.value)}
          className={baseClass}
        >
          <option value="">Select...</option>
          {def.values.map((v) => (
            <option key={v} value={v}>{v}</option>
          ))}
        </select>
      );
    }

    return (
      <input
        type="text"
        value={context[dp] || ''}
        onChange={(e) => handleContextChange(dp, e.target.value)}
        placeholder="Value..."
        className={baseClass}
      />
    );
  };

  return (
    <div className="w-80 h-full bg-white dark:bg-gray-800 border-l border-gray-200 dark:border-gray-700 flex flex-col shadow-xl">
      <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center bg-gray-50 dark:bg-gray-900/50">
        <h3 className="font-semibold text-gray-800 dark:text-gray-200 flex items-center gap-2">
          <FlaskConical size={18} className="text-purple-500" />
          Test Rule Setup
        </h3>
        <button onClick={onClose} className="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-md transition-colors text-gray-500 dark:text-gray-400">
          <X size={18} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <div>
          <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase mb-2">Rule Info</label>
          <div className="text-sm font-medium text-gray-800 dark:text-gray-200">{ruleToTest.name}</div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 font-mono">{ruleToTest.rule_logic}</p>
        </div>

        <div className="space-y-3">
          <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase">Context Datapoints</label>
          {datapoints.map((dp: string) => (
            <div key={dp}>
              <label className="block text-xs text-gray-600 dark:text-gray-300 mb-1">
                {dp}
                {datapointDefinitions.find(d => d.name === dp) && (
                  <span className="ml-1 text-gray-400 dark:text-gray-500">
                    ({datapointDefinitions.find(d => d.name === dp)!.type})
                  </span>
                )}
              </label>
              {renderInput(dp)}
            </div>
          ))}

          <div>
            <label className="block text-xs text-gray-600 dark:text-gray-300 mb-1">Request Description</label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="E.g., User wants to buy a laptop"
              className="w-full text-sm bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg px-3 py-2 text-gray-900 dark:text-white focus:ring-2 focus:ring-purple-500 focus:border-transparent outline-none transition-all"
            />
          </div>
        </div>
      </div>

      <div className="p-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/50">
        <button
          onClick={handleTest}
          disabled={isLoading}
          className="w-full flex items-center justify-center gap-2 bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded-lg font-medium transition-colors disabled:opacity-50"
        >
          <Play size={16} />
          {isLoading ? 'Running...' : 'Run Test'}
        </button>

        {error && (
          <div className="mt-4 p-3 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-sm rounded-lg border border-red-200 dark:border-red-800/50">
            {error}
          </div>
        )}

        {result && (
          <div className="mt-4 space-y-3 relative z-10">
            <h4 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase">Results</h4>

            <div className={`p-3 rounded-lg flex flex-col gap-1 border ${
              result.outcome === 'APPROVE' ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 border-green-200 dark:border-green-800/50' :
              result.outcome === 'REJECT' ? 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 border-red-200 dark:border-red-800/50' :
              'bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400 border-amber-200 dark:border-amber-800/50'
            }`}>
              <div className="text-xs uppercase opacity-70 font-semibold tracking-wider">Final Outcome</div>
              <div className="font-bold text-lg">{result.outcome}</div>
            </div>

            {result.matched_details?.length > 0 && (
              <div className="p-3 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
                 <div className="text-xs uppercase opacity-70 font-semibold tracking-wider mb-2 text-gray-500 dark:text-gray-400">Triggered By</div>
                 <div className="space-y-2">
                   {result.matched_details.map((d: any, i: number) => (
                      <div key={i} className="text-sm">
                        <span className="font-semibold text-gray-800 dark:text-gray-200">{d.rule_name}</span> ({d.hit_type.toUpperCase()})
                        <div className="text-xs font-mono text-gray-500 dark:text-gray-400 mt-1">{d.trigger_expression}</div>
                      </div>
                   ))}
                 </div>
              </div>
            )}

            <div className="text-xs text-gray-400 dark:text-gray-500 truncate">
               Log ID: {result.request_id}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
