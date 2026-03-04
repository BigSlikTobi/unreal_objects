# Unreal Objects UI

This frontend is the rule authoring workspace for Unreal Objects.

## Layout

- Left sidebar: rule groups and workspace controls.
- Center workspace: the selected group's rule library as a grid of cards.
- Primary action card: `Create New Rule`, which opens the rule builder chat flow.
- Existing rule card: opens that rule in edit mode with the fillout form centered and the chat context shown below it.

## Interaction Model

- Browsing a group should prioritize scanning saved rules over showing the chat by default.
- Chat is contextual. It appears when a user starts creating a rule or loads an existing rule for editing.
- Editing a saved rule must preserve the existing update flow, including translate, save, and save-and-test actions.
- In the builder workspace, the fillout form is the primary surface and the chat transcript sits underneath it as supporting context.

## LLM Settings

- When no prior model selection is stored in `sessionStorage`, the OpenAI settings modal should prefill the model field with `gpt-5.2-2025-12-11`.

## Agent Admin

- The workspace should expose a dedicated operator admin surface for MCP agent
  management instead of nesting it inside the LLM settings modal.
- The top of the workspace should prioritize scanning agent cards, similar to
  the rule library.
- Agent-specific management context should open in an overlay when an operator
  opens a specific agent, so the workspace keeps its browse-first card layout.
- Agent cards should carry high-signal summary metadata directly on the card,
  including status, credential count, and latest issued token information.
- Operators must be able to create agents, issue enrollment tokens, and revoke
  credentials from the UI.
- The credentials pane should reflect the MCP admin credentials inventory and
  group the one-time enrollment token display with that credential context,
  rather than with the issuance form alone.
- Enrollment token responses are sensitive one-time bootstrap material; the UI
  should surface them clearly at creation time and persist the latest issued
  token per live agent locally so operators do not lose it by closing a modal.
- Persisted local token state must never create phantom agent cards. After a
  backend restart, the UI should only show agents returned by the admin API and
  should prune stale local token entries for agents that no longer exist.
- Default and allowed rule groups should be selected from the currently
  available rule groups instead of being entered as free-text IDs.
- Allowed rule groups should use explicit multi-select controls in the UI,
  not the browser's native modifier-key listbox, so operators can add and
  remove groups directly.
- When a default group is selected, it should appear as implicitly allowed in
  the allowed-groups checklist and be visually disabled there instead of being
  toggled like a separate choice.
- Agent enrollment form selections such as the default group should survive
  closing and reopening the same agent context during the current session.
- Scopes should remain visible and documented for operators, but they should be
  optional until scope-based enforcement exists beyond rule-group binding.

## Proposal Preview

- Proposed logic previews should highlight quoted string literals once, without duplicating the inner text beside the highlighted token.

## Test Console

- `Save & Test` and the test console should evaluate only the selected rule, not every active rule in the current group.
- The test console inputs still come from the selected rule's extracted datapoints and use the current group context definitions for typing.
