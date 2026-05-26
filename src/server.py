from fastapi import FastAPI, HTTPException, Request

from src.commands import todos
from src.commands.reward import print_reward

app = FastAPI()


@app.post("/webhook")
async def handle_webhook(request: Request):
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    if data.get("event_name") == "item:completed":
        task_content = data["event_data"]["content"]
        if "task print" in task_content.lower():
            todos.main()
        else:
            print_reward(task_content)

    return {"status": "ok"}
