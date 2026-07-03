"""Live adapter: ask the deployed OptiBot Assistant one question, get its text.

Read-only use of the Assistant -- it creates a thread + run to *query*, never
creates or modifies the Assistant's config. That keeps the design rule "code
never touches the Assistant" intact (that rule is about managing its config, not
about invoking it). The pipeline still needs only OPENAI_API_KEY; the eval
additionally needs the Assistant id, passed in here.
"""

from openai import OpenAI


def ask(client: OpenAI, assistant_id: str, question: str) -> str:
    run = client.beta.threads.create_and_run_poll(
        assistant_id=assistant_id,
        thread={"messages": [{"role": "user", "content": question}]},
    )
    messages = client.beta.threads.messages.list(
        thread_id=run.thread_id, order="desc", limit=1
    )
    if not messages.data:
        return ""
    parts = [
        block.text.value
        for block in messages.data[0].content
        if block.type == "text"
    ]
    return "\n".join(parts)
