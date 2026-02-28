import React, { useState } from 'react';
import { Save, X, CheckCircle2 } from 'lucide-react';

export interface DatapointDefinition {
  name: string;
  type: string; // "text" | "number" | "boolean" | "enum"
  values: string[];
}

interface DatapointRow {
  name: string;
  type: string;
  enumInput: string;
  values: string[];
}

interface DatapointConfiguratorProps {
  newDatapoints: string[];
  onSave: (defs: DatapointDefinition[]) => void;
}

export const DatapointConfigurator: React.FC<DatapointConfiguratorProps> = ({ newDatapoints, onSave }) => {
  const [rows, setRows] = useState<DatapointRow[]>(
    newDatapoints.map((name) => ({ name, type: '', enumInput: '', values: [] }))
  );
  const [saved, setSaved] = useState(false);

  const updateRow = (i: number, patch: Partial<DatapointRow>) => {
    setRows((prev) => prev.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  };

  const addEnumValue = (i: number) => {
    const raw = rows[i].enumInput.trim();
    if (!raw) return;
    const newValues = raw
      .split(',')
      .map((v) => v.trim())
      .filter((v) => v && !rows[i].values.includes(v));
    updateRow(i, { values: [...rows[i].values, ...newValues], enumInput: '' });
  };

  const removeEnumValue = (i: number, val: string) => {
    updateRow(i, { values: rows[i].values.filter((v) => v !== val) });
  };

  const canSave = rows.every((r) => r.type !== '' && (r.type !== 'enum' || r.values.length > 0));

  const handleSave = () => {
    onSave(rows.map(({ name, type, values }) => ({ name, type, values })));
    setSaved(true);
  };

  return (
    <div className="mt-2 w-full max-w-2xl bg-white dark:bg-gray-800 border border-blue-200 dark:border-blue-700 rounded-xl overflow-hidden shadow-sm">
      <div className="p-3 border-b border-blue-200 dark:border-blue-700 bg-blue-50 dark:bg-blue-900/20">
        <h4 className="font-semibold text-blue-800 dark:text-blue-300 text-sm">
          Define Datapoint Types
        </h4>
        <p className="text-xs text-blue-600 dark:text-blue-400 mt-0.5">
          Set the type for each new datapoint so the test console and LLM can use the correct format.
        </p>
      </div>

      <div className="p-3 space-y-3">
        {rows.map((row, i) => (
          <div key={row.name} className="space-y-2">
            <div className="flex items-center gap-3">
              <span className="text-sm font-mono font-medium text-gray-800 dark:text-gray-200 w-32 shrink-0 truncate">
                {row.name}
              </span>
              <select
                value={row.type}
                onChange={(e) => updateRow(i, { type: e.target.value, values: [], enumInput: '' })}
                className="flex-1 text-sm bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg px-2 py-1.5 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 outline-none"
              >
                <option value="">Select type…</option>
                <option value="text">Text</option>
                <option value="number">Number</option>
                <option value="boolean">Boolean</option>
                <option value="enum">Enum</option>
              </select>
            </div>

            {row.type === 'enum' && (
              <div className="ml-35 pl-[140px] space-y-1.5">
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={row.enumInput}
                    onChange={(e) => updateRow(i, { enumInput: e.target.value })}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        addEnumValue(i);
                      }
                    }}
                    placeholder="Add values, comma-separated…"
                    className="flex-1 text-sm bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg px-2 py-1.5 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 outline-none"
                  />
                  <button
                    onClick={() => addEnumValue(i)}
                    className="px-2 py-1.5 text-xs bg-blue-100 dark:bg-blue-900/30 hover:bg-blue-200 dark:hover:bg-blue-800/40 text-blue-700 dark:text-blue-300 rounded-lg transition-colors"
                  >
                    Add
                  </button>
                </div>
                {row.values.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {row.values.map((val) => (
                      <span
                        key={val}
                        className="flex items-center gap-1 bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 text-xs px-2 py-0.5 rounded-full font-mono"
                      >
                        {val}
                        <button onClick={() => removeEnumValue(i, val)} className="hover:text-blue-900 dark:hover:text-blue-100">
                          <X size={10} />
                        </button>
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="p-3 border-t border-blue-200 dark:border-blue-700 bg-blue-50 dark:bg-blue-900/20 flex items-center gap-3">
        {saved ? (
          <span className="flex items-center gap-1.5 text-sm font-medium text-green-700 dark:text-green-400">
            <CheckCircle2 size={16} /> Definitions saved — future rules will use these types
          </span>
        ) : (
          <button
            onClick={handleSave}
            disabled={!canSave}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:hover:bg-blue-600 text-white rounded-md text-sm font-medium transition-colors"
          >
            <Save size={14} /> Save Definitions
          </button>
        )}
      </div>
    </div>
  );
};
