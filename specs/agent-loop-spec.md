# Spec: `run_agent()`

**File:** `agent.py`
**Status:** Partially pre-filled — complete the two blank fields before implementing

---

## Purpose

Orchestrate a single conversational turn for the Plant Advisor agent. Given a user message and the conversation history, call the LLM with available tools, execute any tool calls the LLM requests, and return the final text response.

This is the core of what makes Plant Advisor an *agent* rather than a simple chatbot: the ability to decide which tools to call, use their results to inform its response, and loop until it has everything it needs.

---

## Input / Output Contract

**Inputs:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `user_message` | `str` | The user's current message |
| `history` | `list` | Gradio conversation history — list of `[user_msg, assistant_msg]` pairs |

**Output:** `str`

The agent's final text response for this turn. Should never be empty — if something goes wrong, return a user-readable fallback message.

---

## Design Decisions

*Read `specs/system-design.md` (especially the "How the Groq Tool Calling API Works" section) before reviewing these. Complete the two blank fields before writing any code.*

---

### Messages list structure

The messages list must start with the system prompt, then replay the conversation
history, then add the new user message. Gradio history is a list of `[user, assistant]`
pairs — convert each pair to two API-format dicts:

```python
messages = [{"role": "system", "content": SYSTEM_PROMPT}]

for user_msg, assistant_msg in history:
    messages.append({"role": "user", "content": user_msg})
    if assistant_msg:
        messages.append({"role": "assistant", "content": assistant_msg})

messages.append({"role": "user", "content": user_message})
```

---

### Initial LLM call

Pass the model, the messages list, the tool definitions, and `tool_choice="auto"`
so the LLM can decide whether to call a tool or respond directly:

```python
response = client.chat.completions.create(
    model=LLM_MODEL,
    messages=messages,
    tools=TOOL_DEFINITIONS,
    tool_choice="auto",
)
```

---

### Detecting tool calls in the response

The response object has a `choices` list. Index 0 gives the assistant message.
Check its `tool_calls` attribute — if it's truthy, the LLM wants to call tools:

```python
assistant_message = response.choices[0].message

if not assistant_message.tool_calls:
    # No tool calls — LLM has a final answer
    ...
```

---

### Appending the assistant message

When there are tool calls, append the full assistant message object to `messages`
**before** appending any tool results. The API requires this ordering — a tool
result message must immediately follow the assistant message that requested it:

```python
messages.append(assistant_message)  # must come first
```

---

### Executing and appending tool results

For each tool call, extract the name and arguments, call `dispatch_tool()`, and
append the result as a `"tool"` role message. The `tool_call_id` links this result
back to the specific tool call that requested it:

```python
for tool_call in assistant_message.tool_calls:
    tool_name = tool_call.function.name
    tool_args = json.loads(tool_call.function.arguments)
    tool_result = dispatch_tool(tool_name, tool_args)

    messages.append({
        "role": "tool",
        "tool_call_id": tool_call.id,
        "content": tool_result,
    })
```

---

### Loop termination conditions

*The loop should stop when: (a) the LLM returns a response with no tool calls, OR (b) the MAX_TOOL_ROUNDS limit is reached. Describe how you will detect each condition and what you will return in each case.*

```
(a) No tool calls — final answer:
    assistant_message = response.choices[0].message
    if not assistant_message.tool_calls:
        return assistant_message.content or FALLBACK_MESSAGE
    (coalesce because content can be None/empty — contract says never return empty)

(b) Round limit reached:
    Wrap the whole thing in `for round in range(MAX_TOOL_ROUNDS):` so the COUNT OF
    ROUNDS is what's bounded — not len(tool_calls), which is tools-per-response and
    unrelated. If the loop finishes without returning, return an explicit fallback
    string (the last assistant message's content is None because it was a tool-call
    message, so we can't return that).
```

---

### Extracting the final text response

*Once the loop exits because there are no more tool calls, how do you extract the text content from the response object? What field holds the string you should return?*

```
The final text is at response.choices[0].message.content, so the `content`
attribute of the assistant message (the same `assistant_message` used to check
tool_calls). Since `content` can be None/empty (it's None on tool-call messages,
and can be empty even on a final one), return `assistant_message.content or
FALLBACK_MESSAGE` to honor the "never empty" contract. This extraction is exactly
branch (a) of the termination logic, when tool_calls is falsy, return the content.
```

---

## Implementation Notes

*Fill this in after implementing and testing.*

**Trace of a working agent turn (what tools were called and in what order):**

```
When the user asked how to care for a calathea, the agent first called lookup_plant("calathea") and found the plant in the database. Using that information, it answered with care instructions and did not need any additional tool calls.
```

**What happens when you ask about a plant that isn't in the database?**

```
If a plant is not found, the tool returns a message saying so and may suggest similar plants. The agent then tells the user the plant is not in the database and avoids making up plant-specific care information.
```

**One thing about the tool call API that surprised you:**

```
For tools with no required inputs, the model sometimes sends null instead of an empty object {}. This caused errors in the code, so I had to add a check to ensure a dictionary is always passed to the tool.
```
