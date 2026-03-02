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

## Proposal Preview

- Proposed logic previews should highlight quoted string literals once, without duplicating the inner text beside the highlighted token.

## Test Console

- `Save & Test` and the test console should evaluate only the selected rule, not every active rule in the current group.
- The test console inputs still come from the selected rule's extracted datapoints and use the current group context definitions for typing.
