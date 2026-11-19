# Migrate an API to the current library version

Use this prompt with an AI coding agent (Claude Code, Codex, …), run **inside the API's repository**,
to move the API onto the current `tashtiot-apis-library` release and the
[API standards](../reference/api-standards.md).

The prompt first picks one of two modes:

| Mode | When | Result |
|---|---|---|
| **A: Upgrade** | The API already uses the library, on an older version | The smallest safe change. Applies the version-specific upgrade notes and non-breaking fixes. The public contract is kept, and breaking deviations are only reported. |
| **B: Rewrite** | The API doesn't use the library, or you want a full rewrite | The API is rebuilt on the library to the full standards (`{metadata, spec}`, connectors, async, auth, Remote Config if needed). It ships as a new major version. |

## How to use it

1. Copy the prompt below (use the copy button), or take it from
   [`prompts/migrate-api.md`](https://github.com/Platform-Infra-Org/apis-library/blob/master/prompts/migrate-api.md) in the library repository.
2. Run it in the API's repository, on a new branch. Review the agent's mode choice and its
   "Needs a decision" list before merging.

!!! note
    The prompt is updated with every library release, so always take the latest copy. The target
    version is stated at the top of the prompt.

## The prompt

`````markdown
--8<-- "prompts/migrate-api.md"
`````

## See also

- [API standards](../reference/api-standards.md): the rules the migration has to meet.
- [Changelog](../changelog.md): every change between versions.
- [Async and the event loop](../explanation/async.md),
  [Job queues and long-running work](../explanation/job-queues.md).
