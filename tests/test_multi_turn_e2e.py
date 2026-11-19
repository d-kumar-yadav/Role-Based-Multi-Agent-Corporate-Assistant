import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.storage.chat_history_db import append_chat_turn, get_recent_thread_messages
from app.agents.context_memory import (
    is_chat_summary_query,
    handle_chat_summary,
    is_why_explanation_query,
    explain_previous_refusal,
    condense_query,
)

test_user = "test_user_alice"
test_thread = "thread_turn_test_1"

# Step 1: User sends toxic message
append_chat_turn(
    user_id=test_user,
    thread_id=test_thread,
    user_query="yo bitch",
    assistant_response="I can't help with that request.",
    status="blocked",
)

# Step 2: User sends malicious question
append_chat_turn(
    user_id=test_user,
    thread_id=test_thread,
    user_query="how to destroy the growth of my comapy",
    assistant_response="I'm sorry, but I can't help with that.",
    status="blocked",
)

# Retrieve recent turns
history = get_recent_thread_messages(test_user, test_thread, max_messages=6)
print(f"Loaded {len(history)} messages from history:")
for m in history:
    print(f"  [{m.get('role')}]: {m.get('content')[:60]}")

# Turn 3: User asks "why"
user_q3 = "why"
if is_why_explanation_query(user_q3, history):
    resp3 = explain_previous_refusal(user_q3, history)
    print(f"\nTurn 3: {user_q3!r}\nResponse 3:\n{resp3}")
    append_chat_turn(
        user_id=test_user,
        thread_id=test_thread,
        user_query=user_q3,
        assistant_response=resp3,
        status="answered",
    )

# Turn 4: User asks "summize this chat"
history = get_recent_thread_messages(test_user, test_thread, max_messages=6)
user_q4 = "summize this chat"
if is_chat_summary_query(user_q4):
    resp4 = handle_chat_summary(history)
    print(f"\nTurn 4: {user_q4!r}\nResponse 4:\n{resp4}")
    append_chat_turn(
        user_id=test_user,
        thread_id=test_thread,
        user_query=user_q4,
        assistant_response=resp4,
        status="answered",
    )

print("\nSUCCESS: All turns handled seamlessly!")
