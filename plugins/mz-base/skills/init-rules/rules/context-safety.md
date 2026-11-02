## Context After Compaction

Long sessions are compacted automatically near the context limit, and afterwards what you remember of a file is a summary, not the file. Before an edit that depends on code outside the lines you are replacing, re-read the file if the session was compacted or the file may have changed outside your own edits.

## Partial Reads

When a read ends with a notice that only part of the file was shown, page through the rest with offset and limit, or search for what you need. Don't reason about code you haven't seen.

## Large and Truncated Output

When a tool result is replaced by a saved-file path and a preview, read that file instead of re-running the command. Output from a failing command can be cut to its head and tail with nothing saved, so redirect long test or build output to a file and read the part you need. If a search returns suspiciously few results, narrow the scope and run it again.

## Subagents

Use subagents for independent work that can run in parallel, for noisy exploration whose details you don't need, or for a review by a reader who hasn't seen your reasoning. Work you can finish in a handful of tool calls is faster and cheaper done directly.
