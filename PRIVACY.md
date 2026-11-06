# Privacy

The mozg-pipelines plugins run inside Claude Code on your machine. The author runs no server and collects nothing: no telemetry, no analytics, no crash reports. No plugin sends anything to the author.

## What stays on your machine

- Task state, reports, research and memory are plain files under `.mz/` in your project. Nothing uploads them.
- The hooks in mz-dev-pipe, mz-handoff, mz-knowledge and mz-memory are shell scripts that read and write local files. The one exception is mz-memory's background curation, described below.
- mz-biz-outreach and mz-job-outreach save the companies, people and contact details they find as local files under `.mz/outreach/`, with run state under `.mz/task/`. mz-job-outreach also keeps per-source hit counts keyed by a hash of your CV. Each plugin's README lists the folders to delete.
- mz-rules writes rule files, `CLAUDE.md` blocks and entries in your Claude Code settings only after you approve. One entry is a Stop hook that runs your own `pre-commit`. `/init-rules --uninstall` removes what it added.

## What leaves your machine

Every outside call goes through Claude Code or a tool you installed and signed in to yourself:

- **Anthropic.** Your prompts, the files Claude reads and the work of every subagent go to the model you use in Claude Code, under your own account and Anthropic's terms. mz-memory's background curation also runs `claude -p` on your account; `MZ_MEMORY_COMPRESS=0` turns it off.
- **Websites.** Research, review and writing skills use Claude Code's WebSearch and WebFetch tools, which fetch the pages Claude picks for your question.
- **GitHub.** mz-dev-git, mz-dev-pipe and mz-gov reach GitHub through `gh` or, when it fails, a GitHub MCP server in your session. No plugin reads a GitHub token itself.
- **Translation checks.** mz-research-pipe's `/translate` sends short excerpts of the text you translate to public services: up to 9 sentences per run to MyMemory (`api.mymemory.translated.net`) and single words to Wiktionary. Don't translate confidential text with it.
- **YouTube.** mz-knowledge's `/vault-ingest` runs `yt-dlp` to fetch the subtitles of a YouTube link you give it. Voice notes are transcribed locally with whisper-cpp or whisper. The `whisper` CLI downloads its model weights on first use, and your audio stays local.

## Support

Open an issue at <https://github.com/DoctorMozg/claude-pipelines/issues>, or email drmozg@gmail.com.
