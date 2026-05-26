
from todoist_api_python.api import TodoistAPI
from dotenv import load_dotenv
import os

load_dotenv()

API_KEY = os.getenv("TODOIST_API_KEY")
def main():
    if not API_KEY:
        print("TODOIST_API_KEY not set in environment variables.")
        return
    api = TodoistAPI(API_KEY)
    try:
        tasks_iterator = api.get_tasks(limit=10)

        all_tasks = []
        for page in tasks_iterator:
            for task in page:
                all_tasks.append(task)

        for index, task in enumerate(all_tasks):
            print(f"{index + 1}. {task.content}")
            
    except Exception as error:
        print(f"Error fetching tasks: {error}")
        

if __name__ == "__main__":
    main()