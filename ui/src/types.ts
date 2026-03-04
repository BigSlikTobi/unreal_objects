export type DecisionOutcome = 'APPROVE' | 'ASK_FOR_APPROVAL' | 'REJECT';

export type DatapointType = 'text' | 'number' | 'boolean' | 'enum';

export interface DatapointDefinition {
  name: string;
  type: DatapointType;
  values: string[];
}

export interface ProposedField {
  name: string;
  description: string;
  type: string;
}

export interface Rule {
  id: string;
  name: string;
  feature: string;
  active: boolean;
  datapoints: string[];
  edge_cases: string[];
  edge_cases_json: Record<string, unknown>[];
  rule_logic: string;
  rule_logic_json: Record<string, unknown>;
}

export interface RuleGroup {
  id: string;
  name: string;
  description: string;
  rules: Rule[];
  datapoint_definitions: DatapointDefinition[];
}

export interface LlmConfig {
  provider: string;
  model: string;
  api_key: string;
}

export interface RuleTranslation {
  datapoints: string[];
  edge_cases: string[];
  edge_cases_json: Record<string, unknown>[];
  rule_logic: string;
  rule_logic_json: Record<string, unknown>;
  name?: string;
}

export interface RulePayload {
  name: string;
  feature: string;
  active: boolean;
  datapoints: string[];
  edge_cases: string[];
  edge_cases_json: Record<string, unknown>[];
  rule_logic: string;
  rule_logic_json: Record<string, unknown>;
}

export interface MatchedDetail {
  rule_name: string;
  hit_type: string;
  trigger_expression: string;
}

export interface DecisionResult {
  outcome: DecisionOutcome;
  matched_rules?: string[];
  matched_details?: MatchedDetail[];
  request_id: string;
}

export interface AgentRecord {
  agent_id: string;
  name: string;
  description: string;
  status: string;
  metadata?: Record<string, unknown>;
}

export interface CredentialRecord {
  credential_id: string;
  agent_id: string;
  name: string;
  client_id: string;
  scopes: string[];
  default_group_id?: string | null;
  allowed_group_ids: string[];
  status: string;
}

export interface EnrollmentTokenIssue {
  enrollment_token: string;
  enrollment_token_id: string;
  agent_id: string;
  credential_name: string;
  scopes: string[];
  default_group_id?: string | null;
  allowed_group_ids: string[];
  expires_at: string;
}
