# UC02 · The Tools That Got Replaced

One `@tool` function is twelve lines. What the model receives is a contract written in
your docstring — and 38 of the 46 built-in tools are being replaced. This walkthrough
shows the extraction, the validation, the migration and one MCP server.

This is the second article in the *Strands in Action* series. The narrative lives in
[`article.md`](article.md); this file holds the commands. It assumes you read
[UC01](../01-the-loop/) — tool results traveling back as user-role messages is covered
there and not repeated here.

## 1. What you will see when you finish

Six scripts. Three of them never touch an API.

| Script | Expected result |
|---|---|
| `01_tool_spec.py` | the ToolSpec the model receives: name, description, inputSchema |
| `02_docstring_sections.py` | Args is cut from the description; Returns/Raises/Examples are kept |
| `03_type_validation.py` | a Pydantic model accepts good input, rejects bad types and missing fields |
| `04_docstring_is_prompt.py` | two docstrings, two model behaviors (calls Bedrock) |
| `05_mcp_stdio.py` | a stdio MCP server, its tool called by the agent in 2 cycles (calls Bedrock) |
| `06_deprecated_census.py` | 46 modules, 38 deprecated, 17 vended — counted on your machine |

## 2. Setup

```bash
git clone https://github.com/pinxiong/strands-in-action
cd strands-in-action/usecases/02-the-tools-that-got-replaced
uv venv --python 3.11
VIRTUAL_ENV=.venv uv pip install strands-agents==1.63.0 strands-agents-tools==0.8.11
```

Confirm the pinned versions before you trust any output:

```bash
.venv/bin/python -c "from importlib.metadata import version; print(version('strands-agents'), version('strands-agents-tools'), version('mcp'))"
```

Expected: `1.63.0 0.8.11 2.3.0` or newer. Scripts 04 and 05 call Amazon Bedrock; you need
AWS credentials with access to `deepseek.v3.2` in `us-east-1`.

## 3. Run

Run them in order. The first three are free (no API call).

```bash
.venv/bin/python src/01_tool_spec.py
.venv/bin/python src/02_docstring_sections.py
.venv/bin/python src/03_type_validation.py
```

Then the two that call the model:

```bash
.venv/bin/python src/04_docstring_is_prompt.py
.venv/bin/python src/05_mcp_stdio.py
```

`05` spawns `src/mcp_server.py` as a subprocess over stdio and tears it down on exit.
One detail if you adapt it: this environment has `mcp` 2.3.0, where the server class is
`MCPServer` from `mcp.server.mcpserver`. The older `from mcp.server.fastmcp import
FastMCP` raises by design.

And the census, which is free again:

```bash
.venv/bin/python src/06_deprecated_census.py
```

## 4. If something fails

| Symptom | Cause and fix |
|---|---|
| `MCPClientInitializationError: ... No such file or directory` | the subprocess path to the venv Python is wrong. `05` computes it from `__file__`; keep the directory layout as cloned |
| `ModuleNotFoundError: No module named 'mcp.server.fastmcp'` | you are on mcp 2.x. Use `from mcp.server.mcpserver import MCPServer` |
| Bedrock `ValidationException` about model access | your account cannot invoke `deepseek.v3.2` in `us-east-1`. Pick a model you can call and pass it as `model_id` |
| The deprecation warning does not appear | expected for vended tools. It prints once per deprecated module import, on the `strands_tools` import path only |

## 5. Evidence

Every number in the article came out of a run saved under `evidence/`:

| File | Content |
|---|---|
| `01-tool-spec.txt` | the spec output quoted in the article |
| `02-docstring-sections.txt` | full vs bare docstring descriptions |
| `03-type-validation.txt` | valid / rejected / missing parameter outcomes |
| `04-docstring-is-prompt.txt` | both runs, including the raw DSML leakage |
| `05-mcp-stdio.txt` | tool listing, answer, cycle count |
| `06-deprecated-census.txt` | the 46/38/17 census and both lists |
