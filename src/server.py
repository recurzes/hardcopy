from fastapi import FastAPI, HTTPException, Request

from src.commands import todos
from src.commands.reward import print_reward
from src.commands.split import print_split_suggestion_from_webhook

app = FastAPI()


@app.post("/webhook")
async def handle_webhook(request: Request):
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_name = data.get("event_name")
    event_data = data.get("event_data", {})

    if event_name == "item:completed":
        task_content = event_data.get("content", "")
        if "task print" in task_content.lower():
            todos.main()
        else:
            print_reward(task_content)
    elif event_name == "item:added":
        print_split_suggestion_from_webhook(event_data)

    return {"status": "ok"}
